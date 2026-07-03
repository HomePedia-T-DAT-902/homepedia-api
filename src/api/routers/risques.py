"""Router risques — risques naturels et technologiques par commune."""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.config import get_db

router = APIRouter(prefix="/api/v1/risques", tags=["risques"])


class CommuneRisques(BaseModel):
    code_commune: str
    inondation: bool | None = None
    seisme: bool | None = None
    mouvement_terrain: bool | None = None
    retrait_gonflement_argile: bool | None = None
    radon: bool | None = None
    feu_foret: bool | None = None
    icpe: bool | None = None
    source_annee: int | None = None


class RisqueGeopoint(BaseModel):
    id: int
    type_risque: str
    longitude: float
    latitude: float
    code_commune: str | None = None


@router.get("/geopoints", response_model=list[RisqueGeopoint])
async def get_risques_geopoints(
    type_risque: str | None = Query(None, description="Filtrer par type de risque (ex: seisme, inondation)"),
    code_commune: str | None = Query(None, description="Filtrer par code commune"),
    limit: int = Query(100, ge=1, le=5000),
    db: AsyncSession = Depends(get_db),
):
    """Geopoints des risques naturels et technologiques (centroïde de la commune à risque)."""
    filters = []
    params: dict = {"limit": limit}

    if type_risque is not None:
        filters.append("type_risque = :type_risque")
        params["type_risque"] = type_risque
    if code_commune is not None:
        filters.append("code_commune = :code_commune")
        params["code_commune"] = code_commune

    where = ("WHERE " + " AND ".join(filters)) if filters else ""
    result = await db.execute(
        text(f"""
            SELECT id, type_risque, longitude, latitude, code_commune
            FROM risques_geopoints
            {where}
            LIMIT :limit
        """),
        params,
    )
    return [RisqueGeopoint(**row) for row in result.mappings().all()]


@router.get("/{code_commune}", response_model=CommuneRisques)
async def get_risques(code_commune: str, db: AsyncSession = Depends(get_db)):
    """Risques naturels et technologiques d'une commune (source Géorisques)."""
    result = await db.execute(
        text("""
            SELECT code_commune, inondation, seisme, mouvement_terrain,
                   retrait_gonflement_argile, radon, feu_foret, icpe, source_annee
            FROM commune_risques
            WHERE code_commune = :code
        """),
        {"code": code_commune},
    )
    row = result.mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail=f"Aucune donnée risques pour la commune {code_commune}")
    return CommuneRisques(**row)


@router.get("", response_model=list[CommuneRisques])
async def list_risques(
    inondation: bool | None = Query(None, description="Filtrer les communes exposées aux inondations"),
    seisme: bool | None = Query(None, description="Filtrer les communes en zone sismique"),
    feu_foret: bool | None = Query(None, description="Filtrer les communes exposées aux feux de forêt"),
    radon: bool | None = Query(None, description="Filtrer les communes avec risque radon"),
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
):
    """Liste les communes filtrées par type de risque."""
    filters = []
    params: dict = {"limit": limit}

    if inondation is not None:
        filters.append("inondation = :inondation")
        params["inondation"] = inondation
    if seisme is not None:
        filters.append("seisme = :seisme")
        params["seisme"] = seisme
    if feu_foret is not None:
        filters.append("feu_foret = :feu_foret")
        params["feu_foret"] = feu_foret
    if radon is not None:
        filters.append("radon = :radon")
        params["radon"] = radon

    where = ("WHERE " + " AND ".join(filters)) if filters else ""
    result = await db.execute(
        text(f"""
            SELECT code_commune, inondation, seisme, mouvement_terrain,
                   retrait_gonflement_argile, radon, feu_foret, icpe, source_annee
            FROM commune_risques
            {where}
            LIMIT :limit
        """),
        params,
    )
    return [CommuneRisques(**row) for row in result.mappings().all()]
