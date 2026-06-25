"""
Interface abstraite commune à toutes les sources de données Homepedia.

Chaque source (BPE, DVF, DPE, GEO...) implémente cette interface en 4 étapes :

    download()    → télécharge les fichiers bruts             → data/raw/
    preprocess()  → valide et nettoie la donnée brute         → data/raw/ (nettoyé)
    process()     → job Spark, agrégations, enrichissement    → data/processed/ (Parquet)
    load()        → charge le Parquet en PostgreSQL           → DB

Utilisation dans l'orchestrateur :

    for source in [BPESource(), GEOSource(), DVFSource()]:
        source.download()
        source.preprocess()
        source.process()
        source.load()
"""

from abc import ABC, abstractmethod
from pathlib import Path


class DataSource(ABC):
    def __init__(self, raw_dir: Path = Path("data/raw"), processed_dir: Path = Path("data/processed")):
        self.raw_dir = raw_dir
        self.processed_dir = processed_dir

    @abstractmethod
    def download(self) -> None:
        """Télécharge les fichiers bruts depuis la source externe vers data/raw/."""
        ...

    @abstractmethod
    def preprocess(self) -> None:
        """
        Valide et nettoie les fichiers bruts avant le job Spark.
        Vérifie : présence du fichier, colonnes attendues, encoding, valeurs nulles.
        Lève une ValueError si la donnée n'est pas exploitable.
        """
        ...

    @abstractmethod
    def process(self) -> None:
        """Lance le job Spark : nettoyage, agrégations, enrichissement → Parquet."""
        ...

    @abstractmethod
    def load(self) -> None:
        """Charge le Parquet produit par process() en PostgreSQL."""
        ...

    def run(self, skip_download: bool = False) -> None:
        """
        Exécute le pipeline complet dans l'ordre.
        skip_download=True permet de sauter le téléchargement si la raw data est déjà là.
        """
        if not skip_download:
            self.download()
        self.preprocess()
        self.process()
        self.load()
