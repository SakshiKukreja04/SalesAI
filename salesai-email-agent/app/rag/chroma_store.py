"""ChromaDB setup and document indexing utilities."""

from pathlib import Path
from typing import List

import chromadb

from app.config import settings


_client = chromadb.PersistentClient(path=settings.chroma_path)
_collection = None


def ensure_collection():
    """Create or get the project knowledge collection."""
    global _collection
    if _collection is None:
        _collection = _client.get_or_create_collection(name=settings.chroma_collection)
    return _collection


def add_documents(documents: List[str], ids: List[str]) -> None:
    """Store text documents in ChromaDB with matching IDs."""
    collection = ensure_collection()
    collection.upsert(documents=documents, ids=ids)


def seed_knowledge_from_folder(folder_path: str) -> None:
    """Load .txt files from a folder into the Chroma collection."""
    folder = Path(folder_path)
    if not folder.exists():
        return

    docs: List[str] = []
    ids: List[str] = []

    for file_path in folder.glob("*.txt"):
        docs.append(file_path.read_text(encoding="utf-8"))
        ids.append(file_path.stem)

    if docs:
        add_documents(documents=docs, ids=ids)
