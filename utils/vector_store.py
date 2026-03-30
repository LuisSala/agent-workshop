import os
import json
import hashlib
from dotenv import load_dotenv, find_dotenv
from google.cloud import vectorsearch_v1beta
from google.api_core.exceptions import AlreadyExists

# Ensure root .env is loaded automatically whenever this module is imported
load_dotenv(find_dotenv())

def get_project_and_location():
    # Attempt to pull PROJECT_ID from .env, fallback to GOOGLE_CLOUD_PROJECT
    project_id = os.environ.get("PROJECT_ID", os.environ.get("GOOGLE_CLOUD_PROJECT"))
    # Always use LOCATION for Vector Search to decouple from global LLM routing
    location = os.environ.get("LOCATION", "us-central1")
    if not project_id:
        raise ValueError("Missing GCP Project Configuration. Check your .env file.")
    return project_id, location

def get_collection_id() -> str:
    return os.environ.get("VECTOR_SEARCH_COLLECTION_ID", "news_articles")

_CLIENTS = None

def get_clients():
    global _CLIENTS
    if _CLIENTS is None:
        vector_search_service_client = vectorsearch_v1beta.VectorSearchServiceClient()
        data_object_service_client = vectorsearch_v1beta.DataObjectServiceClient()
        data_object_search_service_client = vectorsearch_v1beta.DataObjectSearchServiceClient()
        _CLIENTS = (vector_search_service_client, data_object_service_client, data_object_search_service_client)
    return _CLIENTS

def list_collections():
    project_id, location = get_project_and_location()
    parent = f"projects/{project_id}/locations/{location}"
    client, _, _ = get_clients()
    try:
        req = vectorsearch_v1beta.ListCollectionsRequest(parent=parent)
        return list(client.list_collections(request=req))
    except Exception as e:
        print(f"Error listing collections: {e}")
        return []

def list_objects(page_size=10):
    project_id, location = get_project_and_location()
    collection_id = get_collection_id()
    parent = f"projects/{project_id}/locations/{location}/collections/{collection_id}"
    _, data_client, _ = get_clients()
    try:
        req = vectorsearch_v1beta.ListDataObjectsRequest(parent=parent, page_size=page_size)
        return list(data_client.list_data_objects(request=req))
    except Exception as e:
        print(f"Error listing objects: {e}")
        return []

def delete_object(data_object_id: str):
    project_id, location = get_project_and_location()
    collection_id = get_collection_id()
    name = f"projects/{project_id}/locations/{location}/collections/{collection_id}/dataObjects/{data_object_id}"
    _, data_client, _ = get_clients()
    req = vectorsearch_v1beta.DeleteDataObjectRequest(name=name)
    data_client.delete_data_object(request=req)

def initialize_collection(collection_id=None):
    if not collection_id:
        collection_id = get_collection_id()
        
    print("Initializing Google Cloud Vector Search Collection...")
    project_id, location = get_project_and_location()
    client, _, _ = get_clients()
    
    parent = f"projects/{project_id}/locations/{location}"
    collection_name = f"{parent}/collections/{collection_id}"
    
    try:
        client.get_collection(name=collection_name)
        print(f"Collection '{collection_id}' already exists.")
        return
    except Exception as e:
        if "404" not in str(e) and "NOT_FOUND" not in str(e):
            print(f"Error checking collection: {e}")
            pass
    
    print(f"Creating Collection: '{collection_id}'...")
    request = vectorsearch_v1beta.CreateCollectionRequest(
        parent=parent,
        collection_id=collection_id,
        collection={
            "data_schema": {
                "type": "object",
                "properties": {
                    "source_topic": {"type": "string"},
                    "title": {"type": "string"},
                    "teaser": {"type": "string"},
                    "content": {"type": "string"},
                    "citations": {"type": "string"},
                },
            },
            "vector_schema": {
                "content_embedding": {
                    "dense_vector": {
                        "dimensions": 768,
                        "vertex_embedding_config": {
                            "model_id": os.environ.get("EMBEDDING_MODEL", "text-embedding-004"),
                            "text_template": ("Title: {title} Teaser: {teaser} Content: {content}"),
                            "task_type": "RETRIEVAL_DOCUMENT",
                        },
                    }
                },
            },
        },
    )
    
    operation = client.create_collection(request=request)
    print("Waiting for creation to complete...")
    operation.result()
    print(f"Collection '{collection_id}' created successfully.")

