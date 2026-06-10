from typing import TypedDict, Optional, List

class TicketState(TypedDict):
    ticket_id: str
    customer_email: str
    customer_query: str
    order_id: Optional[str]
    refund_amount: Optional[float]
    draft_response: Optional[str]
    confidence_score: Optional[float]
    needs_escalation: Optional[bool]
    refund_eligibility: Optional[dict]
    kb_sources: Optional[List[str]]
    status: str  # new, draft_ready, escalated, approved, rejected, sent
    human_decision: Optional[str]  # approve, reject
    human_edited_response: Optional[str]
    final_response: Optional[str]