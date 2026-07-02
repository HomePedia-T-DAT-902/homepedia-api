"""Geo router — GeoJSON endpoints (IRIS boundaries)."""

from fastapi import APIRouter, Depends, Query

from src.api.dependencies import get_geo_service
from src.api.schemas.geo import GeoJSONFeatureCollection
from src.api.services.geo_service import GeoService

router = APIRouter(prefix="/api/v1/geo", tags=["geo"])


@router.get("/iris", response_model=GeoJSONFeatureCollection)
async def get_iris(
    bbox: str | None = Query(None, description="Bounding box: min_lon,min_lat,max_lon,max_lat"),
    code_commune: str | None = Query(None, description="INSEE commune code (5 chars)"),
    limit: int = Query(5000, ge=1, le=50000),
    service: GeoService = Depends(get_geo_service),
):
    """Return IRIS boundaries filtered by bbox or code_commune as GeoJSON."""
    return await service.get_iris(bbox, code_commune, limit)


@router.get("/communes/{code_commune}/iris", response_model=GeoJSONFeatureCollection)
async def get_iris_by_commune(
    code_commune: str,
    service: GeoService = Depends(get_geo_service),
):
    """Return all IRIS boundaries for a given commune as GeoJSON."""
    return await service.get_iris_by_commune(code_commune)
