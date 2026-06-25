"""JSON Lines read/write helpers for the ville-ideale source stages."""

import json
from pathlib import Path


def read_jsonl(path: Path) -> list[dict]:
    """Read a JSON Lines file into a list of dicts (empty list if the file is absent)."""
    if not Path(path).exists():
        return []
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: list[dict]) -> None:
    """Write a list of dicts as a JSON Lines file (creating parent dirs as needed)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False))
            f.write("\n")
