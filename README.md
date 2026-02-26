# Solo Bank — AI-Powered Credit Limit Agent Demo

An interactive bank demo featuring an AI agent that processes credit limit increases, with a full web frontend, SQLite backend, and enterprise security policies — all deployed on Kubernetes via ArgoCD.

## Architecture

```
                              Solo Bank Website
                              (FastAPI + HTML/JS)
                            ┌─────────────────────┐
                  Browser ──┤  solo-bank-web:8080  │
                            │  - Dashboard         │
                            │  - Transfers         │
                            │  - Approvals         │
                            │  - AI Chat           │
                            │  - SQLite DB         │
                            └────────┬────────────┘
                                     │ A2A
                                     ▼
┌──────────────────────────────────────────────────────────────────────┐
│  kagent (Kubernetes)                                                 │
│                                                                      │
│  ┌──────────────────────────┐  A2A  ┌───────────────────────────┐   │
│  │ Bank Credit Limit Agent  │──────▶│ Credit Assessment Agent   │   │
│  │ (BYO - LangChain)        │       │ (Declarative - kagent)    │   │
│  │ sebbycorp/bank-credit-   │       │ Risk evaluation via LLM   │   │
│  │ limit-agent:latest       │       └──────────┬────────────────┘   │
│  │                          │                   │                    │
│  │ Tools:                   │                   │                    │
│  │  - get_customer_profile  │                   │                    │
│  │  - get_account_balances  │                   │                    │
│  │  - get_recent_txns       │                   │                    │
│  │  - transfer_funds        │                   │                    │
│  │  - update_credit_limit   │                   │                    │
│  │  - request_credit_assess │                   │                    │
│  └──────────┬───────────────┘                   │                    │
│             │                                   │                    │
│             ▼                                   ▼                    │
│  ┌──────────────────────────────────────────────────────────────┐    │
│  │  AgentGateway Proxy (agentgateway-system)                    │    │
│  │  llm-agentgateway model → OpenAI via gateway                 │    │
│  │  Enterprise Policies: PII guard, rate limits, prompt enrich  │    │
│  │  Tracing: OTel → Langfuse + ClickHouse                      │    │
│  └──────────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────────┘
```

## Components

| Component | Type | Image | Description |
|---|---|---|---|
| `solo-bank-web` | Deployment + Service | `sebbycorp/solo-bank-web` | Bank website (FastAPI + SQLite) |
| `bank-credit-limit-agent` | BYO Agent (LangChain) | `sebbycorp/bank-credit-limit-agent` | AI agent for credit decisions |
| `credit-assessment-agent` | Declarative Agent | kagent built-in | Risk assessor called via A2A |
| Enterprise Policies | 15 AgentGateway policies | — | PII, rate limits, auth, compliance |

## Demo Customers

| ID | Name | Score | Limit | Profile |
|---|---|---|---|---|
| CUST-1001 | Alice Johnson | 780 | $10,000 | Excellent — approved |
| CUST-1002 | Bob Martinez | 650 | $5,000 | Risky — denied |
| CUST-1003 | Carol Chen | 720 | $15,000 | Good — conditional |
| CUST-1004 | David Park | 820 | $25,000 | Excellent — approved |

Each customer has checking, savings, and credit card accounts with realistic balances and transaction history.

## Two Agent Scenarios

### 1. User → Agent (via website)
User opens Solo Bank website → goes to Credit Limit tab → chats with the AI agent → agent pulls customer data from the bank backend API → requests assessment → applies decision.

### 2. Agent → Agent (A2A)
Bank Credit Limit Agent calls `request_credit_assessment` tool → sends A2A `tasks/send` to Credit Assessment Agent → gets structured risk evaluation → acts on recommendation.

## Deployment (via ArgoCD through k8s-rooster)

ArgoCD Applications in `ProfessorSeb/k8s-rooster`:

| App | Source | Target |
|---|---|---|
| `bank-agents` | `bank-agent/k8s/agents/` | `kagent` |
| `bank-web` | `bank-agent/k8s/web/` | `kagent` |
| `bank-enterprise-policies` | `bank-agent/k8s/enterprise-policies/` | `agentgateway-system` |

## Local Development

```bash
# Run the bank website locally
make run-web
# Open http://localhost:8080

# Run the agent locally (connects to local web backend)
export OPENAI_API_KEY="your-key"
make dev-agent
```

## Build & Push

```bash
# Build and push all containers
make push-all

# Or individually
make push       # agent only
make push-web   # web only
```

## Enterprise Security Policies

| Policy | Purpose |
|---|---|
| Prompt Guard (PII) | Block SSN, credit cards, account numbers; mask PII in responses |
| Rate Limiting | 500 tokens/min + 10 req/min per user, 100 req/min global |
| JWT Auth | Token validation for API access |
| RBAC | Role-based access (credit officers only) |
| Prompt Enrichment | ECOA compliance rules injected into every LLM call |
| Tracing | Full OTel tracing → Langfuse + ClickHouse |
| CSRF/CORS | Web security for the bank frontend |
| Audit Headers | Request metadata on all responses |
| DLP (ExtProc) | External processing for data loss prevention |

## Project Structure

```
bank-agent/
├── web/                    # Solo Bank website
│   ├── app.py              #   FastAPI backend + REST API
│   ├── database.py         #   SQLite database (source of truth)
│   └── static/             #   HTML/CSS/JS frontend
├── src/                    # LangChain credit limit agent
│   ├── app.py              #   KAgentApp entry point
│   ├── graph.py            #   LangGraph reactive agent
│   ├── tools.py            #   Banking tools (call web backend API)
│   └── config.py           #   Environment config
├── k8s/
│   ├── agents/             #   kagent Agent CRDs
│   ├── web/                #   Web app Deployment + Service
│   └── enterprise-policies/#   AgentGateway security policies
├── Dockerfile              # Agent container
├── Dockerfile.web          # Web app container
└── Makefile
```
