"""
Les briques d'affichage.

Chaque fonction de ce module rend un fragment de HTML et ne fait rien d'autre :
pas d'appel réseau, pas de logique de recherche. On lui donne un dictionnaire
de résultat, elle renvoie une chaîne. C'est ce qui permet de réutiliser la même
carte dans l'onglet Recherche, dans le duel et dans la démonstration sans
dupliquer une ligne de mise en forme.

### Pourquoi du HTML plutôt que les composants Streamlit

`st.container(border=True)` produit une carte correcte mais figée : impossible
d'y placer une jauge de score, un surlignage à l'intérieur d'un paragraphe, ou
un badge « trouvé uniquement par le sémantique » au bon endroit. Le HTML rendu
en une seule fois donne le contrôle complet de la mise en page, et se trouve
être plus rapide : un bloc au lieu de six composants imbriqués par résultat.

Contrepartie assumée : tout texte venant du corpus doit être échappé avant
d'être inséré. C'est fait dans `src/surlignage.py`, qui échappe systématiquement
avant d'ajouter la moindre balise.
"""

from __future__ import annotations

import html
import re

from src import filtres as module_filtres
from src.surlignage import raccourcir_autour, surligner
from ui.theme import MOTEURS, couleur_moteur, unite_score

# Un texte contenant des caractères arabes doit s'afficher de droite à gauche.
MOTIF_ARABE = re.compile(r"[؀-ۿݐ-ݿ]")

# Seuils de lecture d'un cosinus produit par multilingual-e5-small. Ce modèle
# ne descend presque jamais sous 0,70 : une échelle 0-1 brute donnerait à tous
# les résultats l'air excellent. Ces bornes sont celles observées sur le corpus.
PALIERS_COSINUS = (
    (0.88, "proximité très forte"),
    (0.845, "proximité forte"),
    (0.81, "proximité nette"),
    (0.775, "proximité modérée"),
    (0.0, "proximité faible"),
)


def est_arabe(texte: str) -> bool:
    """Vrai si le texte contient de l'arabe — utilisé pour l'affichage RTL."""
    return bool(MOTIF_ARABE.search(texte or ""))


def _bloc(html_produit: str) -> str:
    """
    Supprime les lignes vides d'un fragment HTML avant de le rendre.

    Ce n'est pas de la cosmétique. Streamlit interprète d'abord la chaîne comme
    du Markdown : une ligne vide au milieu d'un bloc HTML y ferme le bloc, et
    la balise fermante suivante s'affiche telle quelle à l'écran — un `</div>`
    en clair au milieu d'une carte.

    Le cas se produit dès qu'une partie facultative est vide : une carte sans
    note explicative laisse derrière elle deux lignes blanches, invisibles dans
    le code et très visibles dans l'interface.
    """
    return "\n".join(ligne for ligne in html_produit.splitlines() if ligne.strip())


def qualifier(score: float, moteur: str) -> str:
    """
    Traduit un score en mots.

    Uniquement pour le moteur sémantique : un score BM25 n'a pas de borne
    supérieure et un score RRF vaut quelques centièmes, les qualifier sur une
    échelle absolue n'aurait aucun sens.
    """
    if moteur != "semantique":
        return ""
    for seuil, libelle in PALIERS_COSINUS:
        if score >= seuil:
            return libelle
    return ""


def formater_nombre(valeur) -> str:
    """12345 devient « 12 345 » — l'espace fine française, pas la virgule."""
    try:
        return f"{int(valeur):,}".replace(",", " ")
    except (TypeError, ValueError):
        return str(valeur)


# ---------------------------------------------------------------------------
# En-tête de page
# ---------------------------------------------------------------------------

def entete(disponible: bool, infos: dict) -> str:
    """Titre du projet et bandeau d'état de l'index."""
    if disponible:
        puces = [
            '<span class="puce"><span class="point vivant"></span>API connectée</span>',
            f'<span class="puce"><b>{formater_nombre(infos.get("nb_articles", 0))}</b> articles</span>',
            f'<span class="puce"><b>{formater_nombre(infos.get("nb_passages", 0))}</b> passages</span>',
            f'<span class="puce mono">{html.escape(str(infos.get("modele", "")).split("/")[-1])}</span>',
            f'<span class="puce mono">index {html.escape(str(infos.get("type_index", "")))} · '
            f'{infos.get("dimension", 0)}d</span>',
        ]
    else:
        puces = ['<span class="puce"><span class="point rouge"></span>API injoignable</span>']

    return _bloc(f"""
<div class="entete">
  <div>
    <h1 class="entete-titre">Recherche sémantique</h1>
    <div class="entete-sous-titre">
      Pose ta question en français, en arabe ou en anglais.
      Le moteur cherche par le sens dans un corpus arXiv entièrement anglophone.
    </div>
  </div>
  <div class="bandeau-etat">{"".join(puces)}</div>
</div>
""")


