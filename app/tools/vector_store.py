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

def search_similar(issue):
    if not _vector_store_enabled():
        return []

    embedding = _get_model().encode(issue).tolist()
    results = _get_collection().query(
        query_embeddings=[embedding],
        n_results=2
    )
    return results["documents"]
