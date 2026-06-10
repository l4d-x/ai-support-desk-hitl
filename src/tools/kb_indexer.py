from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv
import os
import uuid

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '..', '.env'))

client = QdrantClient(
    url=os.getenv("QDRANT_URL"),
    api_key=os.getenv("QDRANT_API_KEY")
)
model = SentenceTransformer("all-MiniLM-L6-v2")

COLLECTION_NAME = "support_kb"

FAQ_DATA = [
    {
        "topic": "Return Policy",
        "question": "What is your return policy?",
        "answer": "You can return any product within 30 days of purchase for a full refund. Items must be unused, in their original packaging, and accompanied by the receipt."
    },
    {
        "topic": "Shipping",
        "question": "How long does standard shipping take?",
        "answer": "Standard shipping takes 3-5 business days. Express shipping takes 1-2 business days. Shipping is free for orders over $50."
    },
    {
        "topic": "International",
        "question": "Do you offer international shipping?",
        "answer": "Yes, we ship globally! International shipping rates are calculated at checkout, and delivery typically takes 7-14 business days."
    },
    {
        "topic": "Warranty",
        "question": "What is the warranty policy on electronic items?",
        "answer": "All electronics carry a 1-year limited manufacturer warranty. Covers hardware defects but not accidental damage, drops, or water damage."
    },
    {
        "topic": "Refunds",
        "question": "How do I request a refund?",
        "answer": "Refunds are processed back to the original payment method. Verify your email, supply the Order ID, and state the reason. All refunds require manual management approval."
    },
]

def index_faq():
    existing = client.collection_exists(COLLECTION_NAME)
    if existing:
        print("Collection already exists, skipping indexing.")
        return

    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(size=384, distance=Distance.COSINE)
    )

    points = []
    for item in FAQ_DATA:
        text = f"{item['question']} {item['answer']}"
        vector = model.encode(text).tolist()
        points.append(PointStruct(
            id=str(uuid.uuid4()),
            vector=vector,
            payload=item
        ))

    client.upsert(collection_name=COLLECTION_NAME, points=points)
    print(f"Indexed {len(points)} FAQ entries into Qdrant Cloud.")

def search_kb(query: str, top_k: int = 3):
    query_vector = model.encode(query).tolist()
    results = client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        limit=top_k,
        with_payload=True
    )
    return [
        {
            "topic": r.payload["topic"],
            "answer": r.payload["answer"],
            "score": r.score
        }
        for r in results.points
    ]

index_faq()
