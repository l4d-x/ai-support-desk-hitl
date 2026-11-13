"""Markdown knowledge base -> Qdrant.

Nothing runs at import time. `ensure_index()` is called from the API lifespan; it is idempotent
(deterministic point ids) so a restart, or a Qdrant Cloud cluster that was re-created, just works.
"""

from __future__ import annotations

import hashlib
import re
import uuid
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointIdsList, PointStruct, VectorParams

from src.config import COLLECTION_NAME, EMBEDDING_DIM, EMBEDDING_MODEL, get_settings

_ID_NAMESPACE = uuid.UUID("6f1c0f0e-7a3b-4c52-9d0e-3b1f5f7a9c11")


@dataclass(frozen=True)
class Chunk:
    doc: str  # file stem, e.g. "return-policy"
    topic: str  # H1 title of the document
    section: str  # H2 heading ("" for text before the first H2)
    text: str

    @property
    def embed_text(self) -> str:
        head = f"{self.topic} - {self.section}" if self.section else self.topic
        return f"{head}. {self.text}"

    @property
    def point_id(self) -> str:
        digest = hashlib.sha256(f"{self.doc}|{self.section}|{self.text}".encode()).hexdigest()
        return str(uuid.uuid5(_ID_NAMESPACE, digest))


def parse_markdown(doc: str, markdown: str) -> list[Chunk]:
    """An H1 gives the topic; each H2 starts a new chunk."""
    topic = doc.replace("-", " ").title()
    section = ""
    buf: list[str] = []
    chunks: list[Chunk] = []

    def flush() -> None:
        text = " ".join(" ".join(buf).split())
        if text:
            chunks.append(Chunk(doc, topic, section, text))
        buf.clear()

    for line in markdown.splitlines():
        if m := re.match(r"^#\s+(.*)", line):
            flush()
            topic, section = m.group(1).strip(), ""
        elif m := re.match(r"^##\s+(.*)", line):
            flush()
            section = m.group(1).strip()
        else:
            buf.append(line)
    flush()
    return chunks


def load_kb(kb_dir: str | Path | None = None) -> list[Chunk]:
    root = Path(kb_dir or get_settings().kb_dir)
    chunks: list[Chunk] = []
    for path in sorted(root.glob("*.md")):
        chunks.extend(parse_markdown(path.stem, path.read_text(encoding="utf-8")))
    return chunks


@lru_cache(maxsize=1)
def get_embedder():
    from fastembed import TextEmbedding  # heavy import, keep it lazy

    return TextEmbedding(EMBEDDING_MODEL)


def embed(texts: list[str]) -> list[list[float]]:
    return [vec.tolist() for vec in get_embedder().embed(texts)]


@lru_cache(maxsize=1)
def get_qdrant() -> QdrantClient:
    s = get_settings()
    if s.qdrant_url:
        return QdrantClient(url=s.qdrant_url, api_key=s.qdrant_api_key, timeout=30)
    return QdrantClient(":memory:")


def ensure_index(client: QdrantClient | None = None, kb_dir: str | Path | None = None) -> dict:
    """Create the collection if needed and sync it with kb/*.md. Safe to call repeatedly."""
    client = client or get_qdrant()
    chunks = load_kb(kb_dir)
    wanted = {c.point_id: c for c in chunks}

    if not client.collection_exists(COLLECTION_NAME):
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=EMBEDDING_DIM, distance=Distance.COSINE),
        )

    existing: set[str] = set()
    offset = None
    while True:
        points, offset = client.scroll(
            COLLECTION_NAME, limit=256, offset=offset, with_payload=False, with_vectors=False
        )
        existing.update(str(p.id) for p in points)
        if offset is None:
            break

    stale = existing - wanted.keys()
    if stale:
        client.delete(COLLECTION_NAME, points_selector=PointIdsList(points=list(stale)))

    missing = [wanted[i] for i in wanted.keys() - existing]
    if missing:
        vectors = embed([c.embed_text for c in missing])
        client.upsert(
            COLLECTION_NAME,
            points=[
                PointStruct(
                    id=c.point_id,
                    vector=v,
                    payload={"doc": c.doc, "topic": c.topic, "section": c.section, "text": c.text},
                )
                for c, v in zip(missing, vectors, strict=True)
            ],
        )
    return {"chunks": len(chunks), "added": len(missing), "removed": len(stale)}


def search_kb(query: str, top_k: int = 3, client: QdrantClient | None = None) -> list[dict]:
    client = client or get_qdrant()
    result = client.query_points(
        collection_name=COLLECTION_NAME,
        query=embed([query])[0],
        limit=top_k,
        with_payload=True,
    )
    return [
        {
            "doc": p.payload["doc"],
            "topic": p.payload["topic"],
            "section": p.payload["section"],
            "answer": p.payload["text"],
            "score": p.score,
        }
        for p in result.points
    ]
