"""Banking tools and A2A integration for the credit limit agent."""

import json
import uuid
import httpx
from langchain_core.tools import tool

from data import (
    get_customer,
    get_all_customer_ids,
    get_balances,
    get_transactions,
    get_payment_history_rows,
    update_credit_limit_db,
    get_credit_limit_history,
)
from config import KAGENT_CONTROLLER_URL, AGENT_NAMESPACE, CREDIT_ASSESSMENT_AGENT


def _ids_hint() -> str:
    return f"Valid IDs: {', '.join(get_all_customer_ids())}"


@tool
def get_customer_profile(customer_id: str) -> str:
    """Look up a customer's profile including name, income, and account details.

    Args:
        customer_id: The customer ID (e.g. CUST-1001)
    """
    customer = get_customer(customer_id)
    if not customer:
        return f"Customer {customer_id} not found. {_ids_hint()}"

    return json.dumps(
        {
            "id": customer["id"],
            "name": customer["name"],
            "email": customer["email"],
            "annual_income": customer["annual_income"],
            "monthly_debt_payments": customer["monthly_debt_payments"],
            "account_age_months": customer["account_age_months"],
            "current_credit_limit": customer["current_credit_limit"],
            "utilization_rate": customer["utilization_rate"],
        },
        indent=2,
    )


@tool
def get_credit_score(customer_id: str) -> str:
    """Retrieve a customer's credit score and credit history metrics.

    Args:
        customer_id: The customer ID (e.g. CUST-1001)
    """
    customer = get_customer(customer_id)
    if not customer:
        return f"Customer {customer_id} not found. {_ids_hint()}"

    return json.dumps(
        {
            "customer_id": customer["id"],
            "credit_score": customer["credit_score"],
            "recent_inquiries": customer["recent_inquiries"],
            "delinquencies_last_2y": customer["delinquencies_last_2y"],
            "utilization_rate": customer["utilization_rate"],
        },
        indent=2,
    )


@tool
def get_payment_history(customer_id: str) -> str:
    """Retrieve a customer's recent payment history showing on-time vs late payments.

    Args:
        customer_id: The customer ID (e.g. CUST-1001)
    """
    customer = get_customer(customer_id)
    if not customer:
        return f"Customer {customer_id} not found. {_ids_hint()}"

    history = get_payment_history_rows(customer_id)
    on_time = sum(1 for p in history if p["on_time"])
    total = len(history)

    return json.dumps(
        {
            "customer_id": customer["id"],
            "payment_history": [
                {"month": p["month"], "amount_due": p["amount_due"],
                 "amount_paid": p["amount_paid"], "on_time": bool(p["on_time"])}
                for p in history
            ],
            "summary": {
                "total_payments": total,
                "on_time_payments": on_time,
                "late_payments": total - on_time,
                "on_time_rate": round(on_time / total, 2) if total > 0 else 0,
            },
        },
        indent=2,
    )


@tool
def get_account_balances(customer_id: str) -> str:
    """Retrieve a customer's account balances (checking, savings, credit owed).

    Args:
        customer_id: The customer ID (e.g. CUST-1001)
    """
    customer = get_customer(customer_id)
    if not customer:
        return f"Customer {customer_id} not found. {_ids_hint()}"

    balances = get_balances(customer_id)
    if not balances:
        return f"No balance data for {customer_id}"

    return json.dumps(
        {
            "customer_id": customer_id,
            "customer_name": customer["name"],
            "checking_balance": balances["checking_balance"],
            "savings_balance": balances["savings_balance"],
            "credit_balance_owed": balances["credit_balance_owed"],
            "total_assets": balances["checking_balance"] + balances["savings_balance"],
            "last_updated": balances["last_updated"],
        },
        indent=2,
    )


@tool
def get_recent_transactions(customer_id: str, limit: int = 10) -> str:
    """Retrieve a customer's recent transactions (deposits, purchases, payments, withdrawals).

    Args:
        customer_id: The customer ID (e.g. CUST-1001)
        limit: Number of transactions to return (default 10)
    """
    customer = get_customer(customer_id)
    if not customer:
        return f"Customer {customer_id} not found. {_ids_hint()}"

    txns = get_transactions(customer_id, limit)
    return json.dumps(
        {
            "customer_id": customer_id,
            "customer_name": customer["name"],
            "transactions": txns,
            "count": len(txns),
        },
        indent=2,
    )


