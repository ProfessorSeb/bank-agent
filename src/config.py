import os

# LLM Configuration - routed through AgentGateway for observability
LLM_BASE_URL = os.environ.get(
    "LLM_BASE_URL",
    "http://agentgateway-proxy.agentgateway-system.svc.cluster.local:8080/openai",
)
LLM_MODEL = os.environ.get("LLM_MODEL", "gpt-4o-mini-2024-07-18")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

# kagent A2A Configuration
KAGENT_CONTROLLER_URL = os.environ.get(
    "KAGENT_CONTROLLER_URL",
    "http://kagent-controller.kagent.svc.cluster.local:8083",
)
AGENT_NAMESPACE = os.environ.get("AGENT_NAMESPACE", "kagent")

# Agent Settings
AGENT_NAME = "bank-credit-limit-agent"
CREDIT_ASSESSMENT_AGENT = "credit-assessment-agent"
SERVER_PORT = int(os.environ.get("PORT", "8080"))
