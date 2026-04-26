"""Retrieval helpers for fetching relevant knowledge from ChromaDB."""

from dataclasses import dataclass
import logging
from typing import List

from app.config import settings
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
import chromadb
from app.rag.chroma_store import ensure_user_collection


LOGGER = logging.getLogger(__name__)
embedding_fn = SentenceTransformerEmbeddingFunction(model_name="sentence-transformers/all-MiniLM-L6-v2")
LOGGER.info("Using HuggingFace retrieval model: sentence-transformers/all-MiniLM-L6-v2")
_client = chromadb.PersistentClient(path=settings.chroma_path)

_CRITICAL_KEYWORDS = {"refund", "return", "shipping", "delivery", "warranty"}


@dataclass
class RetrievalResult:
    """Final retrieval bundle used by the orchestrator."""

    chunks: List["RetrievedChunk"]
    fallback_relaxed: bool


@dataclass
class RetrievedChunk:
    """Structured retrieval result with score and metadata."""

    text: str
    source_file: str
    topic: str
    version: str
    score: float

    def to_context_block(self) -> str:
        return (
            f"Source File: {self.source_file}\n"
            f"Topic: {self.topic}\n"
            f"Version: {self.version}\n"
            f"Content: {self.text}"
        )


def _distance_to_similarity(distance: float | None) -> float:
    """Normalize vector distance to a 0..1 similarity score."""
    if distance is None:
        return 0.0
    # Robust across distance metrics where lower is more similar.
    return 1.0 / (1.0 + max(0.0, float(distance)))


def _extract_keywords(text: str) -> set[str]:
    words = [w.strip(".,!?;:()[]{}\"'").lower() for w in (text or "").split()]
    return {w for w in words if w and len(w) > 2}


def _keyword_overlap_bonus(query: str, document: str) -> float:
    query_keywords = _extract_keywords(query)
    if not query_keywords:
        return 0.0
    doc_keywords = _extract_keywords(document)
    overlap = len(query_keywords.intersection(doc_keywords))
    return min(0.20, overlap * 0.03)


def _query_embedding_debug_vector(query_text: str) -> tuple[int, list[float]]:
    """Return embedding length and a short preview for debugging."""
    try:
        collection = _client.get_or_create_collection(
            name="salesai_knowledge_v2",
            embedding_function=embedding_fn
        )
        vector = embedding_fn([query_text])[0]
        preview = [round(float(x), 6) for x in vector[:8]]
        return len(vector), preview
    except Exception:
        return 0, []


def _boosted_query(query: str) -> str:
    """Apply lightweight keyword boost for critical support terms."""
    q = (query or "").strip()
    if not q:
        return q

    q_lower = q.lower()
    hits = [kw for kw in _CRITICAL_KEYWORDS if kw in q_lower]
    if not hits:
        return q

    boost = " ".join(hits * 2)
    return f"{q}\nKeyword focus: {boost}"


def retrieve_relevant_chunks(
    query: str,
    top_k: int = 5,
    min_similarity: float = 0.60,
    relaxed_fallback_k: int = 2,
    use_keyword_boost: bool = True,
) -> RetrievalResult:
    """Retrieve and filter knowledge chunks with score thresholding."""
    collection = _client.get_or_create_collection(
        name="salesai_knowledge_v2",
        embedding_function=embedding_fn
    )

    q = _boosted_query(query) if use_keyword_boost else query
    result = collection.query(
        query_texts=[q],
        n_results=max(top_k, 5) * 3,
        include=["documents", "metadatas", "distances"],
    )

    docs_nested = result.get("documents", [[]])
    metadatas_nested = result.get("metadatas", [[]])
    distances_nested = result.get("distances", [[]])

    docs = docs_nested[0] if docs_nested else []
    metadatas = metadatas_nested[0] if metadatas_nested else []
    distances = distances_nested[0] if distances_nested else []

    candidates: List[RetrievedChunk] = []
    for idx, doc in enumerate(docs):
        metadata = metadatas[idx] if idx < len(metadatas) and metadatas[idx] else {}
        if metadata.get("active", "true") != "true":
            continue

        base_score = _distance_to_similarity(distances[idx] if idx < len(distances) else None)
        score = min(1.0, base_score + _keyword_overlap_bonus(query=q, document=doc))
        source_file = str(metadata.get("source_file") or metadata.get("source") or "unknown")
        topic = str(metadata.get("topic") or "unknown")
        version = str(metadata.get("version") or "unknown")

        candidates.append(
            RetrievedChunk(
                text=doc,
                source_file=source_file,
                topic=topic,
                version=version,
                score=score,
            )
        )

    candidates.sort(key=lambda chunk: chunk.score, reverse=True)
    filtered = [chunk for chunk in candidates if chunk.score >= min_similarity][:top_k]

    if settings.rag_debug_logging:
        emb_size, emb_preview = _query_embedding_debug_vector(q)
        LOGGER.info("RAG query=%r", query)
        LOGGER.info("RAG query embedding size=%d preview=%s", emb_size, emb_preview)
        try:
            metric = (collection.metadata or {}).get("hnsw:space", "unknown")
        except Exception:
            metric = "unknown"
        LOGGER.info("RAG vector metric=%s embedding_model=%s", metric, "sentence-transformers/all-MiniLM-L6-v2")
        for idx, chunk in enumerate(candidates[:5], start=1):
            LOGGER.info(
                "RAG top5 #%d score=%.3f source=%s topic=%s version=%s",
                idx,
                chunk.score,
                chunk.source_file,
                chunk.topic,
                chunk.version,
            )

    if filtered:
        return RetrievalResult(chunks=filtered, fallback_relaxed=False)

    relaxed = candidates[: max(relaxed_fallback_k, 0)]
    if relaxed:
        LOGGER.warning(
            "RAG below threshold=%.2f, using relaxed fallback chunks=%d",
            min_similarity,
            len(relaxed),
        )
        return RetrievalResult(chunks=relaxed, fallback_relaxed=True)

    LOGGER.warning("RAG retrieval returned no candidates; embedding/indexing may be broken")
    return RetrievalResult(chunks=[], fallback_relaxed=True)


def retrieve_top_k(query: str, k: int = 2) -> List[str]:
    """Backward-compatible wrapper returning formatted chunk strings."""
    result = retrieve_relevant_chunks(query=query, top_k=k, min_similarity=0.0, relaxed_fallback_k=0)
    return [chunk.to_context_block() for chunk in result.chunks]


def retrieve_similar_user_messages(query: str, k: int = 2) -> List[str]:
    """Retrieve top-k similar past customer messages from user-memory collection."""
    collection = ensure_user_collection()
    result = collection.query(query_texts=[query], n_results=k)

    docs_nested = result.get("documents", [[]])
    ids_nested = result.get("ids", [[]])

    docs = docs_nested[0] if docs_nested else []
    ids = ids_nested[0] if ids_nested else []

    formatted: List[str] = []
    for idx, doc in enumerate(docs):
        doc_id = ids[idx] if idx < len(ids) else f"user-doc-{idx}"
        formatted.append(f"User message ({doc_id}):\n{doc}")

    return formatted