# ---------------------------------------------------------------------------
# Carte de résultat
# ---------------------------------------------------------------------------

def carte_resultat(
    resultat: dict,
    moteur: str,
    score_maximum: float,
    compacte: bool = False,
    exclusif: bool = False,
    rang_ailleurs: dict[str, int] | None = None,
    longueur_extrait: int = 420,
) -> str:
    """
    Rend un résultat complet.

    Args:
        resultat: le dictionnaire renvoyé par l'API.
        moteur: quel moteur l'a produit — détermine la couleur et l'unité.
        score_maximum: meilleur score de la liste courante. La jauge est
                       relative à lui : sur des cosinus tous compris entre 0,78
                       et 0,86, une jauge absolue afficherait cinq barres
                       identiques et n'apprendrait rien.
        exclusif: ce document n'a été trouvé que par ce moteur (mode duel).
        rang_ailleurs: rang du document chez les autres moteurs, s'il y figure.
    """
    accent = couleur_moteur(moteur)
    score = float(resultat.get("score", 0.0))
    largeur = max(4.0, min(100.0, (score / score_maximum * 100) if score_maximum else 0))

    titre = html.escape(resultat.get("titre", "sans titre"))
    url = html.escape(resultat.get("url", ""))
    lien = f'<a href="{url}" target="_blank" rel="noopener">{titre}</a>' if url else titre

    # --- métadonnées ---
    auteurs = resultat.get("auteurs") or []
    texte_auteurs = ", ".join(auteurs[:3]) + (" et al." if len(auteurs) > 3 else "")
    etiquettes = "".join(
        f'<span class="etiquette" title="{html.escape(module_filtres.libelle(c))}">{html.escape(c)}</span>'
        for c in (resultat.get("categories") or [])[:3]
    )
    meta = (
        f'<div class="meta">'
        f'<span>{html.escape(texte_auteurs) or "auteurs inconnus"}</span>'
        f'<span>·</span><span>{html.escape(str(resultat.get("date", ""))[:10])}</span>'
        f'{etiquettes}</div>'
    )

    # --- extrait, phrase clé et termes surlignés ---
    phrase = resultat.get("phrase_cle")
    extrait_brut = resultat.get("extrait", "")
    extrait_court = raccourcir_autour(extrait_brut, phrase, longueur_extrait)
    extrait = surligner(
        extrait_court,
        termes=resultat.get("termes_partages"),
        phrase=phrase if phrase and phrase in extrait_court else None,
    )

    # --- badges ---
    badges = ""
    if exclusif:
        badges = (
            f'<span class="badge badge-exclusif">'
            f'{MOTEURS.get(moteur, {}).get("icone", "•")} trouvé seulement ici</span>'
        )
    elif rang_ailleurs:
        ailleurs = " · ".join(
            f'#{rang} chez {MOTEURS.get(nom, {}).get("libelle", nom).lower()}'
            for nom, rang in rang_ailleurs.items()
        )
        badges = f'<span class="badge badge-commun">{html.escape(ailleurs)}</span>'

    # --- la note qui explique le résultat ---
    note = ""
    if not compacte:
        note = _note_explicative(resultat, moteur)

    # --- le résumé complet, replié ---
    repli = ""
    if not compacte and len(extrait_brut) > len(extrait_court):
        repli = (
            '<details class="repli"><summary>résumé complet</summary>'
            f'<div class="contenu">{html.escape(extrait_brut)}</div></details>'
        )

    qualificatif = qualifier(score, moteur)
    ligne_badges = f'<div class="meta">{badges}</div>' if badges else ""

    # Un score RRF vaut quelques centièmes et se joue à la cinquième décimale ;
    # l'afficher sur trois rendrait tous les résultats ex æquo à l'écran.
    score_affiche = f"{score:.5f}" if moteur == "hybride" else f"{score:.3f}"

    return _bloc(f"""
<div class="carte" style="--accent: {accent};">
  <div class="carte-tete">
    <div style="display:flex; gap:0.55rem; align-items:flex-start; flex:1;">
      <span class="rang">#{resultat.get("rang", "?")}</span>
      <div class="carte-titre">{lien}</div>
    </div>
    <div class="bloc-score">
      <div class="valeur-score">{score_affiche}</div>
      <div class="unite-score">{html.escape(unite_score(moteur))}</div>
      <div class="jauge"><div class="jauge-remplissage" style="width:{largeur:.1f}%"></div></div>
      {f'<div class="unite-score">{qualificatif}</div>' if qualificatif else ''}
    </div>
  </div>
  {meta}
  {ligne_badges}
  <p class="extrait">{extrait}</p>
  {note}
  {repli}
</div>
""")