@tool
def update_credit_limit(customer_id: str, new_limit: float, reason: str) -> str:
    """Apply a credit limit change for a customer. Only call this after receiving
    an approved assessment from the Credit Assessment Agent.

    Args:
        customer_id: The customer ID (e.g. CUST-1001)
        new_limit: The new credit limit amount in dollars
        reason: The reason for the credit limit change
    """
    customer = get_customer(customer_id)
    if not customer:
        return f"Customer {customer_id} not found. {_ids_hint()}"

    old_limit = customer["current_credit_limit"]
    if new_limit <= old_limit:
        return f"New limit (${new_limit:,.2f}) must be higher than current limit (${old_limit:,.2f})"

    if new_limit > old_limit * 3:
        return f"Cannot increase limit by more than 3x. Current: ${old_limit:,.2f}, Max: ${old_limit * 3:,.2f}"

    result = update_credit_limit_db(customer_id, old_limit, new_limit, reason)

    return json.dumps(
        {
            "status": "SUCCESS",
            "customer_id": customer_id,
            "customer_name": customer["name"],
            "previous_limit": old_limit,
            "new_limit": new_limit,
            "increase_amount": new_limit - old_limit,
            "reason": reason,
            "timestamp": result["timestamp"],
        },
        indent=2,
    )


@tool
def get_credit_limit_change_history(customer_id: str) -> str:
    """Retrieve the history of all credit limit changes for a customer.

    Args:
        customer_id: The customer ID (e.g. CUST-1001)
    """
    customer = get_customer(customer_id)
    if not customer:
        return f"Customer {customer_id} not found. {_ids_hint()}"

    changes = get_credit_limit_history(customer_id)
    return json.dumps(
        {
            "customer_id": customer_id,
            "customer_name": customer["name"],
            "current_limit": customer["current_credit_limit"],
            "change_history": changes,
            "total_changes": len(changes),
        },
        indent=2,
    )


@tool
def request_credit_assessment(
    customer_id: str,
    requested_new_limit: float,
) -> str:
    """Send customer data to the Credit Assessment Agent (via A2A) for a risk
    evaluation and recommendation on the credit limit increase request.
    Always call this BEFORE updating any credit limit.

    Args:
        customer_id: The customer ID to assess
        requested_new_limit: The new credit limit the customer is requesting
    """
    customer = get_customer(customer_id)
    if not customer:
        return f"Customer {customer_id} not found. {_ids_hint()}"

    balances = get_balances(customer_id)
    history = get_payment_history_rows(customer_id)

    # Build the assessment request with full customer data
    assessment_request = (
        f"Please assess this credit limit increase request:\n\n"
        f"Customer: {customer['name']} ({customer['id']})\n"
        f"Current Credit Limit: ${customer['current_credit_limit']:,.2f}\n"
        f"Requested New Limit: ${requested_new_limit:,.2f}\n"
        f"Increase Amount: ${requested_new_limit - customer['current_credit_limit']:,.2f}\n\n"
        f"Credit Score: {customer['credit_score']}\n"
        f"Annual Income: ${customer['annual_income']:,.2f}\n"
        f"Monthly Debt Payments: ${customer['monthly_debt_payments']:,.2f}\n"
        f"Debt-to-Income Ratio: {customer['monthly_debt_payments'] * 12 / customer['annual_income']:.2%}\n"
        f"Account Age: {customer['account_age_months']} months\n"
        f"Credit Utilization Rate: {customer['utilization_rate']:.0%}\n"
        f"Recent Credit Inquiries: {customer['recent_inquiries']}\n"
        f"Delinquencies (Last 2 Years): {customer['delinquencies_last_2y']}\n"
    )

    if balances:
        assessment_request += (
            f"\nAccount Balances:\n"
            f"  Checking: ${balances['checking_balance']:,.2f}\n"
            f"  Savings: ${balances['savings_balance']:,.2f}\n"
            f"  Credit Owed: ${balances['credit_balance_owed']:,.2f}\n"
            f"  Total Assets: ${balances['checking_balance'] + balances['savings_balance']:,.2f}\n"
        )

    assessment_request += "\nPayment History (Last 6 Months):\n"
    for p in history[:6]:
        status = "ON TIME" if p["on_time"] else "LATE"
        assessment_request += (
            f"  {p['month']}: Due ${p['amount_due']:,.2f}, "
            f"Paid ${p['amount_paid']:,.2f} - {status}\n"
        )

    # Call the Credit Assessment Agent via kagent A2A protocol
    a2a_url = (
        f"{KAGENT_CONTROLLER_URL}/api/a2a/"
        f"{AGENT_NAMESPACE}/{CREDIT_ASSESSMENT_AGENT}/"
    )
    task_id = str(uuid.uuid4())

    a2a_payload = {
        "jsonrpc": "2.0",
        "method": "tasks/send",
        "params": {
            "id": task_id,
            "message": {
                "role": "user",
                "parts": [{"type": "text", "text": assessment_request}],
            },
        },
        "id": str(uuid.uuid4()),
    }

    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                a2a_url,
                json=a2a_payload,
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
            result = response.json()

        # Extract the assessment from the A2A response
        if "result" in result:
            task_result = result["result"]
            if "status" in task_result and "message" in task_result["status"]:
                parts = task_result["status"]["message"].get("parts", [])
                assessment_text = "\n".join(
                    p.get("text", "") for p in parts if p.get("type") == "text"
                )
                if assessment_text:
                    return assessment_text

            artifacts = task_result.get("artifacts", [])
            for artifact in artifacts:
                for part in artifact.get("parts", []):
                    if part.get("type") == "text":
                        return part["text"]

        return f"Credit Assessment Agent response: {json.dumps(result, indent=2)}"

    except httpx.ConnectError:
        return _local_assessment(customer, balances, history, requested_new_limit)
    except Exception as e:
        return (
            f"Error contacting Credit Assessment Agent: {e}. "
            f"Performing local assessment.\n\n"
            f"{_local_assessment(customer, balances, history, requested_new_limit)}"
        )


