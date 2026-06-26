"""Communes router — search and commune details."""

from fastapi import APIRouter, Depends, Query

from src.api.dependencies import get_commune_service
from src.api.schemas import CommuneDetail, CommuneSearch, DepartementItem, RegionItem
from src.api.services.commune_service import CommuneService

router = APIRouter(prefix="/api/v1/communes", tags=["communes"])


@router.get("/search", response_model=list[CommuneSearch])
async def search_communes(
    q: str = Query(..., min_length=2, description="Search by commune name"),
    limit: int = Query(20, ge=1, le=100),
    service: CommuneService = Depends(get_commune_service),
):
    """Search communes by name (ILIKE + trigram)."""
    return await service.search_communes(q, limit)


@router.get("/regions", response_model=list[RegionItem])
async def list_regions(service: CommuneService = Depends(get_commune_service)):
    """List all regions."""
    return await service.list_regions()


@router.get("/departments", response_model=list[DepartementItem])
async def list_departements(
    region: str | None = Query(None, description="Filter by code_region"),
    service: CommuneService = Depends(get_commune_service),
):
    """List departments, optionally filtered by region."""
    return await service.list_departements(region)


@router.get("/{code_commune}", response_model=CommuneDetail)
async def get_commune(code_commune: str, service: CommuneService = Depends(get_commune_service)):
    """Detailed information for a commune."""
    return await service.get_commune(code_commune)
