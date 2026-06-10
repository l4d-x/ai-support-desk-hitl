import streamlit as st
import requests

API = "http://localhost:8000"

st.title("TechCart Agent Dashboard")
st.subheader("Pending Review Queue")

if st.button("Refresh Queue"):
    st.rerun()

res = requests.get(f"{API}/queue")
queue = res.json()

if not queue:
    st.success("No tickets pending review.")
else:
    for ticket in queue:
        with st.expander(f"Ticket {ticket['ticket_id']} — {ticket['customer_email']}"):
            st.write("**Customer Query:**", ticket["customer_query"])
            st.write("**AI Draft Response:**", ticket["draft_response"])
            st.write("**Confidence Score:**", ticket["confidence_score"])
            st.write("**KB Sources:**", ticket["kb_sources"])

            if ticket.get("refund_eligibility"):
                st.write("**Refund Eligibility:**", ticket["refund_eligibility"])

            edited = st.text_area("Edit Response (optional)", value=ticket["draft_response"], key=ticket["ticket_id"])

            col1, col2 = st.columns(2)

            with col1:
                if st.button("Approve", key=f"approve_{ticket['ticket_id']}"):
                    res = requests.post(f"{API}/review/{ticket['ticket_id']}", json={
                        "decision": "approve",
                        "edited_response": edited
                    })
                    st.success("Approved!")
                    st.rerun()

            with col2:
                if st.button("Reject", key=f"reject_{ticket['ticket_id']}"):
                    res = requests.post(f"{API}/review/{ticket['ticket_id']}", json={
                        "decision": "reject"
                    })
                    st.error("Rejected.")
                    st.rerun()