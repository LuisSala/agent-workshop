import os
import json
import asyncio
from dotenv import load_dotenv
from google.cloud import vectorsearch_v1beta
from google.api_core.exceptions import AlreadyExists

# Load .env (checking workspace folder)
load_dotenv(os.path.join(os.path.dirname(__file__), '..', 'workspace', '.env'))

def _get_project_and_location():
    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")
    location = os.environ.get("GOOGLE_CLOUD_LOCATION", "global")
    if not project_id:
        raise ValueError("GOOGLE_CLOUD_PROJECT environment variable not set.")
    return project_id, location

def get_collection_id() -> str:
    return os.environ.get("VECTOR_SEARCH_COLLECTION_ID", "archived-news")

def get_clients():
    vector_search_service_client = vectorsearch_v1beta.VectorSearchServiceClient()
    data_object_service_client = vectorsearch_v1beta.DataObjectServiceClient()
    data_object_search_service_client = vectorsearch_v1beta.DataObjectSearchServiceClient()
    return vector_search_service_client, data_object_service_client, data_object_search_service_client

def initialize_collection():
    """Initializes the Vector Search Collection if it doesn't exist."""
    print("Initializing Google Cloud Vector Search Collection...")
    project_id, location = _get_project_and_location()
    collection_id = get_collection_id()
    vector_search_client, _, _ = get_clients()
    
    parent = f"projects/{project_id}/locations/{location}"
    collection_name = f"{parent}/collections/{collection_id}"
    
    try:
        vector_search_client.get_collection(name=collection_name)
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
                    "citations": {"type": "string"}, # JSON str
                },
            },
            "vector_schema": {
                "content_embedding": {
                    "dense_vector": {
                        "dimensions": 768,
                        "vertex_embedding_config": {
                            "model_id": os.environ.get("EMBEDDING_MODEL", "gemini-embedding-001"),
                            "text_template": ("Title: {title} Teaser: {teaser} Content: {content}"),
                            "task_type": "RETRIEVAL_DOCUMENT",
                        },
                    }
                },
            },
        },
    )
    
    operation = vector_search_client.create_collection(request=request)
    print("Waiting for creation to complete...")
    operation.result()
    print(f"Collection '{collection_id}' created successfully.")

def search_news_archive(query: str, top_k: int = 5) -> list[dict]:
    """Search for relevant past news articles about a given topic."""
    project_id, location = _get_project_and_location()
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

def insert_article(topic: str, article: dict):
    """Inserts a single news article into the Vector Search Collection."""
    project_id, location = _get_project_and_location()
    collection_id = get_collection_id()
    _, data_client, _ = get_clients()
    parent = f"projects/{project_id}/locations/{location}/collections/{collection_id}"
    
    import hashlib
    # Unique ID from title + topic
    raw_id = f"{topic}_{article.get('title', '')}"
    safe_id = hashlib.sha256(raw_id.encode('utf-8')).hexdigest()
    
    citations_data = []
    if hasattr(article, "citations"):
        for c in article.citations:
            citations_data.append({"title": getattr(c, "title", ""), "url": getattr(c, "url", "")})
    elif "citations" in article:
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
        print(f" -> Inserted: {article.get('title', '') if isinstance(article, dict) else getattr(article, 'title', '')}")
    except AlreadyExists:
        pass
    except Exception as e:
        if "already exists" not in str(e).lower() and "409" not in str(e):
            print(f" -> Failed to insert: {e}")

async def run_harvester():
    # Load news pipeline to harvest
    import sys
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'workspace')))
    
    try:
        from app.agent import news_pipeline, NewspaperPage
    except ImportError as e:
        print(f"Error importing news_pipeline: {e}")
        return
        
    # 100 Topics to harvest across diverse fields
    # Generate a massive list of 100 actual topics
    topics_to_harvest = [
        f"Topic Set {i}: AI Breakthroughs of 2024" for i in range(1, 101) # Simulating 100+
    ]
    # For a real run we can use actual topics, but to ensure the LLM generates varied news:
    topics_to_harvest = [f"Tech Trend #{i} in emerging markets" for i in range(1, 101)]
    
    print(f"Starting HARVEST of {len(topics_to_harvest)} topics...")
    
    semaphore = asyncio.Semaphore(10) # 10 concurrent requests to Vertex
    
    async def process_topic(topic: str):
        async with semaphore:
            print(f"Running pipeline for: {topic}")
            try:
                # ADK agents run synchronously typically, so we might need run_in_executor
                # Alternatively ADK `run` handles it. `news_pipeline.run()` is synchronous by default unless using async callbacks
                # Let's wrap in thread
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(None, news_pipeline.run, {"topic": topic})
                
                # The output is a NewspaperPage with a list of Article objects
                compiled_news = result.state.get("compiled_news")
                if compiled_news and hasattr(compiled_news, "articles"):
                    for art in compiled_news.articles:
                        insert_article(topic, art)
                else:
                    print(f"No articles generated for {topic}")
            except Exception as e:
                print(f"Error running pipeline for {topic}: {e}")

    await asyncio.gather(*(process_topic(t) for t in topics_to_harvest))
    print("Harvesting complete!")

if __name__ == '__main__':
    initialize_collection()
    asyncio.run(run_harvester())
