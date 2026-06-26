import os

_client = None
_collection = None
_model = None


def _vector_store_enabled() -> bool:
    return os.getenv("KUBEOPS_ENABLE_VECTOR_STORE", "true").lower() == "true"


def _get_model():
    global _model

    if _model is None:
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer("all-MiniLM-L6-v2")

    return _model


def _get_collection():
    global _client, _collection

    if _collection is None:
        import chromadb

        _client = chromadb.Client()
        _collection = _client.get_or_create_collection("k8s-issues")

    return _collection

def store_issue(issue, solution):
    if not _vector_store_enabled():
        return

    embedding = _get_model().encode(issue).tolist()
    _get_collection().add(
        embeddings=[embedding],
        documents=[solution],
        ids=[issue]
    )

def search_similar(issue, n_results=5):
    """Retrieve the *n_results* most similar past incidents from ChromaDB.

    Returns raw document lists from ChromaDB.  Use ``format_similar_incidents``
    to convert the output into a human-readable block suitable for LLM prompts.
    """
    if not _vector_store_enabled():
        return []

    embedding = _get_model().encode(issue).tolist()
    results = _get_collection().query(
        query_embeddings=[embedding],
        n_results=n_results,
    )
    return results["documents"]


def format_similar_incidents(raw_documents) -> str:
    """Convert raw ChromaDB query results into a structured text block.

    Args:
        raw_documents: The ``documents`` list returned by ``search_similar()``.
                       Typically a list-of-lists: ``[["doc1", "doc2", ...]]``.

    Returns:
        A numbered, human-readable string ready for injection into an LLM
        prompt.  Returns a placeholder if no past incidents exist.
    """
    if not raw_documents:
        return "(No similar past incidents found in memory.)"

    # ChromaDB returns documents as a list-of-lists; flatten.
    flat: list[str] = []
    for group in raw_documents:
        if isinstance(group, list):
            flat.extend(group)
        elif isinstance(group, str):
            flat.append(group)

    if not flat:
        return "(No similar past incidents found in memory.)"

    lines = []
    for idx, doc in enumerate(flat, 1):
        snippet = doc.strip()
        if snippet:
            lines.append(f"  Incident #{idx}: {snippet}")

    return "\n".join(lines) if lines else "(No similar past incidents found in memory.)"
