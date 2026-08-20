"""
Étape 4 : l'index vectoriel.

FAISS répond à une seule question, mais très vite : « parmi ces N vecteurs,
lesquels ressemblent le plus à celui-ci ? »

Deux structures sont proposées ici.

- IndexFlatIP compare la requête à absolument tous les vecteurs. Le résultat
  est exact. Sur 10 000 vecteurs de 384 dimensions, une recherche prend environ
  une milliseconde : inutile de compliquer.

- IndexIVFFlat regroupe d'abord les vecteurs en « quartiers » (clusters), puis
  ne fouille que les quartiers les plus proches de la requête. Beaucoup plus
  rapide sur des millions de vecteurs, mais approximatif : un bon voisin situé
  dans un quartier non visité est manqué. C'est le compromis classique entre
  vitesse et exhaustivité, et le mesurer fait un bon paragraphe de rapport.

IP signifie *inner product*, produit scalaire. Comme tous nos vecteurs sont
normalisés, ce produit scalaire vaut exactement la similarité cosinus.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

import config


class IndexVectoriel:
    """Enveloppe autour de FAISS, avec sauvegarde et rechargement."""

    def __init__(self, dimension: int | None = None, type_index: str | None = None):
        self.dimension = dimension or config.DIMENSION
        self.type_index = (type_index or config.TYPE_INDEX).lower()
        self.index = None

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def construire(self, vecteurs: np.ndarray, verbeux: bool = True) -> None:
        """Crée l'index et y insère tous les vecteurs d'un coup."""
        import faiss

        if vecteurs.dtype != np.float32:
            vecteurs = vecteurs.astype("float32")

        nb_vecteurs, dimension = vecteurs.shape
        if dimension != self.dimension:
            raise ValueError(
                f"Dimension inattendue : {dimension} reçue, {self.dimension} attendue."
            )

        if self.type_index == "flat":
            self.index = faiss.IndexFlatIP(self.dimension)

        elif self.type_index == "ivf":
            # FAISS demande environ 39 vecteurs d'entraînement par cluster.
            nb_clusters = min(config.NB_CLUSTERS_IVF, max(1, nb_vecteurs // 39))
            quantifieur = faiss.IndexFlatIP(self.dimension)
            self.index = faiss.IndexIVFFlat(
                quantifieur, self.dimension, nb_clusters, faiss.METRIC_INNER_PRODUCT
            )
            if verbeux:
                print(f"Entraînement de l'index IVF ({nb_clusters} clusters) ...")
            self.index.train(vecteurs)
            self.index.nprobe = config.NB_SONDES_IVF

        else:
            raise ValueError(
                f"Type d'index inconnu : {self.type_index!r} (attendu 'flat' ou 'ivf')"
            )

        self.index.add(vecteurs)
        if verbeux:
            print(f"Index {self.type_index} construit : {self.index.ntotal} vecteurs")

    # ------------------------------------------------------------------
    # Recherche
    # ------------------------------------------------------------------

    def rechercher(self, vecteurs_requete: np.ndarray, k: int) -> tuple[np.ndarray, np.ndarray]:
        """
        Cherche les k plus proches voisins.

        Returns:
            (scores, identifiants) — deux tableaux de forme (nb_requêtes, k).
            Un identifiant vaut -1 quand FAISS n'a pas trouvé assez de voisins.
        """
        if self.index is None:
            raise RuntimeError("Index vide : appelle construire() ou charger() d'abord.")

        if vecteurs_requete.dtype != np.float32:
            vecteurs_requete = vecteurs_requete.astype("float32")
        if vecteurs_requete.ndim == 1:
            vecteurs_requete = vecteurs_requete.reshape(1, -1)

        k = max(1, min(k, self.index.ntotal))
        return self.index.search(vecteurs_requete, k)

    # ------------------------------------------------------------------
    # Persistance
    # ------------------------------------------------------------------

    def sauvegarder(self, chemin: Path | None = None) -> None:
        """Écrit l'index sur le disque pour ne jamais avoir à le reconstruire."""
        import faiss

        chemin = Path(chemin or config.FICHIER_INDEX)
        chemin.parent.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self.index, str(chemin))

    @classmethod
    def charger(cls, chemin: Path | None = None) -> "IndexVectoriel":
        """Relit un index déjà construit. Opération quasi instantanée."""
        import faiss

        chemin = Path(chemin or config.FICHIER_INDEX)
        if not chemin.exists():
            raise FileNotFoundError(
                f"Index introuvable : {chemin}\n"
                "Lance d'abord :  python scripts/2_indexer.py"
            )

        objet = cls()
        objet.index = faiss.read_index(str(chemin))
        objet.dimension = objet.index.d

        # nprobe n'est pas toujours conservé dans le fichier : on le repose.
        if hasattr(objet.index, "nprobe"):
            objet.index.nprobe = config.NB_SONDES_IVF
            objet.type_index = "ivf"
        else:
            objet.type_index = "flat"

        return objet

    @property
    def nb_vecteurs(self) -> int:
        return 0 if self.index is None else self.index.ntotal
