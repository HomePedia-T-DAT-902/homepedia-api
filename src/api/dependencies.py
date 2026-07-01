"""FastAPI dependencies for injecting services and repositories."""

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.config import get_db
from src.api.repositories.commune_repository import CommuneRepository
from src.api.repositories.geo_repository import GeoRepository
from src.api.repositories.interfaces import ICommuneRepository, IGeoRepository
from src.api.services.commune_service import CommuneService
from src.api.services.geo_service import GeoService


def get_commune_repository(db: AsyncSession = Depends(get_db)) -> ICommuneRepository:
    return CommuneRepository(db)


def get_geo_repository(db: AsyncSession = Depends(get_db)) -> IGeoRepository:
    return GeoRepository(db)


def get_commune_service(repository: ICommuneRepository = Depends(get_commune_repository)) -> CommuneService:
    return CommuneService(repository)


def get_geo_service(repository: IGeoRepository = Depends(get_geo_repository)) -> GeoService:
    return GeoService(repository)
