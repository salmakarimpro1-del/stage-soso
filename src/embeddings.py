"""
Étape 3 : transformer du texte en vecteurs.

Ce module encapsule Sentence-BERT. C'est le seul endroit du projet qui sait
qu'un modèle de langue existe : tout le reste ne manipule que des tableaux de
nombres.

Deux détails séparent un moteur correct d'un moteur silencieusement cassé.

1. Les préfixes E5. Le modèle a été entraîné avec « query: » devant les
   questions et « passage: » devant les documents. Sans eux, la qualité chute
   nettement, et sans le moindre message d'erreur — un bug très difficile à
   repérer quand on ne le connaît pas.

2. La normalisation. On ramène chaque vecteur à une longueur de 1. Le produit
   scalaire entre deux vecteurs normalisés vaut alors exactement leur cosinus,
   ce qui permet d'utiliser l'index le plus rapide de FAISS tout en mesurant
   une similarité d'angle (le sens) et non de longueur (la taille du texte).
"""

from __future__ import annotations

import numpy as np

import config


class Encodeur:
    """Enveloppe autour de Sentence-BERT : du texte vers des vecteurs normalisés."""

    def __init__(self, nom_modele: str | None = None, verbeux: bool = True):
        self.nom_modele = nom_modele or config.NOM_MODELE
        self.verbeux = verbeux
        self._modele = None   # chargé à la première utilisation seulement

    @property
    def modele(self):
        """
        Charge le modèle au dernier moment.

        Le premier appel télécharge environ 470 Mo depuis Hugging Face, puis le
        modèle reste en cache dans le dossier utilisateur. Les fois suivantes,
        le chargement prend deux ou trois secondes.
        """
        if self._modele is None:
            from sentence_transformers import SentenceTransformer

            if self.verbeux:
                print(f"Chargement du modèle {self.nom_modele} ...")
            self._modele = SentenceTransformer(self.nom_modele, device="cpu")
            if self.verbeux:
                print(f"Modèle prêt — {self.dimension} dimensions par vecteur")
        return self._modele

    @property
    def dimension(self) -> int:
        """Nombre de nombres composant un vecteur (384 pour e5-small)."""
        # Cette méthode a été renommée dans sentence-transformers 6 :
        # on gère les deux noms pour rester compatible avec les versions
        # antérieures, encore très répandues.
        if hasattr(self.modele, "get_embedding_dimension"):
            return self.modele.get_embedding_dimension()
        return self.modele.get_sentence_embedding_dimension()

    def _encoder(self, textes: list[str], prefixe: str, barre: bool) -> np.ndarray:
        if not textes:
            return np.zeros((0, config.DIMENSION), dtype="float32")

        vecteurs = self.modele.encode(
            [prefixe + t for t in textes],
            batch_size=config.TAILLE_LOT,
            normalize_embeddings=True,     # longueur ramenée à 1
            convert_to_numpy=True,
            show_progress_bar=barre,
        )
        # FAISS n'accepte que du float32 contigu en mémoire.
        return np.ascontiguousarray(vecteurs.astype("float32"))

    def encoder_documents(self, textes: list[str], barre: bool = True) -> np.ndarray:
        """Encode des passages de documents (préfixe « passage: »)."""
        return self._encoder(textes, config.PREFIXE_DOCUMENT, barre)

    def encoder_requetes(self, textes: list[str], barre: bool = False) -> np.ndarray:
        """Encode des requêtes utilisateur (préfixe « query: »)."""
        return self._encoder(textes, config.PREFIXE_REQUETE, barre)

    def encoder_requete(self, texte: str) -> np.ndarray:
        """Encode une requête unique et renvoie un tableau de forme (1, d)."""
        return self.encoder_requetes([texte])
