# Configuration

All runtime configuration for local development goes through a **`.env`** file at the **project root** (same directory as `config.py`). `python-dotenv` loads it when `config` is imported; values can still be overridden by real environment variables if your shell sets them.

## Required variables

These must be non-empty or `main.py` exits before the graph runs:

| Variable | Role |
|----------|------|
| `BEDROCK_MODEL_ID` | Amazon Bedrock foundation model ID used by `ChatBedrock` (see AWS docs for IDs in your region). |
| `AWS_ACCESS_KEY_ID` | IAM access key for API calls. |
| `AWS_SECRET_ACCESS_KEY` | IAM secret key. |
| `AWS_DEFAULT_REGION` | Region for Bedrock and boto3. If omitted from `.env`, `config.py` uses `us-east-1`. |
| `TAVILY_API_KEY` | Tavily search API (used by collector agents via `tools/`). |
| `YOUTUBE_API_KEY` | Google YouTube Data API v3 key (video agent). |

## Optional newsletter metadata

| Variable | Default |
|----------|---------|
| `NEWSLETTER_NAME` | `THE AI PULSE` |
| `NEWSLETTER_AUTHOR` | `AI Pulse Team` |
| `NEWSLETTER_ISSUE_NUMBER` | `1` |

Issue number affects filenames and in-app labels (`outputs/newsletter_issue_{N}_...`).

## AWS and Bedrock notes

- The IAM principal needs permission to invoke the chosen Bedrock model in the configured region.
- Model IDs are region-specific; if you change region, confirm the model is offered there.
- The app uses `langchain_aws.ChatBedrock` from `config.get_llm()` with configurable temperature and max tokens per call site.

## Secrets hygiene

- Do not commit `.env`. It should be listed in `.gitignore`.
- Rotate keys if they are ever exposed.

## Changing validation

If you add new required keys, update `_REQUIRED` in `config.py` and document them here so the next person’s build does not fail mysteriously.
