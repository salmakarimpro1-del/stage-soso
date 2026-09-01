"""
L'API du moteur de recherche.

Le moteur est une bibliothèque Python : utile, mais utilisable seulement depuis
Python. FastAPI le transforme en service web interrogeable par n'importe quelle
application — un site, une appli mobile, un script, un autre serveur.

Trois avantages concrets :

1. l'index et le modèle sont chargés UNE fois au démarrage et restent en
   mémoire ; chaque requête ne paie plus que le coût de la recherche ;
2. l'interface graphique n'a aucune connaissance du fonctionnement interne :
   on peut changer de modèle sans toucher à une ligne de l'affichage ;
3. FastAPI génère automatiquement une documentation interactive, où l'on peut
   tester chaque route depuis le navigateur. C'est très pratique en soutenance.

Trois moteurs sont exposés derrière la même interface — sémantique, lexical et
hybride — ce qui permet à l'interface de les comparer sans écrire une ligne de
code spécifique à l'un d'eux.

Lancement :
    uvicorn api.main:application --reload

Puis ouvrir http://127.0.0.1:8000/docs
"""

from __future__ import annotations

import json
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import config
from src import comparaison, filtres, surlignage
from src.baseline_bm25 import MoteurLexical
from src.hybride import MoteurHybride
from src.moteur import MoteurSemantique

# Les moteurs sont gardés dans ce dictionnaire pour rester accessibles depuis
# toutes les routes après le chargement initial.
moteurs: dict = {}

# Noms affichables des moteurs, utilisés dans les verdicts de comparaison.
LIBELLES_MOTEURS = {
    "semantique": "le moteur sémantique",
    "lexical": "la baseline BM25",
    "hybride": "la fusion hybride",
}


@asynccontextmanager
async def cycle_de_vie(app: FastAPI):
    """Charge les index au démarrage, les libère à l'arrêt."""
    print("Chargement des index ...")
    depart = time.perf_counter()

    moteurs["semantique"] = MoteurSemantique(verbeux=True).charger()

    # Le modèle se charge paresseusement : sans ce préchauffage, c'est le
    # premier utilisateur qui paierait les quinze secondes de chargement.
    print("Préchauffage du modèle ...")
    moteurs["semantique"].prechauffer()

    try:
        moteurs["lexical"] = MoteurLexical(verbeux=True).charger()
    except FileNotFoundError:
        print("Index BM25 absent : la comparaison lexicale sera indisponible.")
        moteurs["lexical"] = None

    # Le moteur hybride ne possède pas d'index propre : il ne fait que
    # fusionner les classements des deux autres. Il n'existe donc que si les
    # deux autres existent.
    moteurs["hybride"] = (
        MoteurHybride(moteurs["semantique"], moteurs["lexical"])
        if moteurs["lexical"] is not None
        else None
    )

    # L'inventaire des catégories et des années sert à l'interface pour ne
    # proposer que des filtres ayant réellement des résultats. Il est calculé
    # une fois ici plutôt qu'à chaque appel : c'est un parcours de tout l'index.
    moteurs["facettes"] = filtres.inventorier(moteurs["semantique"].passages)

    print(f"Prêt en {time.perf_counter() - depart:.1f} s")
    yield
    moteurs.clear()


application = FastAPI(
    title="Moteur de recherche sémantique",
    description=(
        "Recherche d'articles scientifiques arXiv à partir de questions en "
        "langage naturel, en français, en arabe ou en anglais. Trois moteurs "
        "comparables : sémantique (Sentence-BERT + FAISS), lexical (BM25) et "
        "hybride (fusion RRF des deux)."
    ),
    version="2.0.0",
    lifespan=cycle_de_vie,
)

# Autorise l'interface Streamlit (ou tout autre client local) à appeler l'API.
application.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Schémas de données — ils servent aussi à générer la documentation
# ---------------------------------------------------------------------------