def _local_assessment(
    customer: dict,
    balances: dict | None,
    history: list[dict],
    requested_new_limit: float,
) -> str:
    """Fallback local credit assessment when the A2A agent is unreachable."""
    score = customer["credit_score"]
    dti = customer["monthly_debt_payments"] * 12 / customer["annual_income"]
    on_time = sum(1 for p in history if p["on_time"])
    total = len(history)
    on_time_rate = on_time / total if total > 0 else 0
    increase_pct = (
        (requested_new_limit - customer["current_credit_limit"])
        / customer["current_credit_limit"]
    )

    risk_factors = []
    if score < 670:
        risk_factors.append(f"Below-average credit score ({score})")
    if dti > 0.40:
        risk_factors.append(f"High debt-to-income ratio ({dti:.0%})")
    if on_time_rate < 0.90:
        risk_factors.append(f"Late payment history ({on_time_rate:.0%} on-time)")
    if customer["utilization_rate"] > 0.70:
        risk_factors.append(f"High credit utilization ({customer['utilization_rate']:.0%})")
    if customer["delinquencies_last_2y"] > 0:
        risk_factors.append(f"{customer['delinquencies_last_2y']} delinquencies in last 2 years")
    if increase_pct > 1.0:
        risk_factors.append(f"Large increase requested ({increase_pct:.0%})")

    if len(risk_factors) == 0:
        recommendation = "APPROVE"
        rationale = "All credit metrics are strong."
    elif len(risk_factors) <= 2 and score >= 700:
        recommendation = "CONDITIONAL_APPROVE"
        rationale = "Mostly positive profile with minor concerns."
    else:
        recommendation = "DENY"
        rationale = "Multiple risk factors present."

    return json.dumps(
        {
            "source": "LOCAL_FALLBACK",
            "recommendation": recommendation,
            "rationale": rationale,
            "risk_factors": risk_factors,
            "customer_id": customer["id"],
            "requested_new_limit": requested_new_limit,
        },
        indent=2,
    )


# All tools exported for the graph
banking_tools = [
    get_customer_profile,
    get_credit_score,
    get_payment_history,
    get_account_balances,
    get_recent_transactions,
    get_credit_limit_change_history,
    request_credit_assessment,
    update_credit_limit,
]
