import json
import os
import logging
from pathlib import Path
from typing import Literal

import httpx
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core.auth import require_edu_email

load_dotenv()

router = APIRouter(prefix="/api", tags=["chat"])
logger = logging.getLogger("tech-signals-api.chat")

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"


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


def _build_city_context_blob() -> str:
    """Summarise city timeseries data into a compact text block."""
    cities_dir = DATA_DIR / "cities"
    if not cities_dir.exists():
        return "No city data available."

    lines: list[str] = []
    for path in sorted(cities_dir.glob("*_timeseries.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue

        city = payload.get("city", path.stem.replace("_timeseries", "").replace("_", " ").title())
        pop = payload.get("population", "N/A")
        ts = payload.get("time_series", [])
        if not ts:
            continue

        lines.append(f"### {city} (pop: {pop:,} )" if isinstance(pop, int) else f"### {city} (pop: {pop})")

        # Show key milestone years: earliest, 2026 (current), 2036, latest
        milestones = {}
        for row in ts:
            y = row["year"]
            if y in (ts[0]["year"], 2026, 2036, ts[-1]["year"]):
                milestones[y] = row

        for y in sorted(milestones):
            r = milestones[y]
            label = "current" if y == 2026 else ("10yr forecast" if y == 2036 else "")
            tag = f" ({label})" if label else ""
            lines.append(
                f"  {y}{tag}: power={r['power_kwh']:,.0f} kWh, "
                f"water={r['water_kgal']:,.0f} kgal, "
                f"co2={r['co2_kg']:,.0f} kg"
            )
        lines.append("")

    return "\n".join(lines) if lines else "No city timeseries data available."


def _build_allocated_tech_context() -> str:
    """Show per-technology allocated values (current + 10yr forecast) from the engine."""
    try:
        from data.technologies import get_all_technologies_flat
        techs = get_all_technologies_flat()
    except Exception:
        return ""

    if not techs:
        return ""

    lines: list[str] = ["## Per-Technology Allocated Resource Values (cross-city average)"]
    for t in techs:
        lines.append(f"### {t['name']}")
        for pillar in ("power", "pollution", "water"):
            p = t.get(pillar, {})
            idx = p.get("forecastIndex", 0)
            unit = p.get("unit", "")
            delta = p.get("delta", 0)
            lines.append(f"  {pillar.title()}: {idx:,.1f} {unit}  (10yr change: {delta:+.1f}%)")
        lines.append("")

    return "\n".join(lines)


EPA_REGULATIONS_CONTEXT = """
## EPA Regulations & Standards Reference

### Clean Air Act (CAA)
- National Ambient Air Quality Standards (NAAQS) regulate six criteria pollutants: CO, lead, NO₂, O₃, PM, SO₂.
- New Source Performance Standards (NSPS) set emission limits for new/modified stationary sources including power plants and industrial facilities.
- Data centers and large compute facilities may trigger Title V permitting if they use backup diesel generators or on-site gas turbines.

### Clean Water Act (CWA)
- NPDES permits required for point-source discharges to waters of the US.
- Cooling water intake structures (§316(b)) must use best technology available to minimize impingement/entrainment — directly relevant to data centers and semiconductor fabs using once-through cooling.
- Effluent guidelines for the Steam Electric Power Generating category (40 CFR Part 423) limit discharge of pollutants from power-related cooling.

### Resource Conservation and Recovery Act (RCRA)
- Semiconductor manufacturing facilities generate hazardous waste (solvents, acids, heavy metals) regulated under RCRA Subtitle C.
- E-waste from decommissioned servers, chips, and batteries falls under RCRA universal waste rules.

### EPA Greenhouse Gas Reporting Program (GHGRP)
- Facilities emitting ≥25,000 metric tons CO₂e/year must report under 40 CFR Part 98.
- Large data centers and AI campuses with on-site generation routinely exceed this threshold.
- Subpart C (stationary combustion), Subpart D (electricity generation) are most relevant.

### Energy Star & Federal Energy Management
- EPA Energy Star for Data Centers: Power Usage Effectiveness (PUE) benchmarking. Industry average PUE ≈ 1.58; best-in-class < 1.2.
- Water Usage Effectiveness (WUE) emerging metric: liters per kWh of IT load. Typical range 0.5–2.0 L/kWh.

### EPA Water Sense & Water Efficiency
- WaterSense program promotes water efficiency; relevant for cooling system design in data centers and fabs.
- Semiconductor fabs use 2–4 million gallons/day of ultrapure water; EPA encourages water recycling and reuse programs.

### Greenhouse Gas Reduction Fund & IRA Provisions
- Inflation Reduction Act (2022) provisions support clean energy tax credits (§45Y, §48E) for data center and tech facility renewable energy transitions.
- EPA's Greenhouse Gas Reduction Fund provides financing for clean technology deployment in communities.

### NEPA (National Environmental Policy Act)
- Environmental Impact Statements (EIS) required for major federal actions — relevant when tech facilities seek federal permits, land use on federal property, or federal funding.
- AI campus and semiconductor plant proposals on greenfield sites commonly trigger NEPA review.

### Toxic Substances Control Act (TSCA)
- PFAS chemicals used in semiconductor manufacturing are under increasing EPA scrutiny.
- EPA's TSCA Section 8(a)(7) rule requires reporting of PFAS manufacturing and use data.

### Key EPA Thresholds for Emerging Tech Facilities
| Metric | Threshold | Regulation |
|--------|-----------|------------|
| GHG Emissions | ≥25,000 MT CO₂e/yr | GHGRP reporting |
| GHG Emissions | ≥100,000 MT CO₂e/yr | PSD/Title V major source |
| Water Withdrawal | ≥100,000 gal/day | State/federal water rights permits |
| Hazardous Waste | ≥1,000 kg/month | RCRA Large Quantity Generator |
| Air Emissions (NOx, PM) | Varies by attainment area | NAAQS, NSR permitting |
| Cooling Water Intake | ≥2 MGD design flow | CWA §316(b) BTA requirements |
"""


_CHAT_SYSTEM_PROMPT = """You are **Chartr AI**, a helpful environmental-technology advisor with expertise in EPA regulations and environmental compliance.

Your knowledge base contains detailed data on emerging technologies and their environmental
externalities across three dimensions: **Power**, **Pollution**, and **Water**.

Below is the full dataset you should use to answer questions:

---
## Technology Specifications
{tech_context}
---

## City Timeseries Data (Historical + Forecast, 2017–2050)
{city_context}
---

## Allocated Per-Technology Values
{allocated_context}
---

{epa_context}
---

Guidelines:
- Answer concisely but thoroughly, citing specific data points (numbers, percentages, units) from the dataset above.
- When asked about regulations, reference specific EPA rules, CFR citations, and thresholds from the EPA reference above.
- Connect regulatory requirements to the specific technologies — e.g., whether a data center's emissions would trigger GHGRP reporting.
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
    print(_user)
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
    city_blob = _build_city_context_blob()
    allocated_blob = _build_allocated_tech_context()
    system_prompt = (
        _CHAT_SYSTEM_PROMPT
        .replace("{tech_context}", context_blob)
        .replace("{city_context}", city_blob)
        .replace("{allocated_context}", allocated_blob)
        .replace("{epa_context}", EPA_REGULATIONS_CONTEXT)
    )

    contents: list[dict] = []
    contents.append({"role": "user", "parts": [{"text": system_prompt}]})
    contents.append({"role": "model", "parts": [{"text": "Understood. I have the full Chartr AI dataset loaded and I'm ready to help with environmental technology analysis. What would you like to know?"}]})

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
