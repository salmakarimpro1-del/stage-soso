"""
Évaluation : la partie qui transforme une démonstration en travail scientifique.

Une belle démo peut toujours être une coïncidence. Ce module mesure, sur des
centaines de requêtes, ce que chaque moteur retrouve réellement.

Trois protocoles complémentaires sont implémentés.

1. Titre vers résumé (avec vérité terrain automatique)
   On prend le titre d'un article au hasard et on s'en sert comme requête. Le
   bon résultat est connu d'avance : c'est l'article lui-même. Cela produit
   des centaines de requêtes annotées sans le moindre travail manuel.
   Le titre et le résumé partagent du vocabulaire sans être identiques, ce qui
   en fait une tâche honnête pour les deux moteurs.
   Rappel : le titre n'est PAS indexé (voir INCLURE_TITRE_DANS_INDEX dans
   config.py), sinon BM25 gagnerait par simple correspondance exacte.

2. Cohérence multilingue (sans annotation)
   La même question est posée en français, en arabe et en anglais. Si l'espace
   vectoriel est réellement indépendant de la langue, les trois requêtes
   doivent renvoyer à peu près les mêmes articles. On mesure le taux de
   recouvrement des dix premiers résultats entre deux langues. Aucune
   annotation n'est nécessaire, et la mesure attaque directement l'argument
   central du projet.

3. Latence et coût
   Temps de réponse (médiane et 95e centile), temps de construction, taille de
   l'index, et comparaison entre index exact et index approximatif.
"""

from __future__ import annotations

import math
import random
import statistics
import time

import config
from src.baseline_bm25 import tokeniser


# ---------------------------------------------------------------------------
# Métriques
# ---------------------------------------------------------------------------

def rang_du_document(resultats: list[dict], id_attendu: str) -> int | None:
    """Position (à partir de 1) du bon document, ou None s'il est absent."""
    for rang, resultat in enumerate(resultats, start=1):
        if resultat["id_doc"] == id_attendu:
            return rang
    return None


def recall_at_k(rang: int | None, k: int) -> float:
    """1 si le bon document figure dans les k premiers résultats, sinon 0.

    Sur une requête à un seul document pertinent, le rappel se confond avec la
    précision at k et se lit simplement : « le moteur a-t-il trouvé ? »
    """
    return 1.0 if rang is not None and rang <= k else 0.0


def reciprocal_rank(rang: int | None, k: int | None = None) -> float:
    """1/rang : 1 si le bon document est premier, 0.5 s'il est deuxième, etc.

    Moyenné sur toutes les requêtes, cela donne le MRR (Mean Reciprocal Rank),
    la métrique la plus utilisée quand il n'y a qu'un seul bon résultat.

    Si `k` est fourni, un document trouvé au-delà du rang k compte pour zéro :
    c'est la définition stricte du MRR@k.
    """
    if rang is None or (k is not None and rang > k):
        return 0.0
    return 1.0 / rang


def ndcg_at_k(rang: int | None, k: int) -> float:
    """
    Gain cumulé actualisé normalisé.

    Avec un unique document pertinent, la formule se simplifie en
    1 / log2(rang + 1) : le gain décroît logarithmiquement avec la position,
    ce qui traduit qu'un utilisateur regarde surtout le haut de la liste.
    """
    if rang is None or rang > k:
        return 0.0
    return 1.0 / math.log2(rang + 1)


# ---------------------------------------------------------------------------
# Protocole 1 : titre vers résumé
# ---------------------------------------------------------------------------

def construire_requetes_titres(
    corpus: list[dict],
    nb_requetes: int = 500,
    graine: int = 42,
    longueur_min: int = 4,
) -> tuple[list[str], list[str]]:
    """
    Tire au sort des articles et utilise leur titre comme requête.

    Args:
        longueur_min: on écarte les titres de moins de 4 mots, trop ambigus
                      pour constituer une requête exploitable.

    Returns:
        (requêtes, identifiants attendus)
    """
    candidats = [
        document for document in corpus
        if len(document.get("titre", "").split()) >= longueur_min
        and document.get("resume")
    ]

    generateur = random.Random(graine)   # graine fixe = résultats reproductibles
    echantillon = generateur.sample(candidats, min(nb_requetes, len(candidats)))

    return [d["titre"] for d in echantillon], [d["id"] for d in echantillon]


