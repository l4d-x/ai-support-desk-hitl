from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Request
from langgraph.types import Command
from pydantic import BaseModel, Field

from src.api.security import MinuteLimiter, email_key, require_api_key
from src.config import get_settings
from src.graph.state import TicketStatus
from src.graph.workflow import build_graph
from src.store import make_persistence

log = logging.getLogger("support_desk")

EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
AUTH = [Depends(require_api_key)]


class TicketRequest(BaseModel):
    customer_email: str = Field(max_length=254, pattern=EMAIL_PATTERN)
    customer_query: str = Field(min_length=1, max_length=1000)
    order_id: str | None = Field(default=None, max_length=32)
    refund_amount: float | None = Field(default=None, gt=0, le=100_000)


class ReviewRequest(BaseModel):
    decision: Literal["approve", "reject"]
    edited_response: str | None = Field(default=None, max_length=2000)


class StatusRequest(BaseModel):
    ticket_id: str = Field(max_length=64)
    customer_email: str = Field(max_length=254)


class TicketResponse(BaseModel):
    ticket_id: str
    status: str
    final_response: str | None = None
    draft_response: str | None = None
    confidence_score: float | None = None
    needs_escalation: bool | None = None


class StatusResponse(BaseModel):
    ticket_id: str
    status: str
    final_response: str | None = None  # only once a reply has actually been sent


class QueueItem(BaseModel):
    ticket_id: str
    customer_email: str
    customer_query: str
    draft_response: str | None
    confidence_score: float | None
    refund_eligibility: dict | None
    kb_sources: list[str] | None


class ReviewResponse(BaseModel):
    ticket_id: str
    status: str
    final_response: str | None


def _config(ticket_id: str) -> dict:
    return {"configurable": {"thread_id": ticket_id}}


def create_app(graph=None, store=None, init_resources: bool = True) -> FastAPI:
    """Pass `graph` and `store` to inject them (tests); otherwise they are built in the lifespan."""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        close = lambda: None  # noqa: E731
        if app.state.graph is None:
            checkpointer, app.state.store, close = make_persistence(get_settings().database_url)
            app.state.graph = build_graph(checkpointer)
        if init_resources:
            from src.tools.kb_indexer import ensure_index
            from src.tools.order_tools import init_db

            init_db()
            ensure_index()
        try:
            yield
        finally:
            close()

    app = FastAPI(title="AI Support Desk", lifespan=lifespan)
    app.state.graph = graph
    app.state.store = store
    app.state.minute_limiter = MinuteLimiter(get_settings().minute_ticket_limit)

    def get_state_values(request: Request, ticket_id: str) -> dict:
        state = request.app.state.graph.get_state(_config(ticket_id))
        if not state or not state.values:
            raise HTTPException(status_code=404, detail="Ticket not found")
        return state.values

    def enforce_limits(request: Request, email: str) -> None:
        s = get_settings()
        if not request.app.state.minute_limiter.allow():
            raise HTTPException(429, "Too many requests right now. Please try again in a minute.")
        st = request.app.state.store
        if not st.hit(email_key(email), s.email_daily_limit):
            raise HTTPException(429, "Daily ticket limit reached for this email. Try tomorrow.")
        if not st.hit("global", s.daily_ticket_limit):
            raise HTTPException(429, "The demo has reached its daily limit. Please try tomorrow.")

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/health/deep")
    def health_deep(request: Request):
        """Touches Postgres and Qdrant so free-tier clusters count it as activity (keep-alive)."""
        from src.config import COLLECTION_NAME
        from src.tools.kb_indexer import get_qdrant

        checks = {}
        for name, probe in (
            ("database", request.app.state.store.ping),
            ("vector_db", lambda: get_qdrant().collection_exists(COLLECTION_NAME)),
        ):
            try:
                checks[name] = bool(probe())
            except Exception:
                log.exception("health probe %s failed", name)
                checks[name] = False
        if not all(checks.values()):
            raise HTTPException(status_code=503, detail=checks)
        return {"status": "ok", **checks}

    @app.post("/ticket", response_model=TicketResponse, dependencies=AUTH)
    def submit_ticket(req: TicketRequest, request: Request):
        enforce_limits(request, req.customer_email)
        ticket_id = str(uuid.uuid4())
        initial_state = {
            "ticket_id": ticket_id,
            "customer_email": req.customer_email,
            "customer_query": req.customer_query,
            "order_id": req.order_id,
            "refund_amount": req.refund_amount,
            "status": TicketStatus.NEW.value,
            "draft_response": None,
            "confidence_score": None,
            "needs_escalation": None,
            "refund_eligibility": None,
            "kb_sources": None,
            "human_decision": None,
            "human_edited_response": None,
            "final_response": None,
        }
        store_ = request.app.state.store
        store_.add_ticket(ticket_id, TicketStatus.NEW.value)
        try:
            result = request.app.state.graph.invoke(initial_state, config=_config(ticket_id))
        except Exception:
            log.exception("ticket %s failed", ticket_id)
            store_.set_status(ticket_id, TicketStatus.ERROR.value)
            raise HTTPException(
                status_code=502, detail="The assistant is temporarily unavailable. Please retry."
            ) from None
        store_.set_status(ticket_id, result["status"])
        return TicketResponse(
            ticket_id=ticket_id,
            status=result["status"],
            final_response=result.get("final_response"),
            draft_response=result.get("draft_response"),
            confidence_score=result.get("confidence_score"),
            needs_escalation=result.get("needs_escalation"),
        )

    @app.post("/status", response_model=StatusResponse, dependencies=AUTH)
    def ticket_status(req: StatusRequest, request: Request):
        """Customer-facing lookup. Needs ticket id AND the email it was filed with."""
        state = request.app.state.graph.get_state(_config(req.ticket_id))
        values = state.values if state else None
        if not values or values["customer_email"].lower() != req.customer_email.strip().lower():
            raise HTTPException(status_code=404, detail="No ticket found for that ID and email")
        sent = values["status"] in (TicketStatus.SENT.value, TicketStatus.REJECTED.value)
        return StatusResponse(
            ticket_id=req.ticket_id,
            status=values["status"],
            final_response=values.get("final_response") if sent else None,
        )

    @app.get("/queue", response_model=list[QueueItem], dependencies=AUTH)
    def get_queue(request: Request):
        queue = []
        for ticket_id in request.app.state.store.ticket_ids(TicketStatus.ESCALATED.value):
            state = request.app.state.graph.get_state(_config(ticket_id))
            if state and state.values:
                values = state.values
                queue.append(QueueItem(**{k: values.get(k) for k in QueueItem.model_fields}))
        return queue

    @app.post("/review/{ticket_id}", response_model=ReviewResponse, dependencies=AUTH)
    def review_ticket(ticket_id: str, req: ReviewRequest, request: Request):
        values = get_state_values(request, ticket_id)
        if values.get("status") != TicketStatus.ESCALATED.value:
            raise HTTPException(
                status_code=409, detail=f"Ticket is '{values.get('status')}', not awaiting review"
            )
        result = request.app.state.graph.invoke(
            Command(resume={"decision": req.decision, "edited_response": req.edited_response}),
            config=_config(ticket_id),
        )
        request.app.state.store.set_status(ticket_id, result["status"])
        return ReviewResponse(
            ticket_id=ticket_id,
            status=result["status"],
            final_response=result.get("final_response"),
        )

    @app.get("/ticket/{ticket_id}", dependencies=AUTH)
    def get_ticket(ticket_id: str, request: Request):
        return get_state_values(request, ticket_id)

    return app


app = create_app()
