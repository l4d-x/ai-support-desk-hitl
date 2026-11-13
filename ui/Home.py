"""Customer page (Streamlit entrypoint). The manager dashboard is in pages/."""

import streamlit as st

from api import MAX_TICKETS_PER_SESSION, ApiError, call

st.set_page_config(page_title="TechCart Support", page_icon="🎧")
st.title("🎧 TechCart Support")
st.caption(
    "AI-assisted support. Confident answers are sent instantly; anything uncertain or any refund "
    "is reviewed by a human first."
)

DEMO_QUESTIONS = [
    "How long does standard shipping take?",
    "What is your return policy?",
    "My headphones keep cutting out, what can I do?",
    "Do you sell pizza?",
]

st.session_state.setdefault("tickets_sent", 0)

new_tab, status_tab = st.tabs(["New ticket", "Check ticket status"])

with new_tab:
    with st.expander("Demo data you can try"):
        st.markdown(
            "- Questions: " + " · ".join(f"*{q}*" for q in DEMO_QUESTIONS) + "\n"
            "- Refund with a manager review: `alice@example.com`, order `ORD001`, amount `50`\n"
            "- Refund that is refused: email `bob@example.com`, order `ORD002` (still shipping)\n"
            "- Orders: ORD001 alice, ORD002 bob, ORD003 carol, ORD004 dave, ORD005 eve "
            "(`@example.com`)"
        )

    with st.form("ticket"):
        email = st.text_input("Your email")
        query = st.text_area("How can we help?", max_chars=1000)
        with st.expander("Refund request (optional)"):
            order_id = st.text_input("Order ID", placeholder="ORD001")
            amount = st.number_input("Refund amount ($)", min_value=0.0, step=1.0)
        submitted = st.form_submit_button("Send")

    if submitted:
        if st.session_state.tickets_sent >= MAX_TICKETS_PER_SESSION:
            st.warning(f"Demo limit reached ({MAX_TICKETS_PER_SESSION} tickets per session).")
        elif not email.strip() or not query.strip():
            st.warning("Please enter your email and a question.")
        else:
            payload = {
                "customer_email": email.strip(),
                "customer_query": query.strip(),
                "order_id": order_id.strip() or None,
                "refund_amount": amount or None,
            }
            try:
                with st.spinner("Looking that up..."):
                    data = call("POST", "/ticket", json=payload)
                st.session_state.tickets_sent += 1
            except ApiError as err:
                st.error(str(err))
            else:
                if data["status"] == "sent":
                    st.success("Here's your answer:")
                    st.write(data["final_response"])
                else:
                    st.info(
                        "A support specialist needs to review this before we reply. "
                        "Use the **Check ticket status** tab with the details below."
                    )
                st.code(f"Ticket ID: {data['ticket_id']}", language=None)

with status_tab:
    with st.form("status"):
        tid = st.text_input("Ticket ID")
        mail = st.text_input("Email used on the ticket")
        look = st.form_submit_button("Check")
    if look:
        try:
            data = call("POST", "/status", json={"ticket_id": tid.strip(), "customer_email": mail})
        except ApiError as err:
            st.error(str(err))
        else:
            if data["final_response"]:
                st.success("Our reply:")
                st.write(data["final_response"])
            elif data["status"] == "error":
                st.error("We hit a problem processing this ticket. Please submit it again.")
            else:
                st.info("Still waiting for a specialist. Check back soon.")
