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

Lancement :
    uvicorn api.main:application --reload

Puis ouvrir http://127.0.0.1:8000/docs
"""

from __future__ import annotations

import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import config
from src.baseline_bm25 import MoteurLexical
from src.moteur import MoteurSemantique

# Les moteurs sont gardés dans ce dictionnaire pour rester accessibles depuis
# toutes les routes après le chargement initial.
moteurs: dict = {}


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

    print(f"Prêt en {time.perf_counter() - depart:.1f} s")
    yield
    moteurs.clear()


application = FastAPI(
    title="Moteur de recherche sémantique",
    description=(
        "Recherche d'articles scientifiques arXiv à partir de questions en "
        "langage naturel, en français, en arabe ou en anglais."
    ),
    version="1.0.0",
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
    score: float = Field(..., description="similarité cosinus, entre -1 et 1")
    id_doc: str
    titre: str
    auteurs: list[str]
    categories: list[str]
    date: str
    url: str
    extrait: str


class ReponseRecherche(BaseModel):
    requete: str
    moteur: str
    nb_resultats: int
    duree_ms: float
    resultats: list[Resultat]


class DemandeRecherche(BaseModel):
    requete: str = Field(..., min_length=1, examples=["détection de fraude bancaire"])
    k: int = Field(config.TOP_K, ge=1, le=100)
    moteur: str = Field("semantique", pattern="^(semantique|lexical)$")


# ---------------------------------------------------------------------------
# Routes
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
            "GET /statistiques": "taille du corpus et de l'index",
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
        "modele": config.NOM_MODELE,
    }


@application.get("/statistiques", tags=["general"])
def statistiques() -> dict:
    """Quelques chiffres sur ce qui est indexé."""
    semantique = moteurs.get("semantique")
    if semantique is None:
        raise HTTPException(status_code=503, detail="Index non chargé.")
    return {
        "nb_articles": semantique.nb_documents,
        "nb_passages": semantique.nb_passages,
        "dimension": config.DIMENSION,
        "type_index": semantique.index.type_index,
        "modele": config.NOM_MODELE,
    }


def _chercher(requete: str, k: int, nom_moteur: str) -> ReponseRecherche:
    """Logique commune aux routes GET et POST."""
    moteur = moteurs.get("semantique" if nom_moteur == "semantique" else "lexical")

    if moteur is None:
        raise HTTPException(
            status_code=503,
            detail=f"Moteur '{nom_moteur}' indisponible. Lance scripts/2_indexer.py.",
        )

    depart = time.perf_counter()
    resultats = moteur.chercher(requete, k=k)
    duree_ms = round((time.perf_counter() - depart) * 1000, 2)

    return ReponseRecherche(
        requete=requete,
        moteur=nom_moteur,
        nb_resultats=len(resultats),
        duree_ms=duree_ms,
        resultats=[Resultat(**r) for r in resultats],
    )


@application.get("/recherche", response_model=ReponseRecherche, tags=["recherche"])
def recherche_get(
    q: str = Query(..., min_length=1, description="la question, dans n'importe quelle langue"),
    k: int = Query(config.TOP_K, ge=1, le=100, description="nombre de résultats"),
    moteur: str = Query("semantique", pattern="^(semantique|lexical)$"),
) -> ReponseRecherche:
    """
    Recherche des articles à partir d'une question en langage naturel.

    Exemple : `/recherche?q=détection de fraude bancaire&k=5`
    """
    return _chercher(q, k, moteur)


@application.post("/recherche", response_model=ReponseRecherche, tags=["recherche"])
def recherche_post(demande: DemandeRecherche) -> ReponseRecherche:
    """Même chose que la route GET, mais avec un corps JSON."""
    return _chercher(demande.requete, demande.k, demande.moteur)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(application, host=config.HOTE_API, port=config.PORT_API)
