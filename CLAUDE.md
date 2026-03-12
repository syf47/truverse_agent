# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Truverse Agent — 电商对话 Agent，基于 LangChain + LangGraph + GPT-4o，支持多模态（图片 OCR、标注），通过 FastAPI 提供 API 服务。

## Build & Run

- Install dependencies: `uv sync`
- Install with dev deps: `uv sync --group dev`
- Copy env template: `cp .env.example .env` (fill in OPENAI_API_KEY)
- Start server: `uv run uvicorn app.main:app --reload --port 8000`
- Run tests: `uv run pytest tests/`
- Run single test: `uv run pytest tests/test_agent.py::test_health`

## Architecture

```
app/
├── main.py              # FastAPI entry point (routes: /chat, /chat/multimodal, /health)
├── config.py            # Settings from env vars
├── schemas.py           # Pydantic request/response models
├── agent/
│   ├── graph.py         # LangGraph agent workflow (state graph with tool calling)
│   ├── prompts.py       # System prompt templates
│   ├── tools.py         # LangChain @tool definitions (OCR, analyze, annotate, search, query)
│   └── multimodal.py    # Image processing (base64, GPT-4o vision, Pillow annotation)
└── context/
    └── viking.py        # OpenViking context manager (L0/L1/L2 layered context, in-memory stub)
```

- **LLM**: GPT-4o via langchain-openai
- **Agent orchestration**: LangGraph state graph with tool nodes
- **Context**: OpenViking-style L0/L1/L2 layered context (currently in-memory stub)
- **Multimodal**: GPT-4o vision for OCR/image analysis, Pillow for annotation