def evaluer_moteur(
    moteur,
    requetes: list[str],
    identifiants_attendus: list[str],
    k: int = 10,
    valeurs_k: tuple[int, ...] = (1, 5, 10),
) -> dict:
    """
    Fait passer un jeu de requêtes à un moteur et calcule toutes les métriques.

    Le moteur peut être sémantique ou lexical : les deux exposent la même
    méthode `chercher_lot`, ce qui rend la comparaison directe.
    """
    if not requetes:
        return {}

    # On récupère assez de résultats pour calculer toutes les métriques
    # demandées : impossible de mesurer un recall@10 sur 5 résultats.
    k_effectif = max(k, *valeurs_k)

    depart = time.perf_counter()
    tous_resultats = moteur.chercher_lot(requetes, k=k_effectif)
    duree_totale = time.perf_counter() - depart

    rangs = [
        rang_du_document(resultats, attendu)
        for resultats, attendu in zip(tous_resultats, identifiants_attendus)
    ]

    mesures = {f"recall@{valeur}": round(
        statistics.fmean(recall_at_k(rang, valeur) for rang in rangs), 4
    ) for valeur in valeurs_k}

    mesures[f"mrr@{k}"] = round(statistics.fmean(reciprocal_rank(r, k) for r in rangs), 4)
    mesures[f"ndcg@{k}"] = round(statistics.fmean(ndcg_at_k(r, k) for r in rangs), 4)
    mesures["nb_requetes"] = len(requetes)
    mesures["duree_totale_s"] = round(duree_totale, 2)
    mesures["ms_par_requete"] = round(1000 * duree_totale / max(len(requetes), 1), 2)
    mesures["taux_echec"] = round(
        statistics.fmean(1.0 if r is None else 0.0 for r in rangs), 4
    )

    return mesures


# ---------------------------------------------------------------------------
# Protocole 1 bis : stratification par recouvrement lexical
# ---------------------------------------------------------------------------

def recouvrement_lexical(requete: str, texte_document: str) -> float:
    """
    Proportion des mots de la requête présents dans le document.

    C'est exactement la quantité dont BM25 dépend : à 1, il lui suffit de
    compter des occurrences ; à 0, il n'a plus rien sur quoi s'appuyer.
    """
    mots_requete = set(tokeniser(requete))
    if not mots_requete:
        return 0.0
    return len(mots_requete & set(tokeniser(texte_document))) / len(mots_requete)


def stratifier_par_recouvrement(
    requetes: list[str],
    identifiants_attendus: list[str],
    corpus: list[dict],
    nb_groupes: int = 3,
) -> list[dict]:
    """
    Répartit les requêtes en groupes selon leur recouvrement lexical.

    Une évaluation globale mélange deux situations très différentes : les
    requêtes qui partagent beaucoup de vocabulaire avec le bon document, et
    celles qui n'en partagent presque aucun. Les moyenner ensemble masque
    précisément l'endroit où la recherche sémantique apporte quelque chose.

    Ce protocole sépare les deux et évalue chaque groupe à part. C'est la
    mesure qui répond vraiment à la question « quand le sémantique sert-il ? ».
    """
    textes = {document["id"]: document.get("resume", "") for document in corpus}

    scores = [
        recouvrement_lexical(requete, textes.get(identifiant, ""))
        for requete, identifiant in zip(requetes, identifiants_attendus)
    ]

    ordre = sorted(range(len(requetes)), key=lambda i: scores[i])
    noms = ["faible recouvrement", "recouvrement moyen", "fort recouvrement"]
    taille = len(ordre) // nb_groupes
    groupes = []

    for numero in range(nb_groupes):
        debut = numero * taille
        fin = len(ordre) if numero == nb_groupes - 1 else (numero + 1) * taille
        indices = ordre[debut:fin]
        if not indices:
            continue

        groupes.append(
            {
                "nom": noms[numero] if numero < len(noms) else f"groupe {numero + 1}",
                "requetes": [requetes[i] for i in indices],
                "attendus": [identifiants_attendus[i] for i in indices],
                "recouvrement_moyen": round(statistics.fmean(scores[i] for i in indices), 3),
                "recouvrement_min": round(min(scores[i] for i in indices), 3),
                "recouvrement_max": round(max(scores[i] for i in indices), 3),
            }
        )

    return groupes


# ---------------------------------------------------------------------------
# Protocole 1 ter : requêtes appauvries
# ---------------------------------------------------------------------------

