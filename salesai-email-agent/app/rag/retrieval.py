"""Retrieval helpers for fetching relevant knowledge from ChromaDB with Hybrid Dense + BM25 and RRF."""

from app.rag.chroma_store import ensure_user_collection
from app.rag.chroma_store import ensure_collection
from dataclasses import dataclass
import json
import logging
import os
import re
from typing import Dict, List, Optional, Tuple

from app.config import settings

LOGGER = logging.getLogger(__name__)

try:
    from rank_bm25 import BM25Okapi
except ImportError:
    BM25Okapi = None

try:
    import chromadb
    from chromadb.utils.embedding_functions import DefaultEmbeddingFunction
    embedding_fn = DefaultEmbeddingFunction()
    _client = chromadb.PersistentClient(path=settings.chroma_path)
    LOGGER.info("Using ONNX retrieval model: all-MiniLM-L6-v2 via DefaultEmbeddingFunction")
except (ImportError, Exception):
    chromadb = None
    DefaultEmbeddingFunction = None
    embedding_fn = None
    _client = None
    LOGGER.warning("chromadb not initialized in environment, using keyword fallback for RAG")

_CRITICAL_KEYWORDS = {"refund", "return", "shipping", "delivery", "warranty", "exchange", "bluedart", "cod", "upi"}
_BM25_TOKEN_RE = re.compile(r"\b[a-zA-Z0-9_-]+\b")

_bm25_index: Optional[BM25Okapi] = None
_bm25_corpus_docs: List[str] = []
_bm25_corpus_metadatas: List[dict] = []
_bm25_corpus_ids: List[str] = []


def _tokenize_bm25(text: str) -> List[str]:
    """Tokenize query and document texts for BM25 ranking."""
    return [token.lower() for token in _BM25_TOKEN_RE.findall(text or "") if len(token) > 1]


def invalidate_bm25_index() -> None:
    """Invalidate cached BM25 index so it rebuilds on next retrieval."""
    global _bm25_index, _bm25_corpus_docs, _bm25_corpus_metadatas, _bm25_corpus_ids
    _bm25_index = None
    _bm25_corpus_docs = []
    _bm25_corpus_metadatas = []
    _bm25_corpus_ids = []
    LOGGER.info("Invalidated BM25 index cache")


def _get_bm25_index() -> Tuple[Optional[BM25Okapi], List[str], List[dict], List[str]]:
    """Return or lazily construct the BM25 index over the active knowledge collection."""
    global _bm25_index, _bm25_corpus_docs, _bm25_corpus_metadatas, _bm25_corpus_ids
    if _bm25_index is not None and _bm25_corpus_docs:
        return _bm25_index, _bm25_corpus_docs, _bm25_corpus_metadatas, _bm25_corpus_ids

    try:
        col = ensure_collection()
        data = col.get(include=["documents", "metadatas"])
        docs = data.get("documents", []) or []
        metadatas = data.get("metadatas", []) or []
        ids = data.get("ids", []) or []

        active_docs = []
        active_metadatas = []
        active_ids = []
        for i, doc in enumerate(docs):
            meta = metadatas[i] if i < len(metadatas) and metadatas[i] else {}
            if meta.get("active", "true") == "true":
                active_docs.append(doc)
                active_metadatas.append(meta)
                active_ids.append(ids[i] if i < len(ids) else f"doc_{i}")

        if not active_docs:
            return None, [], [], []

        tokenized = [_tokenize_bm25(doc) for doc in active_docs]
        _bm25_index = BM25Okapi(tokenized)
        _bm25_corpus_docs = active_docs
        _bm25_corpus_metadatas = active_metadatas
        _bm25_corpus_ids = active_ids
        LOGGER.info("BM25 index built with %d documents", len(active_docs))
        return _bm25_index, _bm25_corpus_docs, _bm25_corpus_metadatas, _bm25_corpus_ids
    except Exception as exc:
        LOGGER.warning("Failed to build BM25 index: %s", exc)
        return None, [], [], []


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
    section_title: str = ""
    rrf_score: float = 0.0
    grade: str = "relevant"

    def to_context_block(self) -> str:
        sec_line = f"Section: {self.section_title}\n" if self.section_title else ""
        return (
            f"Source File: {self.source_file}\n"
            f"Topic: {self.topic}\n"
            f"{sec_line}"
            f"Version: {self.version}\n"
            f"Content: {self.text}"
        )


