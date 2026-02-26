"""Banking tools — all calls go to the Solo Bank Web Backend API (single source of truth)."""

import json
import uuid
import httpx
from langchain_core.tools import tool

from config import (
    KAGENT_CONTROLLER_URL,
    AGENT_NAMESPACE,
    CREDIT_ASSESSMENT_AGENT,
    BANK_API_URL,
)


def _bank_api(method: str, path: str, body: dict | None = None) -> dict | list:
    """Call the Solo Bank Web Backend API."""
    with httpx.Client(base_url=BANK_API_URL, timeout=15.0) as client:
        if method == "GET":
            resp = client.get(path)
        else:
            resp = client.post(path, json=body)
        resp.raise_for_status()
        return resp.json()


@tool
def get_customer_profile(customer_id: str) -> str:
    """Look up a customer's profile including name, income, credit details, and account info.

    Args:
        customer_id: The customer ID (e.g. CUST-1001)
    """
    try:
        customer = _bank_api("GET", f"/api/customers/{customer_id}")
        accounts = _bank_api("GET", f"/api/customers/{customer_id}/accounts")
        return json.dumps({"customer": customer, "accounts": accounts}, indent=2)
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            customers = _bank_api("GET", "/api/customers")
            ids = ", ".join(c["id"] for c in customers)
            return f"Customer {customer_id} not found. Valid IDs: {ids}"
        raise


@tool
def get_credit_score(customer_id: str) -> str:
    """Retrieve a customer's credit score and credit history metrics.

    Args:
        customer_id: The customer ID (e.g. CUST-1001)
    """
    customer = _bank_api("GET", f"/api/customers/{customer_id}")
    return json.dumps({
        "customer_id": customer["id"],
        "credit_score": customer["credit_score"],
        "recent_inquiries": customer["recent_inquiries"],
        "delinquencies_last_2y": customer["delinquencies_last_2y"],
        "utilization_rate": customer["utilization_rate"],
        "current_credit_limit": customer["current_credit_limit"],
    }, indent=2)


@tool
def get_account_balances(customer_id: str) -> str:
    """Retrieve a customer's account balances (checking, savings, credit).

    Args:
        customer_id: The customer ID (e.g. CUST-1001)
    """
    accounts = _bank_api("GET", f"/api/customers/{customer_id}/accounts")
    total_assets = sum(a["balance"] for a in accounts if a["type"] != "credit")
    total_owed = sum(abs(a["balance"]) for a in accounts if a["type"] == "credit")
    return json.dumps({
        "customer_id": customer_id,
        "accounts": accounts,
        "total_assets": total_assets,
        "total_credit_owed": total_owed,
    }, indent=2)


@tool
def get_recent_transactions(customer_id: str, limit: int = 15) -> str:
    """Retrieve a customer's recent transactions across all accounts.

    Args:
        customer_id: The customer ID (e.g. CUST-1001)
        limit: Number of transactions to return (default 15)
    """
    txns = _bank_api("GET", f"/api/customers/{customer_id}/transactions?limit={limit}")
    return json.dumps({"customer_id": customer_id, "transactions": txns, "count": len(txns)}, indent=2)


@tool
def get_payment_history(customer_id: str) -> str:
    """Retrieve a customer's credit card payment history (on-time vs late).

    Args:
        customer_id: The customer ID (e.g. CUST-1001)
    """
    # Payment history is part of the customer profile context —
    # fetched from the web backend's customer endpoint
    customer = _bank_api("GET", f"/api/customers/{customer_id}")
    return json.dumps({
        "customer_id": customer_id,
        "credit_score": customer["credit_score"],
        "delinquencies_last_2y": customer["delinquencies_last_2y"],
        "account_age_months": customer["account_age_months"],
        "utilization_rate": customer["utilization_rate"],
    }, indent=2)


@tool
def get_credit_limit_change_history(customer_id: str) -> str:
    """Retrieve the history of all credit limit changes for a customer.

    Args:
        customer_id: The customer ID (e.g. CUST-1001)
    """
    history = _bank_api("GET", f"/api/customers/{customer_id}/credit-history")
    customer = _bank_api("GET", f"/api/customers/{customer_id}")
    return json.dumps({
        "customer_id": customer_id,
        "current_limit": customer["current_credit_limit"],
        "change_history": history,
        "total_changes": len(history),
    }, indent=2)


@tool
def transfer_funds(from_account_id: str, to_account_id: str, amount: float, description: str) -> str:
    """Transfer funds between accounts. This writes to the bank database.

    Args:
        from_account_id: Source account ID (e.g. ACC-1001-CHK)
        to_account_id: Destination account ID (e.g. ACC-1001-SAV)
        amount: Amount to transfer in dollars
        description: Reason for the transfer
    """
    result = _bank_api("POST", "/api/transfer", {
        "from_account_id": from_account_id,
        "to_account_id": to_account_id,
        "amount": amount,
        "description": description,
    })
    return json.dumps(result, indent=2)


@tool
def update_credit_limit(customer_id: str, new_limit: float, reason: str) -> str:
    """Apply a credit limit change for a customer. Only call this after receiving
    an approved assessment from the Credit Assessment Agent.
    This writes to the bank database.

    Args:
        customer_id: The customer ID (e.g. CUST-1001)
        new_limit: The new credit limit amount in dollars
        reason: The reason for the credit limit change
    """
    result = _bank_api("POST", f"/api/customers/{customer_id}/credit-limit", {
        "new_limit": new_limit,
        "reason": reason,
        "assessed_by": "credit-assessment-agent",
    })
    return json.dumps(result, indent=2)


