# 🎓 AI University

A multi-agent system that generates full educational courses — curriculum,
Jupyter notebooks, slides, quizzes, and assignments — using specialized LLM
agents with real tool use and live observability.

> **Status: Phase 6 (Advanced, trimmed)** — full agent pipeline (Persona →
> Research → Curriculum → per-lesson content agents → Reviewer), `.ipynb` +
> `.pptx` export, and automatic Anthropic ↔ OpenAI provider failover are all
> in place. See [Roadmap](#roadmap) for what's built vs. cut from scope.

## Why

Most "AI agent" demos are a single model with a system prompt. This project
is an actual multi-agent pipeline: each stage of course creation is handled
by a specialized agent with its own prompt and tools, coordinated by an
orchestrator, with cost/token tracking and a real UI to watch it run.

## Tech stack

| Layer | Choice |
|---|---|
| Orchestration | [smolagents](https://github.com/huggingface/smolagents) |
| LLM routing | [LiteLLM](https://github.com/BerriAI/litellm) (Anthropic + OpenAI, with fallback) |
| Frontend | Streamlit |
| Persistence | SQLite (dev) → PostgreSQL |
| Packaging | Docker + docker-compose |
| Deployment | Hugging Face Spaces |

## Project structure

```text
ai-university/
├── app.py                    # Streamlit entry point
├── config.py                  # Typed settings (env-driven)
├── pages/                     # Streamlit multipage UI
├── agents/
│   ├── base.py                 # Shared agent base class, model resolution, provider failover
│   ├── orchestrator.py         # Runs a named sequence of agents
│   ├── persona_agent.py        # Learner persona from a topic
│   ├── research_agent.py       # Web-search-backed research brief (smolagents ToolCallingAgent)
│   ├── curriculum_agent.py     # Course outline / lesson list
│   ├── lesson_agent_base.py    # Shared base for per-lesson content agents
│   ├── code_agent.py           # Runnable code examples
│   ├── diagram_agent.py        # Mermaid/diagram generation
│   ├── quiz_agent.py           # Quiz questions
│   ├── assignment_agent.py     # Assignments
│   ├── speaker_notes_agent.py  # Slide speaker notes
│   ├── notebook_agent.py       # Assembles lesson content into a notebook draft
│   └── reviewer_agent.py       # Reject/revise loop (REVIEW_MAX_ATTEMPTS)
├── tools/
│   ├── filesystem.py           # Per-run workspace management
│   ├── search.py                # Web search tool used by ResearchAgent
│   ├── export.py                 # Orchestrates run export, zips per-run outputs
│   ├── notebook_export.py       # Builds a real .ipynb via nbformat
│   └── pptx_export.py            # Builds real slides via python-pptx
├── models/
│   └── schemas.py             # Pydantic I/O schemas shared across agents
├── prompts/                   # Versioned system prompts, one module per agent
├── utils/
│   └── logging_config.py      # Centralized loguru setup
├── tests/
├── Dockerfile
├── docker-compose.yml
└── .github/workflows/ci.yml
```

## Getting started

```bash
git clone <your-repo-url>
cd ai-university
cp .env.example .env
# edit .env: set ANTHROPIC_API_KEY and/or OPENAI_API_KEY

pip install -r requirements.txt
streamlit run app.py
```

Or with Docker:

```bash
cp .env.example .env   # fill in your keys
docker compose up --build
```

Then open http://localhost:8501.

## Running tests

```bash
pip install -e ".[dev]"
pytest --cov=.
```

## Roadmap

- [x] **Phase 1 — Foundation**: skeleton, config, logging, orchestrator stub, Streamlit shell, Docker, CI
- [x] **Phase 2 — Core Agents**: Persona → Research → Curriculum → Notebook (Research built on smolagents `ToolCallingAgent`)
- [x] **Phase 3 — Content Generation**: Code, Diagram, Quiz, Assignment, Speaker Notes agents
- [x] **Phase 4 — Quality & Validation**: Reviewer agent loop (reject/revise up to `REVIEW_MAX_ATTEMPTS`)
- [x] **Phase 5 — Export Pipeline**: real `.ipynb` (nbformat) + `.pptx` (python-pptx) export, zipped per run
- [x] **Phase 6 — Advanced (trimmed)**: automatic provider failover (Anthropic ↔ OpenAI on API error), CI, test suite

Not built (cut from original scope to keep this a focused portfolio project rather than a production system): DOCX/PDF export, persistent run memory/resume, a plugin system, and multi-lesson looping (agents currently generate rich content for lesson 1 of the curriculum; every other lesson gets title + objectives only).

## License

MIT — see [LICENSE](LICENSE).
