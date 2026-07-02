"""Repository for accessing geospatial data."""

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.repositories.interfaces import IGeoRepository


class GeoRepository(IGeoRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_iris_in_bbox(
        self, min_lon: float, min_lat: float, max_lon: float, max_lat: float, limit: int
    ) -> list[dict[str, Any]]:
        result = await self.session.execute(
            text("""
                SELECT i.code_iris, i.code_commune, i.nom_iris, i.type_iris,
                       ST_AsGeoJSON(i.geom)::json AS geometry
                FROM iris_quartiers i
                WHERE i.geom && ST_MakeEnvelope(:min_lon, :min_lat, :max_lon, :max_lat, 4326)
                LIMIT :limit
            """),
            {"min_lon": min_lon, "min_lat": min_lat, "max_lon": max_lon, "max_lat": max_lat, "limit": limit},
        )
        return list(result.mappings().all())

    async def get_iris_by_commune(self, code_commune: str) -> list[dict[str, Any]]:
        result = await self.session.execute(
            text("""
                SELECT i.code_iris, i.code_commune, i.nom_iris, i.type_iris,
                       ST_AsGeoJSON(i.geom)::json AS geometry
                FROM iris_quartiers i
                WHERE i.code_commune = :code_commune
                ORDER BY i.code_iris
            """),
            {"code_commune": code_commune},
        )
        return list(result.mappings().all())
