"""Main entry point for the Bank Credit Limit Agent — deployed as a kagent BYO agent."""

import os
import sys

# Add src to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from a2a.types import AgentCard, AgentSkill, AgentCapabilities
from kagent.core._config import KAgentConfig
from kagent.langgraph import KAgentApp

from config import KAGENT_CONTROLLER_URL, AGENT_NAME, AGENT_NAMESPACE, SERVER_PORT
from graph import create_graph


def create_app():
    """Create the KAgentApp wrapping our LangGraph agent."""
    graph = create_graph()

    agent_card = AgentCard(
        name=AGENT_NAME,
        description=(
            "Bank Credit Limit Agent - Handles credit limit increase requests. "
            "Gathers customer data, requests risk assessment from the Credit "
            "Assessment Agent via A2A, and applies approved increases."
        ),
        version="1.0.0",
        url=f"http://localhost:{SERVER_PORT}",
        capabilities=AgentCapabilities(streaming=True),
        defaultInputModes=["text"],
        defaultOutputModes=["text"],
        skills=[
            AgentSkill(
                id="credit-limit-increase",
                name="Credit Limit Increase",
                description=(
                    "Process a credit limit increase request for a customer. "
                    "Retrieves customer data, performs credit assessment via "
                    "the Credit Assessment Agent (A2A), and applies the decision."
                ),
                tags=["banking", "credit", "a2a"],
                examples=[
                    "I'd like to increase the credit limit for customer CUST-1001 to $20,000",
                    "Can you process a credit limit increase for Alice Johnson?",
                    "Customer CUST-1003 is requesting a higher credit limit",
                ],
            ),
        ],
    )

    kagent_config = KAgentConfig(
        url=KAGENT_CONTROLLER_URL,
        name=AGENT_NAME,
        namespace=AGENT_NAMESPACE,
    )

    kagent_app = KAgentApp(
        graph=graph,
        agent_card=agent_card,
        config=kagent_config,
    )

    return kagent_app.build()


app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=SERVER_PORT)
