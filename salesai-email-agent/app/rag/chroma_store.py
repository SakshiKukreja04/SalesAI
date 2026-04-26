"""ChromaDB setup and document indexing utilities."""

from hashlib import sha256
import logging
import re
from pathlib import Path
from typing import Dict, List


import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction


from app.config import settings



LOGGER = logging.getLogger(__name__)
_client = chromadb.PersistentClient(path=settings.chroma_path)
_collection = None
_reply_collection = None
_user_collection = None
embedding_fn = SentenceTransformerEmbeddingFunction(model_name="sentence-transformers/all-MiniLM-L6-v2")
LOGGER.info("Using HuggingFace embedding model: sentence-transformers/all-MiniLM-L6-v2")

_REFUND_FILENAMES = {"refund", "refund_policy", "returns", "return_policy"}
_TOKEN_RE = re.compile(r"\w+|[^\w\s]", re.UNICODE)


def _estimate_tokens(text: str) -> int:
    """Rough token estimate without external tokenizer dependency."""
    return len(_TOKEN_RE.findall(text or ""))


def _split_sentences(text: str) -> List[str]:
    """Split text into sentence-like units for semantic chunking."""
    if not (text or "").strip():
        return []
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [part.strip() for part in parts if part.strip()]


def _semantic_chunk_text(text: str, min_tokens: int = 200, max_tokens: int = 500) -> List[str]:
    """Chunk policy text into semantic blocks targeting token windows."""
    stripped = (text or "").strip()
    if not stripped:
        return []

    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", stripped) if p.strip()]
    chunks: List[str] = []
    current: List[str] = []
    current_tokens = 0

    def flush_current() -> None:
        nonlocal current, current_tokens
        if current:
            chunk = "\n\n".join(current).strip()
            if chunk:
                chunks.append(chunk)
        current = []
        current_tokens = 0

    for paragraph in paragraphs:
        paragraph_tokens = _estimate_tokens(paragraph)

        # Keep very large paragraphs coherent by sentence packing.
        if paragraph_tokens > max_tokens:
            sentences = _split_sentences(paragraph)
            for sentence in sentences:
                sentence_tokens = _estimate_tokens(sentence)
                if current_tokens + sentence_tokens > max_tokens and current_tokens >= min_tokens:
                    flush_current()
                current.append(sentence)
                current_tokens += sentence_tokens
            continue

        if current_tokens + paragraph_tokens > max_tokens and current_tokens >= min_tokens:
            flush_current()

        current.append(paragraph)
        current_tokens += paragraph_tokens

    flush_current()
    return chunks


def _infer_topic(file_path: Path) -> str:
    """Infer topic metadata from the source filename."""
    stem = file_path.stem.lower()
    if stem in _REFUND_FILENAMES:
        return "refund_policy"
    if "shipping" in stem:
        return "shipping_policy"
    if "warranty" in stem:
        return "warranty_policy"
    if "support" in stem:
        return "support_policy"
    if "product" in stem:
        return "product_info"
    if "faq" in stem:
        return "faq"
    return stem.replace("-", "_")


def _document_version(file_path: Path) -> str:
    """Create deterministic version string for a knowledge file."""
    content = file_path.read_bytes()
    digest = sha256(content).hexdigest()[:12]
    return f"v_{digest}"


def _chunk_document(file_path: Path, raw_text: str) -> List[str]:
    """Apply topic-aware chunking for a knowledge document."""
    if file_path.stem.lower() in _REFUND_FILENAMES:
        # Keep refund policy in one semantic block so critical timelines stay together.
        as_one = (raw_text or "").strip()
        return [as_one] if as_one else []
    return _semantic_chunk_text(raw_text, min_tokens=200, max_tokens=500)


