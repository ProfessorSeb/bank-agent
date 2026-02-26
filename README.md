# Solo Bank — AI-Powered Credit Limit Agent Demo

An interactive bank demo featuring an AI agent that processes credit limit increases, with a two-portal web frontend, SQLite backend, and enterprise security policies — all deployed on Kubernetes via ArgoCD.

## Architecture

```
                          Solo Bank Website (K8s NodePort :31691)
                          ┌────────────────────────────────────┐
                Browser ──┤  solo-bank-web:8080                │
                          │  ┌──────────────────────────────┐  │
                          │  │ Customer Portal              │  │
                          │  │  - Dashboard (balances)      │  │
                          │  │  - Transaction History       │  │
                          │  │  - Credit Info               │  │
                          │  ├──────────────────────────────┤  │
                          │  │ Agent / Admin Portal         │  │
                          │  │  - AI Agent Chat             │  │
                          │  │  - Approvals (approve/deny)  │  │
                          │  │  - Transfer Funds            │  │
                          │  │  - Audit Log                 │  │
                          │  └──────────────────────────────┘  │
                          │  SQLite DB (source of truth)       │
                          └──────────┬─────────────────────────┘
                                     │ A2A (JSON-RPC)
                                     ▼
┌──────────────────────────────────────────────────────────────────────┐
│  kagent (Kubernetes)                                                 │
│                                                                      │
│  ┌──────────────────────────┐  A2A  ┌───────────────────────────┐   │
│  │ Bank Credit Limit Agent  │──────▶│ Credit Assessment Agent   │   │
│  │ (BYO - LangChain)        │       │ (Declarative - kagent)    │   │
│  │                          │       │ Risk evaluation via LLM   │   │
│  │ Tools:                   │       └──────────┬────────────────┘   │
│  │  - get_customer_profile  │                   │                    │
│  │  - get_account_balances  │                   │                    │
│  │  - get_recent_txns       │                   │                    │
│  │  - transfer_funds        │                   │                    │
│  │  - update_credit_limit   │─── calls ──▶ Web Backend REST API     │
│  │  - request_credit_assess │                                        │
│  └──────────────────────────┘                                        │
│             │                                                        │
│             ▼                                                        │
│  ┌──────────────────────────────────────────────────────────────┐    │
│  │  AgentGateway Proxy (agentgateway-system)                    │    │
│  │  llm-agentgateway model → OpenAI via gateway                 │    │
│  │  Enterprise Policies: PII guard, rate limits, prompt enrich  │    │
│  │  Tracing: OTel → Langfuse + ClickHouse                      │    │
│  └──────────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────────┘
```

## Access the Website

The Solo Bank website runs in K8s and is accessible via NodePort:

```
http://<any-node-ip>:31691/
```

On the maniak-rooster cluster:
```
http://172.16.10.130:31691/
```

## Two-Portal Design

### Customer Portal
- **Dashboard** — Account cards (checking, savings, credit), recent transactions
- **Transactions** — Full transaction history with balances
- **Credit Info** — Credit score, utilization, DTI ratio, credit limit history

### Agent / Admin Portal
- **AI Agent Chat** — Chat with the Bank Credit Limit Agent to request credit limit increases
- **Approvals** — Review and approve/deny pending large transactions and wire transfers
- **Transfer Funds** — Transfer money between customer accounts
- **Audit Log** — Credit limit change history with assessor info, all transactions

## Components

| Component | Type | Image | Description |
|---|---|---|---|
| `solo-bank-web` | Deployment + NodePort | `sebbycorp/solo-bank-web` | Bank website (FastAPI + SQLite) |
| `bank-credit-limit-agent` | BYO Agent (LangChain) | `sebbycorp/bank-credit-limit-agent` | AI agent for credit decisions |
| `credit-assessment-agent` | Declarative Agent | kagent built-in | Risk assessor called via A2A |
| Enterprise Policies | AgentGateway policies | — | PII, rate limits, auth, compliance |

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
User opens Solo Bank website → switches to Agent/Admin Portal → chats with the AI agent → agent pulls customer data from the bank backend API → calls Credit Assessment Agent via A2A → applies approved credit limit changes → changes reflect immediately in the Customer Portal.

### 2. Agent → Agent (A2A)
Bank Credit Limit Agent calls `request_credit_assessment` tool → sends A2A `tasks/send` to Credit Assessment Agent via kagent controller → gets structured risk evaluation → acts on recommendation → updates credit limit via web backend API.

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

# Or run via Docker
docker run -d -p 9090:8080 \
  -e KAGENT_CONTROLLER_URL=http://<node-ip>:31036 \
  sebbycorp/solo-bank-web:latest
```

## Build & Push

```bash
# Build and push all containers
make push-all TAG=<commit-sha>

# Or individually
make push TAG=<sha>       # agent only
make push-web TAG=<sha>   # web only
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
│   └── static/             #   HTML/CSS/JS frontend (two-portal)
├── src/                    # LangChain credit limit agent
│   ├── app.py              #   KAgentApp entry point
│   ├── graph.py            #   LangGraph reactive agent
│   ├── tools.py            #   Banking tools (call web backend API)
│   └── config.py           #   Environment config
├── k8s/
│   ├── agents/             #   kagent Agent CRDs
│   ├── web/                #   Web app Deployment + NodePort Service
│   └── enterprise-policies/#   AgentGateway security policies
├── Dockerfile              # Agent container
├── Dockerfile.web          # Web app container
└── Makefile
```
