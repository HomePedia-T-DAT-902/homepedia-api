"""Export le schéma OpenAPI depuis l'application FastAPI.

Usage:
    python scripts/export_openapi.py

Génère openapi.json à la racine du repo.
Ce fichier doit être committé — il sert de contrat API.
"""

import json
import sys
from pathlib import Path

# Ajouter le répertoire racine au path pour les imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.api.main import app

OUTPUT = Path(__file__).resolve().parent.parent / "openapi.json"


def main() -> None:
    spec = app.openapi()
    OUTPUT.write_text(
        json.dumps(spec, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"OpenAPI spec exported to {OUTPUT}")


if __name__ == "__main__":
    main()
