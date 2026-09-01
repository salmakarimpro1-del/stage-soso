"""
Les filtres sur métadonnées.

Un moteur de recherche utilisable ne se contente pas de classer : il laisse
restreindre. « Des articles sur la fraude, mais seulement en sécurité
informatique, et publiés après 2024. »

### Le piège du filtrage naïf

L'ordre des opérations n'est pas anodin. Filtrer *après* avoir pris les dix
premiers résultats est faux : si aucun des dix ne relève de la catégorie
demandée, la recherche ne renvoie rien alors que le corpus contient peut-être
cent articles pertinents un peu plus loin dans le classement.

On procède donc dans l'autre sens : on demande à l'index un vivier de
candidats beaucoup plus large, on écarte ceux qui ne passent pas le filtre,
puis on ne garde que les k premiers survivants. C'est la stratégie dite du
*post-filtrage sur sur-échantillon*, celle qu'emploient les moteurs vectoriels
qui ne savent pas filtrer nativement — ce qui est le cas de FAISS.

Sa limite est connue et honnête à énoncer : si le filtre est très sélectif
(une catégorie représentant 1 % du corpus), même un vivier élargi peut ne pas
contenir assez de survivants. Le facteur d'élargissement ci-dessous est donc
un compromis entre exhaustivité et latence, pas une garantie.
"""

from __future__ import annotations

from typing import Callable

# Quand un filtre est actif, on demande à l'index ce multiple de résultats
# avant d'écarter. 20 suffit à couvrir les catégories courantes du corpus tout
# en gardant une recherche sous les 30 ms.
FACTEUR_VIVIER = 20

# Plafond de sécurité : au-delà, on parcourrait presque tout l'index et la
# recherche approchée ne servirait plus à rien.
VIVIER_MAXIMUM = 3000


def construire(
    categories: list[str] | None = None,
    annee_min: int | None = None,
    annee_max: int | None = None,
    auteur: str | None = None,
) -> Callable[[dict], bool] | None:
    """
    Fabrique la fonction de test appliquée à chaque passage candidat.

    Args:
        categories: catégories arXiv acceptées (ex. ["cs.CR", "cs.LG"]).
                    Un article en garde plusieurs : il suffit qu'une seule
                    corresponde.
        annee_min, annee_max: bornes incluses sur l'année de publication.
        auteur: fragment de nom recherché, insensible à la casse.

    Returns:
        Une fonction passage -> booléen, ou None si aucun critère n'est posé.
        Renvoyer None permet à l'appelant de sauter entièrement le mécanisme
        de sur-échantillonnage, qui coûterait cher pour rien.
    """
    categories = [c for c in (categories or []) if c]
    auteur = (auteur or "").strip().lower()

    if not categories and annee_min is None and annee_max is None and not auteur:
        return None

    categories_voulues = set(categories)

    def teste(passage: dict) -> bool:
        if categories_voulues and not categories_voulues.intersection(
            passage.get("categories") or []
        ):
            return False

        if annee_min is not None or annee_max is not None:
            annee = extraire_annee(passage.get("date", ""))
            if annee is None:
                return False
            if annee_min is not None and annee < annee_min:
                return False
            if annee_max is not None and annee > annee_max:
                return False

        if auteur:
            noms = " ".join(passage.get("auteurs") or []).lower()
            if auteur not in noms:
                return False

        return True

    return teste


def extraire_annee(date: str) -> int | None:
    """
    Lit l'année dans une date arXiv (« 2025-03-14 » ou « 2025-03-14T09:12:00Z »).

    Renvoie None sur une date absente ou malformée plutôt que de lever une
    exception : une métadonnée manquante ne doit jamais faire tomber une
    recherche.
    """
    if not date or len(date) < 4:
        return None
    try:
        return int(date[:4])
    except ValueError:
        return None


def taille_vivier(k: int, filtre_actif: bool, multiplicateur_base: int) -> int:
    """
    Combien de passages demander à l'index avant d'appliquer le filtre.

    Sans filtre, on garde le comportement historique du projet (k fois le
    multiplicateur qui compense le regroupement des passages par article).
    Avec filtre, on élargit fortement, dans la limite du plafond.
    """
    if not filtre_actif:
        return k * multiplicateur_base
    return min(k * multiplicateur_base * FACTEUR_VIVIER, VIVIER_MAXIMUM)


def inventorier(passages: list[dict]) -> dict:
    """
    Recense ce qui est filtrable dans l'index : catégories et plage d'années.

    L'interface s'en sert pour ne proposer que des filtres qui ont réellement
    des résultats — proposer une catégorie vide serait une impasse pour
    l'utilisateur.
    """
    compte_categories: dict[str, int] = {}
    annees: set[int] = set()
    documents_vus: set[str] = set()

    for passage in passages:
        id_doc = passage.get("id_doc")
        # On compte des articles, pas des passages : sinon un article long
        # pèserait plus lourd qu'un autre dans les statistiques affichées.
        if id_doc in documents_vus:
            continue
        documents_vus.add(id_doc)

        for categorie in passage.get("categories") or []:
            compte_categories[categorie] = compte_categories.get(categorie, 0) + 1

        annee = extraire_annee(passage.get("date", ""))
        if annee is not None:
            annees.add(annee)

    return {
        "categories": sorted(
            ({"code": code, "nb_articles": nombre} for code, nombre in compte_categories.items()),
            key=lambda c: c["nb_articles"],
            reverse=True,
        ),
        "annee_min": min(annees) if annees else None,
        "annee_max": max(annees) if annees else None,
    }


# Libellés lisibles des catégories arXiv utilisées par le projet. Afficher
# « cs.CR » à un jury n'apprend rien ; afficher « Cryptographie et sécurité »
# si.
LIBELLES_CATEGORIES = {
    "cs.LG": "Apprentissage automatique",
    "cs.CL": "Traitement du langage",
    "cs.CV": "Vision par ordinateur",
    "cs.AI": "Intelligence artificielle",
    "cs.CR": "Cryptographie et sécurité",
    "cs.IR": "Recherche d'information",
    "cs.NE": "Réseaux de neurones",
    "stat.ML": "Apprentissage statistique",
    "cs.RO": "Robotique",
    "cs.SI": "Réseaux sociaux",
    "cs.DC": "Calcul distribué",
    "cs.SE": "Génie logiciel",
    "cs.HC": "Interaction homme-machine",
    "cs.DB": "Bases de données",
    "cs.CY": "Informatique et société",
    "cs.MA": "Systèmes multi-agents",
    "cs.SD": "Traitement du son",
    "eess.AS": "Audio et parole",
    "eess.IV": "Traitement d'images",
    "stat.AP": "Statistiques appliquées",
    "stat.ME": "Méthodologie statistique",
    "math.OC": "Optimisation",
}


def libelle(code: str) -> str:
    """Nom lisible d'une catégorie, ou le code lui-même s'il est inconnu."""
    return LIBELLES_CATEGORIES.get(code, code)
