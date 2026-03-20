"""Retrieval helpers for fetching relevant knowledge from ChromaDB."""

from typing import List

from app.rag.chroma_store import ensure_collection


def retrieve_top_k(query: str, k: int = 2) -> List[str]:
    """Retrieve top-k relevant text chunks for a user query."""
    collection = ensure_collection()
    result = collection.query(query_texts=[query], n_results=k)
    docs = result.get("documents", [[]])
    return docs[0] if docs else []
