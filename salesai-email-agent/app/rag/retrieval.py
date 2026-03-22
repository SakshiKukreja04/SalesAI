"""Retrieval helpers for fetching relevant knowledge from ChromaDB."""

from typing import List

from app.rag.chroma_store import ensure_collection, ensure_user_collection


def retrieve_top_k(query: str, k: int = 2) -> List[str]:
    """Retrieve top-k relevant text chunks for a user query."""
    collection = ensure_collection()
    result = collection.query(query_texts=[query], n_results=k)

    docs_nested = result.get("documents", [[]])
    ids_nested = result.get("ids", [[]])
    metadatas_nested = result.get("metadatas", [[]])

    docs = docs_nested[0] if docs_nested else []
    ids = ids_nested[0] if ids_nested else []
    metadatas = metadatas_nested[0] if metadatas_nested else []

    formatted: List[str] = []
    for idx, doc in enumerate(docs):
        doc_id = ids[idx] if idx < len(ids) else f"doc-{idx}"
        metadata = metadatas[idx] if idx < len(metadatas) and metadatas[idx] else {}
        source = metadata.get("source", doc_id)
        formatted.append(f"Source: {source}\n{doc}")

    return formatted


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
