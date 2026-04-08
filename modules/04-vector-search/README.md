# Module 04: Vector Search & Structured UI Integration

In this module, we will explore integrating Vertex AI Vector Search capabilities into our Agents, allowing them to instantly retrieve historical data from our archival database. We will also harden our previous multi-agent orchestration to map raw unstructured database findings directly into strict, frontend-ready UI structures.

We've intentionally included **all** cumulative code additions from Module 03 (including the robust regex URL JSON parsing for our `ParallelResearcherFactory`) so you have a single source of truth for your agent's state.

## Your Objectives

### 1. Refine the Unstructured "Planning" Hop
To prevent Pydantic parsing errors when models output conversational filler before their JSON arrays (e.g. `Here are your topics: [...]`), we drop strict extraction and manually sanitize the output via regex.  

**Update your `ParallelResearcherFactory` definition in `workspace/app/agent.py`:**
```python
class ParallelResearcherFactory(BaseAgent):
    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        plan_raw = ctx.session.state.get("topic_plan")
        if not plan_raw:
            return

        import json
        import re
        try:
            # Strip potential markdown formatting
            plan_str = plan_raw.strip().strip("```json").strip("```").strip()
            # Use regex to find the first array structure in case the LLM added conversational filler
            match = re.search(r'\[.*\]', plan_str, flags=re.DOTALL)
            if match:
                plan_str = match.group(0)
            topics = json.loads(plan_str)
        except json.JSONDecodeError:
            print(f"Failed to parse topics from planner output: {plan_raw}")
            return

        researchers = [
            create_research_agent(topic, i) for i, topic in enumerate(topics)
        ]

        parallel_runner = ParallelAgent(
            name="parallel_research_executor", sub_agents=researchers
        )

        async for event in parallel_runner.run_async(ctx):
            yield event
```

### 2. Build the Vector Search Tool
You will now implement the `search_news_archive` tool. This tool allows an agent to perform similarity searches against an embedded corpus of historical news records using the Vertex Vector Store.

**Add the following tool definition to `workspace/app/agent.py`:**
```python
def search_news_archive(query: str, top_k: int = 5) -> str:
    """
    Search for existing, previously generated or accumulated news articles.
    Provides historical context on topics that have already been covered.
    """
    import sys, os

    sys.path.append(
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    )
    from utils.vector_store import search_archive

    results = search_archive(query, top_k)
    if not results:
        return "No archived articles found."

    output = ""
    for data in results:
        output += f"Title: {data.get('title')}\nTeaser: {data.get('teaser')}\nContent: {data.get('content')}\n---\n"
    return output
```

### 3. Create the Structured Archive Reader Agent
Out-of-the-box, an archive reader would dump unstructured text. You will override its system instructions and apply the `NewspaperPage` Pydantic `output_schema` to force the librarian agent to synthesize its raw database findings into formal `Article` objects. This guarantees that historical queries instantly render as beautiful, interactive cards on the Web UI!

**Define the agent in `workspace/app/agent.py` (ensure you instantiate this above `root_agent`):**
```python
archive_reader_agent = Agent(
    name="archive_reader_agent",
    model=pro_model,  # Using the pro-model for robust schema adherence
    instruction=f"""
    The current date and time is: {get_current_server_time()}
    You are an archival librarian answering questions using past editions of the newspaper.
    Always search the archive using `search_news_archive`.
    You must output your findings formatted strictly as a NewspaperPage containing multiple Article objects.
    Each article should have a title, an engaging teaser, and the full content body formatted in Markdown. 
    Use the findings from the archive to construct these articles. Ensure the 'citations' array is left empty since this is an archive compilation.
    """,
    tools=[search_news_archive],
    output_schema=NewspaperPage,
    output_key="compiled_news",
)
```

### 4. Connect the Archive Agent to the Root Pipeline
Finally, update your `root_agent` so it knows *when* to trigger the archival flow versus the live news gathering flow. 

**Update `root_agent`:**
```python
root_agent = Agent(
    name="root_agent",
    model=worker_model,
    instruction="""
    You are a helpful, conversational AI. 
    - If the user explicitly asks about past, historical, or previously covered topics, delegate to `archive_reader_agent`.
    - If the user asks you to look up fresh or current news, delegate to `news_pipeline`.
    - Otherwise, answer the user's query directly.
    """,
    sub_agents=[news_pipeline, archive_reader_agent],
)
```

**Test it out!** Run the web UI with `make run-webapp` and use the brand new "Search Archives" button at the top right of the dashboard to trigger a vector search payload that beautifully maps to our custom frontend components!

---

## 🆘 Getting Stuck?

If you fall behind or your code isn't working, you can instantly catch up to the beginning of the **next module** by running:

```bash
make catchup module=05
```
*(Note: This will completely overwrite your current `workspace/` with the known good baseline for the next module!)*