def _distance_to_similarity(distance: float | None) -> float:
    """Normalize vector distance to a 0..1 similarity score."""
    if distance is None:
        return 0.0
    # Robust across distance metrics where lower is more similar.
    return 1.0 / (1.0 + max(0.0, float(distance)))


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


def _fuse_dense_and_sparse(
    query: str,
    dense_docs: List[str],
    dense_metadatas: List[dict],
    dense_distances: List[float],
    top_k: int = 5,
    k_rrf: int = 60,
    sparse_query: str = "",
) -> List[RetrievedChunk]:
    """Fuse dense vector search results and sparse BM25 results using Reciprocal Rank Fusion (RRF)."""
    # 1. Map dense candidates
    dense_ranks: Dict[str, int] = {}
    dense_sims: Dict[str, float] = {}
    dense_meta_map: Dict[str, dict] = {}
    for idx, doc in enumerate(dense_docs):
        meta = dense_metadatas[idx] if idx < len(dense_metadatas) and dense_metadatas[idx] else {}
        if meta.get("active", "true") != "true":
            continue
        rank = len(dense_ranks) + 1
        dense_ranks[doc] = rank
        dist = dense_distances[idx] if idx < len(dense_distances) else None
        dense_sims[doc] = _distance_to_similarity(dist)
        dense_meta_map[doc] = meta

    # 2. Map sparse BM25 candidates
    bm25, corpus_docs, corpus_metas, _ = _get_bm25_index()
    bm25_ranks: Dict[str, Tuple[int, float]] = {}
    bm25_meta_map: Dict[str, dict] = {}

    if bm25 and corpus_docs:
        bm25_q = sparse_query if sparse_query else query
        q_tokens = _tokenize_bm25(bm25_q)
        if q_tokens:
            scores = bm25.get_scores(q_tokens)
            sorted_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
            bm25_rank = 1
            for idx in sorted_indices[:max(top_k * 4, 20)]:
                if scores[idx] > 0.0:
                    doc = corpus_docs[idx]
                    bm25_ranks[doc] = (bm25_rank, float(scores[idx]))
                    bm25_meta_map[doc] = corpus_metas[idx]
                    bm25_rank += 1

    # 3. Reciprocal Rank Fusion
    all_matched_docs = set(dense_ranks.keys()).union(bm25_ranks.keys())
    candidates: List[RetrievedChunk] = []

    for doc in all_matched_docs:
        d_rank = dense_ranks.get(doc)
        b_info = bm25_ranks.get(doc)
        b_rank = b_info[0] if b_info else None

        rrf_score = 0.0
        if d_rank is not None:
            rrf_score += 1.0 / (k_rrf + d_rank)
        if b_rank is not None:
            rrf_score += 1.0 / (k_rrf + b_rank)

        # Calibrate similarity score for thresholding
        d_sim = dense_sims.get(doc, 0.50)
        if d_rank is not None and b_rank is not None:
            # Mutual agreement between dense and sparse: high confidence
            sparse_bonus = 0.20 * (1.0 - min(b_rank - 1, 19) / 20.0)
            score = min(1.0, max(d_sim, 0.55) + sparse_bonus)
        elif b_rank is not None:
            # Document surfaced strongly by sparse keywords (rare entities/codes/names)
            sparse_rel = 1.0 - min(b_rank - 1, 19) / 20.0
            score = min(0.85, 0.62 + 0.20 * sparse_rel)
        else:
            # Pure dense semantic match
            score = d_sim

        meta = dense_meta_map.get(doc) or bm25_meta_map.get(doc) or {}
        source_file = str(meta.get("source_file") or meta.get("source") or "unknown")
        topic = str(meta.get("topic") or "unknown")
        version = str(meta.get("version") or "unknown")
        section_title = str(meta.get("section_title") or "")

        chunk = RetrievedChunk(
            text=doc,
            source_file=source_file,
            topic=topic,
            version=version,
            score=score,
            section_title=section_title,
            rrf_score=rrf_score,
        )
        candidates.append(chunk)

    # Primary sort: Reciprocal Rank Fusion score (descending), secondary by similarity score
    candidates.sort(key=lambda c: (c.rrf_score, c.score), reverse=True)
    return candidates


