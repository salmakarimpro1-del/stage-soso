"""
La baseline lexicale : BM25.

Pourquoi implémenter un moteur « à l'ancienne » dans un projet dont le sujet
est la recherche sémantique ? Parce que sans point de comparaison, la phrase
« notre moteur donne de bons résultats » n'a aucune valeur scientifique. Il
faut montrer par rapport à quoi.

BM25 est la référence du domaine depuis les années 1990, et reste utilisée en
production partout (Elasticsearch, Lucene, Solr). Son principe :

- un document contenant plusieurs fois le mot cherché est plus pertinent ;
- mais avec un rendement décroissant (10 occurrences ne valent pas 10 fois 1) ;
- un mot rare dans le corpus est plus informatif qu'un mot fréquent
  (« transformer » discrimine, « the » non) ;
- un document long est pénalisé, sinon il gagnerait par accumulation.

C'est puissant et très rapide. Sa limite est structurelle et ne se corrige pas
par réglage : si la requête et le document ne partagent aucun mot, le score
est zéro. Aucune reformulation, aucun synonyme, aucune traduction ne passe.
C'est exactement ce que notre évaluation va quantifier.
"""

from __future__ import annotations

import pickle
import re
from pathlib import Path

import config
from src.resultats import regrouper_par_document

# \w en Python couvre l'alphabet latin accentué ET l'alphabet arabe, ce qui
# permet d'utiliser le même découpage pour les trois langues du projet.
MOTIF_MOTS = re.compile(r"\w+", re.UNICODE)


def tokeniser(texte: str) -> list[str]:
    """Découpe un texte en mots minuscules, sans ponctuation."""
    return MOTIF_MOTS.findall(texte.lower())


class MoteurLexical:
    """Recherche par correspondance de mots-clés, avec pondération BM25."""

    def __init__(self, verbeux: bool = True):
        self.verbeux = verbeux
        self.bm25 = None
        self.passages: list[dict] = []

    # ------------------------------------------------------------------

    def indexer(self, passages: list[dict]) -> dict:
        """
        Construit l'index BM25 sur exactement les mêmes passages que le moteur
        sémantique — condition indispensable pour que la comparaison soit juste.
        """
        import time

        from rank_bm25 import BM25Okapi

        depart = time.perf_counter()
        self.passages = passages
        corpus_tokenise = [tokeniser(p["texte_indexe"]) for p in passages]
        self.bm25 = BM25Okapi(corpus_tokenise)
        duree = round(time.perf_counter() - depart, 2)

        if self.verbeux:
            print(f"Index BM25 construit : {len(passages)} passages en {duree} s")

        return {"nb_passages": len(passages), "duree_construction_index_s": duree}

    def sauvegarder(self, chemin: Path | None = None) -> None:
        chemin = Path(chemin or config.FICHIER_BM25)
        chemin.parent.mkdir(parents=True, exist_ok=True)
        with open(chemin, "wb") as sortie:
            pickle.dump({"bm25": self.bm25, "passages": self.passages}, sortie)
        if self.verbeux:
            print(f"Index BM25 écrit dans {chemin}")

    def charger(self, chemin: Path | None = None) -> "MoteurLexical":
        chemin = Path(chemin or config.FICHIER_BM25)
        if not chemin.exists():
            raise FileNotFoundError(
                f"Index BM25 introuvable : {chemin}\n"
                "Lance d'abord :  python scripts/2_indexer.py"
            )
        with open(chemin, "rb") as entree:
            donnees = pickle.load(entree)
        self.bm25 = donnees["bm25"]
        self.passages = donnees["passages"]
        if self.verbeux:
            print(f"Moteur lexical chargé : {len(self.passages)} passages")
        return self

    # ------------------------------------------------------------------

    def chercher(self, requete: str, k: int | None = None) -> list[dict]:
        """Même signature et même format de sortie que le moteur sémantique."""
        k = k or config.TOP_K
        if not requete or not requete.strip() or self.bm25 is None:
            return []

        mots = tokeniser(requete)
        if not mots:
            return []

        import numpy as np

        scores = np.asarray(self.bm25.get_scores(mots))
        nb_a_prendre = min(k * config.MULTIPLICATEUR_PASSAGES, len(scores))

        # argpartition isole les nb_a_prendre meilleurs sans trier les 10 000
        # autres : on ne trie ensuite que ce petit sous-ensemble. Trier le
        # tableau entier coûtait ici trois fois plus cher que la recherche
        # vectorielle elle-même — et aurait faussé la comparaison des latences
        # en faveur du moteur sémantique.
        indices = np.argpartition(-scores, nb_a_prendre - 1)[:nb_a_prendre]
        indices = indices[np.argsort(-scores[indices])]
        meilleurs = [int(i) for i in indices if scores[i] > 0]

        return regrouper_par_document(
            [scores[i] for i in meilleurs], meilleurs, self.passages, k
        )

    def chercher_lot(self, requetes: list[str], k: int | None = None) -> list[list[dict]]:
        """BM25 n'a pas de traitement par lot : on boucle simplement."""
        return [self.chercher(requete, k) for requete in requetes]

    @property
    def nb_documents(self) -> int:
        return len({p["id_doc"] for p in self.passages})
