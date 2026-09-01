"""
Mise en forme des résultats de recherche.

Un détail qui change l'expérience utilisateur : l'index contient des passages,
pas des articles. Si un article a été découpé en trois passages et que les
trois ressemblent à la requête, une recherche naïve affiche trois fois le même
article et n'en montre plus que sept autres.

On regroupe donc les passages par article, en gardant pour chaque article le
meilleur score obtenu par l'un de ses passages. C'est la stratégie « max
pooling », la plus courante et la plus simple à justifier.

Cette fonction est partagée par le moteur sémantique et par la baseline
lexicale, ce qui garantit que les deux sont comparés à traitement identique.
C'est aussi ici que s'appliquent les filtres sur métadonnées, pour la même
raison : un filtre qui ne s'appliquerait qu'à un seul des deux moteurs
invaliderait toute comparaison.
"""

from __future__ import annotations

from typing import Callable


def regrouper_par_document(
    scores: list[float],
    identifiants: list[int],
    passages: list[dict],
    k: int,
    filtre: Callable[[dict], bool] | None = None,
) -> list[dict]:
    """
    Convertit une liste de passages trouvés en liste d'articles.

    Args:
        scores: score de similarité de chaque passage trouvé.
        identifiants: position du passage dans la liste `passages`.
        passages: la liste complète des passages indexés.
        k: nombre d'articles à renvoyer.
        filtre: test optionnel sur les métadonnées (voir src/filtres.py).
                Il s'applique passage par passage, avant le regroupement et
                avant la troncature à k : un article écarté libère donc sa
                place pour le suivant au lieu de laisser un trou.

    Returns:
        Les k meilleurs articles, triés par score décroissant.
    """
    meilleurs: dict[str, dict] = {}

    for score, identifiant in zip(scores, identifiants):
        # FAISS renvoie -1 quand il n'a pas trouvé assez de voisins.
        if identifiant < 0 or identifiant >= len(passages):
            continue

        passage = passages[identifiant]

        if filtre is not None and not filtre(passage):
            continue

        id_doc = passage["id_doc"]
        score = float(score)

        # On ne garde que le meilleur passage de chaque article.
        if id_doc in meilleurs and meilleurs[id_doc]["score"] >= score:
            continue

        meilleurs[id_doc] = {
            "id_doc": id_doc,
            "score": score,
            "titre": passage["titre"],
            "auteurs": passage["auteurs"],
            "categories": passage["categories"],
            "date": passage["date"],
            "url": passage["url"],
            "extrait": passage["texte_affiche"],
            "position_passage": passage["position"],
        }

    classement = sorted(meilleurs.values(), key=lambda r: r["score"], reverse=True)[:k]

    for rang, resultat in enumerate(classement, start=1):
        resultat["rang"] = rang

    return classement


def resumer_extrait(texte: str, longueur: int = 280) -> str:
    """Raccourcit un extrait pour l'affichage, sans couper un mot en deux."""
    if len(texte) <= longueur:
        return texte
    coupe = texte[:longueur].rsplit(" ", 1)[0]
    return coupe + " ..."
