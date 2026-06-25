"""Router qualité de l'air — indice ATMO annuel par commune."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.config import get_db

router = APIRouter(prefix="/api/v1/qualite-air", tags=["qualite-air"])


class CommuneQualiteAir(BaseModel):
    code_commune: str
    annee: int | None = None
    indice_atmo: float | None = None
    nb_jours_bon: int | None = None
    nb_jours_moyen: int | None = None
    nb_jours_degrade: int | None = None
    nb_jours_mauvais: int | None = None
    nb_jours_tres_mauvais: int | None = None
    nb_jours_extremement_mauvais: int | None = None


@router.get("/{code_commune}", response_model=CommuneQualiteAir)
async def get_qualite_air(code_commune: str, db: AsyncSession = Depends(get_db)):
    """Indice ATMO annuel d'une commune (source ATMO France)."""
    result = await db.execute(
        text("""
            SELECT code_commune, annee, indice_atmo,
                   nb_jours_bon, nb_jours_moyen, nb_jours_degrade,
                   nb_jours_mauvais, nb_jours_tres_mauvais, nb_jours_extremement_mauvais
            FROM commune_qualite_air
            WHERE code_commune = :code
        """),
        {"code": code_commune},
    )
    row = result.mappings().first()
    if not row:
        raise HTTPException(
            status_code=404,
            detail=f"Aucune donnée qualité de l'air pour la commune {code_commune}",
        )
    return CommuneQualiteAir(**row)
