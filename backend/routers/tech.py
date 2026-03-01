from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from core.auth import verify_token, require_edu_email
from data.technologies import (
    CATEGORIES,
    REGIONS,
    get_all_technologies_flat,
    get_technology_by_id,
)
from services.cities import load_cities

router = APIRouter(prefix="/api", tags=["tech"])


@router.get("/categories")
async def list_categories():
    """List all technology categories with aggregate metrics."""
    result = []
    for cat in CATEGORIES:
        techs = cat["technologies"]
        n = len(techs)
        avg_power = round(sum(t["power"]["forecastIndex"] for t in techs) / n, 1)
        avg_pollution = round(sum(t["pollution"]["forecastIndex"] for t in techs) / n, 1)
        avg_water = round(sum(t["water"]["forecastIndex"] for t in techs) / n, 1)
        result.append({
            "id": cat["id"],
            "name": cat["name"],
            "description": cat["description"],
            "technologyCount": n,
            "averages": {
                "power": avg_power,
                "pollution": avg_pollution,
                "water": avg_water,
            },
            "technologies": cat["technologies"],
        })
    return result


@router.get("/technologies")
async def list_technologies(
    category: Optional[str] = Query(None),
    power_min: Optional[int] = Query(None, alias="powerMin"),
    power_max: Optional[int] = Query(None, alias="powerMax"),
    pollution_min: Optional[int] = Query(None, alias="pollutionMin"),
    pollution_max: Optional[int] = Query(None, alias="pollutionMax"),
    water_min: Optional[int] = Query(None, alias="waterMin"),
    water_max: Optional[int] = Query(None, alias="waterMax"),
    search: Optional[str] = Query(None),
    sort_by: Optional[str] = Query(None, alias="sortBy"),
):
    """
    Filterable, searchable list of all technologies.
    Supports filters for power, pollution, water ranges, and category.
    """
    techs = get_all_technologies_flat()

    if category:
        techs = [t for t in techs if t["categoryId"] == category]
    if search:
        q = search.lower()
        techs = [t for t in techs if q in t["name"].lower() or q in t["description"].lower()]

    if power_min is not None:
        techs = [t for t in techs if t["power"]["forecastIndex"] >= power_min]
    if power_max is not None:
        techs = [t for t in techs if t["power"]["forecastIndex"] <= power_max]
    if pollution_min is not None:
        techs = [t for t in techs if t["pollution"]["forecastIndex"] >= pollution_min]
    if pollution_max is not None:
        techs = [t for t in techs if t["pollution"]["forecastIndex"] <= pollution_max]
    if water_min is not None:
        techs = [t for t in techs if t["water"]["forecastIndex"] >= water_min]
    if water_max is not None:
        techs = [t for t in techs if t["water"]["forecastIndex"] <= water_max]

    if sort_by == "power":
        techs.sort(key=lambda t: t["power"]["forecastIndex"], reverse=True)
    elif sort_by == "pollution":
        techs.sort(key=lambda t: t["pollution"]["forecastIndex"], reverse=True)
    elif sort_by == "water":
        techs.sort(key=lambda t: t["water"]["forecastIndex"], reverse=True)
    else:
        techs.sort(key=lambda t: t["power"]["forecastIndex"], reverse=True)

    return techs


@router.get("/technologies/{tech_id}")
async def get_technology(tech_id: str):
    """Get detailed technology data including trajectory and drivers."""
    tech = get_technology_by_id(tech_id)
    if not tech:
        raise HTTPException(status_code=404, detail="Technology not found")
    return tech


@router.get("/alerts")
async def alerts():
    """Top technologies ranked by projected environmental strain."""
    techs = get_all_technologies_flat()
    techs.sort(key=lambda t: t["power"]["forecastIndex"], reverse=True)
    return techs[:6]


@router.get("/regions")
async def list_regions():
    return REGIONS


@router.get("/cities")
async def list_cities():
    """List pre-loaded city stats for Forecasts city selector."""
    return load_cities()


@router.get("/scenarios/simulate")
async def simulate_scenario(
    tech_id: str = Query(..., alias="techId"),
    region: str = Query("Global"),
    scale: float = Query(1.0, ge=0.1, le=10.0),
    _edu_user: dict = Depends(require_edu_email),
):
    """
    Run a basic scaling simulation.
    Returns projected Power/Pollution/Water at the given deployment scale.
    """
    tech = get_technology_by_id(tech_id)
    if not tech:
        raise HTTPException(status_code=404, detail="Technology not found")

    trajectory = tech.get("trajectory", {})

    def _scale_series(series, multiplier):
        return {
            "historical": series.get("historical", []),
            "projected": [
                {
                    "month": p["month"],
                    "value": round(p["value"] * multiplier, 1),
                    "upper": round(p["upper"] * multiplier, 1),
                    "lower": round(max(0, p["lower"] * multiplier), 1),
                }
                for p in series.get("projected", [])
            ],
        }

    return {
        "technology": tech["name"],
        "region": region,
        "scale": scale,
        "power": _scale_series(trajectory.get("power", {}), scale),
        "pollution": _scale_series(trajectory.get("pollution", {}), scale),
        "water": _scale_series(trajectory.get("water", {}), scale),
        "metrics": {
            "power": {
                "forecastIndex": min(100, round(tech["power"]["forecastIndex"] * scale)),
                "mwDemand": tech["power"]["mwDemand"],
            },
            "pollution": {
                "forecastIndex": min(100, round(tech["pollution"]["forecastIndex"] * scale)),
                "emissionDelta": tech["pollution"]["emissionDelta"],
            },
            "water": {
                "forecastIndex": min(100, round(tech["water"]["forecastIndex"] * scale)),
                "cubicMetersYear": tech["water"]["cubicMetersYear"],
            },
        },
    }


@router.get("/me")
async def get_current_user(token_payload: dict = Depends(verify_token)):
    """Protected route — returns the authenticated user's token payload."""
    return {
        "sub": token_payload.get("sub"),
        "email": token_payload.get("email"),
        "permissions": token_payload.get("permissions", []),
    }
