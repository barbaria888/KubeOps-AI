import chromadb
from sentence_transformers import SentenceTransformer

client = chromadb.Client()
collection = client.get_or_create_collection("k8s-issues")

model = SentenceTransformer("all-MiniLM-L6-v2")

def store_issue(issue, solution):
    embedding = model.encode(issue).tolist()
    collection.add(
        embeddings=[embedding],
        documents=[solution],
        ids=[issue]
    )

def search_similar(issue):
    embedding = model.encode(issue).tolist()
    results = collection.query(
        query_embeddings=[embedding],
        n_results=2
    )
    return results["documents"]
