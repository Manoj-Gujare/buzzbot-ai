"""
prompt_agent.py — Generates the "Prompt of the Week" section.

Based on top_news[0] (or a fallback topic).
The prompt must be immediately copy-pasteable into ChatGPT, Claude, or Gemini.

Returns: prompt_of_the_week, prompt_category, prompt_use_case, prompt_pro_tip
"""

from __future__ import annotations

import json
import re
import sys
import os


from state import NewsletterState
import config


def _parse_json(text: str) -> dict:
    text = text.strip()
    for fence in ["```json", "```"]:
        if fence in text:
            parts = text.split(fence)
            if len(parts) >= 3:
                text = parts[1].strip()
                break
    try:
        return json.loads(text)
    except Exception:
        pass
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except Exception:
            pass
    return {}


def prompt_agent(state: NewsletterState) -> dict:
    errors: list[str] = []

    # ── Determine theme ───────────────────────────────────────────────────────
    top_news = state.get("top_news", [])
    if top_news:
        story = top_news[0]
        theme = story.get("title", "")
        context = story.get("why_it_matters", story.get("summary", ""))
    else:
        week_label = state.get("week_label", "this week")
        theme = f"AI productivity and automation — {week_label}"
        context = "A practical prompt to help professionals leverage the latest AI capabilities."

    llm_prompt = f"""You are an AI prompt engineer writing a "Prompt of the Week" column for a newsletter.

This week's theme is based on: {theme}
Context: {context}

Create an immediately useful, professional prompt that:
- Can be pasted directly into ChatGPT, Claude, or Gemini RIGHT NOW
- Solves a real professional or creative problem connected to this week's theme
- Uses [BRACKETS] for user-specific placeholders (min 2, max 5 placeholders)
- Is 100-200 words long
- Produces highly specific, actionable output

Return a JSON object with EXACTLY these keys:
{{
  "prompt_category": "One of: Productivity / Research / Coding / Strategy / Writing / Analysis / Marketing",
  "prompt_use_case": "One sentence describing what problem this prompt solves",
  "prompt_of_the_week": "The full, ready-to-use prompt text with [PLACEHOLDER] substitutions",
  "prompt_pro_tip": "One sentence on how to get even better results from this prompt"
}}

IMPORTANT:
- prompt_of_the_week should be the actual prompt text a user would copy-paste, NOT a description of it
- Make it professional-grade and immediately useful
- Return ONLY the JSON. No preamble, no markdown fences."""

    try:
        llm = config.get_llm(temperature=0.7, max_tokens=1000)
        from langchain_core.messages import HumanMessage, SystemMessage
        response = llm.invoke([
            SystemMessage(content="You are a world-class AI prompt engineer. Return only valid JSON."),
            HumanMessage(content=llm_prompt),
        ])
        data = _parse_json(response.content)

        prompt_of_the_week = data.get("prompt_of_the_week", "")
        prompt_category = data.get("prompt_category", "Productivity")
        prompt_use_case = data.get("prompt_use_case", "")
        prompt_pro_tip = data.get("prompt_pro_tip", "Add specific examples to get more tailored output.")

    except Exception as e:
        errors.append(f"prompt_agent LLM call failed: {e}")
        prompt_of_the_week = (
            f"You are a [ROLE] working in [INDUSTRY]. "
            f"I need you to analyze the following AI development and explain its implications for my work: {theme}. "
            f"Focus on: 1) Immediate practical applications, 2) Skills I should develop, "
            f"3) Risks to watch out for. My current context: [YOUR CONTEXT]."
        )
        prompt_category = "Analysis"
        prompt_use_case = "Help professionals understand AI developments relevant to their field."
        prompt_pro_tip = "Add your specific role and industry for highly tailored insights."

    return {
        "prompt_of_the_week": prompt_of_the_week,
        "prompt_category": prompt_category,
        "prompt_use_case": prompt_use_case,
        "prompt_pro_tip": prompt_pro_tip,
        "errors": errors,
    }
