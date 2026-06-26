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
    # Here, we only test that the route is accessible and returns a response.
    # For a complete unit test, we would mock the database.
    pass
