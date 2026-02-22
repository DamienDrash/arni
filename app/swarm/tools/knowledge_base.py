from __future__ import annotations

from app.core.knowledge.retriever import DEFAULT_COLLECTION, HybridRetriever


def search_knowledge_base(query: str, collection_name: str = DEFAULT_COLLECTION) -> str:
    """Search the tenant knowledge base for relevant information.

    Use this to look up prices, rules, opening hours, or policy questions.

    Args:
        query: Search term or question (e.g. "Was kostet Premium?")
        collection_name: ChromaDB collection for this tenant (default: system collection)

    Returns:
        Relevant text snippets from the knowledge base, or an informative fallback.
    """
    try:
        retriever = HybridRetriever(collection_name=collection_name)
        results = retriever.search(query, top_n=3)

        if not results:
            return "Keine passenden Informationen in der Wissensbasis gefunden."

        output = []
        for res in results:
            source = res.metadata.get("source", "Wissensbasis")
            output.append(f"[{source}]\n{res.content}")

        return "\n\n".join(output)

    except Exception as exc:
        return f"Wissensbasis nicht verfügbar: {exc}"