def _call_groq_completion(prompt: str, max_tokens: int = 150) -> str:
    """Helper to query Groq with reliable models and fallback."""
    api_key = settings.groq_api_key or os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        return ""

    try:
        from groq import Groq
        client = Groq(api_key=api_key)
        # Prioritize chat models that reliably output non-empty text
        candidate_models = ["qwen/qwen3.8-27b", "qwen/qwen3.6-27b", settings.groq_model, "openai/gpt-oss-120b"]
        tried = set()

        for model in candidate_models:
            if not model or model in tried:
                continue
            tried.add(model)
            try:
                res = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=max_tokens,
                    temperature=0.0,
                )
                raw = res.choices[0].message.content or ""
                if "<think>" in raw and "</think>" in raw:
                    raw = raw.split("</think>")[-1].strip()
                cleaned = raw.strip()
                if cleaned:
                    return cleaned
            except Exception as e:
                LOGGER.debug("Groq model %s failed: %s", model, e)
                continue
        return ""
    except Exception as exc:
        LOGGER.debug("Groq client failure: %s", exc)
        return ""


def generate_hypothetical_document(query: str) -> str:
    """Generate a hypothetical policy passage using Groq (HyDE) for dense vector matching."""
    prompt = (
        "You are an expert customer support policy writer for an e-commerce platform.\n"
        "Write a short 2-3 sentence hypothetical policy passage that answers this customer question.\n"
        "Use formal policy terms such as refund window, return conditions, warranty claims, delivery timelines, reverse pickup, or payment methods.\n"
        "Do not write greetings, conversational filler, or caveats. Output ONLY the policy text.\n\n"
        f"Customer question: {query}"
    )
    cleaned = _call_groq_completion(prompt, max_tokens=120)
    if cleaned:
        LOGGER.info("HyDE generated hypothetical passage (len=%d): %s", len(cleaned), cleaned[:90])
    return cleaned


def grade_retrieved_chunks(query: str, chunks: List[RetrievedChunk]) -> List[RetrievedChunk]:
    """Grade retrieved chunks with Groq (CRAG-style) and filter out irrelevant ones."""
    if not chunks:
        return []

    chunk_previews = []
    for idx, chunk in enumerate(chunks, 1):
        text_preview = (chunk.text or "").strip().replace("\n", " ")[:250]
        sec = f" | Section: {chunk.section_title}" if chunk.section_title else ""
        chunk_previews.append(f"[{idx}] Source: {chunk.source_file}{sec}\nContent: {text_preview}")

    grading_prompt = (
        "You are a Corrective RAG (CRAG) retrieval grader for e-commerce customer support.\n"
        "Evaluate each numbered context chunk against the customer inquiry.\n\n"
        f"Customer Inquiry: \"{query}\"\n\n"
        "Retrieved Contexts:\n"
        + "\n\n".join(chunk_previews)
        + "\n\nAssign a grade for each numbered context: 'relevant', 'partial', or 'irrelevant'.\n"
        "- 'relevant': directly answers or contains crucial policy terms for the inquiry.\n"
        "- 'partial': contains related or helpful context for the inquiry.\n"
        "- 'irrelevant': completely unrelated topic or product.\n\n"
        "Return ONLY valid JSON matching this schema:\n"
        "{\n"
        "  \"grades\": [\n"
        "    {\"index\": 1, \"grade\": \"relevant\"|\"partial\"|\"irrelevant\", \"reason\": \"...\"}\n"
        "  ]\n"
        "}"
    )

    raw_text = _call_groq_completion(grading_prompt, max_tokens=300)
    if not raw_text:
        return chunks

    try:
        start = raw_text.find("{")
        end = raw_text.rfind("}")
        if start != -1 and end != -1 and end > start:
            parsed = json.loads(raw_text[start : end + 1])
            grade_list = parsed.get("grades", [])
            grade_map = {item.get("index"): str(item.get("grade", "relevant")).lower() for item in grade_list}

            graded_chunks: List[RetrievedChunk] = []
            for idx, chunk in enumerate(chunks, 1):
                grade = grade_map.get(idx, "relevant")
                chunk.grade = grade
                if grade != "irrelevant":
                    graded_chunks.append(chunk)
                else:
                    LOGGER.info("CRAG filtered out irrelevant chunk #%d (%s: %s)", idx, chunk.source_file, chunk.section_title)

            return graded_chunks
        return chunks
    except Exception as exc:
        LOGGER.debug("CRAG grading parsing skipped on error: %s", exc)
        return chunks


