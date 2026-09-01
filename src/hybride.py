"""
La recherche hybride : faire voter les deux moteurs.

L'évaluation du projet aboutit à une conclusion nuancée. Là où les mots se
recouvrent, BM25 reste légèrement meilleur ; là où ils ne se recouvrent pas
— autre langue, autre vocabulaire — le moteur sémantique est le seul à
répondre. Aucun des deux ne domine partout.

La conséquence logique n'est pas de choisir, c'est de combiner. C'est ce que
fait ce module, et c'est devenu le standard en production (Elasticsearch,
Vespa, Weaviate proposent tous une fusion de ce type).

### Pourquoi fusionner les rangs et non les scores

Un score BM25 vaut typiquement entre 0 et 40, sans borne supérieure, et dépend
du corpus. Un cosinus vaut entre -1 et 1. Les additionner directement n'a
aucun sens : l'échelle de BM25 écraserait l'autre. On pourrait normaliser les
scores (min-max, z-score), mais la normalisation dépend alors du lot de
résultats renvoyé, donc de la requête — deux requêtes ne sont plus comparables.

La *Reciprocal Rank Fusion* (Cormack et al., 2009) contourne le problème en
n'utilisant que les **rangs**, qui sont dans la même unité par construction :

    score_RRF(document) = somme sur chaque moteur de  poids / (K + rang)

Un document premier chez un moteur reçoit 1/(60+1), deuxième 1/(60+2), etc.
La constante K = 60 (valeur de l'article d'origine) amortit le sommet du
classement : sans elle, la première place vaudrait deux fois la deuxième, ce
qui donnerait à un seul moteur un droit de veto sur la fusion.

Un document trouvé honorablement par les deux moteurs finit ainsi devant un
document trouvé premier par un seul. C'est exactement le comportement voulu :
l'accord entre deux méthodes indépendantes est un signal de pertinence.
"""

from __future__ import annotations

import config

# Constante d'amortissement de la RRF. 60 est la valeur de l'article original,
# reprise telle quelle par la plupart des implémentations.
K_RRF = 60

# Nombre de candidats demandés à chaque moteur avant fusion. Fusionner
# seulement les 10 premiers de chacun perdrait les documents classés 15e par
# les deux, qui sont précisément ceux que la fusion sait faire remonter.
PROFONDEUR_FUSION = 50


def fusion_rrf(
    classements: dict[str, list[dict]],
    k: int | None = None,
    poids: dict[str, float] | None = None,
    k_rrf: int = K_RRF,
) -> list[dict]:
    """
    Fusionne plusieurs classements en un seul par Reciprocal Rank Fusion.

    Args:
        classements: un dictionnaire {nom du moteur: liste de résultats},
                     chaque liste étant déjà triée par pertinence décroissante.
        k: nombre de résultats à renvoyer.
        poids: importance relative de chaque moteur (1.0 par défaut). Mettre
               2.0 sur le sémantique le fait peser double dans le vote.
        k_rrf: constante d'amortissement.

    Returns:
        Les k meilleurs documents, chacun enrichi de sa provenance : rang et
        score obtenus dans chaque moteur d'origine. C'est cette traçabilité
        qui permet à l'interface d'expliquer *pourquoi* un document est là.
    """
    k = k or config.TOP_K
    poids = poids or {}

    fusionnes: dict[str, dict] = {}

    for nom_moteur, resultats in classements.items():
        poids_moteur = poids.get(nom_moteur, 1.0)
        if poids_moteur == 0:
            continue

        for rang, resultat in enumerate(resultats, start=1):
            id_doc = resultat["id_doc"]

            if id_doc not in fusionnes:
                # On recopie les métadonnées du premier moteur qui trouve le
                # document, puis on y accroche les informations de fusion.
                fusionnes[id_doc] = {
                    **resultat,
                    "score_rrf": 0.0,
                    "sources": [],
                    "rangs": {},
                    "scores": {},
                }

            entree = fusionnes[id_doc]
            entree["score_rrf"] += poids_moteur / (k_rrf + rang)
            entree["sources"].append(nom_moteur)
            entree["rangs"][nom_moteur] = rang
            entree["scores"][nom_moteur] = round(float(resultat["score"]), 4)

            # L'extrait affiché vient du moteur qui classe le document le
            # mieux : c'est le passage le plus susceptible d'être pertinent.
            if rang < entree["rangs"].get(entree.get("_meilleur_moteur", ""), 10**9):
                entree["_meilleur_moteur"] = nom_moteur
                entree["extrait"] = resultat["extrait"]

    classement = sorted(
        fusionnes.values(), key=lambda r: r["score_rrf"], reverse=True
    )[:k]

    for rang, resultat in enumerate(classement, start=1):
        resultat["rang"] = rang
        # Le score exposé reste dans la clé « score » pour que l'API, l'interface
        # et l'évaluation traitent ce moteur exactement comme les deux autres.
        #
        # Il n'est volontairement pas arrondi : les scores RRF valent quelques
        # centièmes et se distinguent souvent à la cinquième décimale. Un
        # arrondi d'affichage placé ici rendrait des documents artificiellement
        # ex æquo. C'est à l'affichage de choisir son format, pas au moteur.
        resultat["score"] = resultat["score_rrf"]
        resultat.pop("_meilleur_moteur", None)

    return classement


