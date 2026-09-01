"""
Le moteur sémantique : la pièce qui assemble tout le reste.

C'est la classe que l'API, l'interface et les scripts d'évaluation utilisent.
Elle expose deux opérations, qui correspondent exactement aux deux phases du
système :

    indexer()  — phase hors ligne, lente, exécutée une seule fois ;
    chercher() — phase en ligne, rapide, exécutée à chaque requête.

Le point crucial : `indexer` et `chercher` passent par le MÊME encodeur. Si
l'on indexait avec un modèle et cherchait avec un autre, les deux ensembles de
vecteurs vivraient dans des espaces différents et les résultats seraient du
pur hasard — sans qu'aucune erreur ne s'affiche.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import config
from src.embeddings import Encodeur
from src.filtres import taille_vivier
from src.index_faiss import IndexVectoriel
from src.pretraitement import preparer_passages
from src.resultats import regrouper_par_document


class MoteurSemantique:
    """Recherche par similarité de sens, appuyée sur Sentence-BERT et FAISS."""

    def __init__(self, verbeux: bool = True):
        self.verbeux = verbeux
        self.encodeur = Encodeur(verbeux=verbeux)
        self.index: IndexVectoriel | None = None
        self.passages: list[dict] = []

    # ------------------------------------------------------------------
    # Phase 1 : indexation
    # ------------------------------------------------------------------

    def indexer(self, corpus: list[dict]) -> dict:
        """
        Construit l'index à partir du corpus brut, puis l'écrit sur le disque.

        Returns:
            Un dictionnaire de statistiques (durées, volumes) réutilisable
            dans le rapport.
        """
        statistiques: dict = {}

        depart = time.perf_counter()
        self.passages = preparer_passages(corpus)
        statistiques["nb_documents"] = len(corpus)
        statistiques["nb_passages"] = len(self.passages)
        statistiques["duree_preparation_s"] = round(time.perf_counter() - depart, 2)

        if not self.passages:
            raise ValueError("Aucun passage à indexer : le corpus est vide.")

        if self.verbeux:
            print(f"{len(corpus)} documents découpés en {len(self.passages)} passages")

        depart = time.perf_counter()
        textes = [p["texte_indexe"] for p in self.passages]
        vecteurs = self.encodeur.encoder_documents(textes, barre=self.verbeux)
        statistiques["duree_encodage_s"] = round(time.perf_counter() - depart, 2)
        statistiques["dimension"] = int(vecteurs.shape[1])

        depart = time.perf_counter()
        self.index = IndexVectoriel(dimension=vecteurs.shape[1])
        self.index.construire(vecteurs, verbeux=self.verbeux)
        statistiques["duree_construction_index_s"] = round(time.perf_counter() - depart, 2)
        statistiques["type_index"] = self.index.type_index

        self._sauvegarder(vecteurs)
        statistiques["taille_index_mo"] = round(
            Path(config.FICHIER_INDEX).stat().st_size / (1024 * 1024), 2
        )

        if self.verbeux:
            print(
                f"Encodage : {statistiques['duree_encodage_s']} s "
                f"({len(self.passages) / max(statistiques['duree_encodage_s'], 0.01):.0f} passages/s)"
            )

        return statistiques

    def _sauvegarder(self, vecteurs=None) -> None:
        """Écrit l'index FAISS, la table des passages et les vecteurs bruts."""
        self.index.sauvegarder(config.FICHIER_INDEX)

        if vecteurs is not None:
            import numpy as np

            np.save(config.FICHIER_VECTEURS, vecteurs)

        config.FICHIER_PASSAGES.parent.mkdir(parents=True, exist_ok=True)
        with open(config.FICHIER_PASSAGES, "w", encoding="utf-8") as sortie:
            json.dump(self.passages, sortie, ensure_ascii=False)

        if self.verbeux:
            print(f"Index écrit dans      {config.FICHIER_INDEX}")
            print(f"Passages écrits dans  {config.FICHIER_PASSAGES}")

    # ------------------------------------------------------------------
    # Phase 2 : recherche
    # ------------------------------------------------------------------

    def charger(self) -> "MoteurSemantique":
        """
        Relit l'index et la table des passages depuis le disque.

        Sans cette étape, il faudrait ré-encoder tout le corpus à chaque
        démarrage : c'est l'erreur qui rend tant de projets étudiants
        inutilisables en démonstration.
        """
        self.index = IndexVectoriel.charger(config.FICHIER_INDEX)

        if not config.FICHIER_PASSAGES.exists():
            raise FileNotFoundError(
                f"Table des passages introuvable : {config.FICHIER_PASSAGES}\n"
                "Lance d'abord :  python scripts/2_indexer.py"
            )

        with open(config.FICHIER_PASSAGES, encoding="utf-8") as entree:
            self.passages = json.load(entree)

        if self.index.nb_vecteurs != len(self.passages):
            raise ValueError(
                f"Index et passages désynchronisés : {self.index.nb_vecteurs} vecteurs "
                f"pour {len(self.passages)} passages. Relance l'indexation."
            )

        if self.verbeux:
            print(f"Moteur chargé : {self.index.nb_vecteurs} vecteurs, "
                  f"{self.nb_documents} articles")
        return self

    def prechauffer(self) -> None:
        """
        Force le chargement du modèle avant la première vraie requête.

        L'encodeur charge son modèle paresseusement, à la première utilisation.
        C'est le bon comportement pour un script, mais pas pour un service :
        sans ce préchauffage, le tout premier utilisateur attend une quinzaine
        de secondes pendant que le modèle se charge, et lui seul.
        """
        self.encodeur.encoder_requetes(["préchauffage"], barre=False)

    def chercher(self, requete: str, k: int | None = None, filtres=None) -> list[dict]:
        """
        Recherche les articles les plus proches d'une requête en langage naturel.

        Args:
            requete: la question de l'utilisateur, dans n'importe quelle langue.
            k: nombre d'articles souhaités.
            filtres: test optionnel sur les métadonnées (voir src/filtres.py).

        Returns:
            Une liste d'articles triés du plus pertinent au moins pertinent.
            Le score est un cosinus : plus il est proche de 1, plus le sens
            est voisin.
        """
        k = k or config.TOP_K
        if not requete or not requete.strip():
            return []

        vecteur = self.encodeur.encoder_requete(requete)
        # On demande plus de passages que d'articles voulus, car plusieurs
        # passages peuvent appartenir au même article — et beaucoup plus encore
        # quand un filtre va en écarter une partie.
        nb_candidats = taille_vivier(k, filtres is not None, config.MULTIPLICATEUR_PASSAGES)
        scores, identifiants = self.index.rechercher(vecteur, nb_candidats)
        return regrouper_par_document(
            scores[0], identifiants[0], self.passages, k, filtre=filtres
        )

    def chercher_lot(
        self, requetes: list[str], k: int | None = None, filtres=None
    ) -> list[list[dict]]:
        """
        Version par lot, utilisée par l'évaluation.

        Encoder 500 requêtes d'un seul coup est nettement plus rapide que de
        les encoder une par une : le modèle exploite mieux le processeur.
        """
        k = k or config.TOP_K
        if not requetes:
            return []

        vecteurs = self.encodeur.encoder_requetes(requetes, barre=self.verbeux)
        nb_candidats = taille_vivier(k, filtres is not None, config.MULTIPLICATEUR_PASSAGES)
        scores, identifiants = self.index.rechercher(vecteurs, nb_candidats)
        return [
            regrouper_par_document(
                scores[i], identifiants[i], self.passages, k, filtre=filtres
            )
            for i in range(len(requetes))
        ]

    # ------------------------------------------------------------------

    @property
    def nb_documents(self) -> int:
        return len({p["id_doc"] for p in self.passages})

    @property
    def nb_passages(self) -> int:
        return len(self.passages)
