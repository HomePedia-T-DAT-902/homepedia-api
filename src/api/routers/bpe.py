"""Router BPE — équipements et services par commune."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.config import get_db

router = APIRouter(prefix="/api/v1/equipements", tags=["equipements"])


class CommuneEquipements(BaseModel):
    code_commune: str
    nb_equipements_total: int | None = None
    nb_maternelles: int | None = None
    nb_primaires: int | None = None
    nb_creches: int | None = None
    nb_colleges: int | None = None
    nb_lycees: int | None = None
    nb_medecins: int | None = None
    nb_pharmacies: int | None = None
    nb_urgences: int | None = None
    nb_supermarches: int | None = None
    nb_hypermarches: int | None = None
    nb_gares: int | None = None


@router.get("/{code_commune}", response_model=CommuneEquipements)
async def get_equipements(code_commune: str, db: AsyncSession = Depends(get_db)):
    """Équipements et services d'une commune (BPE — INSEE)."""
    result = await db.execute(
        text("""
            SELECT code_commune, nb_equipements_total,
                   nb_maternelles, nb_primaires, nb_creches, nb_colleges, nb_lycees,
                   nb_medecins, nb_pharmacies, nb_urgences,
                   nb_supermarches, nb_hypermarches, nb_gares
            FROM bpe_commune_stats
            WHERE code_commune = :code
        """),
        {"code": code_commune},
    )
    row = result.mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail=f"Aucune donnée équipements pour la commune {code_commune}")
    return CommuneEquipements(**row)
