"""
Script 1 — Télécharger le corpus depuis arXiv.

Utilisation :
    python scripts/1_collecter.py                    # 10 000 articles (~5 min)
    python scripts/1_collecter.py --par-categorie 200   # version rapide de test
    python scripts/1_collecter.py --par-categorie 6250  # 50 000 articles (~25 min)

Le fichier produit est data/brut/corpus_arxiv.jsonl. Tant qu'il existe, il est
inutile de relancer ce script.
"""

import argparse
import sys
from pathlib import Path

# Rend les modules du projet importables quel que soit le dossier d'appel.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import config
from src.collecte import collecter


def main() -> None:
    analyseur = argparse.ArgumentParser(description="Collecte d'articles arXiv")
    analyseur.add_argument(
        "--par-categorie",
        type=int,
        default=config.NB_DOCS_PAR_CATEGORIE,
        help="nombre d'articles à récupérer par catégorie",
    )
    analyseur.add_argument(
        "--categories",
        nargs="+",
        default=config.CATEGORIES_ARXIV,
        help="liste des catégories arXiv (ex. cs.LG cs.CL)",
    )
    arguments = analyseur.parse_args()

    total_vise = arguments.par_categorie * len(arguments.categories)
    duree_estimee = (total_vise / config.TAILLE_PAGE_ARXIV) * config.DELAI_ENTRE_REQUETES

    print("=" * 70)
    print("COLLECTE DU CORPUS ARXIV")
    print("=" * 70)
    print(f"Catégories       : {', '.join(arguments.categories)}")
    print(f"Par catégorie    : {arguments.par_categorie}")
    print(f"Total visé       : {total_vise} articles (avant dédoublonnage)")
    print(f"Durée estimée    : {duree_estimee / 60:.1f} minutes")
    print(f"Fichier de sortie: {config.FICHIER_CORPUS}")
    print()

    total = collecter(
        categories=arguments.categories,
        nb_par_categorie=arguments.par_categorie,
    )

    if total == 0:
        print("\nAucun article récupéré. Vérifie ta connexion internet.")
        sys.exit(1)

    print("\nÉtape suivante :  python scripts/2_indexer.py")


if __name__ == "__main__":
    main()
