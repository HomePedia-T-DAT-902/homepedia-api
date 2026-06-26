"""Service for commune business logic."""

from fastapi import HTTPException

from src.api.repositories.interfaces import ICommuneRepository


class CommuneService:
    def __init__(self, repository: ICommuneRepository):
        self.repository = repository

    async def search_communes(self, query: str, limit: int) -> list[dict]:
        return await self.repository.search(query, limit)

    async def get_commune(self, code_commune: str) -> dict:
        commune = await self.repository.get_by_code(code_commune)
        if not commune:
            raise HTTPException(status_code=404, detail=f"Commune {code_commune} not found")
        return commune

    async def list_regions(self) -> list[dict]:
        return await self.repository.list_regions()

    async def list_departements(self, region: str | None = None) -> list[dict]:
        return await self.repository.list_departements(region)
