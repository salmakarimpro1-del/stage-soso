"""
Script 3 — Chercher depuis le terminal.

C'est l'outil de test rapide, avant même de lancer l'API ou l'interface.

Utilisation :
    python scripts/3_chercher.py                              # mode interactif
    python scripts/3_chercher.py -q "détection de fraude"
    python scripts/3_chercher.py -q "كشف الاحتيال" -k 5
    python scripts/3_chercher.py -q "fraud detection" --comparer

L'option --comparer affiche côte à côte le moteur sémantique et la baseline
BM25 : c'est la démonstration la plus parlante du projet.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import config
from src.baseline_bm25 import MoteurLexical
from src.moteur import MoteurSemantique
from src.resultats import resumer_extrait

EXEMPLES = [
    "détection de la fraude bancaire par apprentissage automatique",
    "كشف الاحتيال المصرفي باستخدام التعلم الآلي",
    "how do transformers handle long documents",
    "réseaux de neurones pour l'imagerie médicale",
]


def afficher(resultats: list[dict], titre_section: str) -> None:
    """Affiche une liste de résultats de façon lisible dans le terminal."""
    print()
    print(titre_section)
    print("-" * len(titre_section))

    if not resultats:
        print("  aucun résultat")
        return

    for resultat in resultats:
        print(f"  {resultat['rang']:>2}. [{resultat['score']:.3f}] {resultat['titre']}")
        auteurs = ", ".join(resultat["auteurs"][:3])
        if len(resultat["auteurs"]) > 3:
            auteurs += " et al."
        print(f"      {auteurs}  |  {resultat['date']}  |  {resultat['url']}")
        print(f"      {resumer_extrait(resultat['extrait'], 200)}")
        print()


def main() -> None:
    analyseur = argparse.ArgumentParser(description="Recherche en ligne de commande")
    analyseur.add_argument("-q", "--requete", type=str, default=None)
    analyseur.add_argument("-k", type=int, default=config.TOP_K)
    analyseur.add_argument("--comparer", action="store_true",
                           help="afficher aussi les résultats de BM25")
    analyseur.add_argument("--lexical", action="store_true",
                           help="utiliser uniquement BM25")
    arguments = analyseur.parse_args()

    moteur_semantique = None
    moteur_lexical = None

    if not arguments.lexical:
        moteur_semantique = MoteurSemantique(verbeux=True).charger()
    if arguments.lexical or arguments.comparer:
        moteur_lexical = MoteurLexical(verbeux=True).charger()

    def traiter(requete: str) -> None:
        if moteur_semantique is not None:
            afficher(moteur_semantique.chercher(requete, k=arguments.k),
                     "MOTEUR SÉMANTIQUE (Sentence-BERT + FAISS)")
        if moteur_lexical is not None:
            afficher(moteur_lexical.chercher(requete, k=arguments.k),
                     "BASELINE LEXICALE (BM25)")

    # Mode une seule requête
    if arguments.requete:
        print(f"\nRequête : {arguments.requete}")
        traiter(arguments.requete)
        return

    # Mode interactif
    print("\n" + "=" * 70)
    print("RECHERCHE INTERACTIVE — tape ta question, ou 'q' pour quitter")
    print("=" * 70)
    print("Exemples de requêtes :")
    for exemple in EXEMPLES:
        print(f"  - {exemple}")

    while True:
        try:
            requete = input("\nRequête > ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if requete.lower() in {"q", "quit", "exit"}:
            break
        if not requete:
            continue

        traiter(requete)


if __name__ == "__main__":
    main()