def retrieve_relevant_chunks(
    query: str,
    top_k: int = 5,
    min_similarity: float = 0.60,
    relaxed_fallback_k: int = 2,
    use_keyword_boost: bool = True,
    use_hyde: bool = True,
    use_crag: bool = True,
) -> RetrievalResult:
    """Retrieve and filter knowledge chunks using Hybrid Dense + BM25, HyDE, and CRAG grading."""
    if _client is None:
        LOGGER.debug("Chroma client unavailable, returning empty knowledge retrieval result")
        return RetrievalResult(chunks=[], fallback_relaxed=True)

    collection = _client.get_or_create_collection(
        name="salesai_knowledge_v2",
        embedding_function=embedding_fn
    )

    q = _boosted_query(query) if use_keyword_boost else query

    # HyDE: Generate hypothetical policy answer for dense & sparse semantic matching
    if use_hyde:
        hypo_passage = generate_hypothetical_document(query)
        dense_query = f"{q}\n{hypo_passage}" if hypo_passage else q
        sparse_query = f"{query} {hypo_passage}" if hypo_passage else query
    else:
        dense_query = q
        sparse_query = query

    result = collection.query(
        query_texts=[dense_query],
        n_results=max(top_k, 5) * 4,
        include=["documents", "metadatas", "distances"],
    )

    docs_nested = result.get("documents", [[]])
    metadatas_nested = result.get("metadatas", [[]])
    distances_nested = result.get("distances", [[]])

    docs = docs_nested[0] if docs_nested else []
    metadatas = metadatas_nested[0] if metadatas_nested else []
    distances = distances_nested[0] if distances_nested else []

    # Fuse Dense + Sparse (BM25) via Reciprocal Rank Fusion
    candidates = _fuse_dense_and_sparse(
        query=query,
        dense_docs=docs,
        dense_metadatas=metadatas,
        dense_distances=distances,
        top_k=top_k,
        sparse_query=sparse_query,
    )

    filtered = [chunk for chunk in candidates if chunk.score >= min_similarity][:top_k]

    # CRAG: Post-retrieval relevance grading with Groq
    if use_crag and filtered:
        graded = grade_retrieved_chunks(query=query, chunks=filtered)
        if graded:
            filtered = graded

    if settings.rag_debug_logging:
        emb_size, emb_preview = _query_embedding_debug_vector(dense_query)
        LOGGER.info("RAG query=%r dense_query_len=%d", query, len(dense_query))
        LOGGER.info("RAG query embedding size=%d preview=%s", emb_size, emb_preview)
        try:
            metric = (collection.metadata or {}).get("hnsw:space", "unknown")
        except Exception:
            metric = "unknown"
        LOGGER.info("RAG vector metric=%s embedding_model=%s", metric, "sentence-transformers/all-MiniLM-L6-v2")
        for idx, chunk in enumerate(candidates[:5], start=1):
            LOGGER.info(
                "RAG top5 #%d rrf=%.4f score=%.3f grade=%s source=%s topic=%s section=%s version=%s",
                idx,
                chunk.rrf_score,
                chunk.score,
                chunk.grade,
                chunk.source_file,
                chunk.topic,
                chunk.section_title,
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
    try:
        collection = ensure_user_collection()
        if collection.count() == 0:
            return []
        result = collection.query(query_texts=[query], n_results=min(k, collection.count()))

        docs_nested = result.get("documents", [[]])
        ids_nested = result.get("ids", [[]])

        docs = docs_nested[0] if docs_nested else []
        ids = ids_nested[0] if ids_nested else []

        formatted: List[str] = []
        for idx, doc in enumerate(docs):
            doc_id = ids[idx] if idx < len(ids) else f"user-doc-{idx}"
            formatted.append(f"User message ({doc_id}):\n{doc}")

        return formatted
    except Exception as exc:
        LOGGER.debug("retrieve_similar_user_messages fallback on error: %s", exc)
        return []