class Resultat(BaseModel):
    rang: int = Field(..., description="position dans le classement, à partir de 1")
    score: float = Field(..., description="similarité cosinus, entre -1 et 1 (score RRF pour l'hybride)")
    id_doc: str
    titre: str
    auteurs: list[str]
    categories: list[str]
    date: str
    url: str
    extrait: str

    # --- justification du résultat (route appelée avec expliquer=true) ---
    phrase_cle: str | None = Field(
        None, description="phrase du résumé la plus proche de la question"
    )
    score_phrase: float | None = Field(
        None, description="similarité de cette phrase avec la question"
    )
    termes_partages: list[str] | None = Field(
        None, description="mots significatifs communs à la question et au document"
    )
    taux_recouvrement_lexical: float | None = Field(
        None, description="part des mots de la question retrouvés dans le document"
    )
    sans_recouvrement_lexical: bool | None = Field(
        None, description="vrai si aucun mot n'est partagé — le cas qui démontre l'apport sémantique"
    )

    # --- provenance (moteur hybride uniquement) ---
    sources: list[str] | None = Field(None, description="moteurs ayant trouvé ce document")
    rangs: dict[str, int] | None = Field(None, description="rang obtenu dans chaque moteur")
    scores: dict[str, float] | None = Field(None, description="score obtenu dans chaque moteur")


class ReponseRecherche(BaseModel):
    requete: str
    moteur: str
    nb_resultats: int
    duree_ms: float
    duree_explication_ms: float = 0.0
    filtres_actifs: dict = {}
    resultats: list[Resultat]


class ReponseComparaison(BaseModel):
    requete: str
    moteurs: list[str]
    duree_ms: float
    resultats: dict[str, list[Resultat]]
    analyse: dict
    verdict: str


class DemandeRecherche(BaseModel):
    requete: str = Field(..., min_length=1, examples=["détection de fraude bancaire"])
    k: int = Field(config.TOP_K, ge=1, le=100)
    moteur: str = Field("semantique", pattern="^(semantique|lexical|hybride)$")
    expliquer: bool = False
    nb_explications: int = Field(surlignage.NB_EXPLICATIONS_PAR_DEFAUT, ge=0, le=50)
    categories: list[str] | None = None
    annee_min: int | None = None
    annee_max: int | None = None
    auteur: str | None = None


# ---------------------------------------------------------------------------
# Fonctions internes
# ---------------------------------------------------------------------------

def _obtenir_moteur(nom: str):
    """Récupère un moteur chargé, ou explique précisément ce qui manque."""
    moteur = moteurs.get(nom)
    if moteur is None:
        raise HTTPException(
            status_code=503,
            detail=(
                f"Moteur '{nom}' indisponible. "
                "Lance d'abord :  python scripts/2_indexer.py"
            ),
        )
    return moteur


def _chercher(
    requete: str,
    k: int,
    nom_moteur: str,
    expliquer: bool = False,
    categories: list[str] | None = None,
    annee_min: int | None = None,
    annee_max: int | None = None,
    auteur: str | None = None,
    nb_explications: int = surlignage.NB_EXPLICATIONS_PAR_DEFAUT,
) -> ReponseRecherche:
    """Logique commune aux routes GET et POST."""
    moteur = _obtenir_moteur(nom_moteur)
    filtre = filtres.construire(categories, annee_min, annee_max, auteur)

    depart = time.perf_counter()
    resultats = moteur.chercher(requete, k=k, filtres=filtre)
    duree_ms = round((time.perf_counter() - depart) * 1000, 2)

    # L'explication est facturée séparément : elle demande un second passage
    # dans le modèle, et l'interface doit pouvoir montrer les deux coûts.
    duree_explication = 0.0
    if expliquer and resultats:
        depart = time.perf_counter()
        surlignage.expliquer_resultats(
            requete, resultats, moteurs["semantique"].encodeur,
            nb_maximum=nb_explications,
        )
        duree_explication = round((time.perf_counter() - depart) * 1000, 2)

    return ReponseRecherche(
        requete=requete,
        moteur=nom_moteur,
        nb_resultats=len(resultats),
        duree_ms=duree_ms,
        duree_explication_ms=duree_explication,
        filtres_actifs={
            "categories": categories or [],
            "annee_min": annee_min,
            "annee_max": annee_max,
            "auteur": auteur,
        },
        resultats=[Resultat(**r) for r in resultats],
    )


