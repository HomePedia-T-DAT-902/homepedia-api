"""Package des schémas Pydantic."""

from src.api.schemas.commune import CommuneDetail, CommuneSearch, DepartementItem, RegionItem
from src.api.schemas.geo import GeoJSONFeature, GeoJSONFeatureCollection
from src.api.schemas.pagination import PaginatedResponse

__all__ = [
    "CommuneSearch",
    "CommuneDetail",
    "RegionItem",
    "DepartementItem",
    "GeoJSONFeature",
    "GeoJSONFeatureCollection",
    "PaginatedResponse",
]