def _note_explicative(resultat: dict, moteur: str) -> str:
    """
    La ligne qui dit pourquoi ce document est là.

    Le cas remarquable — aucun mot partagé entre la question et le document —
    est mis en valeur : c'est la démonstration que demande la condition de
    validation n°7 du cahier des charges, et elle se produit d'elle-même sur
    les requêtes arabes.
    """
    termes = resultat.get("termes_partages")
    sans_recouvrement = resultat.get("sans_recouvrement_lexical")
    phrase = resultat.get("phrase_cle")
    score_phrase = resultat.get("score_phrase")

    if sans_recouvrement is None:
        return ""

    if sans_recouvrement and moteur != "lexical":
        detail = ""
        if phrase and score_phrase:
            detail = (
                f" La phrase surlignée est celle dont le vecteur est le plus proche "
                f"de la question (cosinus {score_phrase:.3f})."
            )
        return (
            '<div class="note remarquable">'
            '<span>◆</span><span><b>Aucun mot en commun</b> entre la question et cet '
            f'article : le rapprochement est purement sémantique.{detail}</span></div>'
        )

    if termes:
        liste = ", ".join(f"<b>{html.escape(t)}</b>" for t in termes[:6])
        reste = f" (+{len(termes) - 6})" if len(termes) > 6 else ""
        taux = resultat.get("taux_recouvrement_lexical")
        mesure = f" — {taux:.0%} des mots de la question" if taux else ""
        return (
            f'<div class="note"><span>▦</span><span>Mots partagés : {liste}{reste}{mesure}</span></div>'
        )

    return ""


# ---------------------------------------------------------------------------
# Panneaux
# ---------------------------------------------------------------------------

def markdown_leger(texte: str) -> str:
    """
    Convertit les `**gras**` d'un texte en `<b>`.

    L'API renvoie ses verdicts en texte légèrement balisé, sans HTML : c'est
    une donnée, elle doit rester lisible par n'importe quel client. La
    conversion en balises appartient donc à l'interface. Et comme Streamlit
    ne traite pas le markdown situé à l'intérieur d'un bloc HTML, il faut la
    faire nous-mêmes.
    """
    fragments = html.escape(texte).split("**")
    # Les positions impaires sont ce qui se trouvait entre deux paires de **.
    return "".join(
        f"<b>{fragment}</b>" if position % 2 else fragment
        for position, fragment in enumerate(fragments)
    )


def panneau(contenu: str, titre: str | None = None, variante: str = "") -> str:
    """Encadré générique. `variante` vaut "" , "verdict" ou "alerte"."""
    classes = "panneau" + (f" panneau-{variante}" if variante else "")
    entete_html = f'<div class="panneau-titre">{html.escape(titre)}</div>' if titre else ""
    return f'<div class="{classes}">{entete_html}{contenu}</div>'


def etat_vide(message: str, indice: str = "") -> str:
    """Message affiché quand il n'y a rien à montrer."""
    indice_html = f'<div style="font-size:0.8rem; margin-top:0.5rem;">{indice}</div>' if indice else ""
    return f'<div class="panneau panneau-vide">{html.escape(message)}{indice_html}</div>'


def chiffres(entrees: list[tuple[str, str, str]]) -> str:
    """
    Grille de chiffres clés.

    Chaque entrée est (valeur, légende, couleur d'accent).
    """
    cases = "".join(
        f'<div class="chiffre" style="--accent: {couleur}">'
        f'<div class="valeur">{valeur}</div>'
        f'<div class="legende">{legende}</div></div>'
        for valeur, legende, couleur in entrees
    )
    return f'<div class="grille-chiffres">{cases}</div>'


def tete_colonne(moteur: str, nb_resultats: int, duree_ms: float | None = None) -> str:
    """Bandeau qui identifie la colonne d'un moteur dans le duel."""
    identite = MOTEURS.get(moteur, {})
    detail = f"{nb_resultats} résultat{'s' if nb_resultats > 1 else ''}"
    if duree_ms is not None:
        detail += f" · {duree_ms:.0f} ms"

    return _bloc(f"""
<div class="tete-colonne" style="--accent: {couleur_moteur(moteur)};">
  <span class="marque">{identite.get("icone", "•")}</span>
  <div>
    <div class="nom">{html.escape(identite.get("libelle", moteur))}</div>
    <div style="font-size:0.72rem; color:var(--texte-faible);">
      {html.escape(identite.get("sous_titre", ""))} — {html.escape(identite.get("description", ""))}
    </div>
  </div>
  <div class="detail">{detail}</div>
</div>
""")


def rappel_requete(requete: str) -> str:
    """Affiche la question posée, en respectant le sens d'écriture de l'arabe."""
    classe = "rtl" if est_arabe(requete) else ""
    return (
        f'<div class="panneau" style="padding:0.7rem 1rem;">'
        f'<div class="panneau-titre">question posée</div>'
        f'<div class="{classe}" style="font-size:1.02rem; color:var(--texte);">'
        f'{html.escape(requete)}</div></div>'
    )
