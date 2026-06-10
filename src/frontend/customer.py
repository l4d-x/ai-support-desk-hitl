import streamlit as st
import requests

API = "http://localhost:8000"

st.title("TechCart Customer Support")

st.subheader("Submit a Support Ticket")

email = st.text_input("Your Email")
query = st.text_area("Describe your issue")
order_id = st.text_input("Order ID (optional)")
refund_amount = st.number_input("Refund Amount (optional)", min_value=0.0, value=0.0)

if st.button("Submit"):
    if not email or not query:
        st.warning("Email and query are required.")
    else:
        payload = {
            "customer_email": email,
            "customer_query": query,
            "order_id": order_id if order_id else None,
            "refund_amount": refund_amount if refund_amount > 0 else None
        }
        res = requests.post(f"{API}/ticket", json=payload)
        data = res.json()

        st.success(f"Ticket ID: {data['ticket_id']}")
        st.info(f"Status: {data['status']}")

        if data.get("final_response"):
            st.write("**Response:**", data["final_response"])
        elif data.get("needs_escalation"):
            st.write("Your ticket has been escalated for manager review. Please check back shortly.")