# 🎓 AI University

A multi-agent system that generates full educational courses — curriculum,
Jupyter notebooks, slides, quizzes, and assignments — using specialized LLM
agents with real tool use and live observability.

> **Status: Phase 1 (Foundation)** — project skeleton, config, logging,
> orchestrator stub, and a working Streamlit shell are in place. Specialized
> agents (Persona, Research, Curriculum, Notebook, ...) land in Phase 2.

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
├── app.py                  # Streamlit entry point
├── config.py                # Typed settings (env-driven)
├── pages/                   # Streamlit multipage UI
├── agents/
│   ├── base.py               # Shared agent base class + registry
│   └── orchestrator.py       # Runs a named sequence of agents
├── tools/
│   ├── filesystem.py         # Per-run workspace management
│   └── search.py              # Web search (Phase 1 stub)
├── utils/
│   └── logging_config.py     # Centralized loguru setup
├── models/                   # Pydantic I/O schemas (Phase 2+)
├── prompts/                  # Versioned system prompts (Phase 2+)
├── templates/                # Jinja/Markdown templates (Phase 2+)
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
- [ ] **Phase 2 — Core Agents**: Persona → Research → Curriculum → Notebook
- [ ] **Phase 3 — Content Generation**: Code, Diagram, Quiz, Assignment, Speaker Notes agents
- [ ] **Phase 4 — Quality & Validation**: Reviewer agent, notebook execution checks
- [ ] **Phase 5 — Export Pipeline**: PPTX, DOCX, PDF, Notebook, ZIP packaging
- [ ] **Phase 6 — Advanced**: multi-LLM routing strategies, plugin system, deeper test coverage

## License

MIT — see [LICENSE](LICENSE).
