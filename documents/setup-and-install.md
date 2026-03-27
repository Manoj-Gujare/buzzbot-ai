# Setup and install

## 1. Python

The project targets **Python 3.13+** (`requires-python` in `pyproject.toml`). The repo pins a default in `.python-version` for pyenv-style tools.

Use a virtual environment so dependencies do not pollute your system Python.

## 2. Get the code

Clone the repository and open a terminal at the project root (the directory that contains `pyproject.toml`, `main.py`, and `config.py`).

## 3. Install dependencies

The lockfile `uv.lock` is checked in. Recommended:

```bash
uv sync
```

That creates `.venv` (by default) and installs everything from the lockfile.

Alternatives:

- `uv pip install -e .` or `pip install -e .` after creating a venv manually, if you prefer not to use `uv sync`.
- `pip install -r` is not provided; use `pyproject.toml` / `uv.lock` as the source of truth.

Main runtime packages include: `langgraph`, `langchain`, `langchain-aws`, `tavily-python`, `arxiv`, `google-api-python-client`, `boto3`, `python-dotenv`, `rich`, `jinja2`.

## 4. Environment file

Before the app can start, create a `.env` file in the **project root** (next to `config.py`). See [configuration.md](configuration.md) for every variable.

`config.validate()` runs at import time from `main.py` and exits with a list of missing keys if anything required is blank.

## 5. Run

From the project root, with the venv activated if needed:

```bash
python main.py
```

You should see a Rich panel with the newsletter name/issue, then a live table of agents. On success, the compiler prints a green panel with the output path under `outputs/`.

### Windows

`main.py` sets UTF-8 for stdout/stderr on Windows so emoji and Unicode from Rich are less likely to crash the console. Use a modern terminal (Windows Terminal) if you still see encoding issues.

## 6. Verify the build

- No import errors after `uv sync` / install.
- `python main.py` passes startup validation (all required env vars set).
- A file appears in `outputs/` named like `newsletter_issue_<N>_<YYYY-MM-DD>.md`.

If Bedrock returns errors (model access, region, or IAM), fix AWS configuration and model availability in your account; the stack trace will usually point to the API call.
