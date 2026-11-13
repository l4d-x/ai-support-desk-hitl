from enum import StrEnum
from typing import TypedDict


class TicketStatus(StrEnum):
    NEW = "new"
    DRAFT_READY = "draft_ready"
    ESCALATED = "escalated"  # waiting for a human in the review queue
    SENT = "sent"  # reply delivered (auto-resolved, or human-approved)
    REJECTED = "rejected"  # human rejected the draft; customer gets the rejection notice
    ERROR = "error"  # the model/vector DB failed while handling the ticket


class TicketState(TypedDict):
    ticket_id: str
    customer_email: str
    customer_query: str
    order_id: str | None
    refund_amount: float | None
    draft_response: str | None
    confidence_score: float | None
    needs_escalation: bool | None
    guard_flagged: bool | None
    refund_eligibility: dict | None
    kb_sources: list[str] | None
    status: str  # a TicketStatus value (stored as a plain str so checkpoints stay JSON-friendly)
    human_decision: str | None  # "approve" | "reject"
    human_edited_response: str | None
    final_response: str | None
