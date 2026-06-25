"""Router avis — synthèse des avis citoyens (ville-ideale.fr).

Lecture *cache-first* : on sert depuis la table ``city_reviews`` si la commune y est et
n'est pas trop ancienne (TTL). Sinon, on scrape **cette commune à la demande** (lazy
loading), on la stocke, puis on la renvoie. Les avis sont donc récupérés au fil des
visites — un filet de requêtes plutôt qu'un crawl massif qui se fait rate-limiter.
"""

import asyncio
import datetime as dt
import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.config import get_db
from src.sources.ville_ideale.on_demand import ThrottledError, fetch_commune

router = APIRouter(prefix="/api/v1/reviews", tags=["reviews"])

# Re-scrape a commune at most once per this window (reviews change slowly).
CACHE_TTL_DAYS = 30


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
    word_cloud: list[WordCloudEntry] = []


# ── Helpers ──────────────────────────────────────────────────────────────────


def _as_json(value):
    """Le JSONB peut revenir en str ou déjà désérialisé selon le driver — normalise."""
    if isinstance(value, str):
        return json.loads(value)
    return value


def _build_summary(code_commune, note_globale, nb_avis, notes, word_cloud) -> ReviewSummary:
    return ReviewSummary(
        code_commune=code_commune,
        note_globale=note_globale,
        nb_avis=nb_avis or 0,
        ratings=ReviewRatings(**notes) if notes else None,
        word_cloud=word_cloud or [],
    )


def _summary_from_row(code_commune, row) -> ReviewSummary:
    return _build_summary(
        code_commune, row["note_globale"], row["nb_avis"], _as_json(row["notes"]), _as_json(row["word_cloud"])
    )


def _is_fresh(date_scraping) -> bool:
    if date_scraping is None:
        return False
    if isinstance(date_scraping, str):
        date_scraping = dt.date.fromisoformat(date_scraping[:10])
    return date_scraping >= dt.date.today() - dt.timedelta(days=CACHE_TTL_DAYS)


_UPSERT_SQL = text("""
    INSERT INTO city_reviews
        (code_commune, note_globale, nb_avis, notes, avis, word_cloud, rang, avis_complets, date_scraping)
    VALUES (:code, :note, :nb, CAST(:notes AS JSONB), CAST(:avis AS JSONB), CAST(:cloud AS JSONB),
            :rang, :complets, :date)
    ON CONFLICT (code_commune) DO UPDATE SET
        note_globale = EXCLUDED.note_globale, nb_avis = EXCLUDED.nb_avis,
        notes = EXCLUDED.notes, avis = EXCLUDED.avis, word_cloud = EXCLUDED.word_cloud,
        rang = EXCLUDED.rang, avis_complets = EXCLUDED.avis_complets, date_scraping = EXCLUDED.date_scraping
""")


async def _store(db: AsyncSession, record: dict) -> None:
    await db.execute(
        _UPSERT_SQL,
        {
            "code": record["code_commune"],
            "note": record["note_globale"],
            "nb": record["nb_avis"],
            "notes": json.dumps(record["notes"]),
            "avis": json.dumps(record["avis"]),
            "cloud": json.dumps(record["word_cloud"]),
            "rang": record["rang"],
            "complets": record["avis_complets"],
            "date": dt.date.fromisoformat(record["date_scraping"][:10]),
        },
    )
    await db.commit()


# ── Endpoint ─────────────────────────────────────────────────────────────────


@router.get("/{code_commune}", response_model=ReviewSummary)
async def get_reviews(code_commune: str, db: AsyncSession = Depends(get_db)):
    """Synthèse des avis d'une commune (cache-first, scrape à la demande sur cache miss)."""
    result = await db.execute(
        text("""
            SELECT note_globale, nb_avis, notes, word_cloud, date_scraping
            FROM city_reviews WHERE code_commune = :code
        """),
        {"code": code_commune},
    )
    row = result.mappings().first()
    if row and _is_fresh(row["date_scraping"]):
        return _summary_from_row(code_commune, row)

    # Cache miss or stale entry → scrape this commune on demand (off the event loop).
    try:
        record = await asyncio.to_thread(fetch_commune, code_commune)
    except ThrottledError as exc:
        if row:  # rate-limited but we have an older copy → serve it rather than failing
            return _summary_from_row(code_commune, row)
        raise HTTPException(
            status_code=503,
            detail="ville-ideale momentanément indisponible (limite de requêtes), réessayez plus tard",
        ) from exc

    if record is None:
        raise HTTPException(status_code=404, detail=f"Pas d'avis pour la commune {code_commune}")

    try:
        await _store(db, record)
    except Exception:
        await db.rollback()  # e.g. commune absent from the communes reference — still return the data

    return _build_summary(
        code_commune, record["note_globale"], record["nb_avis"], record["notes"], record["word_cloud"]
    )
