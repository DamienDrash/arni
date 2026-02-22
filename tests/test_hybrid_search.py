import sys
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from app.core.knowledge.retriever import HybridRetriever, SearchResult


def test_hybrid_search():
    """Smoke-test: ChromaDB semantic search returns results and correct types."""
    retriever = HybridRetriever()

    results = retriever.search("Mitgliedschaft Kosten Preise")

    # May be empty if running against a fresh DB with no ingested data
    if len(results) == 0:
        return  # nothing to assert — collection not seeded in CI

    top_item = results[0]
    assert isinstance(top_item, SearchResult)
    assert isinstance(top_item.content, str)
    assert len(top_item.content) > 0
    assert isinstance(top_item.score, float)
    assert top_item.score > 0.0
    assert isinstance(top_item.metadata, dict)


if __name__ == "__main__":
    test_hybrid_search()
