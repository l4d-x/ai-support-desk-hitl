import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional
import uuid
from src.graph.workflow import build_graph

app = FastAPI()
graph = build_graph()

# In-memory ticket store
tickets = {}

class TicketRequest(BaseModel):
    customer_email: str
    customer_query: str
    order_id: Optional[str] = None
    refund_amount: Optional[float] = None

class ReviewRequest(BaseModel):
    decision: str  # approve or reject
    edited_response: Optional[str] = None

@app.post("/ticket")
def submit_ticket(req: TicketRequest):
    ticket_id = str(uuid.uuid4())[:8]
    
    initial_state = {
        "ticket_id": ticket_id,
        "customer_email": req.customer_email,
        "customer_query": req.customer_query,
        "order_id": req.order_id,
        "refund_amount": req.refund_amount,
        "status": "new",
        "draft_response": None,
        "confidence_score": None,
        "needs_escalation": None,
        "refund_eligibility": None,
        "kb_sources": None,
        "human_decision": None,
        "human_edited_response": None,
        "final_response": None
    }

    config = {"configurable": {"thread_id": ticket_id}}
    result = graph.invoke(initial_state, config=config)
    tickets[ticket_id] = config
    
    return {
        "ticket_id": ticket_id,
        "status": result["status"],
        "final_response": result.get("final_response"),
        "draft_response": result.get("draft_response"),
        "confidence_score": result.get("confidence_score"),
        "needs_escalation": result.get("needs_escalation")
    }

@app.get("/queue")
def get_queue():
    queue = []
    for ticket_id, config in tickets.items():
        state = graph.get_state(config)
        if state and state.values.get("status") == "escalated":
            queue.append({
                "ticket_id": ticket_id,
                "customer_email": state.values.get("customer_email"),
                "customer_query": state.values.get("customer_query"),
                "draft_response": state.values.get("draft_response"),
                "confidence_score": state.values.get("confidence_score"),
                "refund_eligibility": state.values.get("refund_eligibility"),
                "kb_sources": state.values.get("kb_sources")
            })
    return queue

@app.post("/review/{ticket_id}")
def review_ticket(ticket_id: str, req: ReviewRequest):
    if ticket_id not in tickets:
        return {"error": "Ticket not found"}
    
    config = tickets[ticket_id]
    graph.update_state(
        config,
        {
            "human_decision": req.decision,
            "human_edited_response": req.edited_response
        },
        as_node="human_review"
    )

    result = graph.invoke(None, config=config)
    return {
        "ticket_id": ticket_id,
        "status": result["status"],
        "final_response": result.get("final_response")
    }

@app.get("/ticket/{ticket_id}")
def get_ticket(ticket_id: str):
    if ticket_id not in tickets:
        return {"error": "Ticket not found"}
    config = tickets[ticket_id]
    state = graph.get_state(config)
    return state.values