def _chunk_text(text: str, max_chars: int = 800, overlap: int = 120) -> List[str]:
    """Backward-compatible chunk helper retained for older callers."""
    stripped = (text or "").strip()
    if not stripped:
        return []

    chunks: List[str] = []
    start = 0
    text_len = len(stripped)
    while start < text_len:
        end = min(start + max_chars, text_len)
        chunk = stripped[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= text_len:
            break
        start = max(0, end - overlap)
    return chunks


def ensure_collection():
    """Create or get the project knowledge collection."""
    global _collection
    if _collection is None:
        _collection = _client.get_or_create_collection(
            name="salesai_knowledge_v2",
            embedding_function=embedding_fn
        )
    return _collection


def ensure_reply_collection():
    """Create or get the project reply-memory collection."""
    global _reply_collection
    if _reply_collection is None:
        _reply_collection = _client.get_or_create_collection(name=settings.chroma_reply_collection)
    return _reply_collection


def ensure_user_collection():
    """Create or get the project user-message memory collection."""
    global _user_collection
    if _user_collection is None:
        # Reuse configured reply-memory collection for conversational memory.
        _user_collection = _client.get_or_create_collection(name=settings.chroma_reply_collection)
    return _user_collection


def add_documents(documents: List[str], ids: List[str], metadatas: List[Dict[str, str]] | None = None) -> None:
    """Store text documents in ChromaDB with matching IDs and optional metadata."""
    collection = ensure_collection()
    if metadatas:
        collection.upsert(documents=documents, ids=ids, metadatas=metadatas)
    else:
        collection.upsert(documents=documents, ids=ids)


def add_reply_documents(documents: List[str], ids: List[str], metadatas: List[Dict[str, str]] | None = None) -> None:
    """Store generated reply texts in ChromaDB for reply-memory retrieval."""
    collection = ensure_reply_collection()
    if metadatas:
        collection.upsert(documents=documents, ids=ids, metadatas=metadatas)
    else:
        collection.upsert(documents=documents, ids=ids)


def add_user_documents(documents: List[str], ids: List[str], metadatas: List[Dict[str, str]] | None = None) -> None:
    """Store normalized customer message texts for user-memory retrieval."""
    collection = ensure_user_collection()
    if metadatas:
        collection.upsert(documents=documents, ids=ids, metadatas=metadatas)
    else:
        collection.upsert(documents=documents, ids=ids)


def refresh_knowledge_embeddings(folder_path: str) -> Dict[str, int]:
    """Refresh KB embeddings with versioning and stale-vector cleanup.

    For each text file:
    - compute deterministic content version
    - remove previous vectors for the same source file
    - chunk into semantic units
    - upsert new vectors with metadata needed for retrieval filtering
    LOGGER = logging.getLogger(__name__)
    _client = chromadb.PersistentClient(path=settings.chroma_path)
    _collection = None
    _reply_collection = None
    _user_collection = None
    embedding_fn = SentenceTransformerEmbeddingFunction(model_name="sentence-transformers/all-MiniLM-L6-v2")
    LOGGER.info("Using HuggingFace embedding model: sentence-transformers/all-MiniLM-L6-v2")
    """
    folder = Path(folder_path)
    if not folder.exists():
        LOGGER.warning("Knowledge folder does not exist: %s", folder_path)
        return {"files": 0, "chunks": 0, "deleted": 0}

    collection = ensure_collection()
    total_files = 0
    total_chunks = 0
    total_deleted = 0

    for file_path in sorted(folder.glob("*.txt")):
        total_files += 1
        raw_text = file_path.read_text(encoding="utf-8")
        chunks = _chunk_document(file_path=file_path, raw_text=raw_text)
        version = _document_version(file_path)
        topic = _infer_topic(file_path)

        try:
            existing = collection.get(where={"source_file": file_path.name}, include=[])
            existing_ids = existing.get("ids", []) if existing else []
            if existing_ids:
                collection.delete(ids=existing_ids)
                total_deleted += len(existing_ids)
        except Exception as exc:
            LOGGER.warning("Failed stale-vector cleanup for %s: %s", file_path.name, exc)

        if not chunks:
            LOGGER.warning("No chunks generated for %s", file_path.name)
            continue

        docs: List[str] = []
        ids: List[str] = []
        metadatas: List[Dict[str, str]] = []

        for idx, chunk in enumerate(chunks):
            docs.append(chunk)
            ids.append(f"{file_path.stem}:{version}:{idx}")
            metadatas.append(
                {
                    "source_file": file_path.name,
                    "topic": topic,
                    "version": version,
                    "active": "true",
                    "chunk_index": str(idx),
                    "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
                }
            )

        collection.upsert(documents=docs, ids=ids, metadatas=metadatas)
        total_chunks += len(docs)

        LOGGER.info(
            "Indexed %s: version=%s topic=%s chunks=%d",
            file_path.name,
            version,
            topic,
            len(docs),
        )

    return {"files": total_files, "chunks": total_chunks, "deleted": total_deleted}


def seed_knowledge_from_folder(folder_path: str) -> None:
    """Compatibility alias that now performs versioned refresh indexing."""
    refresh_knowledge_embeddings(folder_path)


def hard_reindex_knowledge(folder_path: str) -> Dict[str, int]:
    """Delete and recreate knowledge collection before reindexing from scratch."""
    global _collection
    try:
        _client.delete_collection(name=settings.chroma_collection)
    except Exception:
        # Collection may not exist on first run.
        pass

    _collection = None
    ensure_collection()
    return refresh_knowledge_embeddings(folder_path)
