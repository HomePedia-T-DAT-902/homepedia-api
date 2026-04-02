"""Router geo — endpoints GeoJSON (parcelles cadastrales, contours)."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.config import get_db

router = APIRouter(prefix="/api/v1/geo", tags=["geo"])


@router.get("/parcelles")
async def get_parcelles(
    bbox: str = Query(..., description="Bounding box: min_lon,min_lat,max_lon,max_lat"),
    limit: int = Query(5000, ge=1, le=10000),
    db: AsyncSession = Depends(get_db),
):
    """Retourne les parcelles cadastrales dans une bounding box en GeoJSON."""
    parts = bbox.split(",")
    if len(parts) != 4:
        return {"error": "bbox doit contenir 4 valeurs: min_lon,min_lat,max_lon,max_lat"}

    min_lon, min_lat, max_lon, max_lat = (float(p) for p in parts)

    result = await db.execute(
        text("""
            SELECT p.id, p.code_commune, p.section, p.numero, p.contenance,
                   ST_AsGeoJSON(p.geom)::json AS geometry
            FROM parcelles_cadastrales p
            WHERE p.geom && ST_MakeEnvelope(:min_lon, :min_lat, :max_lon, :max_lat, 4326)
            LIMIT :limit
        """),
        {"min_lon": min_lon, "min_lat": min_lat, "max_lon": max_lon, "max_lat": max_lat, "limit": limit},
    )
    rows = result.mappings().all()

    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "id": row["id"],
                    "code_commune": row["code_commune"],
                    "section": row["section"],
                    "numero": row["numero"],
                    "contenance": row["contenance"],
                },
                "geometry": row["geometry"],
            }
            for row in rows
        ],
    }