def _frequences_documentaires(corpus: list[dict]) -> dict[str, int]:
    """Compte dans combien de documents chaque mot apparaît."""
    frequences: dict[str, int] = {}
    for document in corpus:
        for mot in set(tokeniser(document.get("resume", ""))):
            frequences[mot] = frequences.get(mot, 0) + 1
    return frequences


def construire_requetes_appauvries(
    corpus: list[dict],
    nb_requetes: int = 500,
    nb_mots_retires: int = 3,
    graine: int = 42,
) -> tuple[list[str], list[str], list[str]]:
    """
    Fabrique des requêtes dont on a retiré les mots les plus discriminants.

    Le protocole « titre vers résumé » ne teste pas la compréhension du sens :
    même son tiers le plus difficile partage encore les deux tiers de son
    vocabulaire avec le bon document. La raison est que les titres
    scientifiques contiennent des termes rares — un nom de méthode, un
    acronyme — qu'il suffit de faire correspondre.

    On retire donc de chaque titre ses mots les plus rares dans le corpus.
    Il ne reste que du vocabulaire courant, c'est-à-dire du sujet sans
    signature lexicale. BM25 perd alors ce sur quoi il s'appuie ; un moteur
    qui comprend le sujet devrait mieux résister.

    Returns:
        (requêtes appauvries, identifiants attendus, requêtes d'origine)
    """
    frequences = _frequences_documentaires(corpus)
    requetes_origine, attendus = construire_requetes_titres(corpus, nb_requetes, graine)
    appauvries = []

    for requete in requetes_origine:
        mots = tokeniser(requete)
        # Les mots inconnus du corpus sont les plus rares de tous.
        rares = sorted(set(mots), key=lambda mot: frequences.get(mot, 0))[:nb_mots_retires]
        restants = [mot for mot in mots if mot not in set(rares)]
        # Si le titre était très court, on garde au moins deux mots.
        appauvries.append(" ".join(restants) if len(restants) >= 2 else requete)

    return appauvries, attendus, requetes_origine


# ---------------------------------------------------------------------------
# Protocole 2 : cohérence multilingue
# ---------------------------------------------------------------------------

def _identifiants(resultats: list[dict]) -> list[str]:
    return [r["id_doc"] for r in resultats]


def recouvrement(liste_a: list[str], liste_b: list[str]) -> float:
    """Proportion d'articles communs entre deux listes de résultats."""
    if not liste_a or not liste_b:
        return 0.0
    commun = set(liste_a) & set(liste_b)
    return len(commun) / max(len(liste_a), len(liste_b))


def evaluer_coherence_multilingue(moteur, triplets: list[dict], k: int = 10) -> dict:
    """
    Vérifie qu'une même question posée en trois langues donne les mêmes articles.

    Args:
        triplets: liste de dictionnaires {"fr": ..., "ar": ..., "en": ...}.

    Returns:
        Les recouvrements moyens par paire de langues, plus le détail requête
        par requête pour pouvoir illustrer le rapport.
    """
    requetes_fr = [t["fr"] for t in triplets]
    requetes_ar = [t["ar"] for t in triplets]
    requetes_en = [t["en"] for t in triplets]

    resultats_fr = moteur.chercher_lot(requetes_fr, k=k)
    resultats_ar = moteur.chercher_lot(requetes_ar, k=k)
    resultats_en = moteur.chercher_lot(requetes_en, k=k)

    detail = []
    for i, triplet in enumerate(triplets):
        ids_fr = _identifiants(resultats_fr[i])
        ids_ar = _identifiants(resultats_ar[i])
        ids_en = _identifiants(resultats_en[i])

        detail.append(
            {
                "theme": triplet.get("theme", ""),
                "fr": triplet["fr"],
                "ar": triplet["ar"],
                "en": triplet["en"],
                "recouvrement_fr_en": round(recouvrement(ids_fr, ids_en), 3),
                "recouvrement_ar_en": round(recouvrement(ids_ar, ids_en), 3),
                "recouvrement_fr_ar": round(recouvrement(ids_fr, ids_ar), 3),
                "nb_resultats_fr": len(ids_fr),
                "nb_resultats_ar": len(ids_ar),
                "nb_resultats_en": len(ids_en),
                "titre_premier_fr": resultats_fr[i][0]["titre"] if resultats_fr[i] else "",
                "titre_premier_en": resultats_en[i][0]["titre"] if resultats_en[i] else "",
                "titre_premier_ar": resultats_ar[i][0]["titre"] if resultats_ar[i] else "",
            }
        )

    def moyenne(cle: str) -> float:
        return round(statistics.fmean(d[cle] for d in detail), 4) if detail else 0.0

    return {
        "nb_triplets": len(triplets),
        "recouvrement_moyen_fr_en": moyenne("recouvrement_fr_en"),
        "recouvrement_moyen_ar_en": moyenne("recouvrement_ar_en"),
        "recouvrement_moyen_fr_ar": moyenne("recouvrement_fr_ar"),
        "requetes_sans_resultat_fr": sum(1 for d in detail if d["nb_resultats_fr"] == 0),
        "requetes_sans_resultat_ar": sum(1 for d in detail if d["nb_resultats_ar"] == 0),
        "detail": detail,
    }


