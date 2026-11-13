"""LangGraph workflow: draft -> (auto-send | escalate -> human review) -> done.

Human-in-the-loop uses a dynamic `interrupt()` inside `human_review`. The API resumes the thread
with `Command(resume={...})`, so `human_review` genuinely runs with the manager's decision.
"""

from __future__ import annotations

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.types import interrupt

from src.agents.rag_agent import run_rag_agent
from src.graph.state import TicketState, TicketStatus

REJECTION_MESSAGE = (
    "Your request has been reviewed and unfortunately cannot be processed at this time."
)


def draft_response_node(state: TicketState) -> dict:
    result = run_rag_agent(
        customer_query=state["customer_query"],
        customer_email=state["customer_email"],
        order_id=state.get("order_id"),
        refund_amount=state.get("refund_amount"),
    )
    return {**result, "status": TicketStatus.DRAFT_READY.value}


def confidence_router(state: TicketState) -> str:
    return "escalate" if state["needs_escalation"] else "auto_send"


def auto_send_node(state: TicketState) -> dict:
    return {"final_response": state["draft_response"], "status": TicketStatus.SENT.value}


def escalate_node(state: TicketState) -> dict:
    return {"status": TicketStatus.ESCALATED.value}


def human_review_node(state: TicketState) -> dict:
    # Pauses the graph here. Resumed with Command(resume={"decision": ..., "edited_response": ...}).
    review = interrupt({"ticket_id": state["ticket_id"], "draft_response": state["draft_response"]})

    decision = review["decision"]
    edited = (review.get("edited_response") or "").strip() or None

    if decision == "approve":
        return {
            "human_decision": decision,
            "human_edited_response": edited,
            "final_response": edited or state["draft_response"],
            "status": TicketStatus.SENT.value,
        }
    return {
        "human_decision": decision,
        "human_edited_response": None,
        "final_response": REJECTION_MESSAGE,
        "status": TicketStatus.REJECTED.value,
    }


def build_graph(checkpointer=None):
    graph = StateGraph(TicketState)

    graph.add_node("draft_response", draft_response_node)
    graph.add_node("auto_send", auto_send_node)
    graph.add_node("escalate", escalate_node)
    graph.add_node("human_review", human_review_node)

    graph.set_entry_point("draft_response")
    graph.add_conditional_edges(
        "draft_response",
        confidence_router,
        {"auto_send": "auto_send", "escalate": "escalate"},
    )
    graph.add_edge("auto_send", END)
    graph.add_edge("escalate", "human_review")
    graph.add_edge("human_review", END)

    return graph.compile(checkpointer=checkpointer or MemorySaver())
