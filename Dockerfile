FROM python:3.11-slim

WORKDIR /app

# Dépendances système pour psycopg2 et geopandas
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    libgdal-dev \
    && rm -rf /var/lib/apt/lists/*

# Installation Poetry
RUN pip install --no-cache-dir poetry

# Copie des fichiers de dépendances
COPY pyproject.toml poetry.lock* README.md ./

# Installation des dépendances API uniquement (sans dev, bigdata, scraping, utils)
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi --only main --no-root

# Copie du code source
COPY src/ ./src/

EXPOSE 8000

CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
