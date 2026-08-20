"""
Étape 2 : préparer les textes avant de les encoder.

Deux opérations très simples mais qui pèsent lourd sur la qualité finale :

1. le nettoyage — supprimer les retours à la ligne, les espaces multiples et
   les artefacts LaTeX que l'on trouve dans les résumés arXiv ;
2. le découpage en passages — un modèle d'embeddings ne peut traiter qu'une
   longueur limitée de texte (512 tokens ici). Au-delà, il tronque
   silencieusement. Et même sans troncature, un texte trop long produit un
   vecteur « moyen » qui ne représente plus rien de précis.

Le vocabulaire employé dans tout le projet : un *document* est un article
arXiv ; un *passage* est un morceau de ce document. C'est le passage qui est
encodé et indexé, jamais le document entier.
"""

from __future__ import annotations

import re

import config

# Quelques motifs LaTeX fréquents dans les résumés arXiv.
MOTIF_ESPACES = re.compile(r"\s+")
MOTIF_LATEX_INLINE = re.compile(r"\$[^$]{0,200}\$")
MOTIF_COMMANDE_LATEX = re.compile(r"\\[a-zA-Z]+\{([^}]*)\}")


def nettoyer_texte(texte: str) -> str:
    """
    Normalise un texte brut : formules LaTeX simplifiées, espaces réduits.

    On ne nettoie pas agressivement : un résumé scientifique privé de ses
    termes techniques perdrait tout son sens. On se contente de rendre le
    texte lisible d'un seul tenant.
    """
    if not texte:
        return ""

    texte = MOTIF_COMMANDE_LATEX.sub(r"\1", texte)   # \textit{mot} devient mot
    texte = MOTIF_LATEX_INLINE.sub(" ", texte)       # une formule devient un espace
    texte = MOTIF_ESPACES.sub(" ", texte)
    return texte.strip()


def decouper_en_passages(
    texte: str,
    taille: int | None = None,
    chevauchement: int | None = None,
) -> list[str]:
    """
    Découpe un texte en morceaux de `taille` mots qui se chevauchent.

    Le chevauchement évite de couper une idée en deux : si une phrase
    importante tombe pile sur une frontière, elle se retrouve entière dans
    l'un des deux passages voisins.

    Exemple avec taille=5 et chevauchement=2 sur 9 mots :
        passage 1 : mots 1 à 5
        passage 2 : mots 4 à 8
        passage 3 : mots 7 à 9
    """
    taille = taille or config.TAILLE_CHUNK_MOTS
    if chevauchement is None:
        chevauchement = config.CHEVAUCHEMENT_MOTS

    if chevauchement >= taille:
        raise ValueError("Le chevauchement doit être plus petit que la taille du passage.")

    mots = texte.split()
    if not mots:
        return []
    if len(mots) <= taille:
        return [texte]

    pas = taille - chevauchement
    passages = []
    for depart in range(0, len(mots), pas):
        morceau = mots[depart:depart + taille]
        if not morceau:
            break
        passages.append(" ".join(morceau))
        if depart + taille >= len(mots):
            break

    return passages


def preparer_passages(corpus: list[dict]) -> list[dict]:
    """
    Transforme la liste des articles en liste de passages prêts à encoder.

    Chaque passage garde un lien vers son document d'origine (`id_doc`), ce
    qui permettra de regrouper les résultats plus tard : si trois passages du
    même article remontent, on n'affiche l'article qu'une seule fois.

    Returns:
        Une liste de dictionnaires, dans l'ordre. La position d'un passage
        dans cette liste est exactement l'identifiant entier que FAISS lui
        attribuera — c'est ce qui relie les vecteurs aux textes.
    """
    passages = []

    for document in corpus:
        resume_propre = nettoyer_texte(document.get("resume", ""))
        if not resume_propre:
            continue

        morceaux = decouper_en_passages(resume_propre)
        titre = nettoyer_texte(document.get("titre", ""))

        for position, morceau in enumerate(morceaux):
            # Texte réellement soumis au modèle. Voir le commentaire de
            # INCLURE_TITRE_DANS_INDEX dans config.py pour la justification.
            if config.INCLURE_TITRE_DANS_INDEX:
                texte_indexe = f"{titre}. {morceau}"
            else:
                texte_indexe = morceau

            passages.append(
                {
                    "id_passage": len(passages),
                    "id_doc": document["id"],
                    "position": position,
                    "texte_indexe": texte_indexe,
                    "texte_affiche": morceau,
                    "titre": titre,
                    "auteurs": document.get("auteurs", []),
                    "categories": document.get("categories", []),
                    "date": document.get("date", ""),
                    "url": document.get("url", ""),
                }
            )

    return passages
