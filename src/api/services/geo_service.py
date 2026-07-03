"""Service for geospatial business logic."""

from fastapi import HTTPException

from src.api.repositories.interfaces import IGeoRepository


class GeoService:
    def __init__(self, repository: IGeoRepository):
        self.repository = repository

    def _build_iris_feature(self, row: dict) -> dict:
        return {
            "type": "Feature",
            "properties": {
                "code_iris": row.get("code_iris"),
                "code_commune": row.get("code_commune"),
                "nom_iris": row.get("nom_iris"),
                "type_iris": row.get("type_iris"),
            },
            "geometry": row.get("geometry"),
        }

    async def get_iris(self, bbox: str | None, code_commune: str | None, limit: int) -> dict:
        if not bbox and not code_commune:
            raise HTTPException(status_code=422, detail="bbox or code_commune required")

        if code_commune:
            rows = await self.repository.get_iris_by_commune(code_commune)
            if not rows:
                raise HTTPException(status_code=404, detail=f"No IRIS found for commune {code_commune}")
            return {
                "type": "FeatureCollection",
                "code_commune": code_commune,
                "count": len(rows),
                "features": [self._build_iris_feature(row) for row in rows],
            }

        parts = bbox.split(",")
        if len(parts) != 4:
            raise HTTPException(status_code=422, detail="bbox must contain 4 values: min_lon,min_lat,max_lon,max_lat")

        try:
            min_lon, min_lat, max_lon, max_lat = (float(p) for p in parts)
        except ValueError:
            raise HTTPException(status_code=422, detail="bbox values must be numbers")

        rows = await self.repository.get_iris_in_bbox(min_lon, min_lat, max_lon, max_lat, limit)

        return {
            "type": "FeatureCollection",
            "truncated": len(rows) == limit,
            "count": len(rows),
            "features": [self._build_iris_feature(row) for row in rows],
        }

    async def get_iris_by_commune(self, code_commune: str) -> dict:
        rows = await self.repository.get_iris_by_commune(code_commune)
        if not rows:
            raise HTTPException(status_code=404, detail=f"No IRIS found for commune {code_commune}")

        return {
            "type": "FeatureCollection",
            "code_commune": code_commune,
            "count": len(rows),
            "features": [self._build_iris_feature(row) for row in rows],
        }