def insert_article(topic: str, article: dict):
    """Inserts a single news article into the Vector Search Collection."""
    project_id, location = get_project_and_location()
    collection_id = get_collection_id()
    _, data_client, _ = get_clients()
    parent = f"projects/{project_id}/locations/{location}/collections/{collection_id}"
    
    raw_id = f"{topic}_{article.get('title', '')}" if isinstance(article, dict) else f"{topic}_{getattr(article, 'title', '')}"
    safe_id = hashlib.sha256(raw_id.encode('utf-8')).hexdigest()
    
    citations_data = []
    if hasattr(article, "citations"):
        for c in article.citations:
            citations_data.append({"title": getattr(c, "title", ""), "url": getattr(c, "url", "")})
    elif isinstance(article, dict) and "citations" in article:
        citations_data = article["citations"]
        
    request = vectorsearch_v1beta.CreateDataObjectRequest(
        parent=parent,
        data_object_id=safe_id,
        data_object={
            "data": {
                "source_topic": topic,
                "title": article.get("title", "") if isinstance(article, dict) else getattr(article, "title", ""),
                "teaser": article.get("teaser", "") if isinstance(article, dict) else getattr(article, "teaser", ""),
                "content": str(article.get("content", "") if isinstance(article, dict) else getattr(article, "content", ""))[-32000:],
                "citations": json.dumps(citations_data),
            },
            "vectors": {},  # Trigger auto-embed
        },
    )
    try:
        data_client.create_data_object(request=request)
        print(f" -> Inserted into Vector Search: {article.get('title', '') if isinstance(article, dict) else getattr(article, 'title', '')}")
    except AlreadyExists:
        pass
    except Exception as e:
        if "already exists" not in str(e).lower() and "409" not in str(e):
            print(f" -> Failed to insert: {e}")

def search_archive(query: str, top_k: int = 5) -> list[dict]:
    """Search for relevant past news articles about a given topic."""
    project_id, location = get_project_and_location()
    collection_id = get_collection_id()
    _, _, data_search_client = get_clients()
    parent = f"projects/{project_id}/locations/{location}/collections/{collection_id}"
    
    batch_search_request = vectorsearch_v1beta.BatchSearchDataObjectsRequest(
        parent=parent,
        searches=[
            vectorsearch_v1beta.Search(
                semantic_search=vectorsearch_v1beta.SemanticSearch(
                    search_text=query,
                    search_field="content_embedding",
                    task_type="QUESTION_ANSWERING",
                    top_k=top_k,
                    output_fields=vectorsearch_v1beta.OutputFields(data_fields=["*"]),
                )
            ),
            vectorsearch_v1beta.Search(
                text_search=vectorsearch_v1beta.TextSearch(
                    search_text=query,
                    data_field_names=["title", "teaser", "content"],
                    top_k=top_k,
                    output_fields=vectorsearch_v1beta.OutputFields(data_fields=["*"]),
                )
            ),
        ],
        combine=vectorsearch_v1beta.BatchSearchDataObjectsRequest.CombineResultsOptions(
            ranker=vectorsearch_v1beta.Ranker(
                rrf=vectorsearch_v1beta.ReciprocalRankFusion(weights=[1.0, 1.0])
            )
        ),
    )
    
    try:
        batch_results = data_search_client.batch_search_data_objects(batch_search_request)
        results = []
        if batch_results.results:
            combined_results = batch_results.results[0]
            for result in combined_results.results:
                data = result.data_object.data
                results.append({
                    "topic": data.get("source_topic", ""),
                    "title": data.get("title", ""),
                    "teaser": data.get("teaser", ""),
                    "content": data.get("content", ""),
                    "citations": json.loads(data.get("citations", "[]")),
                })
        return results
    except Exception as e:
        print(f"Archive search failed: {e}")
        return []