@tool
def request_credit_assessment(customer_id: str, requested_new_limit: float) -> str:
    """Send customer data to the Credit Assessment Agent (via A2A) for a risk
    evaluation. Always call this BEFORE updating any credit limit.

    Args:
        customer_id: The customer ID to assess
        requested_new_limit: The new credit limit the customer is requesting
    """
    # Fetch full customer data from the bank backend
    customer = _bank_api("GET", f"/api/customers/{customer_id}")
    accounts = _bank_api("GET", f"/api/customers/{customer_id}/accounts")

    dti = customer["monthly_debt_payments"] * 12 / customer["annual_income"]
    total_assets = sum(a["balance"] for a in accounts if a["type"] != "credit")
    total_owed = sum(abs(a["balance"]) for a in accounts if a["type"] == "credit")

    assessment_request = (
        f"Please assess this credit limit increase request:\n\n"
        f"Customer: {customer['name']} ({customer['id']})\n"
        f"Current Credit Limit: ${customer['current_credit_limit']:,.2f}\n"
        f"Requested New Limit: ${requested_new_limit:,.2f}\n"
        f"Increase Amount: ${requested_new_limit - customer['current_credit_limit']:,.2f}\n\n"
        f"Credit Score: {customer['credit_score']}\n"
        f"Annual Income: ${customer['annual_income']:,.2f}\n"
        f"Monthly Debt Payments: ${customer['monthly_debt_payments']:,.2f}\n"
        f"Debt-to-Income Ratio: {dti:.2%}\n"
        f"Account Age: {customer['account_age_months']} months\n"
        f"Credit Utilization: {customer['utilization_rate']:.0%}\n"
        f"Recent Inquiries: {customer['recent_inquiries']}\n"
        f"Delinquencies (Last 2Y): {customer['delinquencies_last_2y']}\n\n"
        f"Account Balances:\n"
        f"  Total Assets: ${total_assets:,.2f}\n"
        f"  Total Credit Owed: ${total_owed:,.2f}\n"
    )

    for a in accounts:
        assessment_request += f"  {a['name']} ({a['type']}): ${a['balance']:,.2f}\n"

    # Call Credit Assessment Agent via A2A
    a2a_url = f"{KAGENT_CONTROLLER_URL}/api/a2a/{AGENT_NAMESPACE}/{CREDIT_ASSESSMENT_AGENT}/"
    task_id = str(uuid.uuid4())

    payload = {
        "jsonrpc": "2.0",
        "method": "tasks/send",
        "params": {
            "id": task_id,
            "message": {"role": "user", "parts": [{"type": "text", "text": assessment_request}]},
        },
        "id": str(uuid.uuid4()),
    }

    try:
        with httpx.Client(timeout=60.0) as client:
            resp = client.post(a2a_url, json=payload, headers={"Content-Type": "application/json"})
            resp.raise_for_status()
            result = resp.json()

        if "result" in result:
            task_result = result["result"]
            if "status" in task_result and "message" in task_result["status"]:
                parts = task_result["status"]["message"].get("parts", [])
                text = "\n".join(p.get("text", "") for p in parts if p.get("type") == "text")
                if text:
                    return text
            for artifact in task_result.get("artifacts", []):
                for part in artifact.get("parts", []):
                    if part.get("type") == "text":
                        return part["text"]

        return f"Agent response: {json.dumps(result, indent=2)}"

    except httpx.ConnectError:
        return _local_assessment(customer, requested_new_limit, dti)
    except Exception as e:
        return f"A2A error: {e}\n\n{_local_assessment(customer, requested_new_limit, dti)}"


def _local_assessment(customer: dict, requested_new_limit: float, dti: float) -> str:
    """Fallback local assessment when A2A agent is unreachable."""
    score = customer["credit_score"]
    risk_factors = []
    if score < 670:
        risk_factors.append(f"Below-average credit score ({score})")
    if dti > 0.40:
        risk_factors.append(f"High DTI ({dti:.0%})")
    if customer["utilization_rate"] > 0.70:
        risk_factors.append(f"High utilization ({customer['utilization_rate']:.0%})")
    if customer["delinquencies_last_2y"] > 0:
        risk_factors.append(f"{customer['delinquencies_last_2y']} delinquencies")

    rec = "APPROVE" if not risk_factors else ("CONDITIONAL_APPROVE" if score >= 700 else "DENY")
    return json.dumps({
        "source": "LOCAL_FALLBACK",
        "recommendation": rec,
        "risk_factors": risk_factors,
        "customer_id": customer["id"],
    }, indent=2)


@tool
def create_credit_limit_approval(
    customer_id: str, requested_limit: float, reason: str, risk_summary: str,
) -> str:
    """Create a pending credit limit approval for admin manual review.
    Use this when the customer does NOT meet auto-approve criteria.

    Args:
        customer_id: The customer ID (e.g. CUST-1001)
        requested_limit: The requested new credit limit amount
        reason: Why the customer is requesting an increase
        risk_summary: Summary of risk factors from the credit assessment
    """
    customer = _bank_api("GET", f"/api/customers/{customer_id}")
    result = _bank_api("POST", f"/api/customers/{customer_id}/credit-limit-approval", {
        "requested_new_limit": requested_limit,
        "current_limit": customer["current_credit_limit"],
        "reason": reason,
        "assessment_summary": risk_summary,
    })
    return json.dumps(result, indent=2)


banking_tools = [
    get_customer_profile,
    get_credit_score,
    get_account_balances,
    get_recent_transactions,
    get_payment_history,
    get_credit_limit_change_history,
    transfer_funds,
    request_credit_assessment,
    update_credit_limit,
    create_credit_limit_approval,
]
