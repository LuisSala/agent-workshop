# Spike: `agents-cli scaffold create` baseline

Branch: `experiment/agents-cli-scaffold` · `agents-cli` version: **0.1.2**

Goal: see what the simplest `agents-cli scaffold create` produces so we can decide what shape the workshop's `workspace/` should take if we eventually have students bootstrap their own scaffold.

Command run:

```bash
cd /tmp && agents-cli scaffold create scaffold-spike \
  --agent adk \
  --prototype \
  --agent-guidance-filename CLAUDE.md
```

Tree snapshot is in [`scaffold-tree.txt`](./scaffold-tree.txt). Source project lives at `/tmp/scaffold-spike` until the next reboot.

## Findings

### 1. `--prototype` still creates `Dockerfile` and `app/fast_api_app.py`

Even with `--prototype` (which sets `deployment_target='none'`), the CLI generates a `Dockerfile` and a FastAPI wrapper at `app/fast_api_app.py` that calls `get_fast_api_app(...)` from `google.adk.cli.fast_api`. The Dockerfile's `CMD` runs uvicorn against that module. Implication: the scaffold's "prototype" is not as bare as it sounds — it includes everything you need to containerize and serve via HTTP, just no terraform / CI/CD wiring.

For the workshop, this is interesting context: students bootstrapping their `workspace/app/` would pick up these files without asking. We'd either embrace them (and wire the workshop UI to call FastAPI) or strip them out per module.

### 2. Scaffold pins **ADK 1.x**

```toml
"google-adk>=1.15.0,<2.0.0"
```

This conflicts directly with our workshop, which is now on `google-adk>=2.0.0a1` (Beta). Two paths:
- Run `agents-cli scaffold upgrade` after `create` — see if it migrates the pin and any code patterns
- Wait for `agents-cli` itself to default to ADK 2.0
- Manually edit `pyproject.toml` after scaffold (what we did in the workshop migration)

### 3. CLI requires running from cwd, NOT an absolute path

`agents-cli scaffold create /tmp/scaffold-spike` failed with `FileNotFoundError`. Running `cd /tmp && agents-cli scaffold create scaffold-spike` works. The CLI seems to assume the project name is a relative dir created under cwd. Worth confirming with upstream — if it's intended, the workshop's `make solve` etc. pattern doesn't translate cleanly.

### 4. Generated `CLAUDE.md` is template-quality, references `make` aliases that don't exist

The generated `CLAUDE.md` lists commands like `agents-cli playground`, `agents-cli eval run`, `agents-cli infra single-project` — mapping our workshop's `make` targets 1:1. But the README that gets generated in the same project still references **`GEMINI.md`** in its project-structure tree (a small template bug).

The `Coding Agent Guide` content is good baseline material; this workshop's existing GEMINI.md goes further with operational guidelines (model preservation, env config, Workshop Workflow critical rule). Worth comparing side-by-side if we ever auto-regenerate.

### 5. Scaffold includes an `eval/` framework we don't have yet

`tests/eval/eval_config.json` defines a rubric-based judge model evaluation:

```json
"rubric_based_final_response_quality_v1": {
  "threshold": 0.8,
  "judgeModelOptions": { "judgeModel": "gemini-flash-latest", ... },
  "rubrics": [{ "rubricId": "relevance", ...}, { "rubricId": "helpfulness", ...}]
}
```

Mod06 in our workshop is a placeholder for evaluation work — this scaffold gives us a free starting point.

### 6. Integration test pattern matches what mod05+ would need

`tests/integration/test_agent.py` uses `Runner` + `InMemorySessionService` to drive `app.agent.root_agent` and asserts on event content. Our existing integration tests reference a non-existent `app.agent_engine_app` — they'd need rework anyway.

### 7. Top-level differences vs `modules/01-foundation/start`

| File / dir | Scaffold | mod01-start | Notes |
|---|---|---|---|
| `app/__init__.py` | ✓ | ✓ | Identical except http→https URL in license header |
| `app/agent.py` | ✓ | ✓ | Different baseline tools, different model string, different auth bootstrap |
| `app/agent_engine_app.py` | ✗ | ✓ | Workshop has it; scaffold prototype omits it (would arrive with `--deployment-target agent_runtime`) |
| `app/app_utils/telemetry.py` | ✓ | ✓ | Same pattern |
| `app/app_utils/typing.py` | ✓ | ✓ | Same pattern |
| `app/app_utils/deploy.py` | ✗ | ✓ | Same as `agent_engine_app.py` — deployment-related, omitted by --prototype |
| `app/fast_api_app.py` | ✓ | ✗ | NEW — FastAPI wrapper for HTTP serving |
| `Dockerfile` | ✓ | ✗ | NEW |
| `tests/eval/` | ✓ | ✗ | NEW — workshop has tests/ at repo root, not per-module |
| `tests/integration/` | ✓ | ✗ | NEW |
| `tests/unit/` | ✓ | ✗ | NEW |
| `Makefile` | ✗ | ✗ | Workshop uses repo-root Makefile; scaffold uses `agents-cli` commands directly |
| `CLAUDE.md` | ✓ | ✗ | NEW (per `--agent-guidance-filename`) |
| `pyproject.toml` | ✓ | (n/a — repo-level only) | Each scaffold is its own project |

## Implications for the eventual "students bootstrap their own scaffold" plan

If the workshop transitions to having students run `agents-cli scaffold create` inside `workspace/`, several gaps need decisions:

1. **ADK version pin mismatch.** Until `agents-cli` defaults to 2.0, students bootstrap a 1.x project that doesn't match the curriculum's API patterns. Either we instruct students to immediately edit `pyproject.toml`, run `agents-cli scaffold upgrade`, or wait.

2. **Per-project `pyproject.toml`** vs repo-level. Each scaffold is its own project with its own deps. Our `utils/citations.py` and `utils/vector_store.py` live at repo root and are imported via `sys.path` hacks. Students bootstrapping inside `workspace/` would need either: (a) the helpers vendored into each module's start, (b) a published `agent-workshop-utils` package, (c) a `[tool.uv.sources]` path-dependency added to the scaffolded project.

3. **Tests live in the project, not at repo root.** Our `tests/` is repo-level; the scaffold's `tests/` is project-level. To match, we'd either move tests or accept duplicate test trees per module.

4. **`Makefile` vs `agents-cli` commands.** Workshop currently teaches `make playground`, `make solve`, etc. Scaffold expects `agents-cli playground`. Two parallel UX vocabularies; pick one or document both.

5. **Workshop snapshot/cascade tooling assumes `workspace/app/` layout** — `make solve module=N` does `rm -rf workspace/* && cp -R modules/N/solution/* workspace/`. If a student `cd workspace && agents-cli scaffold create my-agent`, the result is `workspace/my-agent/app/...` which breaks the `workspace/app/` assumption. The scaffold convention would need either a flat `--name=app` (if supported) or post-processing.

## Suggested next experiments

- Run `agents-cli scaffold upgrade /tmp/scaffold-spike` and see what changes (does it move to ADK 2.0?).
- Try `--agent agentic_rag --datastore agent_platform_vector_search --prototype` to compare with mod04's vector-search structure.
- Try `agents-cli scaffold enhance . --deployment-target agent_runtime` on the spike and see what gets added — useful for what mod05 (Agent Engine) would teach.

## Reference files in this directory

- [`scaffold-tree.txt`](./scaffold-tree.txt) — full file tree of the scaffolded project (the source `/tmp/scaffold-spike` will be wiped at next reboot).
