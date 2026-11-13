"""Manager dashboard: review the escalation queue. Password-protected."""

import hmac

import streamlit as st

from api import ApiError, _secret, call

st.set_page_config(page_title="Agent Dashboard", page_icon="🧑‍💼", layout="wide")
st.title("🧑‍💼 Agent review queue")


def check_password() -> bool:
    expected = _secret("AGENT_PASSWORD")
    if not expected:
        st.error("AGENT_PASSWORD is not configured, so this page is locked.")
        return False
    if st.session_state.get("agent_ok"):
        return True
    with st.form("login"):
        pw = st.text_input("Password", type="password")
        if st.form_submit_button("Sign in"):
            if hmac.compare_digest(pw.encode(), expected.encode()):
                st.session_state.agent_ok = True
                st.rerun()
            st.error("Wrong password.")
    return False


if not check_password():
    st.stop()

top = st.columns([1, 6])
if top[0].button("🔄 Refresh"):
    st.rerun()

try:
    queue = call("GET", "/queue")
except ApiError as err:
    st.error(str(err))
    st.stop()

if not queue:
    st.success("Queue is empty. Nothing needs review.")

for item in queue:
    tid = item["ticket_id"]
    score = item["confidence_score"]
    label = f"{item['customer_email']} · confidence {score:.2f}" if score is not None else "ticket"
    with st.expander(f"{label} — {item['customer_query'][:70]}", expanded=True):
        left, right = st.columns(2)
        left.markdown(f"**Customer question**\n\n{item['customer_query']}")
        right.markdown(
            "**Knowledge-base sources**\n\n" + (", ".join(item["kb_sources"] or []) or "none")
        )
        elig = item.get("refund_eligibility")
        if elig:
            icon = "✅" if elig["eligible"] else "❌"
            st.markdown(f"**Refund check** {icon} {elig['reason']}")

        edited = st.text_area(
            "AI draft (edit before approving)",
            item["draft_response"] or "",
            key=f"e_{tid}",
            height=140,
        )
        approve, reject, _ = st.columns([1, 1, 6])
        decision = None
        if approve.button("Approve", key=f"a_{tid}", type="primary"):
            decision = "approve"
        if reject.button("Reject", key=f"r_{tid}"):
            decision = "reject"
        if decision:
            try:
                call(
                    "POST",
                    f"/review/{tid}",
                    json={
                        "decision": decision,
                        "edited_response": edited if edited != item["draft_response"] else None,
                    },
                )
            except ApiError as err:
                st.error(str(err))
            else:
                st.toast(f"Ticket {decision}d")
                st.rerun()
