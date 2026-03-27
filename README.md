# buzzbot-ai

Multi-agent **AI newsletter** pipeline: scouts news, research, tools, video, jobs, and events; runs analysis and prompt engineering; then compiles a Markdown issue with Jinja2. Built with **LangGraph** and **AWS Bedrock** (`langchain-aws`).

## What it does

`main.py` runs a LangGraph workflow with a live **Rich** status table (per-agent phases and timing). The final Markdown is written under `outputs/` as `newsletter_issue_{N}_{YYYY-MM-DD}.md`, using `templates/newsletter.j2`.

## Pipeline (graph)

| Phase | Mode | Agents |
|-------|------|--------|
| **1** | Parallel from `START` | `news_agent`, `research_agent`, `tools_agent`, `youtube_agent`, `jobs_agent`, `events_agent` |
| **2** | Sequential | `analysis_agent` → `prompt_agent` (waits until all Phase 1 nodes finish) |
| **3** | Compile | `compiler_agent` → `END` (editor’s note, closing thoughts, Jinja render, file save) |

Shared state is defined in `state.py` (`NewsletterState`): collected sections (news, papers, tools, YouTube, jobs, events, quotes, etc.), LLM-written fields (deep dive, prompt of the week, sentiment), and `final_markdown` / `errors`.

## Requirements

- **Python** `>=3.13` (see `.python-version` for the repo default).
- **AWS** credentials and a **Bedrock** model ID the account can invoke.
- **Tavily** API key (web search / news-style gathering in agents).
- **YouTube Data API** key (video curation).

## Setup

1. Clone the repo and create a `.env` in the project root (same directory as `config.py`).

2. Set **required** variables (startup fails fast if any are empty):

   | Variable | Purpose |
   |----------|---------|
   | `BEDROCK_MODEL_ID` | Bedrock chat model ID |
   | `AWS_ACCESS_KEY_ID` | AWS access key |
   | `AWS_SECRET_ACCESS_KEY` | AWS secret key |
   | `AWS_DEFAULT_REGION` | Region (default in code: `us-east-1`) |
   | `TAVILY_API_KEY` | Tavily |
   | `YOUTUBE_API_KEY` | YouTube Data API |

3. **Optional** newsletter metadata:

   | Variable | Default |
   |----------|---------|
   | `NEWSLETTER_NAME` | `THE AI PULSE` |
   | `NEWSLETTER_AUTHOR` | `AI Pulse Team` |
   | `NEWSLETTER_ISSUE_NUMBER` | `1` |

4. Install dependencies (e.g. with [uv](https://github.com/astral-sh/uv) — `uv.lock` is present):

   ```bash
   uv sync
   ```

   Or use your preferred tool against `pyproject.toml`.

## Run

```bash
python main.py
```

On Windows, the entry point forces UTF-8 I/O so Rich output (including emoji) is less likely to break the console.

## Project layout

- `main.py` — CLI entry, state init, graph stream, live status
- `graph.py` — `StateGraph` wiring
- `config.py` — `.env` loading, validation, `get_llm()` (ChatBedrock)
- `state.py` — `NewsletterState` and `default_state()`
- `agents/` — one module per graph node
- `tools/` — Tavily, arXiv, YouTube helpers used by collectors
- `templates/newsletter.j2` — issue template
- `outputs/` — generated `.md` files

## Stack (from `pyproject.toml`)

LangChain / LangGraph, `langchain-aws`, Tavily, arXiv, Google API client, boto3, python-dotenv, Rich, Jinja2.
