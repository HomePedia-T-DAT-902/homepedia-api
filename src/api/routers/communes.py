"""Router communes — recherche et fiche commune."""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.config import get_db

router = APIRouter(prefix="/api/v1/communes", tags=["communes"])


# ── Schémas Pydantic ─────────────────────────────────────────────────────────


class CommuneSearch(BaseModel):
    code_commune: str
    nom: str
    code_postal: str | None = None
    nom_departement: str | None = None
    nom_region: str | None = None


class CommuneDetail(CommuneSearch):
    code_departement: str | None = None
    code_region: str | None = None
    population: int | None = None
    superficie: float | None = None
    densite: float | None = None
    latitude: float | None = None
    longitude: float | None = None


class RegionItem(BaseModel):
    code_region: str
    nom: str


class DepartementItem(BaseModel):
    code_departement: str
    nom: str
    code_region: str | None = None


# ── Endpoints ────────────────────────────────────────────────────────────────


@router.get("/search", response_model=list[CommuneSearch])
async def search_communes(
    q: str = Query(..., min_length=2, description="Recherche par nom de commune"),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Recherche de communes par nom (ILIKE + trigram)."""
    result = await db.execute(
        text("""
            SELECT c.code_commune, c.nom, c.code_postal,
                   d.nom AS nom_departement, r.nom AS nom_region
            FROM communes c
            LEFT JOIN departements d ON c.code_departement = d.code_departement
            LEFT JOIN regions r ON c.code_region = r.code_region
            WHERE c.nom ILIKE :pattern
            ORDER BY similarity(c.nom, :query) DESC, c.population DESC NULLS LAST
            LIMIT :limit
        """),
        {"pattern": f"%{q}%", "query": q, "limit": limit},
    )
    rows = result.mappings().all()
    return [CommuneSearch(**row) for row in rows]


@router.get("/regions", response_model=list[RegionItem])
async def list_regions(db: AsyncSession = Depends(get_db)):
    """Liste toutes les régions."""
    result = await db.execute(text("SELECT code_region, nom FROM regions ORDER BY nom"))
    return [RegionItem(**row) for row in result.mappings().all()]


@router.get("/departments", response_model=list[DepartementItem])
async def list_departements(
    region: str | None = Query(None, description="Filtrer par code_region"),
    db: AsyncSession = Depends(get_db),
):
    """Liste les départements, optionnellement filtrés par région."""
    if region:
        result = await db.execute(
            text("""
                SELECT code_departement, nom, code_region
                FROM departements WHERE code_region = :region ORDER BY nom
            """),
            {"region": region},
        )
    else:
        result = await db.execute(text("SELECT code_departement, nom, code_region FROM departements ORDER BY nom"))
    return [DepartementItem(**row) for row in result.mappings().all()]


@router.get("/{code_commune}", response_model=CommuneDetail)
async def get_commune(code_commune: str, db: AsyncSession = Depends(get_db)):
    """Fiche détaillée d'une commune."""
    result = await db.execute(
        text("""
            SELECT c.code_commune, c.nom, c.code_postal,
                   c.code_departement, c.code_region,
                   c.population, c.superficie, c.densite,
                   c.latitude, c.longitude,
                   d.nom AS nom_departement, r.nom AS nom_region
            FROM communes c
            LEFT JOIN departements d ON c.code_departement = d.code_departement
            LEFT JOIN regions r ON c.code_region = r.code_region
            WHERE c.code_commune = :code
        """),
        {"code": code_commune},
    )
    row = result.mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail=f"Commune {code_commune} non trouvée")
    return CommuneDetail(**row)
