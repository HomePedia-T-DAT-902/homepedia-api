"""Pydantic schemas for communes and administrative geography."""

from pydantic import BaseModel


class CommuneSearch(BaseModel):
    code_commune: str
    nom: str
    code_postal: str | None = None
    nom_departement: str | None = None
    nom_region: str | None = None


class CommuneDetail(CommuneSearch):
    code_departement: str | None = None
    code_region: str | None = None
    population: int | None = None
    superficie: float | None = None
    densite: float | None = None
    latitude: float | None = None
    longitude: float | None = None


class RegionItem(BaseModel):
    code_region: str
    nom: str


class DepartementItem(BaseModel):
    code_departement: str
    nom: str
    code_region: str | None = None
