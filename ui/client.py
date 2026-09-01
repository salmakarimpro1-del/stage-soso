"""
Le client de l'API.

L'interface ne connaît ni Sentence-BERT, ni FAISS, ni BM25 : elle ne sait
qu'appeler des routes HTTP. C'est ce découplage qui permet de changer
entièrement le moteur sans toucher une ligne d'affichage — et inversement.

Ce module est le seul endroit de l'interface qui parle réseau. Tout le reste
manipule des dictionnaires déjà reçus.

### Ce qui est mis en cache, et pourquoi

Streamlit ré-exécute tout le script à chaque interaction — un clic sur une case
à cocher relance la page depuis la première ligne. Sans cache, déplacer un
curseur relancerait la recherche précédente, le modèle réencoderait la requête,
et l'interface donnerait l'impression de ramer alors que le moteur répond en
17 ms.

Les réponses sont donc mémorisées selon leurs paramètres. Les données qui ne
bougent jamais pendant une session (statistiques, facettes, exemples, métriques)
sont gardées sans limite de durée ; les recherches, elles, expirent au bout de
quelques minutes pour ne pas masquer une réindexation.
"""

from __future__ import annotations

import requests
import streamlit as st

import config

DELAI_COURT = 5      # secondes, pour les appels d'état
DELAI_RECHERCHE = 60  # secondes : le premier appel peut charger le modèle


class ErreurAPI(Exception):
    """Erreur d'appel à l'API, avec un message directement affichable."""


def _appeler(route: str, parametres: dict | None = None, delai: int = DELAI_RECHERCHE) -> dict:
    """Appelle une route et renvoie le JSON, ou lève une ErreurAPI lisible."""
    try:
        reponse = requests.get(f"{config.URL_API}{route}", params=parametres, timeout=delai)
    except requests.exceptions.ConnectionError:
        raise ErreurAPI(
            "L'API ne répond pas. Démarre-la dans un autre terminal :\n\n"
            "    uvicorn api.main:application"
        )
    except requests.exceptions.Timeout:
        raise ErreurAPI(
            f"L'API n'a pas répondu en {delai} s. Au tout premier appel, "
            "le modèle peut mettre une quinzaine de secondes à se charger."
        )

    if reponse.status_code >= 400:
        # FastAPI renvoie ses messages d'erreur dans un champ « detail » : on
        # les remonte tels quels, ils sont déjà rédigés pour être lus.
        try:
            detail = reponse.json().get("detail", reponse.text)
        except ValueError:
            detail = reponse.text
        raise ErreurAPI(str(detail))

    return reponse.json()


# ---------------------------------------------------------------------------
# État du service
# ---------------------------------------------------------------------------

@st.cache_data(ttl=10, show_spinner=False)
def etat() -> tuple[bool, dict]:
    """
    (disponible, statistiques). Ne lève jamais : l'interface doit pouvoir
    s'afficher même sans API, en expliquant comment la démarrer.
    """
    try:
        return True, _appeler("/statistiques", delai=DELAI_COURT)
    except ErreurAPI:
        return False, {}


@st.cache_data(show_spinner=False)
def facettes() -> dict:
    """Catégories et plage d'années disponibles pour les filtres."""
    try:
        return _appeler("/facettes", delai=DELAI_COURT)
    except ErreurAPI:
        return {"categories": [], "annee_min": None, "annee_max": None}


@st.cache_data(show_spinner=False)
def exemples() -> list[dict]:
    """Les triplets de questions multilingues du jeu d'évaluation."""
    try:
        return _appeler("/exemples", delai=DELAI_COURT).get("triplets", [])
    except ErreurAPI:
        return []


@st.cache_data(show_spinner=False)
def metriques() -> dict | None:
    """Les résultats de l'évaluation, ou None si elle n'a pas encore tourné."""
    try:
        return _appeler("/metriques", delai=DELAI_COURT)
    except ErreurAPI:
        return None


# ---------------------------------------------------------------------------
# Recherche
# ---------------------------------------------------------------------------

@st.cache_data(ttl=300, show_spinner=False)
def rechercher(
    requete: str,
    k: int,
    moteur: str,
    expliquer: bool = True,
    categories: tuple[str, ...] = (),
    annee_min: int | None = None,
    annee_max: int | None = None,
    auteur: str | None = None,
) -> dict:
    """
    Lance une recherche.

    Les catégories sont un tuple et non une liste : Streamlit exige des
    arguments hachables pour indexer son cache, et une liste ne l'est pas.
    """
    parametres: dict = {"q": requete, "k": k, "moteur": moteur, "expliquer": expliquer}
    if categories:
        parametres["categories"] = list(categories)
    if annee_min is not None:
        parametres["annee_min"] = annee_min
    if annee_max is not None:
        parametres["annee_max"] = annee_max
    if auteur:
        parametres["auteur"] = auteur

    return _appeler("/recherche", parametres)


@st.cache_data(ttl=300, show_spinner=False)
def comparer(
    requete: str,
    k: int,
    moteurs: tuple[str, ...] = ("semantique", "lexical"),
    expliquer: bool = True,
    categories: tuple[str, ...] = (),
    annee_min: int | None = None,
    annee_max: int | None = None,
) -> dict:
    """
    Soumet la même requête à plusieurs moteurs et récupère l'analyse.

    Un seul appel réseau plutôt qu'un par moteur : l'API fait tourner les
    moteurs sur la même requête et calcule au passage ce que chacun est seul
    à trouver, ce que l'interface ne pourrait pas recalculer aussi
    fidèlement de son côté.
    """
    parametres: dict = {
        "q": requete,
        "k": k,
        "moteurs": list(moteurs),
        "expliquer": expliquer,
    }
    if categories:
        parametres["categories"] = list(categories)
    if annee_min is not None:
        parametres["annee_min"] = annee_min
    if annee_max is not None:
        parametres["annee_max"] = annee_max

    return _appeler("/comparer", parametres)
