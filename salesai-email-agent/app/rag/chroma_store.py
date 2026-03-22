"""ChromaDB setup and document indexing utilities."""

from pathlib import Path
from typing import Dict, List

import chromadb

from app.config import settings


_client = chromadb.PersistentClient(path=settings.chroma_path)
_collection = None
_reply_collection = None
_user_collection = None


def _chunk_text(text: str, max_chars: int = 800, overlap: int = 120) -> List[str]:
    """Split long policy text into overlapping chunks for better retrieval."""
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
        _collection = _client.get_or_create_collection(name=settings.chroma_collection)
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


def seed_knowledge_from_folder(folder_path: str) -> None:
    """Load .txt files from a folder into the Chroma collection."""
    folder = Path(folder_path)
    if not folder.exists():
        return

    docs: List[str] = []
    ids: List[str] = []
    metadatas: List[Dict[str, str]] = []

    for file_path in folder.glob("*.txt"):
        raw_text = file_path.read_text(encoding="utf-8")
        chunks = _chunk_text(raw_text)
        for idx, chunk in enumerate(chunks):
            docs.append(chunk)
            ids.append(f"{file_path.stem}-{idx}")
            metadatas.append({"source": file_path.name, "chunk": str(idx)})

    if docs:
        add_documents(documents=docs, ids=ids, metadatas=metadatas)
