"""Main entry point for the Bank Credit Limit Agent — deployed as a kagent BYO agent."""

import os
import sys

# Add src to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from kagent.langgraph import KAgentApp, KAgentConfig
from config import KAGENT_CONTROLLER_URL, AGENT_NAME, SERVER_PORT
from graph import create_graph


def create_app():
    """Create the KAgentApp wrapping our LangGraph agent."""
    graph = create_graph()

    kagent_app = KAgentApp(
        graph=graph,
        agent_card={
            "name": AGENT_NAME,
            "description": (
                "Bank Credit Limit Agent - Handles credit limit increase requests. "
                "Gathers customer data, requests risk assessment from the Credit "
                "Assessment Agent via A2A, and applies approved increases."
            ),
            "version": "1.0.0",
            "capabilities": {"streaming": True},
            "defaultInputModes": ["text"],
            "defaultOutputModes": ["text"],
            "skills": [
                {
                    "id": "credit-limit-increase",
                    "name": "Credit Limit Increase",
                    "description": (
                        "Process a credit limit increase request for a customer. "
                        "Retrieves customer data, performs credit assessment via "
                        "the Credit Assessment Agent (A2A), and applies the decision."
                    ),
                    "tags": ["banking", "credit", "a2a"],
                    "examples": [
                        "I'd like to increase the credit limit for customer CUST-1001 to $20,000",
                        "Can you process a credit limit increase for Alice Johnson?",
                        "Customer CUST-1003 is requesting a higher credit limit",
                    ],
                },
            ],
        },
        config=KAgentConfig(
            url=KAGENT_CONTROLLER_URL,
            app_name=AGENT_NAME,
        ),
    )

    return kagent_app.build()


app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=SERVER_PORT)
