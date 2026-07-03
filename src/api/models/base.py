"""SQLAlchemy ORM models definition for the Homepedia API."""

from datetime import date
from typing import Any

from geoalchemy2 import Geometry
from sqlalchemy import Date, Float, ForeignKey, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""

    pass


class Region(Base):
    __tablename__ = "regions"

    code_region: Mapped[str] = mapped_column(String(3), primary_key=True)
    nom: Mapped[str] = mapped_column(String(255), nullable=False)
    geom: Mapped[Any] = mapped_column(Geometry("MULTIPOLYGON", srid=4326), nullable=True)

    departements: Mapped[list["Departement"]] = relationship(back_populates="region")
    communes: Mapped[list["Commune"]] = relationship(back_populates="region")


class Departement(Base):
    __tablename__ = "departements"

    code_departement: Mapped[str] = mapped_column(String(3), primary_key=True)
    nom: Mapped[str] = mapped_column(String(255), nullable=False)
    code_region: Mapped[str | None] = mapped_column(ForeignKey("regions.code_region"))
    geom: Mapped[Any] = mapped_column(Geometry("MULTIPOLYGON", srid=4326), nullable=True)

    region: Mapped["Region"] = relationship(back_populates="departements")
    communes: Mapped[list["Commune"]] = relationship(back_populates="departement")


class Commune(Base):
    __tablename__ = "communes"

    code_commune: Mapped[str] = mapped_column(String(5), primary_key=True)
    nom: Mapped[str] = mapped_column(String(255), nullable=False)
    code_departement: Mapped[str | None] = mapped_column(ForeignKey("departements.code_departement"))
    code_region: Mapped[str | None] = mapped_column(ForeignKey("regions.code_region"))
    code_postal: Mapped[str | None] = mapped_column(String(5))
    population: Mapped[int | None] = mapped_column(Integer)
    superficie: Mapped[float | None] = mapped_column(Float)
    densite: Mapped[float | None] = mapped_column(Float)
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    geom: Mapped[Any] = mapped_column(Geometry("MULTIPOLYGON", srid=4326), nullable=True)
    geom_simplified: Mapped[Any] = mapped_column(Geometry("MULTIPOLYGON", srid=4326), nullable=True)

    region: Mapped["Region"] = relationship(back_populates="communes")
    departement: Mapped["Departement"] = relationship(back_populates="communes")


class DvfTransaction(Base):
    __tablename__ = "dvf_transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_mutation: Mapped[str | None] = mapped_column(String(20))
    code_commune: Mapped[str | None] = mapped_column(ForeignKey("communes.code_commune"))
    date_mutation: Mapped[date | None] = mapped_column(Date)
    nature_mutation: Mapped[str | None] = mapped_column(String(30))
    type_local: Mapped[str | None] = mapped_column(String(50))
    valeur_fonciere: Mapped[float | None] = mapped_column(Float)
    surface_reelle_bati: Mapped[float | None] = mapped_column(Float)
    nb_pieces: Mapped[int | None] = mapped_column(Integer)
    surface_terrain: Mapped[float | None] = mapped_column(Float)
    prix_m2: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    latitude: Mapped[float | None] = mapped_column(Float)
    geom: Mapped[Any] = mapped_column(Geometry("POINT", srid=4326), nullable=True)


class PriceTrend(Base):
    __tablename__ = "price_trends"

    code_commune: Mapped[str] = mapped_column(ForeignKey("communes.code_commune"), primary_key=True)
    annee: Mapped[int] = mapped_column(Integer, primary_key=True)
    trimestre: Mapped[int] = mapped_column(Integer, primary_key=True)
    type_local: Mapped[str] = mapped_column(String(50), primary_key=True)
    prix_median_m2: Mapped[float | None] = mapped_column(Float)
    nb_transactions: Mapped[int | None] = mapped_column(Integer)
    variation_annuelle_pct: Mapped[float | None] = mapped_column(Float)


class BpeCommuneStat(Base):
    __tablename__ = "bpe_commune_stats"

    code_commune: Mapped[str] = mapped_column(ForeignKey("communes.code_commune"), primary_key=True)
    nb_equipements_total: Mapped[int | None] = mapped_column(Integer)
    nb_a: Mapped[int | None] = mapped_column(Integer)
    nb_b: Mapped[int | None] = mapped_column(Integer)
    nb_c: Mapped[int | None] = mapped_column(Integer)
    nb_d: Mapped[int | None] = mapped_column(Integer)
    nb_e: Mapped[int | None] = mapped_column(Integer)
    nb_f: Mapped[int | None] = mapped_column(Integer)
    nb_maternelles: Mapped[int | None] = mapped_column(Integer)
    nb_primaires: Mapped[int | None] = mapped_column(Integer)
    nb_creches: Mapped[int | None] = mapped_column(Integer)
    nb_colleges: Mapped[int | None] = mapped_column(Integer)
    nb_lycees: Mapped[int | None] = mapped_column(Integer)
    nb_medecins: Mapped[int | None] = mapped_column(Integer)
    nb_pharmacies: Mapped[int | None] = mapped_column(Integer)
    nb_urgences: Mapped[int | None] = mapped_column(Integer)
    nb_supermarches: Mapped[int | None] = mapped_column(Integer)
    nb_hypermarches: Mapped[int | None] = mapped_column(Integer)
    nb_gares: Mapped[int | None] = mapped_column(Integer)