# ---------------------------------------------------------------------------
# Routes générales
# ---------------------------------------------------------------------------

@application.get("/", tags=["general"])
def accueil() -> dict:
    """Point d'entrée : rappelle les routes disponibles."""
    return {
        "nom": "Moteur de recherche sémantique",
        "documentation": "/docs",
        "routes": {
            "GET /sante": "état du service",
            "GET /recherche": "recherche par paramètres d'URL",
            "POST /recherche": "recherche par corps JSON",
            "GET /comparer": "les trois moteurs sur la même requête, avec analyse",
            "GET /statistiques": "taille du corpus et de l'index",
            "GET /facettes": "catégories et années disponibles pour filtrer",
            "GET /exemples": "jeu de questions multilingues de démonstration",
            "GET /metriques": "résultats de l'évaluation expérimentale",
        },
    }


@application.get("/sante", tags=["general"])
def sante() -> dict:
    """Vérifie que les index sont bien chargés (utile pour la supervision)."""
    semantique = moteurs.get("semantique")
    return {
        "statut": "ok" if semantique else "index non chargé",
        "moteur_semantique": semantique is not None,
        "moteur_lexical": moteurs.get("lexical") is not None,
        "moteur_hybride": moteurs.get("hybride") is not None,
        "modele": config.NOM_MODELE,
    }


@application.get("/statistiques", tags=["general"])
def statistiques() -> dict:
    """Quelques chiffres sur ce qui est indexé."""
    semantique = _obtenir_moteur("semantique")
    return {
        "nb_articles": semantique.nb_documents,
        "nb_passages": semantique.nb_passages,
        "dimension": config.DIMENSION,
        "type_index": semantique.index.type_index,
        "modele": config.NOM_MODELE,
        "moteurs_disponibles": [
            nom for nom in ("semantique", "lexical", "hybride")
            if moteurs.get(nom) is not None
        ],
    }


@application.get("/facettes", tags=["general"])
def facettes() -> dict:
    """
    Ce sur quoi on peut filtrer : catégories présentes et plage d'années.

    Calculé une seule fois au démarrage. L'interface s'en sert pour ne
    proposer que des filtres qui ont réellement des résultats.
    """
    inventaire = moteurs.get("facettes")
    if inventaire is None:
        raise HTTPException(status_code=503, detail="Index non chargé.")

    return {
        **inventaire,
        "categories": [
            {**categorie, "libelle": filtres.libelle(categorie["code"])}
            for categorie in inventaire["categories"]
        ],
    }


@application.get("/exemples", tags=["general"])
def exemples() -> dict:
    """
    Les questions du jeu d'évaluation multilingue.

    Chaque entrée est la même question en français, en arabe et en anglais.
    L'interface s'en sert pour son mode démonstration : ces questions ont été
    définies avant les mesures, elles ne sont donc pas choisies pour flatter
    le moteur.
    """
    if not config.FICHIER_REQUETES_MULTI.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Jeu de requêtes introuvable : {config.FICHIER_REQUETES_MULTI}",
        )
    with open(config.FICHIER_REQUETES_MULTI, encoding="utf-8") as entree:
        return json.load(entree)


@application.get("/metriques", tags=["general"])
def metriques() -> dict:
    """
    Les résultats de l'évaluation expérimentale, tels que produits par
    `python scripts/4_evaluer.py`.

    L'API se contente de servir le fichier : les chiffres ne sont jamais
    recalculés à la volée, ce qui garantit que l'interface affiche exactement
    ce que le rapport contient.
    """
    fichier = config.DOSSIER_RESULTATS / "evaluation.json"
    if not fichier.exists():
        raise HTTPException(
            status_code=404,
            detail="Évaluation absente. Lance :  python scripts/4_evaluer.py",
        )
    with open(fichier, encoding="utf-8") as entree:
        return json.load(entree)


# ---------------------------------------------------------------------------
# Routes de recherche
# ---------------------------------------------------------------------------