# ---------------------------------------------------------------------------
# Protocole 3 : latence et coût
# ---------------------------------------------------------------------------

def mesurer_latences(moteur, requetes: list[str], k: int = 10) -> dict:
    """
    Chronomètre des recherches une par une, comme le ferait un vrai utilisateur.

    On rapporte la médiane et le 95e centile plutôt que la moyenne : c'est la
    convention pour un service en ligne, car la moyenne masque les cas lents.
    """
    # Une requête à blanc pour écarter le coût de démarrage du premier appel.
    if requetes:
        moteur.chercher(requetes[0], k=k)

    durees = []
    for requete in requetes:
        depart = time.perf_counter()
        moteur.chercher(requete, k=k)
        durees.append((time.perf_counter() - depart) * 1000)

    if not durees:
        return {}

    durees_triees = sorted(durees)
    centile_95 = durees_triees[max(0, int(0.95 * len(durees_triees)) - 1)]

    return {
        "nb_mesures": len(durees),
        "latence_moyenne_ms": round(statistics.fmean(durees), 2),
        "latence_mediane_ms": round(statistics.median(durees), 2),
        "latence_p95_ms": round(centile_95, 2),
        "latence_max_ms": round(max(durees), 2),
    }


def comparer_types_index(vecteurs, vecteurs_requetes, k: int = 10) -> list[dict]:
    """
    Compare l'index exact et l'index approximatif.

    L'index exact sert de référence : on considère ses résultats comme la
    vérité, puis on mesure quelle proportion de ces bons résultats l'index
    approximatif retrouve, et à quelle vitesse. C'est le compromis central de
    la recherche vectorielle à grande échelle.
    """
    from src.index_faiss import IndexVectoriel

    dimension = vecteurs.shape[1]
    tableau = []

    # Référence exacte
    index_exact = IndexVectoriel(dimension=dimension, type_index="flat")
    depart = time.perf_counter()
    index_exact.construire(vecteurs, verbeux=False)
    duree_construction = time.perf_counter() - depart

    depart = time.perf_counter()
    _, ids_reference = index_exact.rechercher(vecteurs_requetes, k)
    duree_recherche = time.perf_counter() - depart

    tableau.append(
        {
            "index": "flat (exact)",
            "nprobe": "-",
            "construction_s": round(duree_construction, 2),
            "ms_par_requete": round(1000 * duree_recherche / len(vecteurs_requetes), 3),
            "rappel_vs_exact": 1.0,
        }
    )

    # Variantes approximatives, à différents niveaux de fouille
    for nb_sondes in (1, 5, 10, 20):
        index_approx = IndexVectoriel(dimension=dimension, type_index="ivf")
        depart = time.perf_counter()
        index_approx.construire(vecteurs, verbeux=False)
        duree_construction = time.perf_counter() - depart
        index_approx.index.nprobe = nb_sondes

        depart = time.perf_counter()
        _, ids_approx = index_approx.rechercher(vecteurs_requetes, k)
        duree_recherche = time.perf_counter() - depart

        # Rappel : proportion des voisins exacts que l'approximation retrouve.
        rappels = [
            len(set(ids_reference[i]) & set(ids_approx[i])) / k
            for i in range(len(vecteurs_requetes))
        ]

        tableau.append(
            {
                "index": "ivf (approché)",
                "nprobe": nb_sondes,
                "construction_s": round(duree_construction, 2),
                "ms_par_requete": round(1000 * duree_recherche / len(vecteurs_requetes), 3),
                "rappel_vs_exact": round(statistics.fmean(rappels), 4),
            }
        )

    return tableau
