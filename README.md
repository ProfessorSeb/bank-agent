# Bank Credit Limit Agent

A bank AI agent demo that processes credit limit increase requests using two scenarios:

1. **User → Agent**: A user talks directly to the Bank Credit Limit Agent (LangChain/LangGraph)
2. **Agent → Agent**: The Bank Credit Limit Agent calls the Credit Assessment Agent via A2A protocol for risk evaluation

## Architecture

```
┌─────────────┐     ┌──────────────────────────────┐     ┌──────────────────────────┐
│   User /    │────▶│  Bank Credit Limit Agent     │────▶│  Credit Assessment Agent │
│  kagent UI  │     │  (BYO - LangChain/LangGraph) │ A2A │  (Declarative - kagent)  │
└─────────────┘     └──────────────┬───────────────┘     └────────────┬─────────────┘
                                   │                                  │
                                   ▼                                  ▼
                    ┌──────────────────────────────┐   ┌──────────────────────────┐
                    │   AgentGateway Proxy          │   │   AgentGateway Proxy     │
                    │   (LLM routing + logging)     │   │   (LLM routing + logging)│
                    └──────────────┬───────────────┘   └────────────┬─────────────┘
                                   │                                │
                                   ▼                                ▼
                              ┌────────────────────────────────────────┐
                              │         OpenAI / LLM Provider          │
                              └────────────────────────────────────────┘
```

Both agents use the `llm-agentgateway` ModelConfig, which routes all LLM calls through the Solo AgentGateway proxy for full observability (tracing via OpenTelemetry → Langfuse + ClickHouse).

## Components

| Component | Type | Framework | Model Config |
|---|---|---|---|
| `bank-credit-limit-agent` | BYO (custom container) | LangChain + LangGraph | `llm-agentgateway` (via env vars) |
| `credit-assessment-agent` | Declarative (kagent CRD) | kagent ADK | `llm-agentgateway` |

## Demo Customers

| ID | Name | Credit Score | Current Limit | Profile |
|---|---|---|---|---|
| CUST-1001 | Alice Johnson | 780 | $10,000 | Excellent — will be approved |
| CUST-1002 | Bob Martinez | 650 | $5,000 | Risky — will likely be denied |
| CUST-1003 | Carol Chen | 720 | $15,000 | Good — conditional approval |
| CUST-1004 | David Park | 820 | $25,000 | Excellent — will be approved |

## Deployment

### Prerequisites
- `maniak-rooster` K8s cluster with kagent and AgentGateway installed
- ArgoCD running in the cluster
- `kagent-openai` secret in the `kagent` namespace
- Container image pushed to `ghcr.io/professorseb/bank-credit-limit-agent`

### Build & Push Container
```bash
make build
make push
```

### Deploy via ArgoCD
```bash
make argocd-apply
```

### Deploy directly via kubectl
```bash
make deploy
```

### Local development
```bash
export OPENAI_API_KEY="your-key"
export LLM_BASE_URL="https://api.openai.com/v1"
make dev
```

## How It Works

### Scenario 1: User → Agent
User opens the kagent UI, selects `bank-credit-limit-agent`, and requests a credit limit increase. The LangChain agent:
1. Looks up the customer profile
2. Checks credit score and payment history
3. Calls the Credit Assessment Agent via A2A for risk evaluation
4. Applies the approved credit limit change

### Scenario 2: Agent → Agent (A2A)
The Bank Credit Limit Agent calls `request_credit_assessment` tool, which sends an A2A `tasks/send` request to the Credit Assessment Agent. The assessment agent evaluates the customer's creditworthiness using its LLM-powered risk model and returns a structured recommendation (APPROVE / CONDITIONAL_APPROVE / DENY).

## Project Structure
```
bank-agent/
├── src/
│   ├── app.py          # FastAPI entry point (KAgentApp)
│   ├── graph.py         # LangGraph reactive agent
│   ├── tools.py         # Banking tools + A2A integration
│   ├── data.py          # Mock customer database
│   └── config.py        # Environment configuration
├── k8s/
│   ├── agents/          # kagent Agent CRDs
│   └── argocd/          # ArgoCD Application manifest
├── Dockerfile
├── Makefile
└── requirements.txt
```
