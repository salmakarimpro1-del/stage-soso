"""
Script 2 — Construire les deux index.

C'est la phase hors ligne : lente, exécutée une seule fois. Elle produit
quatre fichiers dans data/index/ :

    index.faiss    les vecteurs organisés pour la recherche rapide
    passages.json  le texte et les métadonnées de chaque passage
    vecteurs.npy   les vecteurs bruts (pour rejouer des expériences d'index)
    bm25.pkl       l'index lexical de comparaison

Utilisation :
    python scripts/2_indexer.py
    python scripts/2_indexer.py --sans-bm25     # index sémantique seulement
"""

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import config
from src.baseline_bm25 import MoteurLexical
from src.collecte import charger_corpus
from src.moteur import MoteurSemantique


def main() -> None:
    analyseur = argparse.ArgumentParser(description="Construction des index")
    analyseur.add_argument("--sans-bm25", action="store_true",
                           help="ne pas construire l'index lexical de comparaison")
    arguments = analyseur.parse_args()

    print("=" * 70)
    print("CONSTRUCTION DES INDEX")
    print("=" * 70)

    corpus = charger_corpus()
    print(f"Corpus chargé : {len(corpus)} articles")
    print(f"Modèle        : {config.NOM_MODELE}")
    print(f"Type d'index  : {config.TYPE_INDEX}")
    print()

    depart_total = time.perf_counter()

    # --- Index sémantique -------------------------------------------------
    print("--- Moteur sémantique ---")
    moteur = MoteurSemantique(verbeux=True)
    statistiques = moteur.indexer(corpus)

    # --- Index lexical de comparaison ------------------------------------
    if not arguments.sans_bm25:
        print("\n--- Baseline lexicale (BM25) ---")
        lexical = MoteurLexical(verbeux=True)
        statistiques_bm25 = lexical.indexer(moteur.passages)
        lexical.sauvegarder()
        statistiques["bm25"] = statistiques_bm25

    statistiques["duree_totale_s"] = round(time.perf_counter() - depart_total, 2)
    statistiques["modele"] = config.NOM_MODELE

    config.DOSSIER_RESULTATS.mkdir(parents=True, exist_ok=True)
    fichier_stats = config.DOSSIER_RESULTATS / "statistiques_indexation.json"
    with open(fichier_stats, "w", encoding="utf-8") as sortie:
        json.dump(statistiques, sortie, ensure_ascii=False, indent=2)

    print()
    print("=" * 70)
    print("RÉSUMÉ")
    print("=" * 70)
    print(f"Articles indexés     : {statistiques['nb_documents']}")
    print(f"Passages indexés     : {statistiques['nb_passages']}")
    print(f"Dimensions           : {statistiques['dimension']}")
    print(f"Encodage             : {statistiques['duree_encodage_s']} s")
    print(f"Construction index   : {statistiques['duree_construction_index_s']} s")
    print(f"Taille de l'index    : {statistiques['taille_index_mo']} Mo")
    print(f"Durée totale         : {statistiques['duree_totale_s']} s")
    print(f"\nStatistiques écrites dans {fichier_stats}")
    print("\nÉtape suivante :  python scripts/3_chercher.py")


if __name__ == "__main__":
    main()
