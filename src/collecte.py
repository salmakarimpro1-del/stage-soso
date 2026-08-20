"""
Étape 1 du projet : construire le corpus.

On interroge l'API publique d'arXiv pour récupérer des articles scientifiques
(titre, résumé, auteurs, catégories) et on les enregistre dans un fichier
JSONL — un article par ligne, ce qui permet de lire le corpus sans jamais
tout charger en mémoire.

L'API arXiv est gratuite, sans clé d'accès, mais elle demande de respecter
un délai de 3 secondes entre deux appels. Ce module le fait automatiquement.
"""

from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

import config

URL_API_ARXIV = "http://export.arxiv.org/api/query"

# Les réponses d'arXiv sont du XML Atom : chaque balise porte un espace de
# noms qu'il faut préciser pour la retrouver.
ESPACES_NOMS = {
    "atom": "http://www.w3.org/2005/Atom",
    "arxiv": "http://arxiv.org/schemas/atom",
}


def _texte(element, chemin: str) -> str:
    """Lit le texte d'une sous-balise, ou renvoie une chaîne vide si absente."""
    trouve = element.find(chemin, ESPACES_NOMS)
    if trouve is None or trouve.text is None:
        return ""
    return " ".join(trouve.text.split())


def _analyser_entree(entree) -> dict | None:
    """Transforme une balise <entry> du XML en dictionnaire Python."""
    url = _texte(entree, "atom:id")
    if not url:
        return None

    # url ressemble à http://arxiv.org/abs/2401.12345v1 : on garde 2401.12345
    identifiant = url.rsplit("/", 1)[-1].split("v")[0]

    titre = _texte(entree, "atom:title")
    resume = _texte(entree, "atom:summary")
    if not titre or not resume:
        return None

    auteurs = [
        " ".join(nom.text.split())
        for nom in entree.findall("atom:author/atom:name", ESPACES_NOMS)
        if nom.text
    ]

    categories = [
        cat.attrib.get("term", "")
        for cat in entree.findall("atom:category", ESPACES_NOMS)
    ]

    return {
        "id": identifiant,
        "titre": titre,
        "resume": resume,
        "auteurs": auteurs[:8],
        "categories": [c for c in categories if c],
        "date": _texte(entree, "atom:published")[:10],
        "url": f"https://arxiv.org/abs/{identifiant}",
    }


def interroger_arxiv(categorie: str, debut: int, nombre: int) -> list[dict]:
    """
    Récupère une page de résultats pour une catégorie donnée.

    Args:
        categorie: code arXiv, par exemple "cs.LG".
        debut: index du premier résultat (pagination).
        nombre: nombre d'articles demandés (200 maximum recommandé).

    Returns:
        La liste des articles trouvés. Liste vide si la page est vide.
    """
    parametres = urllib.parse.urlencode(
        {
            "search_query": f"cat:{categorie}",
            "start": debut,
            "max_results": nombre,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }
    )
    url = f"{URL_API_ARXIV}?{parametres}"

    derniere_erreur = None
    for tentative in range(config.NB_TENTATIVES):
        try:
            requete = urllib.request.Request(
                url,
                headers={"User-Agent": "moteur-semantique-pfa/1.0"},
            )
            with urllib.request.urlopen(requete, timeout=60) as reponse:
                brut = reponse.read()

            racine = ET.fromstring(brut)
            entrees = racine.findall("atom:entry", ESPACES_NOMS)
            articles = [_analyser_entree(e) for e in entrees]
            return [a for a in articles if a is not None]

        except Exception as erreur:  # réseau instable, XML tronqué, quota…
            derniere_erreur = erreur
            attente = config.DELAI_ENTRE_REQUETES * (tentative + 2)
            print(f"    tentative {tentative + 1} échouée ({erreur}), "
                  f"nouvel essai dans {attente:.0f}s")
            time.sleep(attente)

    print(f"    abandon de cette page : {derniere_erreur}")
    return []


def collecter(
    categories: list[str] | None = None,
    nb_par_categorie: int | None = None,
    fichier_sortie: Path | None = None,
) -> int:
    """
    Télécharge le corpus complet et l'écrit dans un fichier JSONL.

    Les doublons sont éliminés : un même article peut apparaître dans
    plusieurs catégories (un papier de NLP est souvent à la fois cs.CL
    et cs.LG), on ne le garde qu'une fois.

    Returns:
        Le nombre d'articles uniques écrits.
    """
    categories = categories or config.CATEGORIES_ARXIV
    nb_par_categorie = nb_par_categorie or config.NB_DOCS_PAR_CATEGORIE
    fichier_sortie = fichier_sortie or config.FICHIER_CORPUS
    fichier_sortie.parent.mkdir(parents=True, exist_ok=True)

    vus: set[str] = set()
    total = 0

    with open(fichier_sortie, "w", encoding="utf-8") as sortie:
        for categorie in categories:
            print(f"\n[{categorie}] objectif : {nb_par_categorie} articles")
            recuperes = 0
            debut = 0

            while recuperes < nb_par_categorie:
                taille = min(config.TAILLE_PAGE_ARXIV, nb_par_categorie - recuperes)
                articles = interroger_arxiv(categorie, debut, taille)

                if not articles:
                    print("    plus de résultats disponibles, passage à la suite")
                    break

                nouveaux = 0
                for article in articles:
                    if article["id"] in vus:
                        continue
                    vus.add(article["id"])
                    sortie.write(json.dumps(article, ensure_ascii=False) + "\n")
                    nouveaux += 1

                recuperes += len(articles)
                total += nouveaux
                debut += len(articles)
                print(f"    {recuperes}/{nb_par_categorie} lus "
                      f"({nouveaux} nouveaux, {total} au total)")

                time.sleep(config.DELAI_ENTRE_REQUETES)

    print(f"\nCorpus écrit dans {fichier_sortie}")
    print(f"{total} articles uniques")
    return total


def charger_corpus(fichier: Path | None = None) -> list[dict]:
    """Relit le fichier JSONL produit par collecter()."""
    fichier = fichier or config.FICHIER_CORPUS
    if not fichier.exists():
        raise FileNotFoundError(
            f"Corpus introuvable : {fichier}\n"
            "Lance d'abord :  python scripts/1_collecter.py"
        )

    with open(fichier, encoding="utf-8") as entree:
        return [json.loads(ligne) for ligne in entree if ligne.strip()]
