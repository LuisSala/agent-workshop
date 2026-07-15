import os
import json
import asyncio
import argparse
from dotenv import load_dotenv

import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from utils.vector_store import initialize_collection, insert_article

async def run_harvester(do_harvest: bool, do_ingest: bool):
    corpus_path = os.path.join(os.path.dirname(__file__), "corpus.jsonl")
    processed_file = os.path.join(os.path.dirname(__file__), "processed_topics.txt")

    if do_harvest:
        try:
            from workspace.app.agent import news_workflow, NewspaperPage
        except ImportError as e:
            print(f"Error importing news_workflow: {e}")
            return
            
        topics_to_harvest = [f"Tech Trend #{i} in emerging markets" for i in range(1, 101)]
        
        processed_topics = set()
        if os.path.exists(processed_file):
            with open(processed_file, "r") as f:
                processed_topics = set(line.strip() for line in f if line.strip())

        remaining_topics = [t for t in topics_to_harvest if t not in processed_topics]
        
        if not remaining_topics:
            print("All topics have already been processed for harvesting.")
        else:
            print(f"Starting HARVEST of {len(remaining_topics)} remaining topics...")
            
            semaphore = asyncio.Semaphore(10)
            file_lock = asyncio.Lock()
            
            async def process_topic(topic: str):
                async with semaphore:
                    print(f"Running pipeline for: {topic}")
                    try:
                        from google.adk.runners import Runner
                        from google.adk.sessions import InMemorySessionService
                        from google.genai import types

                        session_svc = InMemorySessionService()
                        runner = Runner(agent=news_workflow, app_name="harvest", session_service=session_svc)
                        
                        session_id = f"harvest-{hash(topic)}"
                        await session_svc.create_session(app_name="harvest", user_id="harvester", session_id=session_id)
                        msg = types.Content(role="user", parts=[types.Part(text=f"Research topic: {topic}")])
                        
                        async for event in runner.run_async(new_message=msg, user_id="harvester", session_id=session_id):
                            pass
                        
                        session_data = await session_svc.get_session("harvest", "harvester", session_id)
                        compiled_news = session_data.state.get("compiled_news")

                        if compiled_news and hasattr(compiled_news, "articles"):
                            new_articles = []
                            for art in compiled_news.articles:
                                art_dict = {
                                    "source_topic": topic,
                                    "title": getattr(art, "title", ""),
                                    "teaser": getattr(art, "teaser", ""),
                                    "content": getattr(art, "content", ""),
                                    "citations": []
                                }
                                if hasattr(art, "citations") and art.citations:
                                    art_dict["citations"] = [
                                        {"title": getattr(c, "title", ""), "url": getattr(c, "url", "")} 
                                        for c in art.citations
                                    ]
                                new_articles.append(art_dict)
                                
                            async with file_lock:
                                with open(corpus_path, "a", encoding="utf-8") as f:
                                    for a in new_articles:
                                        f.write(json.dumps(a) + "\n")
                                with open(processed_file, "a") as f:
                                    f.write(topic + "\n")
                        else:
                            print(f"No articles generated for {topic}")
                                
                    except Exception as e:
                        print(f"Error running pipeline for {topic}: {e}")

            await asyncio.gather(*(process_topic(t) for t in remaining_topics))
            print("Harvesting complete!")

    if do_ingest:
        if not os.path.exists(corpus_path):
            print(f"Error: {corpus_path} not found. Nothing to ingest.")
            return
            
        print(f"Reading corpus from {corpus_path} for ingestion...")
        
        articles_to_insert = []
        with open(corpus_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    article_data = json.loads(line)
                    articles_to_insert.append(article_data)
                except Exception as e:
                    print(f"Error parsing line: {e}")
                    
        if not articles_to_insert:
            print("No articles found in corpus.jsonl.")
            return
            
        print(f"Starting Ingestion of {len(articles_to_insert)} articles to Vector Search...")
        semaphore = asyncio.Semaphore(5)
        
        async def process_article(article):
            async with semaphore:
                topic = article.get("source_topic", article.get("topic", "corpus_ingest"))
                try:
                    await asyncio.to_thread(insert_article, topic, article)
                except Exception as e:
                    print(f"Error inserting article '{article.get('title')}': {e}")
                    
        tasks = [process_article(article) for article in articles_to_insert]
        await asyncio.gather(*tasks)
            
        print("Ingestion complete!")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="News Harvester and Ingester")
    parser.add_argument("--harvest", action="store_true", help="Harvest news and append to corpus")
    parser.add_argument("--ingest", action="store_true", help="Ingest corpus into Vector Search")
    args = parser.parse_args()
    
    if not args.harvest and not args.ingest:
        print("No operation specified. Defaulting to --harvest and --ingest")
        do_harvest = True
        do_ingest = True
    else:
        do_harvest = args.harvest
        do_ingest = args.ingest

    initialize_collection()
    asyncio.run(run_harvester(do_harvest, do_ingest))
