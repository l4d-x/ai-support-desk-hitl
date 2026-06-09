---

## How It Works

### Ticket Flow — Auto Resolved
1. Customer submits query via frontend
2. RAG agent searches Qdrant knowledge base
3. Groq LLM generates draft response
4. Confidence score > 0.75 → auto-sent to customer

### Ticket Flow — Escalated (HITL)
1. Customer submits refund request with Order ID
2. RAG agent checks order eligibility via SQLite
3. Eligible refund → needs_escalation = True
4. LangGraph graph **interrupts** at `human_review` node
5. Ticket appears in Agent Dashboard with full context
6. Manager approves, edits, or rejects
7. Graph resumes → final response sent to customer

---

## Setup & Run

### 1. Clone the repo
```bash
git clone https://github.com/l4d-x/ai-support-desk-hitl.git
cd ai-support-desk-hitl
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Set up environment
```bash
cp .env.example .env
# Add your GROQ_API_KEY to .env
```

### 4. Run FastAPI backend
```bash
$env:PYTHONPATH="."; uvicorn src.api.main:app --reload
```

### 5. Run Agent Dashboard
```bash
streamlit run src/frontend/agent_dashboard.py
```

### 6. Run Customer Frontend
```bash
streamlit run src/frontend/customer.py --server.port 8502
```

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| POST | `/ticket` | Submit new support ticket |
| GET | `/queue` | Get all escalated tickets pending review |
| POST | `/review/{ticket_id}` | Submit human decision (approve/reject) |
| GET | `/ticket/{ticket_id}` | Get ticket status and details |

---

## Sample Test Queries

**Auto-resolved (high confidence):**
```json
{
  "customer_email": "user@example.com",
  "customer_query": "How long does standard shipping take?"
}
```

**Escalated — Refund Request:**
```json
{
  "customer_email": "alice@example.com",
  "customer_query": "I want a refund",
  "order_id": "ORD001",
  "refund_amount": 50.00
}
```

**Auto-rejected — Ineligible Refund:**
```json
{
  "customer_email": "bob@example.com",
  "customer_query": "I want a refund",
  "order_id": "ORD002",
  "refund_amount": 50.00
}
```

---

## Why This Project

Most fresher AI projects are basic RAG chatbots. This project demonstrates:

- **Agentic AI** — autonomous decision-making with conditional routing
- **LangGraph** — production-grade state machine with interrupt/resume
- **HITL** — human oversight before sensitive actions reach customers
- **System Design** — separated concerns across agents, tools, API, and frontend

Directly relevant to enterprise AI roles at companies building conversational AI platforms.

---

## Requirements
