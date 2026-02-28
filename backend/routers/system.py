from fastapi import APIRouter

from data.technologies import ENGINE_STATUS, MACRO_SUMMARY

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/health")
async def health():
    return {"status": "ok", "service": "tech-signals-api"}


@router.get("/engine-status")
async def engine_status():
    """Engine Status metrics for the Home dashboard."""
    return ENGINE_STATUS


@router.get("/macro-summary")
async def macro_summary():
    """AI-generated macro summary of environmental shifts."""
    return {"summary": MACRO_SUMMARY}
