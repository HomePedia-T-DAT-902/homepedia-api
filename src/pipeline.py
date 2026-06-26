"""
Orchestrateur du pipeline de données Homepedia.

Remplace les 26 targets Makefile par une seule interface CLI cohérente.

Usage :
    # Pipeline complet
    python -m src.pipeline run-all

    # Sources spécifiques uniquement
    python -m src.pipeline run --sources geo bpe

    # Tout sauf les sources lourdes
    python -m src.pipeline run-all --skip dvf dpe

    # Relancer sans re-télécharger (données raw déjà présentes)
    python -m src.pipeline run --sources bpe --skip-download

    # Étapes individuelles
    python -m src.pipeline download --sources geo
    python -m src.pipeline preprocess --sources bpe
    python -m src.pipeline process --sources geo bpe
    python -m src.pipeline load --sources geo bpe
"""

import argparse
import logging
import sys
import time

from src.sources.base import DataSource
from src.sources.bpe.source import BPESource
from src.sources.cadastre.source import CadastreSource
from src.sources.crime.source import CrimeSource
from src.sources.dpe.source import DPESource
from src.sources.dvf.source import DVFSource
from src.sources.geo.source import GEOSource
from src.sources.iris.source import IRISSource

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ── Registre des sources disponibles ─────────────────────────────────────────
# Ajouter une nouvelle source = une ligne ici
SOURCES: dict[str, type[DataSource]] = {
    "geo": GEOSource,
    "bpe": BPESource,
    "dvf": DVFSource,
    "dpe": DPESource,
    "iris": IRISSource,
    "cadastre": CadastreSource,
    "crime": CrimeSource,
}


def _resolve_sources(names: list[str] | None, skip: list[str] | None) -> dict[str, DataSource]:
    """Retourne les instances des sources à exécuter, dans l'ordre déclaré dans SOURCES."""
    available = list(SOURCES.keys())

    selected = names if names else available
    unknown = [s for s in selected if s not in SOURCES]
    if unknown:
        logger.error(f"Sources inconnues : {unknown}. Disponibles : {available}")
        sys.exit(1)

    excluded = set(skip or [])
    final = [s for s in selected if s not in excluded]

    if not final:
        logger.error("Aucune source sélectionnée après exclusions.")
        sys.exit(1)

    logger.info(f"Sources sélectionnées : {final}")
    return {name: SOURCES[name]() for name in final}


def _run_step(source_name: str, source: DataSource, step: str) -> bool:
    """Exécute une étape sur une source. Retourne False si erreur."""
    fn = getattr(source, step)
    try:
        logger.info(f"▶ [{source_name}] {step}()")
        t0 = time.time()
        fn()
        elapsed = time.time() - t0
        logger.info(f"✓ [{source_name}] {step}() — {elapsed:.1f}s")
        return True
    except Exception as e:
        logger.error(f"✗ [{source_name}] {step}() ÉCHEC : {e}")
        return False


# ── Commandes ─────────────────────────────────────────────────────────────────


def cmd_run(args) -> None:
    """Exécute le pipeline complet (ou les étapes sélectionnées) sur les sources choisies."""
    sources = _resolve_sources(args.sources, args.skip)
    steps = ["preprocess", "process", "load"] if args.skip_download else ["download", "preprocess", "process", "load"]
    errors = []

    for name, source in sources.items():
        logger.info(f"\n{'=' * 50}")
        logger.info(f"SOURCE : {name.upper()}")
        logger.info(f"{'=' * 50}")
        for step in steps:
            if not _run_step(name, source, step):
                errors.append(f"{name}.{step}")
                logger.warning(f"[{name}] Pipeline interrompu à l'étape '{step}'")
                break

    _print_summary(errors)


def cmd_step(step: str, args) -> None:
    """Exécute une seule étape sur les sources choisies."""
    sources = _resolve_sources(args.sources, args.skip)
    errors = []
    for name, source in sources.items():
        if not _run_step(name, source, step):
            errors.append(f"{name}.{step}")
    _print_summary(errors)


def _print_summary(errors: list[str]) -> None:
    logger.info(f"\n{'=' * 50}")
    if errors:
        logger.error(f"Pipeline terminé avec {len(errors)} erreur(s) : {errors}")
        sys.exit(1)
    else:
        logger.info("Pipeline terminé avec succès ✓")


# ── CLI ───────────────────────────────────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m src.pipeline",
        description="Orchestrateur du pipeline de données Homepedia.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    source_args = argparse.ArgumentParser(add_help=False)
    source_args.add_argument(
        "--sources", nargs="+", metavar="SOURCE", help=f"Sources à traiter. Disponibles : {list(SOURCES.keys())}"
    )
    source_args.add_argument("--skip", nargs="+", metavar="SOURCE", help="Sources à exclure.")

    # run / run-all
    p_run = subparsers.add_parser("run", parents=[source_args], help="Pipeline complet sur les sources choisies.")
    p_run.add_argument("--skip-download", action="store_true", help="Skip le download (données raw déjà présentes).")
    subparsers.add_parser("run-all", parents=[source_args], help="Pipeline complet sur toutes les sources disponibles.")

    # Étapes individuelles
    for step in ("download", "preprocess", "process", "load"):
        subparsers.add_parser(step, parents=[source_args], help=f"Exécute uniquement l'étape '{step}'.")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "run-all":
        args.skip_download = False
        cmd_run(args)
    elif args.command == "run":
        cmd_run(args)
    else:
        cmd_step(args.command, args)


if __name__ == "__main__":
    main()
