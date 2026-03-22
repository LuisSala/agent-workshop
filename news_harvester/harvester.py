import os
import sys
import json
import asyncio
import uuid
from datetime import datetime
import google.auth

import aiohttp
import importlib

# Setup credentials mimicking webapp
_, project_id = google.auth.default()
os.environ["GOOGLE_CLOUD_PROJECT"] = project_id
os.environ["GOOGLE_CLOUD_LOCATION"] = "global"

# Import agent directly from the verified module 03 snapshot
snapshot_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'modules', '03-advanced-orchestration', 'solution'))
sys.path.append(snapshot_path)
agent_module = importlib.import_module("app.agent")
root_agent = agent_module.root_agent

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

async def process_topic(runner: Runner, session_service: InMemorySessionService, topic: str, file_mode: str = "a"):
    session_id = str(uuid.uuid4())
    print(f"\n[HARVESTER] Dispatching agent for topic: '{topic}' (Session: {session_id})")
    
    await session_service.create_session(
        app_name=runner.app_name, 
        user_id="harvester_bot", 
        session_id=session_id
    )
    
    msg = types.Content(role="user", parts=[types.Part(text=f"Find the best news regarding {topic}")])
    
    # We drain the async generator to force completion
    async for _ in runner.run_async(user_id="harvester_bot", session_id=session_id, new_message=msg):
        pass # Ignore printing the live stream to stdout to keep it clean

    # Retrieve final structured output
    session = await session_service.get_session(
        app_name=runner.app_name, 
        user_id="harvester_bot", 
        session_id=session_id
    )
    
    compiled = session.state.get("compiled_news", {})
    if hasattr(compiled, "model_dump"):
        compiled_data = compiled.model_dump()
    elif hasattr(compiled, "dict"):
        compiled_data = compiled.dict()
    else:
        compiled_data = compiled
        
    articles = compiled_data.get("articles", [])
    
    # De-reference Vertex AI redirects
    async with aiohttp.ClientSession() as http_session:
        for article in articles:
            if "citations" in article and article["citations"]:
                for cit in article["citations"]:
                    try:
                        async with http_session.get(cit["url"], allow_redirects=True, timeout=5) as resp:
                            cit["url"] = str(resp.url)
                    except Exception:
                        pass # Retain original URL if resolution fails or times out
                        
    print(f"[HARVESTER] Success! Extracted {len(articles)} articles for topic '{topic}'")
    
    # Append to JSONL with date
    run_date = datetime.now().isoformat()
    corpus_file = os.path.join(os.path.dirname(__file__), "corpus.jsonl")
    with open(corpus_file, file_mode) as f:
        for article in articles:
            # Inject metadata
            article["crawl_date"] = run_date
            f.write(json.dumps(article) + "\n")

async def main():
    topics_file = os.path.join(os.path.dirname(__file__), "topics.txt")
    with open(topics_file, "r") as f:
        topics = [t.strip() for t in f.readlines() if t.strip()]
    
    print(f"Loaded {len(topics)} topics from {topics_file}.")
    
    processed_file = os.path.join(os.path.dirname(__file__), "processed_topics.txt")
    processed_topics = set()
    if os.path.exists(processed_file):
        with open(processed_file, "r") as f:
            processed_topics = set([t.strip() for t in f.readlines() if t.strip()])
            
    print(f"Found {len(processed_topics)} previously processed topics.")

    session_service = InMemorySessionService()
    runner = Runner(app_name="data_harvester", agent=root_agent, session_service=session_service)

    for topic in topics:
        if topic in processed_topics:
            print(f"Skipping '{topic}' (already processed).")
            continue
            
        try:
            await process_topic(runner, session_service, topic, file_mode="a")
            # Mark processed
            with open(processed_file, "a") as f:
                f.write(topic + "\n")
        except Exception as e:
            print(f"[ERROR] Failed to process topic '{topic}': {e}")

if __name__ == "__main__":
    asyncio.run(main())
