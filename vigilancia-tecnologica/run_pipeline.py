"""Punto de entrada del pipeline de extracción y análisis inicial."""

from app.analysis import analyze_corpus
from app.build_dataset import build_dataset


if __name__ == "__main__":
    build_dataset()
    analyze_corpus()
