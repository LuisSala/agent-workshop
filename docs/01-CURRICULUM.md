# Production AI Agents: A hands-on Workshop

## Course Overview
This workshop is designed to take developers from zero to a deployed, production-ready AI agent on Google Cloud. We will leverage Google's Agent Starter Pack and the Agent Development Kit (ADK) to build the core logic, ground the agent using Vertex AI Vector Search 2.0, and manage orchestration via Vertex AI Agent Engine.

**Objectives:**
* Understand the Google AI Agent ecosystem (Agent Starter Pack vs. ADK).
* Build and prompt a base agent with custom tools.
* Implement RAG by connecting your agent to Vector Search 2.0.
* Orchestrate and manage agent state using Agent Engine.
* Evaluate, refine, and deploy the agent for production use.

## Module 1: The Agent Ecosystem & Setup
* **Concepts:** What is an AI Agent? Core components (Model, Memory, Tools, Orchestration).
* **Tooling:** Overview of Google's Agent Starter Pack and the Agent Development Kit (ADK).
* **Hands-on:**
  * Environment setup and authentication.
  * Running the base starter pack.

## Module 2: Building the Foundation (Agent Development Kit)
* **Concepts:** Designing the agent persona, defining system instructions, and tool schemas.
* **Hands-on:**
  * Initializing an agent using the ADK.
  * Writing custom Python functions and exposing them as tools.
  * Testing basic tool-calling capabilities (e.g., getting local data or calling a public API).

## Module 3: Grounding with Vertex AI Vector Search 2.0
* **Concepts:** Embeddings, RAG (Retrieval-Augmented Generation), and high-performance vector databases.
* **Hands-on:**
  * Creating a Vector Search 2.0 index and deploying an endpoint.
  * Generating embeddings for a sample dataset.
  * Building a custom semantic search tool and dynamically equipping the agent with it.
  * Validating grounded responses.

## Module 4: Orchestration with Agent Engine
* **Concepts:** Moving from a local script to a managed agent lifecycle. Handling sessions, state, and complex routing.
* **Hands-on:**
  * Porting the ADK agent logic to Agent Engine.
  * Setting up long-term memory and session management.
  * Tracing execution paths and understanding reasoning steps.

## Module 5: Advanced Patterns: Evaluation & Iteration
* **Concepts:** It rarely works perfectly the first time. How do we test and iterate?
* **Hands-on:**
  * Implementing a Writer-Critic pattern using multi-agent collaboration.
  * Setting up guardrails and safety settings.
  * Reviewing traces to debug hallucinations or tool-calling failures.

## Module 6: Deploying to Production
* **Concepts:** From notebook/script to an API.
* **Hands-on:**
  * Wrapping the agent in a lightweight web service (e.g., Flask, FastAPI, or using the Starter Pack's web interface).
  * Containerizing and deploying to Google Cloud Run.
  * Monitoring usage and setting up telemetry.

## Capstone Project
Students will apply the concepts learned to build a specialized agent (e.g., a customer support bot grounded in product manuals, or an internal research assistant) and present their deployed application.
