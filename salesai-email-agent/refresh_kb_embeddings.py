"""Manual KB embedding refresh entrypoint.

Usage:
    python refresh_kb_embeddings.py
    python refresh_kb_embeddings.py --hard-reset
"""

import argparse
import logging

from app.rag.chroma_store import ensure_collection, hard_reindex_knowledge, refresh_knowledge_embeddings


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
LOGGER = logging.getLogger(__name__)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Refresh or hard-reset KB embeddings")
    parser.add_argument(
        "--hard-reset",
        action="store_true",
        help="Delete knowledge collection and rebuild embeddings from scratch",
    )
    args = parser.parse_args()

    ensure_collection()
    if args.hard_reset:
        stats = hard_reindex_knowledge("data/knowledge")
    else:
        stats = refresh_knowledge_embeddings("data/knowledge")
    LOGGER.info(
        "Refresh complete: files=%d chunks=%d deleted=%d",
        stats.get("files", 0),
        stats.get("chunks", 0),
        stats.get("deleted", 0),
    )
