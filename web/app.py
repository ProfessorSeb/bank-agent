"""Solo Bank — FastAPI backend serving the bank website and REST API."""

import os
import uuid
import httpx
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

import database as db

KAGENT_CONTROLLER_URL = os.environ.get(
    "KAGENT_CONTROLLER_URL",
    "http://kagent-controller.kagent.svc.cluster.local:8083",
)
AGENT_NAMESPACE = os.environ.get("AGENT_NAMESPACE", "kagent")
CREDIT_AGENT = os.environ.get("CREDIT_AGENT_NAME", "bank-credit-limit-agent")

app = FastAPI(title="Solo Bank", version="1.0.0")


# ---- Pydantic models ----

class TransferRequest(BaseModel):
    from_account_id: str
    to_account_id: str
    amount: float
    description: str = ""


class ApprovalAction(BaseModel):
    action: str  # "approve" or "deny"


class CreditLimitUpdate(BaseModel):
    new_limit: float
    reason: str
    assessed_by: str = "credit-assessment-agent"


class ChatMessage(BaseModel):
    customer_id: str
    message: str


# ---- API routes ----

@app.get("/api/customers")
def list_customers():
    return db.get_all_customers()


@app.get("/api/customers/{customer_id}")
def get_customer(customer_id: str):
    c = db.get_customer(customer_id)
    if not c:
        raise HTTPException(404, "Customer not found")
    c.pop("pin", None)
    return c


@app.get("/api/customers/{customer_id}/accounts")
def get_accounts(customer_id: str):
    return db.get_accounts(customer_id)


@app.get("/api/customers/{customer_id}/transactions")
def get_transactions(customer_id: str, limit: int = 30):
    return db.get_all_transactions(customer_id, limit)


@app.get("/api/accounts/{account_id}/transactions")
def get_account_transactions(account_id: str, limit: int = 20):
    return db.get_transactions(account_id, limit)


@app.post("/api/transfer")
def transfer(req: TransferRequest):
    result = db.transfer_funds(req.from_account_id, req.to_account_id, req.amount, req.description)
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@app.get("/api/customers/{customer_id}/approvals")
def get_approvals(customer_id: str):
    return db.get_pending_approvals(customer_id)


@app.post("/api/approvals/{approval_id}")
def resolve_approval(approval_id: int, req: ApprovalAction):
    result = db.resolve_approval(approval_id, req.action)
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@app.get("/api/customers/{customer_id}/credit-history")
def credit_history(customer_id: str):
    return db.get_credit_limit_history(customer_id)


@app.post("/api/customers/{customer_id}/credit-limit")
def update_credit_limit(customer_id: str, req: CreditLimitUpdate):
    result = db.update_credit_limit(customer_id, req.new_limit, req.reason, req.assessed_by)
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@app.post("/api/chat")
def chat_with_agent(req: ChatMessage):
    """Send a message to the Bank Credit Limit Agent via A2A."""
    a2a_url = f"{KAGENT_CONTROLLER_URL}/api/a2a/{AGENT_NAMESPACE}/{CREDIT_AGENT}/"
    task_id = str(uuid.uuid4())

    payload = {
        "jsonrpc": "2.0",
        "method": "tasks/send",
        "params": {
            "id": task_id,
            "message": {
                "role": "user",
                "parts": [{"type": "text", "text": req.message}],
            },
        },
        "id": str(uuid.uuid4()),
    }

    try:
        with httpx.Client(timeout=120.0) as client:
            resp = client.post(a2a_url, json=payload, headers={"Content-Type": "application/json"})
            resp.raise_for_status()
            result = resp.json()

        # Extract response text
        if "result" in result:
            task_result = result["result"]
            # Check status message
            if "status" in task_result and "message" in task_result["status"]:
                parts = task_result["status"]["message"].get("parts", [])
                text = "\n".join(p.get("text", "") for p in parts if p.get("type") == "text")
                if text:
                    return {"response": text, "task_id": task_id}
            # Check artifacts
            for artifact in task_result.get("artifacts", []):
                for part in artifact.get("parts", []):
                    if part.get("type") == "text":
                        return {"response": part["text"], "task_id": task_id}

        return {"response": f"Agent responded: {result}", "task_id": task_id}

    except httpx.ConnectError:
        return {
            "response": "The AI Credit Agent is currently unavailable. Please try again later or contact a branch representative.",
            "task_id": task_id,
            "error": True,
        }
    except Exception as e:
        return {"response": f"Error communicating with agent: {str(e)}", "task_id": task_id, "error": True}


# ---- Serve frontend ----

static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/")
def index():
    return FileResponse(os.path.join(static_dir, "index.html"))