@application.get("/recherche", response_model=ReponseRecherche, tags=["recherche"])
def recherche_get(
    q: str = Query(..., min_length=1, description="la question, dans n'importe quelle langue"),
    k: int = Query(config.TOP_K, ge=1, le=100, description="nombre de résultats"),
    moteur: str = Query("semantique", pattern="^(semantique|lexical|hybride)$"),
    expliquer: bool = Query(False, description="calculer la phrase clé et les mots partagés"),
    nb_explications: int = Query(
        surlignage.NB_EXPLICATIONS_PAR_DEFAUT, ge=0, le=50,
        description=(
            "nombre de résultats recevant une phrase clé. Les mots partagés, "
            "eux, sont calculés pour tous : ils ne coûtent aucun appel au modèle."
        ),
    ),
    categories: list[str] | None = Query(None, description="catégories arXiv acceptées"),
    annee_min: int | None = Query(None, ge=1990, le=2100),
    annee_max: int | None = Query(None, ge=1990, le=2100),
    auteur: str | None = Query(None, description="fragment de nom d'auteur"),
) -> ReponseRecherche:
    """
    Recherche des articles à partir d'une question en langage naturel.

    Exemple : `/recherche?q=détection de fraude bancaire&k=5&expliquer=true`
    """
    return _chercher(
        q, k, moteur, expliquer, categories, annee_min, annee_max, auteur, nb_explications
    )


@application.post("/recherche", response_model=ReponseRecherche, tags=["recherche"])
def recherche_post(demande: DemandeRecherche) -> ReponseRecherche:
    """Même chose que la route GET, mais avec un corps JSON."""
    return _chercher(
        demande.requete,
        demande.k,
        demande.moteur,
        demande.expliquer,
        demande.categories,
        demande.annee_min,
        demande.annee_max,
        demande.auteur,
        demande.nb_explications,
    )


@application.get("/comparer", response_model=ReponseComparaison, tags=["recherche"])
def comparer(
    q: str = Query(..., min_length=1, description="la question à soumettre à tous les moteurs"),
    k: int = Query(config.TOP_K, ge=1, le=50),
    moteurs_demandes: list[str] = Query(
        ["semantique", "lexical"],
        alias="moteurs",
        description="moteurs à comparer",
    ),
    expliquer: bool = Query(True, description="calculer les justifications"),
    nb_explications: int = Query(surlignage.NB_EXPLICATIONS_PAR_DEFAUT, ge=0, le=50),
    categories: list[str] | None = Query(None),
    annee_min: int | None = Query(None, ge=1990, le=2100),
    annee_max: int | None = Query(None, ge=1990, le=2100),
) -> ReponseComparaison:
    """
    Soumet la même question à plusieurs moteurs et analyse leurs différences.

    C'est la route qui répond à l'exigence 3.9 du cahier des charges. Elle ne
    renvoie pas seulement deux listes : elle calcule ce que chaque moteur est
    **seul** à trouver, le taux de recouvrement, les articles fortement
    reclassés, et rédige le verdict correspondant.
    """
    inconnus = [m for m in moteurs_demandes if m not in ("semantique", "lexical", "hybride")]
    if inconnus:
        raise HTTPException(status_code=422, detail=f"Moteurs inconnus : {inconnus}")

    filtre = filtres.construire(categories, annee_min, annee_max)

    depart = time.perf_counter()
    classements: dict[str, list[dict]] = {}
    for nom in moteurs_demandes:
        moteur = _obtenir_moteur(nom)
        classements[nom] = moteur.chercher(q, k=k, filtres=filtre)

    if expliquer:
        encodeur = moteurs["semantique"].encodeur
        for resultats in classements.values():
            surlignage.expliquer_resultats(
                q, resultats, encodeur, nb_maximum=nb_explications
            )

    duree_ms = round((time.perf_counter() - depart) * 1000, 2)

    analyse = comparaison.analyser(classements, k=k)

    return ReponseComparaison(
        requete=q,
        moteurs=moteurs_demandes,
        duree_ms=duree_ms,
        resultats={
            nom: [Resultat(**r) for r in resultats]
            for nom, resultats in classements.items()
        },
        analyse=analyse,
        verdict=comparaison.verdict(analyse, LIBELLES_MOTEURS),
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(application, host=config.HOTE_API, port=config.PORT_API)
