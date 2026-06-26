"""Pydantic schemas for GeoJSON responses."""

from typing import Any

from pydantic import BaseModel


class GeoJSONFeature(BaseModel):
    type: str = "Feature"
    properties: dict[str, Any]
    geometry: dict[str, Any]


class GeoJSONFeatureCollection(BaseModel):
    type: str = "FeatureCollection"
    code_commune: str | None = None
    truncated: bool | None = None
    count: int
    features: list[GeoJSONFeature]
