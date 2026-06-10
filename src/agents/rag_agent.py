import sys
import os

from dotenv import load_dotenv
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '..', '.env'))

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from src.tools.kb_indexer import search_kb
from src.tools.order_tools import check_refund_eligibility, get_order
from langchain_groq import ChatGroq

llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    api_key=os.getenv("GROQ_API_KEY")
)

def run_rag_agent(customer_query: str, order_id: str = None, refund_amount: float = None):
    
    kb_results = search_kb(customer_query)
    top_score = kb_results[0]["score"] if kb_results else 0.0

    kb_context = "\n".join([
        f"- {r['topic']}: {r['answer']}" for r in kb_results
    ])

    refund_info = ""
    refund_eligibility = None

    if order_id and refund_amount:
        refund_eligibility = check_refund_eligibility(order_id, refund_amount)
        if refund_eligibility["eligible"]:
            order = refund_eligibility["order"]
            refund_info = f"""
Order ID: {order['order_id']}
Product: {order['product_name']}
Purchase Price: ${order['purchase_price']}
Refund Requested: ${refund_amount}
Eligibility: ELIGIBLE - Requires manager approval.
"""
        else:
            refund_info = f"Refund not eligible: {refund_eligibility['reason']}"

    prompt = f"""You are a helpful customer support agent for TechCart.

Knowledge Base Context:
{kb_context}

{f"Refund Details:{refund_info}" if refund_info else ""}

Customer Query: {customer_query}

Instructions:
- Answer the customer clearly and professionally.
- If this is a refund request and it's eligible, tell them it will be reviewed by a manager.
- If refund is not eligible, explain why politely.
- Keep response concise, under 100 words.
"""

    response = llm.invoke(prompt)
    draft = response.content

    needs_escalation = False
    if refund_eligibility and refund_eligibility["eligible"]:
        needs_escalation = True
    elif top_score < 0.75:
        needs_escalation = True

    return {
        "draft_response": draft,
        "confidence_score": round(top_score, 3),
        "needs_escalation": needs_escalation,
        "refund_eligibility": refund_eligibility,
        "kb_sources": [r["topic"] for r in kb_results]
    }