"""Citation extraction utilities for the AI Newsroom workshop.

Used by Modules 03 (advanced orchestration) and 04 (vector search) to pull
verified URLs from Google Search grounding metadata that ADK attaches to
LLM response events when the `google_search` tool runs.

Why this lives in utils/ — same reason as `vector_store.py`: the workshop
modules focus on agent-orchestration concepts; helper code that is mechanical
(walking event streams, formatting drafts) is better kept out of the agent
file so students see the pipeline, not the plumbing.

References:
- ADK 2.0 Workflow + grounding:
    .agents/skills/google-agents-cli-adk-code/references/adk-2.0.md
- Original 1.x callback pattern (mod 03/04 history):
    modules/03-advanced-orchestration/README.md
- Grounding internals (ADK source): the `google_search` tool emits grounding
  via LLM response events; in 2.0 these events are authored by the *workflow*
  (not per-agent), which is why this helper takes a slice of session.events
  rather than filtering by `event.author == agent_name` like 1.x did.

Limitation worth knowing: in a `Workflow` with parallel `ctx.run_node`
researchers, all parallel tasks share one `session.events` stream and start
at the same event index. Each researcher's slice ends when *that* researcher
returns, so later-completing researchers see grounding chunks from peers that
finished earlier. The cleanest workshop framing: treat the union of citations
collected in the orchestrator as a "verified URL pool" and let the compiler
attribute them by content. Per-researcher attribution under parallel
execution requires either sequential research or a per-run callback hook
(out of scope for the workshop).
"""

from __future__ import annotations

from typing import Any


def extract_citations_from_events(
    events: list[Any],
) -> tuple[list[dict], str | None]:
    """Walk a slice of session events and pull verified citation URLs.

    Returns:
        (citations, search_entry_point_html)
        - citations: list of {"title": str, "url": str} dicts, deduped by URL
        - search_entry_point_html: the rendered HTML for Google Search's
          required attribution chip, if present in any event's grounding
          metadata. Per Google's TOS, this HTML must be displayed alongside
          any content grounded by Google Search results.

    Args:
        events: a slice of `ctx.session.events` (or `session.events` in 1.x).
            The function only reads `event.grounding_metadata.grounding_chunks`
            and `event.grounding_metadata.search_entry_point.rendered_content`,
            tolerating events that have neither.
    """
    citations: list[dict] = []
    seen_urls: set[str] = set()
    rendered_html: str | None = None

    for event in events:
        grounding = getattr(event, "grounding_metadata", None)
        if not grounding:
            continue

        chunks = getattr(grounding, "grounding_chunks", None)
        if chunks:
            for chunk in chunks:
                web = getattr(chunk, "web", None)
                uri = getattr(web, "uri", None) if web else None
                if uri and uri not in seen_urls:
                    seen_urls.add(uri)
                    citations.append({
                        "title": getattr(web, "title", "No Title"),
                        "url": uri,
                    })

        sep = getattr(grounding, "search_entry_point", None)
        if sep:
            rendered_html = getattr(sep, "rendered_content", None) or rendered_html

    return citations, rendered_html
