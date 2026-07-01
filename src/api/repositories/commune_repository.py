"""Repository for accessing commune data."""

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.repositories.interfaces import ICommuneRepository


class CommuneRepository(ICommuneRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def search(self, query: str, limit: int) -> list[dict[str, Any]]:
        result = await self.session.execute(
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
            {"pattern": f"%{query}%", "query": query, "limit": limit},
        )
        return list(result.mappings().all())

    async def get_by_code(self, code_commune: str) -> dict[str, Any] | None:
        result = await self.session.execute(
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
        return dict(row) if row else None

    async def list_regions(self) -> list[dict[str, Any]]:
        result = await self.session.execute(text("SELECT code_region, nom FROM regions ORDER BY nom"))
        return list(result.mappings().all())

    async def list_departements(self, region: str | None = None) -> list[dict[str, Any]]:
        if region:
            result = await self.session.execute(
                text("""
                    SELECT code_departement, nom, code_region
                    FROM departements WHERE code_region = :region ORDER BY nom
                """),
                {"region": region},
            )
        else:
            result = await self.session.execute(
                text("SELECT code_departement, nom, code_region FROM departements ORDER BY nom")
            )
        return list(result.mappings().all())
