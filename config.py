"""
config.py — Load and validate all environment variables.
Raises a clear error at startup if any required key is missing.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# .env lives in the same directory as this file (the project root)
_env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=_env_path, override=True)

# ── AWS / Bedrock ─────────────────────────────────────────────────────────────
BEDROCK_MODEL_ID: str = os.getenv("BEDROCK_MODEL_ID", "")
AWS_ACCESS_KEY_ID: str = os.getenv("AWS_ACCESS_KEY_ID", "")
AWS_SECRET_ACCESS_KEY: str = os.getenv("AWS_SECRET_ACCESS_KEY", "")
AWS_DEFAULT_REGION: str = os.getenv("AWS_DEFAULT_REGION", "us-east-1")

# ── Third-party APIs ──────────────────────────────────────────────────────────
TAVILY_API_KEY: str = os.getenv("TAVILY_API_KEY", "")
YOUTUBE_API_KEY: str = os.getenv("YOUTUBE_API_KEY", "")

# ── Newsletter meta ───────────────────────────────────────────────────────────
NEWSLETTER_NAME: str = os.getenv("NEWSLETTER_NAME", "THE AI PULSE")
NEWSLETTER_AUTHOR: str = os.getenv("NEWSLETTER_AUTHOR", "AI Pulse Team")
NEWSLETTER_ISSUE_NUMBER: int = int(os.getenv("NEWSLETTER_ISSUE_NUMBER", "1"))

# ── Required keys — exit immediately if any are blank ─────────────────────────
_REQUIRED = {
    "BEDROCK_MODEL_ID": BEDROCK_MODEL_ID,
    "AWS_ACCESS_KEY_ID": AWS_ACCESS_KEY_ID,
    "AWS_SECRET_ACCESS_KEY": AWS_SECRET_ACCESS_KEY,
    "AWS_DEFAULT_REGION": AWS_DEFAULT_REGION,
    "TAVILY_API_KEY": TAVILY_API_KEY,
    "YOUTUBE_API_KEY": YOUTUBE_API_KEY,
}


def validate():
    """Call once at startup. Exits with a descriptive message if any key is missing."""
    missing = [k for k, v in _REQUIRED.items() if not v]
    if missing:
        print("\n[ERROR] The following required environment variables are not set:")
        for key in missing:
            print(f"  • {key}")
        print(f"\nPlease fill them in: {_env_path}\n")
        sys.exit(1)


# ── LLM factory ───────────────────────────────────────────────────────────────
def get_llm(temperature: float = 0.7, max_tokens: int = 4096):
    """Return a ChatBedrock instance using the configured model."""
    from langchain_aws import ChatBedrock

    return ChatBedrock(
        model_id=BEDROCK_MODEL_ID,
        region_name=AWS_DEFAULT_REGION,
        model_kwargs={
            "temperature": temperature,
            "max_tokens": max_tokens,
        },
    )
