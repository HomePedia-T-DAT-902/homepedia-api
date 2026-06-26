"""Stage 3/4 — process: enrich each commune with a word cloud.

Reads the preprocessed records and adds a ``word_cloud`` field computed from the reviews'
free text:

    data/processed/ville_ideale/communes.jsonl
        -> data/processed/ville_ideale/communes_enriched.jsonl

This is the "fréquences mots basique" enrichment (backlog P2-4). At ville-ideale's scale
a full Spark/spaCy pipeline is unnecessary: tokenise, drop French stop words, count. The
NLP logic is kept inside this folder (stdlib only) so the pipeline stays self-contained.

Usage:
    python -m src.sources.ville_ideale.process
"""

import argparse
import logging
import re
from collections import Counter

from pathlib import Path

from src.sources.ville_ideale import config
from src.sources.ville_ideale.io_utils import read_jsonl, write_jsonl

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Minimal French stop-word list. Words elided with an apostrophe (l', d', c'…) reduce to a
# single letter after tokenisation and are removed by the length filter, so they are not
# listed here.
STOPWORDS_FR = frozenset(
    """
    alors au aux avec ce ces cet cette dans de des du elle elles en encore est et eux
    ici il ils je la le les leur leurs lui ma mais me mes moi mon ne nos notre nous on
    ont ou où par pas peu plus pour quel quelle quelles quels qui sa sans ses si son sont
    sur ta te tes toi ton tous tout toute toutes tu un une vos votre vous tres très trop
    bien mal aussi comme donc car ni or que quoi dont entre vers chez sous avant apres
    après pendant depuis contre selon ainsi cela celui celle ceux celles meme même autre
    autres chaque tel telle aucun aucune avait avaient ait fut furent etre être suis es
    sommes etes êtes sera seront serait etait était etaient étaient ai as avons avez
    faire fait font faut peut peuvent doit doivent va vais vont y a deja déjà non oui rien
    quelque quelques beaucoup vraiment surtout assez presque toujours jamais souvent ville
    """.split()
)

# Letters only (incl. French accents); apostrophes/digits/punctuation split tokens.
_TOKEN_RE = re.compile(r"[a-zàâäçéèêëîïôöùûüÿœæ]+", re.IGNORECASE)
_MIN_LENGTH = 3


def tokenize(text: str) -> list[str]:
    """Lower-case a string and return tokens of >=3 letters that are not stop words."""
    if not text:
        return []
    return [
        token for token in _TOKEN_RE.findall(text.lower()) if len(token) >= _MIN_LENGTH and token not in STOPWORDS_FR
    ]


def word_cloud(texts, top_n: int = 30) -> list[dict]:
    """Return ``[{"mot": w, "frequence": n}, ...]`` for the most frequent words."""
    counter: Counter[str] = Counter()
    for text in texts:
        counter.update(tokenize(text))
    return [{"mot": word, "frequence": count} for word, count in counter.most_common(top_n)]


def enrich(records: list[dict], top_n: int = 30) -> list[dict]:
    """Add a ``word_cloud`` field to each commune record from its reviews' free text."""
    for record in records:
        texts = [
            text
            for avis in record.get("avis", [])
            for text in (avis.get("points_positifs"), avis.get("points_negatifs"))
        ]
        record["word_cloud"] = word_cloud(texts, top_n=top_n)
    return records


def run(raw_dir: Path = config.RAW_DIR, processed_dir: Path = config.PROCESSED_DIR) -> None:
    records = read_jsonl(raw_dir / config.COMMUNES_FILE)
    if not records:
        logger.warning("No preprocessed records in %s — run preprocess first", raw_dir / config.COMMUNES_FILE)
        return
    enrich(records)
    out = processed_dir / config.ENRICHED_FILE
    write_jsonl(out, records)
    logger.info("Enriched %d communes with word clouds -> %s", len(records), out)


def main() -> None:
    argparse.ArgumentParser(description="Add review word clouds to preprocessed communes.").parse_args()
    run()


if __name__ == "__main__":
    main()
