"""Router prix — transactions DVF (latitude, longitude, prix_m2)."""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.config import get_db

router = APIRouter(prefix="/api/v1/prix", tags=["prix"])


class TransactionPoint(BaseModel):
    latitude: float
    longitude: float
    prix_m2_moyen: float
    nb_transactions: int


@router.get("/points", response_model=list[TransactionPoint])
async def get_prix_points(
    bbox: str = Query(..., description="min_lon,min_lat,max_lon,max_lat"),
    annee: int | None = Query(None, description="Filtrer par année"),
    type_local: str | None = Query(None, description="Filtrer par type : Appartement, Maison"),
    limit: int = Query(5000, ge=1, le=20000),
    db: AsyncSession = Depends(get_db),
):
    """Points DVF agrégés par coordonnées et année — prix/m² moyen et nb transactions."""
    try:
        min_lon, min_lat, max_lon, max_lat = [float(x) for x in bbox.split(",")]
    except ValueError:
        raise HTTPException(status_code=400, detail="bbox invalide — format attendu : min_lon,min_lat,max_lon,max_lat")

    filters = """
        WHERE latitude BETWEEN :min_lat AND :max_lat
          AND longitude BETWEEN :min_lon AND :max_lon
          AND prix_m2 IS NOT NULL AND prix_m2 > 0
          AND latitude IS NOT NULL AND longitude IS NOT NULL
    """
    params: dict = {
        "min_lat": min_lat,
        "max_lat": max_lat,
        "min_lon": min_lon,
        "max_lon": max_lon,
        "limit": limit,
    }

    if annee:
        filters += " AND EXTRACT(YEAR FROM date_mutation) = :annee"
        params["annee"] = annee
    if type_local:
        filters += " AND type_local = :type_local"
        params["type_local"] = type_local

    result = await db.execute(
        text(f"""
            SELECT
                latitude,
                longitude,
                ROUND(AVG(prix_m2)::numeric, 0)  AS prix_m2_moyen,
                COUNT(*)                          AS nb_transactions
            FROM dvf_transactions
            {filters}
            GROUP BY latitude, longitude
            LIMIT :limit
        """),
        params,
    )
    return [TransactionPoint(**row) for row in result.mappings().all()]