class MoteurHybride:
    """
    Assemble le moteur sémantique et la baseline lexicale en un seul moteur.

    La classe expose `chercher` et `chercher_lot` avec exactement la même
    signature que les deux autres moteurs. Conséquence pratique : l'API,
    l'interface et le script d'évaluation l'utilisent sans une ligne de code
    spécifique — il suffit de le passer là où on passait les autres.
    """

    def __init__(
        self,
        moteur_semantique,
        moteur_lexical,
        poids_semantique: float = 1.0,
        poids_lexical: float = 1.0,
        profondeur: int = PROFONDEUR_FUSION,
    ):
        self.semantique = moteur_semantique
        self.lexical = moteur_lexical
        self.poids = {
            "semantique": poids_semantique,
            "lexical": poids_lexical,
        }
        self.profondeur = profondeur

    # ------------------------------------------------------------------

    def chercher(self, requete: str, k: int | None = None, filtres=None) -> list[dict]:
        """Interroge les deux moteurs, puis fusionne leurs classements."""
        k = k or config.TOP_K
        if not requete or not requete.strip():
            return []

        profondeur = max(self.profondeur, k)
        classements = {}

        if self.semantique is not None and self.poids["semantique"]:
            classements["semantique"] = self.semantique.chercher(
                requete, k=profondeur, filtres=filtres
            )

        # BM25 renvoie une liste vide dès que la requête ne partage aucun mot
        # avec le corpus — le cas des requêtes arabes. La fusion continue
        # alors avec le seul moteur sémantique, sans traitement particulier :
        # une somme sur un seul terme reste une somme valide.
        if self.lexical is not None and self.poids["lexical"]:
            classements["lexical"] = self.lexical.chercher(
                requete, k=profondeur, filtres=filtres
            )

        return fusion_rrf(classements, k=k, poids=self.poids)

    def chercher_lot(self, requetes: list[str], k: int | None = None, filtres=None) -> list[list[dict]]:
        """
        Version par lot pour l'évaluation.

        Le moteur sémantique encode les requêtes par paquets, ce qui est
        nettement plus rapide que de les traiter une par une ; on conserve donc
        cette optimisation au lieu de boucler sur `chercher`.
        """
        k = k or config.TOP_K
        if not requetes:
            return []

        profondeur = max(self.profondeur, k)

        lots_semantiques = (
            self.semantique.chercher_lot(requetes, k=profondeur, filtres=filtres)
            if self.semantique is not None
            else [[] for _ in requetes]
        )
        lots_lexicaux = (
            self.lexical.chercher_lot(requetes, k=profondeur, filtres=filtres)
            if self.lexical is not None
            else [[] for _ in requetes]
        )

        return [
            fusion_rrf(
                {"semantique": lots_semantiques[i], "lexical": lots_lexicaux[i]},
                k=k,
                poids=self.poids,
            )
            for i in range(len(requetes))
        ]

    # ------------------------------------------------------------------

    @property
    def nb_documents(self) -> int:
        if self.semantique is not None:
            return self.semantique.nb_documents
        return self.lexical.nb_documents if self.lexical is not None else 0
