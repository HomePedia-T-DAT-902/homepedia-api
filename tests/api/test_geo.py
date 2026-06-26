"""Tests for the geo router."""

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.main import app


@pytest.mark.asyncio
async def test_get_parcelles_requires_bbox():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/v1/geo/parcelles")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_get_parcelles_invalid_bbox():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/v1/geo/parcelles?bbox=invalid")
    assert response.status_code == 422
