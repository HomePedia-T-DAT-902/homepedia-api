"""Geo router — GeoJSON endpoints (cadastral parcels, IRIS, boundaries)."""

from fastapi import APIRouter, Depends, Query

from src.api.dependencies import get_geo_service
from src.api.schemas.geo import GeoJSONFeature, GeoJSONFeatureCollection
from src.api.services.geo_service import GeoService

router = APIRouter(prefix="/api/v1/geo", tags=["geo"])


@router.get("/parcelles", response_model=GeoJSONFeatureCollection)
async def get_parcelles(
    bbox: str = Query(..., description="Bounding box: min_lon,min_lat,max_lon,max_lat"),
    limit: int = Query(5000, ge=1, le=50000),
    service: GeoService = Depends(get_geo_service),
):
    """Returns cadastral parcels within a bounding box as GeoJSON."""
    return await service.get_parcelles(bbox, limit)


@router.get("/parcelles/{parcel_id}", response_model=GeoJSONFeature)
async def get_parcelle(
    parcel_id: str,
    service: GeoService = Depends(get_geo_service),
):
    """Returns parcel details by its Etalab ID."""
    return await service.get_parcelle(parcel_id)


@router.get("/communes/{code_commune}/parcelles", response_model=GeoJSONFeatureCollection)
async def get_parcelles_by_commune(
    code_commune: str,
    limit: int = Query(5000, ge=1, le=50000),
    service: GeoService = Depends(get_geo_service),
):
    """Returns all cadastral parcels for a commune as GeoJSON."""
    return await service.get_parcelles_by_commune(code_commune, limit)


# ── IRIS (infra-communal districts) ────────────────────────────────────────


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
