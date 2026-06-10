import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from src.graph.state import TicketState
from src.agents.rag_agent import run_rag_agent
import uuid

def draft_response_node(state: TicketState) -> TicketState:
    result = run_rag_agent(
        customer_query=state["customer_query"],
        order_id=state.get("order_id"),
        refund_amount=state.get("refund_amount")
    )
    return {
        **state,
        "draft_response": result["draft_response"],
        "confidence_score": result["confidence_score"],
        "needs_escalation": result["needs_escalation"],
        "refund_eligibility": result["refund_eligibility"],
        "kb_sources": result["kb_sources"],
        "status": "draft_ready"
    }

def confidence_router(state: TicketState) -> str:
    if state["needs_escalation"]:
        return "escalate"
    return "auto_send"

def auto_send_node(state: TicketState) -> TicketState:
    return {
        **state,
        "final_response": state["draft_response"],
        "status": "sent"
    }

def escalate_node(state: TicketState) -> TicketState:
    return {
        **state,
        "status": "escalated"
    }

def human_review_node(state: TicketState) -> TicketState:
    # This node is interrupted — FastAPI resumes it with human decision
    decision = state.get("human_decision")
    edited = state.get("human_edited_response")

    if decision == "approve":
        final = edited if edited else state["draft_response"]
        return {
            **state,
            "final_response": final,
            "status": "approved"
        }
    elif decision == "reject":
        return {
            **state,
            "final_response": "Your request has been reviewed and unfortunately cannot be processed at this time.",
            "status": "rejected"
        }
    return state

def send_final_node(state: TicketState) -> TicketState:
    return {
        **state,
        "status": "sent"
    }

def build_graph():
    graph = StateGraph(TicketState)

    graph.add_node("draft_response", draft_response_node)
    graph.add_node("auto_send", auto_send_node)
    graph.add_node("escalate", escalate_node)
    graph.add_node("human_review", human_review_node)
    graph.add_node("send_final", send_final_node)

    graph.set_entry_point("draft_response")

    graph.add_conditional_edges(
        "draft_response",
        confidence_router,
        {
            "auto_send": "auto_send",
            "escalate": "escalate"
        }
    )

    graph.add_edge("auto_send", END)
    graph.add_edge("escalate", "human_review")
    graph.add_edge("human_review", "send_final")
    graph.add_edge("send_final", END)

    memory = MemorySaver()
    return graph.compile(checkpointer=memory, interrupt_before=["human_review"])