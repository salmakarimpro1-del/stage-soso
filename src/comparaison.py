"""
Comparer deux classements produits par deux moteurs sur la même requête.

Le cahier des charges demande une comparaison lexical / sémantique. Afficher
deux listes côte à côte en est la forme minimale, et c'est aussi la moins
informative : deux colonnes de dix titres se ressemblent toujours un peu, et
l'œil ne sait pas où regarder.

Ce module calcule ce que les deux listes ne montrent pas d'elles-mêmes :

- quels articles **un seul** des deux moteurs a trouvés — c'est là que se situe
  la différence réelle entre les deux approches ;
- de combien de places un même article se déplace d'un classement à l'autre ;
- le taux de recouvrement, qui résume le tout en un nombre.

Le cas le plus parlant est produit automatiquement : quand la baseline lexicale
renvoie une liste vide alors que le moteur sémantique répond, la comparaison
n'est plus une question de degré. C'est la situation des requêtes arabes sur un
corpus anglophone, et c'est exactement la condition de validation n°7 du
cahier des charges.
"""

from __future__ import annotations

# Au-delà de ce déplacement, un article est signalé comme « fortement
# reclassé » : il ne s'agit plus d'un écart d'appréciation mais d'un désaccord
# entre les deux méthodes.
SEUIL_DEPLACEMENT_NOTABLE = 3


def analyser(classements: dict[str, list[dict]], k: int | None = None) -> dict:
    """
    Compare plusieurs classements portant sur la même requête.

    Args:
        classements: {nom du moteur: liste de résultats triés}.
        k: ne comparer que les k premiers de chaque liste. Comparer des listes
           de longueurs différentes fausserait le taux de recouvrement.

    Returns:
        Un dictionnaire d'analyse directement exploitable par l'interface.
    """
    noms = list(classements.keys())
    tronques = {
        nom: (resultats[:k] if k else resultats) for nom, resultats in classements.items()
    }

    ensembles = {nom: {r["id_doc"] for r in resultats} for nom, resultats in tronques.items()}
    titres = {
        r["id_doc"]: r.get("titre", "")
        for resultats in tronques.values()
        for r in resultats
    }
    rangs = {
        nom: {r["id_doc"]: r["rang"] for r in resultats}
        for nom, resultats in tronques.items()
    }

    # --- ce que chaque moteur est seul à trouver ---
    uniques: dict[str, list[dict]] = {}
    for nom in noms:
        autres = set().union(*(ensembles[a] for a in noms if a != nom)) if len(noms) > 1 else set()
        uniques[nom] = [
            {"id_doc": id_doc, "titre": titres.get(id_doc, ""), "rang": rangs[nom][id_doc]}
            for id_doc in sorted(ensembles[nom] - autres, key=lambda d: rangs[nom][d])
        ]

    # --- ce sur quoi tout le monde s'accorde ---
    communs_ids = set.intersection(*ensembles.values()) if ensembles else set()
    communs = [
        {
            "id_doc": id_doc,
            "titre": titres.get(id_doc, ""),
            "rangs": {nom: rangs[nom][id_doc] for nom in noms},
            "deplacement": _deplacement(rangs, noms, id_doc),
        }
        for id_doc in sorted(communs_ids, key=lambda d: min(rangs[nom][d] for nom in noms))
    ]

    # --- le résumé chiffré ---
    tailles = [len(ensembles[nom]) for nom in noms]
    plus_grande = max(tailles) if tailles else 0
    taux = round(len(communs_ids) / plus_grande, 3) if plus_grande else 0.0

    return {
        "moteurs": noms,
        "nb_resultats": {nom: len(tronques[nom]) for nom in noms},
        "recouvrement": taux,
        "nb_communs": len(communs_ids),
        "communs": communs,
        "uniques": uniques,
        "nb_uniques": {nom: len(liste) for nom, liste in uniques.items()},
        "moteurs_muets": [nom for nom in noms if not ensembles[nom]],
        "reclassements_notables": [
            entree for entree in communs
            if entree["deplacement"] >= SEUIL_DEPLACEMENT_NOTABLE
        ],
    }


def _deplacement(rangs: dict[str, dict[str, int]], noms: list[str], id_doc: str) -> int:
    """Écart maximal de position d'un article entre les classements comparés."""
    positions = [rangs[nom][id_doc] for nom in noms if id_doc in rangs[nom]]
    return max(positions) - min(positions) if len(positions) > 1 else 0


def verdict(analyse: dict, libelles: dict[str, str] | None = None) -> str:
    """
    Rédige en une phrase ce que la comparaison a montré.

    L'interface l'affiche telle quelle. C'est aussi la phrase à prononcer en
    soutenance : elle est calculée à partir des résultats réels, pas écrite
    d'avance.
    """
    libelles = libelles or {}

    def nom_lisible(cle: str) -> str:
        return libelles.get(cle, cle)

    muets = analyse.get("moteurs_muets") or []
    actifs = [m for m in analyse["moteurs"] if m not in muets]

    if muets and actifs:
        return (
            f"{nom_lisible(muets[0])} ne renvoie **aucun résultat** sur cette requête, "
            f"tandis que {nom_lisible(actifs[0])} en trouve "
            f"{analyse['nb_resultats'][actifs[0]]}. Les deux approches ne sont pas "
            "à départager ici : une seule fonctionne."
        )

    if len(analyse["moteurs"]) < 2:
        return "Un seul moteur interrogé : rien à comparer."

    taux = analyse["recouvrement"]
    a, b = analyse["moteurs"][0], analyse["moteurs"][1]

    if taux == 1.0:
        return (
            "Les deux moteurs renvoient exactement les mêmes articles : sur une "
            "requête dont les mots figurent dans le corpus, la recherche lexicale "
            "suffit."
        )

    if taux >= 0.6:
        return (
            f"Les deux moteurs s'accordent sur {analyse['nb_communs']} articles "
            f"({taux:.0%} de recouvrement). Le vocabulaire de la question est "
            "présent dans le corpus : les deux approches convergent."
        )

    if taux >= 0.2:
        return (
            f"Recouvrement partiel ({taux:.0%}) : {analyse['nb_uniques'][a]} articles "
            f"ne sont trouvés que par {nom_lisible(a)}, "
            f"{analyse['nb_uniques'][b]} seulement par {nom_lisible(b)}. "
            "Les deux moteurs lisent la question différemment."
        )

    return (
        f"Recouvrement quasi nul ({taux:.0%}) : les deux moteurs ne parlent pas "
        "de la même chose. La question est formulée avec un vocabulaire absent "
        "du corpus — le terrain où la recherche lexicale décroche."
    )
