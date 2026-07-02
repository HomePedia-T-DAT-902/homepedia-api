"""Router éducation — résultats baccalauréat par commune (IVAL lycées GT)."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.config import get_db

router = APIRouter(prefix="/api/v1/education", tags=["education"])


class EducationAnnee(BaseModel):
    annee: int
    bac_presents: int | None = None
    bac_taux_reussite: float | None = None


class CommuneEducation(BaseModel):
    code_commune: str
    historique: list[EducationAnnee]


@router.get("/{code_commune}", response_model=CommuneEducation)
async def get_education(code_commune: str, db: AsyncSession = Depends(get_db)):
    """Résultats du baccalauréat d'une commune, toutes années disponibles."""
    result = await db.execute(
        text("""
            SELECT annee, bac_presents, bac_taux_reussite
            FROM education_commune
            WHERE code_commune = :code
            ORDER BY annee
        """),
        {"code": code_commune},
    )
    rows = result.mappings().all()
    if not rows:
        raise HTTPException(status_code=404, detail=f"Aucune donnée éducation pour la commune {code_commune}")
    return CommuneEducation(
        code_commune=code_commune,
        historique=[EducationAnnee(**row) for row in rows],
    )
