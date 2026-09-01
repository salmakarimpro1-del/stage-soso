"""
Expliquer un résultat : pourquoi cet article, pour cette question ?

Un moteur qui affiche un score de 0,84 sans rien d'autre demande qu'on lui
fasse confiance. Ce module produit les éléments qui rendent un résultat
vérifiable à l'œil nu, et il le fait différemment selon le moteur interrogé —
parce que les deux moteurs ne trouvent pas pour les mêmes raisons.

**Côté lexical**, la justification est directe : ce sont les mots partagés
entre la question et le document. On les repère et on les surligne.

**Côté sémantique**, il n'y a souvent aucun mot partagé — c'est tout l'intérêt
du moteur, et c'est aussi ce qui le rend opaque. On procède alors autrement :
le passage est redécoupé en phrases, chaque phrase est encodée séparément, et
l'on met en évidence celle dont le vecteur est le plus proche de celui de la
question. Le modèle désigne lui-même ce qui, dans le document, a déclenché le
rapprochement.

C'est la différence entre « le moteur a trouvé cet article » et « le moteur a
trouvé cet article *à cause de cette phrase-là* ». La seconde formulation est
la seule qui se défend en soutenance.

### Le cas qui vaut la démonstration

Quand la question et le document ne partagent **aucun** mot — requête arabe,
corpus anglais — le champ `sans_recouvrement_lexical` passe à vrai. C'est la
condition de validation n°7 du cahier des charges, détectée automatiquement au
lieu d'être cherchée à la main pendant la soutenance.
"""

from __future__ import annotations

import html
import re

import numpy as np

from src.baseline_bm25 import tokeniser

# Fin de phrase : une ponctuation forte suivie d'un espace et d'une majuscule.
# Le contexte évite de couper sur « et al. », « Fig. 2 » ou « e.g. », fréquents
# dans les résumés scientifiques.
MOTIF_FIN_PHRASE = re.compile(r"(?<=[.!?])\s+(?=[A-Z؀-ۿ])")

# Mots trop courants pour constituer une justification. Les surligner
# noierait les vrais termes discriminants dans un fond de « the » et « de ».
MOTS_VIDES = {
    # anglais
    "the", "a", "an", "of", "and", "or", "to", "in", "on", "for", "with", "by",
    "is", "are", "was", "were", "be", "been", "this", "that", "these", "those",
    "we", "our", "it", "its", "as", "at", "from", "which", "can", "we", "not",
    "has", "have", "but", "than", "then", "such", "also", "more", "most", "using",
    # français
    "le", "la", "les", "un", "une", "des", "du", "de", "et", "ou", "à", "au",
    "aux", "en", "dans", "pour", "par", "sur", "avec", "est", "sont", "ce",
    "cette", "ces", "qui", "que", "quoi", "dont", "comment", "plus", "moins",
    "son", "sa", "ses", "leur", "leurs", "d", "l", "n", "s", "y", "il", "elle",
    # arabe
    "في", "من", "على", "إلى", "عن", "مع", "هذا", "هذه", "التي", "الذي", "ما",
    "أن", "إن", "هو", "هي", "كان", "كيف", "بين",
}

# En dessous de cette longueur, un fragment n'est pas une phrase : c'est un
# reste de découpage (« Fig. », un numéro). On le recolle au voisin.
LONGUEUR_MINIMALE_PHRASE = 25


# ---------------------------------------------------------------------------
# Découpage
# ---------------------------------------------------------------------------

def decouper_en_phrases(texte: str) -> list[str]:
    """
    Découpe un passage en phrases exploitables.

    Les fragments trop courts sont fusionnés avec la phrase précédente : mieux
    vaut une phrase un peu longue qu'un « al. » isolé présenté comme la
    justification d'un résultat.
    """
    if not texte or not texte.strip():
        return []

    morceaux = [m.strip() for m in MOTIF_FIN_PHRASE.split(texte.strip()) if m.strip()]
    if not morceaux:
        return []

    phrases: list[str] = []
    for morceau in morceaux:
        if phrases and len(morceau) < LONGUEUR_MINIMALE_PHRASE:
            phrases[-1] = f"{phrases[-1]} {morceau}"
        else:
            phrases.append(morceau)

    return phrases


# ---------------------------------------------------------------------------
# Justification lexicale : les mots partagés
# ---------------------------------------------------------------------------

def termes_partages(requete: str, texte: str) -> list[str]:
    """
    Mots significatifs présents à la fois dans la question et dans le texte.

    Une liste vide est une information forte, pas un échec : elle signifie que
    le rapprochement s'est fait sans le moindre appui lexical.
    """
    mots_requete = {m for m in tokeniser(requete) if m not in MOTS_VIDES and len(m) > 2}
    if not mots_requete:
        return []

    mots_texte = set(tokeniser(texte))
    return sorted(mots_requete.intersection(mots_texte))


def taux_recouvrement(requete: str, texte: str) -> float:
    """Part des mots significatifs de la question que l'on retrouve dans le texte."""
    mots_requete = {m for m in tokeniser(requete) if m not in MOTS_VIDES and len(m) > 2}
    if not mots_requete:
        return 0.0
    mots_texte = set(tokeniser(texte))
    return round(len(mots_requete & mots_texte) / len(mots_requete), 3)


# ---------------------------------------------------------------------------
# Justification sémantique : la phrase la plus proche
# ---------------------------------------------------------------------------

# Nombre de résultats pour lesquels on cherche la phrase clé. La justification
# lexicale, elle, est calculée pour tous : elle ne coûte rien.
#
# Ce plafond n'est pas cosmétique. Sur un processeur sans carte graphique,
# encoder les 78 phrases de dix résumés prend environ trois secondes, alors que
# la recherche elle-même en prend cent millisecondes. L'explicabilité coûte
# donc trente fois la recherche — un chiffre à connaître et à assumer plutôt
# qu'à masquer. On la réserve aux résultats que l'utilisateur lit vraiment.
NB_EXPLICATIONS_PAR_DEFAUT = 5

