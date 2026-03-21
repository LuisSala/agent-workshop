# Scenario Idea 2: The Executive Assistant / Chief of Staff

**The Concept:**
The user asks the agent: "Prepare me for my 10am meeting with Acme Corp." The agent deeply researches Acme Corp externally, cross-references internal notes, synthesizes a "Morning Briefing" dossier, critiques its own work, and generates a visual asset for the meeting.

**Feature Mapping:**
1. **Foundation (Mod 1):** Weather/Time tools for the daily briefing context.
2. **Orchestration (Mod 2):** "Chief of Staff" delegates to "External Researcher" and "Internal Archivist", combining their outputs.
3. **Advanced Tooling (Mod 3):** Playwright MCP scrapes recent news on the client. Vector Search hits a dummy "CRM" or "Past Meeting Notes" DB.
4. **Critique & Callbacks (Mod 4):** Critic loops to ensure the briefing has actionable next steps. Callback generates a custom "Icebreaker" slide image based on news.
5. **Evals & A2UI (Mod 5):** Rendered as a polished morning dashboard.
6. **Deployment (Mod 6):** Agent Engine via Cloud Run.

*Pros:* Universally desired persona, feels very powerful.
*Cons:* Requires building realistic synthetic CRM/meeting notes data to make the Vector Search step feel authentic. PII/real-world client friction.
