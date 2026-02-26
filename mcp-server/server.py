"""Bank MCP Server — exposes banking tools via MCP (streamable HTTP).

Tools call the Solo Bank web backend REST API to read/write data.
Deployed in agentgateway-system and proxied through AgentGateway.
"""

import os
import json
import httpx
from mcp.server.fastmcp import FastMCP

BANK_API_URL = os.environ.get("BANK_API_URL", "http://solo-bank-web.kagent.svc.cluster.local:8080")

mcp = FastMCP(
    "Bank MCP Server",
    instructions="Banking tools for Solo Bank. Use these to look up customers, check balances, transfer funds, update credit limits, and manage approvals.",
    host="0.0.0.0",
    port=3001,
)


def _bank_api(method: str, path: str, body: dict | None = None) -> dict | list:
    with httpx.Client(base_url=BANK_API_URL, timeout=15.0) as client:
        if method == "GET":
            resp = client.get(path)
        else:
            resp = client.post(path, json=body)
        resp.raise_for_status()
        return resp.json()


@mcp.tool()
def get_customer_profile(customer_id: str) -> str:
    """Look up a customer's profile including name, income, credit score, and account info.

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


@mcp.tool()
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


@mcp.tool()
def get_account_balances(customer_id: str) -> str:
    """Retrieve all account balances for a customer (checking, savings, credit).

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


@mcp.tool()
def get_recent_transactions(customer_id: str, limit: int = 15) -> str:
    """Retrieve recent transactions across all accounts for a customer.

    Args:
        customer_id: The customer ID (e.g. CUST-1001)
        limit: Number of transactions to return (default 15)
    """
    txns = _bank_api("GET", f"/api/customers/{customer_id}/transactions?limit={limit}")
    return json.dumps({"customer_id": customer_id, "transactions": txns, "count": len(txns)}, indent=2)


@mcp.tool()
def get_credit_limit_history(customer_id: str) -> str:
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


@mcp.tool()
def transfer_funds(from_account_id: str, to_account_id: str, amount: float, description: str) -> str:
    """Transfer funds between accounts. Writes to the bank database.

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


@mcp.tool()
def update_credit_limit(customer_id: str, new_limit: float, reason: str) -> str:
    """Apply a credit limit change for a customer. Writes to the bank database.
    Only call this after the request has been assessed and approved.

    Args:
        customer_id: The customer ID (e.g. CUST-1001)
        new_limit: The new credit limit amount in dollars
        reason: The reason for the credit limit change
    """
    result = _bank_api("POST", f"/api/customers/{customer_id}/credit-limit", {
        "new_limit": new_limit,
        "reason": reason,
        "assessed_by": "bank-credit-limit-agent",
    })
    return json.dumps(result, indent=2)


@mcp.tool()
def create_credit_limit_approval(
    customer_id: str, requested_limit: float, reason: str, risk_summary: str
) -> str:
    """Create a pending credit limit approval for admin review.
    Use this when the customer does NOT meet auto-approve criteria.

    Args:
        customer_id: The customer ID (e.g. CUST-1001)
        requested_limit: The requested new credit limit
        reason: Why the customer is requesting an increase
        risk_summary: Summary of risk factors from the assessment
    """
    customer = _bank_api("GET", f"/api/customers/{customer_id}")
    result = _bank_api("POST", f"/api/customers/{customer_id}/credit-limit-approval", {
        "requested_new_limit": requested_limit,
        "current_limit": customer["current_credit_limit"],
        "reason": reason,
        "assessment_summary": risk_summary,
    })
    return json.dumps(result, indent=2)


@mcp.tool()
def list_pending_approvals() -> str:
    """List all pending approvals across all customers (for admin review)."""
    result = _bank_api("GET", "/api/approvals")
    return json.dumps(result, indent=2)


@mcp.tool()
def resolve_approval(approval_id: int, action: str) -> str:
    """Approve or deny a pending approval.

    Args:
        approval_id: The approval ID
        action: Either "approve" or "deny"
    """
    result = _bank_api("POST", f"/api/approvals/{approval_id}", {"action": action})
    return json.dumps(result, indent=2)


@mcp.tool()
def list_customers() -> str:
    """List all bank customers."""
    customers = _bank_api("GET", "/api/customers")
    return json.dumps(customers, indent=2)


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