# Au-delà, on est dans la queue d'un résumé, très rarement la phrase la plus
# proche de la question.
MAX_PHRASES_PAR_DOCUMENT = 8


def expliquer_resultats(
    requete: str,
    resultats: list[dict],
    encodeur,
    nb_maximum: int | None = NB_EXPLICATIONS_PAR_DEFAUT,
) -> list[dict]:
    """
    Enrichit chaque résultat de sa justification, sur place.

    Toutes les phrases retenues sont encodées en **un seul lot**. Encoder
    résultat par résultat multiplierait par dix le nombre d'appels au modèle
    pour la même quantité de texte : sur CPU, la différence est de l'ordre
    d'un facteur trois.

    Args:
        nb_maximum: nombre de résultats recevant une phrase clé. None les
                    traite tous, au prix indiqué ci-dessus.

    Champs ajoutés à chaque résultat :
        termes_partages            les mots communs question / document
        taux_recouvrement_lexical  la part des mots de la question retrouvés
        sans_recouvrement_lexical  vrai si aucun mot n'est partagé
    Et, pour les `nb_maximum` premiers :
        phrase_cle                 la phrase du passage la plus proche de la question
        score_phrase               son cosinus avec la question
    """
    if not resultats:
        return resultats

    a_traiter = resultats if nb_maximum is None else resultats[:nb_maximum]

    # --- justification lexicale, gratuite : appliquée à tous les résultats ---
    for resultat in resultats:
        texte = f"{resultat.get('titre', '')} {resultat.get('extrait', '')}"
        partages = termes_partages(requete, texte)
        resultat["termes_partages"] = partages
        resultat["taux_recouvrement_lexical"] = taux_recouvrement(requete, texte)
        resultat["sans_recouvrement_lexical"] = not partages

    # --- justification sémantique, un seul appel au modèle ---
    phrases_a_encoder: list[str] = []
    # Pour chaque résultat : (position de sa première phrase, nombre de phrases)
    reperes: list[tuple[int, int]] = []

    for resultat in a_traiter:
        phrases = decouper_en_phrases(resultat.get("extrait", ""))[:MAX_PHRASES_PAR_DOCUMENT]
        reperes.append((len(phrases_a_encoder), len(phrases)))
        phrases_a_encoder.extend(phrases)

    if not phrases_a_encoder:
        return resultats

    vecteur_requete = encodeur.encoder_requete(requete)          # (1, d)
    vecteurs_phrases = encodeur.encoder_documents(phrases_a_encoder, barre=False)

    # Les vecteurs sont normalisés : le produit scalaire vaut le cosinus.
    similarites = (vecteurs_phrases @ vecteur_requete[0]).astype(float)

    for resultat, (depart, nombre) in zip(a_traiter, reperes):
        if nombre == 0:
            continue
        scores_locaux = similarites[depart:depart + nombre]
        meilleure = int(np.argmax(scores_locaux))
        resultat["phrase_cle"] = phrases_a_encoder[depart + meilleure]
        resultat["score_phrase"] = round(float(scores_locaux[meilleure]), 4)

    return resultats


# ---------------------------------------------------------------------------
# Rendu HTML
# ---------------------------------------------------------------------------

def surligner(
    texte: str,
    termes: list[str] | None = None,
    phrase: str | None = None,
    classe_terme: str = "terme-surligne",
    classe_phrase: str = "phrase-cle",
) -> str:
    """
    Produit le HTML d'un extrait, phrase clé et termes partagés mis en valeur.

    Le texte est échappé **avant** l'insertion des balises : un résumé arXiv
    contient des chevrons et des esperluettes, et les laisser passer casserait
    la mise en page — voire ouvrirait une injection HTML dans l'interface.
    """
    if not texte:
        return ""

    rendu = html.escape(texte)

    # 1. La phrase clé, en premier : elle englobe potentiellement des termes.
    if phrase:
        phrase_echappee = html.escape(phrase.strip())
        if phrase_echappee and phrase_echappee in rendu:
            rendu = rendu.replace(
                phrase_echappee,
                f'<span class="{classe_phrase}">{phrase_echappee}</span>',
                1,
            )

    # 2. Les termes partagés, sur les mots entiers uniquement, pour ne pas
    #    surligner « al » à l'intérieur de « evaluation ».
    for terme in sorted(termes or [], key=len, reverse=True):
        if len(terme) < 3:
            continue
        motif = re.compile(rf"(?<!\w)({re.escape(html.escape(terme))})(?!\w)", re.IGNORECASE)
        rendu = motif.sub(rf'<mark class="{classe_terme}">\1</mark>', rendu)

    return rendu


def raccourcir_autour(texte: str, phrase: str | None, longueur: int = 420) -> str:
    """
    Réduit un extrait trop long en gardant la phrase clé dans la fenêtre.

    Couper bêtement les 420 premiers caractères ferait souvent disparaître
    précisément la phrase que l'on voulait montrer.
    """
    if len(texte) <= longueur:
        return texte

    if phrase and phrase in texte:
        position = texte.index(phrase)
        marge = max(0, (longueur - len(phrase)) // 2)
        debut = max(0, position - marge)
        fin = min(len(texte), debut + longueur)
        extrait = texte[debut:fin]
        if debut > 0:
            extrait = "... " + extrait.split(" ", 1)[-1]
        if fin < len(texte):
            extrait = extrait.rsplit(" ", 1)[0] + " ..."
        return extrait

    return texte[:longueur].rsplit(" ", 1)[0] + " ..."
