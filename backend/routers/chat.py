import json
import os
import logging
from typing import Literal

import httpx
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core.auth import require_edu_email

load_dotenv()

router = APIRouter(prefix="/api", tags=["chat"])
logger = logging.getLogger("tech-signals-api.chat")


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1, max_length=4000)


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(..., min_length=1, max_length=40)


def _build_tech_context_blob() -> str:
    """Collect all technology JSON data into a compact text block for the LLM."""
    from data.article_generator import _load_tech_context

    techs = _load_tech_context()  # all technology JSONs
    if not techs:
        return "No technology data is currently available."

    lines: list[str] = []
    for t in techs:
        lines.append(f"### {t.get('_name', t.get('_stem', 'Unknown'))}")
        clean = {k: v for k, v in t.items() if not k.startswith("_")}
        lines.append(json.dumps(clean, indent=2, default=str))
        lines.append("")
    return "\n".join(lines)


_CHAT_SYSTEM_PROMPT = """You are **Tech Signals AI**, a helpful environmental-technology advisor.

Your knowledge base contains detailed data on emerging technologies and their environmental
externalities across three dimensions: **Power**, **Pollution**, and **Water**.

Below is the full dataset you should use to answer questions:

---
{context}
---

Guidelines:
- Answer concisely but thoroughly, citing specific data points (numbers, percentages, units) from the dataset above.
- If a question is outside the data you have, say so honestly and suggest what the user could explore instead.
- Format answers in Markdown for readability (headings, bullet points, bold for key figures).
- When comparing technologies, use tables if helpful.
- Always consider the business perspective: cost, risk, scalability, and regulatory implications.
- Keep a professional, consultative tone appropriate for business decision-makers.
"""


@router.post("/chat")
async def api_chat(
    payload: ChatRequest,
    _user: dict = Depends(require_edu_email),
):
    """
    Authenticated Gemini chat endpoint.
    Expects: { "messages": [ { "role": "user"|"assistant", "content": "..." }, ... ] }
    Returns: { "reply": "..." }
    """
    messages = payload.messages

    gemini_api_key = os.getenv("GEMINI_KEY", "").strip()
    if not gemini_api_key:
        raise HTTPException(status_code=503, detail="GEMINI_KEY is not configured")

    gemini_model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip() or "gemini-2.5-flash"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{gemini_model}:generateContent"

    context_blob = _build_tech_context_blob()
    system_prompt = _CHAT_SYSTEM_PROMPT.replace("{context}", context_blob)

    contents: list[dict] = []
    contents.append({"role": "user", "parts": [{"text": system_prompt}]})
    contents.append({"role": "model", "parts": [{"text": "Understood. I have the full Tech Signals dataset loaded and I'm ready to help with environmental technology analysis. What would you like to know?"}]})

    for msg in messages:
        role = "model" if msg.role == "assistant" else "user"
        text = msg.content.strip()
        if text:
            contents.append({"role": role, "parts": [{"text": text}]})

    body = {
        "contents": contents,
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 4096,
        },
    }

    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            resp = await client.post(url, params={"key": gemini_api_key}, json=body)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as exc:
        status_code = exc.response.status_code if exc.response is not None else 'unknown'
        logger.warning("Gemini API status error (%s)", status_code)
        raise HTTPException(status_code=502, detail="Upstream AI service error")
    except httpx.HTTPError as exc:
        logger.warning("Gemini request failure: %s", exc)
        raise HTTPException(status_code=502, detail="Upstream AI service unavailable")

    candidates = data.get("candidates", [])
    if not candidates:
        raise HTTPException(status_code=502, detail="Gemini returned no candidates")

    parts = candidates[0].get("content", {}).get("parts", [])
    reply = "".join(p.get("text", "") for p in parts).strip()

    if not reply:
        raise HTTPException(status_code=502, detail="Gemini returned an empty response")

    return {"reply": reply}
