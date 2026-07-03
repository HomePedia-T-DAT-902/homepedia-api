"""Repository interfaces."""

from abc import ABC, abstractmethod
from typing import Any


class ICommuneRepository(ABC):
    @abstractmethod
    async def search(self, query: str, limit: int) -> list[dict[str, Any]]:
        pass

    @abstractmethod
    async def get_by_code(self, code_commune: str) -> dict[str, Any] | None:
        pass

    @abstractmethod
    async def list_regions(self) -> list[dict[str, Any]]:
        pass

    @abstractmethod
    async def list_departements(self, region: str | None = None) -> list[dict[str, Any]]:
        pass


class IGeoRepository(ABC):
    @abstractmethod
    async def get_iris_in_bbox(
        self, min_lon: float, min_lat: float, max_lon: float, max_lat: float, limit: int
    ) -> list[dict[str, Any]]:
        pass

    @abstractmethod
    async def get_iris_by_commune(self, code_commune: str) -> list[dict[str, Any]]:
        pass
