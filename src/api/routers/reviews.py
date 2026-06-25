"""Router avis — synthèse des avis citoyens (ville-ideale.fr)."""

import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.config import get_db

router = APIRouter(prefix="/api/v1/reviews", tags=["reviews"])


# ── Schémas Pydantic ─────────────────────────────────────────────────────────


class ReviewRatings(BaseModel):
    """Notes moyennes par critère (0-10). Les 9 critères de ville-ideale.fr."""

    environnement: float | None = None
    transports: float | None = None
    securite: float | None = None
    sante: float | None = None
    sports_loisirs: float | None = None
    culture: float | None = None
    enseignement: float | None = None
    commerces: float | None = None
    qualite_vie: float | None = None


class WordCloudEntry(BaseModel):
    mot: str
    frequence: int


class ReviewSummary(BaseModel):
    code_commune: str
    note_globale: float | None = None
    nb_avis: int
    ratings: ReviewRatings | None = None
    # Alimenté par le traitement NLP (spark_reviews.py, P2-4) — vide tant qu'il n'est pas branché.
    word_cloud: list[WordCloudEntry] = []


# ── Endpoints ────────────────────────────────────────────────────────────────


def _as_json(value):
    """Le JSONB peut revenir en str ou déjà désérialisé selon le driver — normalise."""
    if isinstance(value, str):
        return json.loads(value)
    return value


@router.get("/{code_commune}", response_model=ReviewSummary)
async def get_reviews(code_commune: str, db: AsyncSession = Depends(get_db)):
    """Synthèse des avis d'une commune : note globale, nombre d'avis, notes par critère, nuage de mots."""
    result = await db.execute(
        text("""
            SELECT code_commune, note_globale, nb_avis, notes, word_cloud
            FROM city_reviews
            WHERE code_commune = :code
        """),
        {"code": code_commune},
    )
    row = result.mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail=f"Avis pour la commune {code_commune} non trouvés")

    notes = _as_json(row["notes"])
    return ReviewSummary(
        code_commune=row["code_commune"],
        note_globale=row["note_globale"],
        nb_avis=row["nb_avis"],
        ratings=ReviewRatings(**notes) if notes else None,
        word_cloud=_as_json(row["word_cloud"]) or [],
    )
