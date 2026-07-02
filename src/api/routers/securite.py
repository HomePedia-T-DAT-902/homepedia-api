"""Router sécurité — délinquance communale (SSMSI)."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.config import get_db

router = APIRouter(prefix="/api/v1/securite", tags=["securite"])


class SecuriteAnnee(BaseModel):
    annee: int
    cambriolages_nombre: int | None = None
    cambriolages_pour_mille: float | None = None
    violences_nombre: int | None = None
    violences_pour_mille: float | None = None
    vols_nombre: int | None = None
    vols_pour_mille: float | None = None
    stups_nombre: int | None = None
    stups_pour_mille: float | None = None
    destructions_nombre: int | None = None
    destructions_pour_mille: float | None = None


class CommuneSecurite(BaseModel):
    code_commune: str
    historique: list[SecuriteAnnee]


@router.get("/{code_commune}", response_model=CommuneSecurite)
async def get_securite(code_commune: str, db: AsyncSession = Depends(get_db)):
    """Données de délinquance d'une commune, toutes années disponibles."""
    result = await db.execute(
        text("""
            SELECT annee,
                   cambriolages_nombre, cambriolages_pour_mille,
                   violences_nombre,    violences_pour_mille,
                   vols_nombre,         vols_pour_mille,
                   stups_nombre,        stups_pour_mille,
                   destructions_nombre, destructions_pour_mille
            FROM securite_commune
            WHERE code_commune = :code
            ORDER BY annee
        """),
        {"code": code_commune},
    )
    rows = result.mappings().all()
    if not rows:
        raise HTTPException(status_code=404, detail=f"Aucune donnée sécurité pour la commune {code_commune}")
    return CommuneSecurite(
        code_commune=code_commune,
        historique=[SecuriteAnnee(**row) for row in rows],
    )
