"""Router geo — endpoints GeoJSON (parcelles cadastrales, contours)."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.config import get_db

router = APIRouter(prefix="/api/v1/geo", tags=["geo"])


def _build_feature(row) -> dict:
    return {
        "type": "Feature",
        "properties": {
            "id": row["id"],
            "code_commune": row["code_commune"],
            "prefixe": row["prefixe"],
            "section": row["section"],
            "numero": row["numero"],
            "contenance": row["contenance"],
            "created": str(row["created"]) if row["created"] else None,
            "updated": str(row["updated"]) if row["updated"] else None,
        },
        "geometry": row["geometry"],
    }


@router.get("/parcelles")
async def get_parcelles(
    bbox: str = Query(..., description="Bounding box: min_lon,min_lat,max_lon,max_lat"),
    limit: int = Query(5000, ge=1, le=10000),
    db: AsyncSession = Depends(get_db),
):
    """Retourne les parcelles cadastrales dans une bounding box en GeoJSON."""
    parts = bbox.split(",")
    if len(parts) != 4:
        raise HTTPException(status_code=422, detail="bbox doit contenir 4 valeurs: min_lon,min_lat,max_lon,max_lat")

    try:
        min_lon, min_lat, max_lon, max_lat = (float(p) for p in parts)
    except ValueError:
        raise HTTPException(status_code=422, detail="Les valeurs bbox doivent être des nombres")

    result = await db.execute(
        text("""
            SELECT p.id, p.code_commune, p.section, p.numero, p.contenance,
                   p.prefixe, p.created, p.updated,
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
        "truncated": len(rows) == limit,
        "count": len(rows),
        "features": [_build_feature(row) for row in rows],
    }


@router.get("/parcelles/{parcel_id}")
async def get_parcelle(
    parcel_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Retourne le détail d'une parcelle cadastrale par son identifiant Etalab."""
    result = await db.execute(
        text("""
            SELECT p.id, p.code_commune, p.prefixe, p.section, p.numero,
                   p.contenance, p.created, p.updated,
                   ST_AsGeoJSON(p.geom)::json AS geometry,
                   c.nom AS nom_commune, c.code_departement, c.code_postal
            FROM parcelles_cadastrales p
            LEFT JOIN communes c ON p.code_commune = c.code_commune
            WHERE p.id = :id
        """),
        {"id": parcel_id},
    )
    row = result.mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail=f"Parcelle {parcel_id} non trouvée")

    feature = _build_feature(row)
    feature["properties"].update(
        {
            "nom_commune": row["nom_commune"],
            "code_departement": row["code_departement"],
            "code_postal": row["code_postal"],
        }
    )
    return feature


@router.get("/communes/{code_commune}/parcelles")
async def get_parcelles_by_commune(
    code_commune: str,
    limit: int = Query(5000, ge=1, le=10000),
    db: AsyncSession = Depends(get_db),
):
    """Retourne toutes les parcelles cadastrales d'une commune en GeoJSON."""
    result = await db.execute(
        text("""
            SELECT p.id, p.code_commune, p.section, p.numero, p.contenance,
                   p.prefixe, p.created, p.updated,
                   ST_AsGeoJSON(p.geom)::json AS geometry
            FROM parcelles_cadastrales p
            WHERE p.code_commune = :code_commune
            LIMIT :limit
        """),
        {"code_commune": code_commune, "limit": limit},
    )
    rows = result.mappings().all()

    if not rows:
        raise HTTPException(status_code=404, detail=f"Aucune parcelle trouvée pour la commune {code_commune}")

    return {
        "type": "FeatureCollection",
        "code_commune": code_commune,
        "truncated": len(rows) == limit,
        "count": len(rows),
        "features": [_build_feature(row) for row in rows],
    }
