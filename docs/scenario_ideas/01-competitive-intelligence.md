# Scenario Idea 1: Competitive Intelligence / Market Researcher

**The Concept:**
A user asks the agent to research a competitor or a new market. The agent outputs a highly polished marketing brief, complete with a generated logo/header image, heavily grounded in real-world data from the web and internal company documents.

**Feature Mapping:**
1. **Foundation (Mod 1):** Weather/Time tools.
2. **Orchestration (Mod 2):** "Director" delegates to "Researcher Agent" and "Marketer Agent". Output keys transport context.
3. **Advanced Tooling (Mod 3):** Playwright MCP scrapes the competitor website. Vector Search hits a dummy DB of "Past Marketing Campaigns".
4. **Critique & Callbacks (Mod 4):** Critic loops with Marketer to remove jargon. Callback catches an Imagen 3 generated mood-board image.
5. **Evals & A2UI (Mod 5):** Renders the result as a dynamic intelligence dossier.
6. **Deployment (Mod 6):** Agent Engine API.

*Pros:* Highly relevant to tech/business users.
*Cons:* Mentions real-world companies, relies on synthetic corporate data (CRM, campaign notes) which isn't universally relatable.
