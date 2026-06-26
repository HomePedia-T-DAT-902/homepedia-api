"""Tests for the communes router."""

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.main import app


@pytest.mark.asyncio
async def test_search_communes_requires_query():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/v1/communes/search")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_list_regions():
    from src.api.dependencies import get_commune_service

    class MockCommuneService:
        async def list_regions(self):
            return []

    app.dependency_overrides[get_commune_service] = lambda: MockCommuneService()
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.get("/api/v1/communes/regions")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
    finally:
        app.dependency_overrides.pop(get_commune_service, None)
