"""
Les graphiques de l'onglet Évaluation.

Ce module ne calcule aucune métrique : il lit le fichier produit par
`python scripts/4_evaluer.py` et le met en image. La séparation est
volontaire — un graphique qui recalculerait ses chiffres à l'affichage
pourrait montrer autre chose que le rapport, et c'est exactement le genre
d'écart qu'un jury repère.

Les couleurs sont celles des moteurs, définies une seule fois dans
`ui/theme.py` : le violet est le sémantique dans les cartes de résultats comme
dans les histogrammes.
"""

from __future__ import annotations

import altair as alt
import pandas as pd

from ui.theme import MOTEURS, PALETTES

# Noms lisibles des métriques. « recall@1 » ne dit rien à qui découvre le
# domaine ; « bon article en 1re position » se comprend sans glossaire.
LIBELLES_METRIQUES = {
    "recall@1": "Trouvé en 1re position",
    "recall@5": "Trouvé dans le top 5",
    "recall@10": "Trouvé dans le top 10",
    "mrr@10": "MRR@10",
    "ndcg@10": "nDCG@10",
}

ORDRE_METRIQUES = list(LIBELLES_METRIQUES.values())

# Le fichier d'évaluation nomme la baseline « bm25 » ; l'interface l'appelle
# « lexical ». On traduit ici plutôt que de renommer des données déjà produites
# et citées dans le rapport.
CLES_MOTEURS = {"semantique": "semantique", "bm25": "lexical", "hybride": "hybride"}


def _echelle_couleurs(donnees: pd.DataFrame | None = None) -> alt.Scale:
    """
    Associe chaque moteur à sa couleur d'identité.

    Le domaine est restreint aux moteurs réellement présents dans les données :
    déclarer les trois ferait apparaître « Hybride » dans la légende de
    graphiques qui n'en contiennent aucune barre, ce qui laisse croire à un
    résultat manquant plutôt qu'à un moteur non évalué.
    """
    ordre = ["semantique", "lexical", "hybride"]
    libelles = {MOTEURS[m]["libelle"]: MOTEURS[m]["couleur"] for m in ordre}

    if donnees is not None and "Moteur" in donnees:
        presents = [nom for nom in libelles if nom in set(donnees["Moteur"])]
    else:
        presents = list(libelles)

    return alt.Scale(domain=presents, range=[libelles[nom] for nom in presents])


def _habiller(graphique: alt.Chart, theme: str) -> alt.Chart:
    """Applique les couleurs de texte et de grille du thème courant."""
    p = PALETTES.get(theme, PALETTES["sombre"])
    return (
        graphique.configure_view(strokeWidth=0, fill=None)
        .configure_axis(
            labelColor=p["texte_doux"],
            titleColor=p["texte_faible"],
            gridColor=p["grille"],
            domainColor=p["grille"],
            tickColor=p["grille"],
            labelFontSize=11,
            titleFontSize=11,
            labelFont="Inter, sans-serif",
            titleFont="Inter, sans-serif",
        )
        .configure_legend(
            labelColor=p["texte_doux"],
            titleColor=p["texte_faible"],
            labelFontSize=11,
            titleFontSize=11,
            orient="top",
            direction="horizontal",
        )
        .configure_title(color=p["texte"], fontSize=13, anchor="start", font="Inter, sans-serif")
    )


def _nom_moteur(cle: str) -> str:
    """« bm25 » devient « Lexical »."""
    return MOTEURS.get(CLES_MOTEURS.get(cle, cle), {}).get("libelle", cle)


# ---------------------------------------------------------------------------
# Protocole 1 — qualité du classement
# ---------------------------------------------------------------------------

def qualite_classement(bloc: dict, theme: str, titre: str = "") -> alt.Chart:
    """
    Histogramme groupé des cinq métriques, un groupe par moteur.

    Toutes les métriques affichées vivent entre 0 et 1, ce qui autorise à les
    mettre sur le même axe — c'est ce qui rend la lecture immédiate.
    """
    lignes = []
    for cle_moteur, mesures in bloc.items():
        if not isinstance(mesures, dict):
            continue
        for cle_metrique, libelle in LIBELLES_METRIQUES.items():
            if cle_metrique in mesures:
                lignes.append(
                    {
                        "Moteur": _nom_moteur(cle_moteur),
                        "Métrique": libelle,
                        "Valeur": round(float(mesures[cle_metrique]), 4),
                    }
                )

    donnees = pd.DataFrame(lignes)

    graphique = (
        alt.Chart(donnees)
        .mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3, size=26)
        .encode(
            x=alt.X("Métrique:N", sort=ORDRE_METRIQUES, title=None,
                    axis=alt.Axis(labelAngle=-18)),
            y=alt.Y("Valeur:Q", scale=alt.Scale(domain=[0, 1]), title=None),
            color=alt.Color("Moteur:N", scale=_echelle_couleurs(donnees), title=None),
            xOffset=alt.XOffset("Moteur:N"),
            tooltip=["Moteur", "Métrique", alt.Tooltip("Valeur:Q", format=".3f")],
        )
        .properties(height=250, title=titre)
    )

    return _habiller(graphique, theme)


# ---------------------------------------------------------------------------
# Protocole 2 — cohérence multilingue
# ---------------------------------------------------------------------------

def coherence_multilingue(bloc: dict, theme: str) -> alt.Chart:
    """
    Le graphique central du projet.

    Il montre le taux de recouvrement entre les résultats d'une même question
    posée dans deux langues. La baseline lexicale y tombe à zéro sur l'arabe :
    ce n'est pas un mauvais réglage, c'est qu'aucun mot arabe n'existe dans un
    corpus anglophone.
    """
    paires = {
        "recouvrement_moyen_fr_en": "français ↔ anglais",
        "recouvrement_moyen_ar_en": "arabe ↔ anglais",
        "recouvrement_moyen_fr_ar": "français ↔ arabe",
    }

    lignes = [
        {
            "Moteur": _nom_moteur(cle_moteur),
            "Paire de langues": libelle,
            "Recouvrement": round(float(mesures.get(cle, 0.0)), 4),
        }
        for cle_moteur, mesures in bloc.items()
        if isinstance(mesures, dict)
        for cle, libelle in paires.items()
    ]

    donnees = pd.DataFrame(lignes)

    graphique = (
        alt.Chart(donnees)
        .mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3, size=34)
        .encode(
            x=alt.X("Paire de langues:N", title=None, axis=alt.Axis(labelAngle=0)),
            y=alt.Y("Recouvrement:Q", scale=alt.Scale(domain=[0, 1]),
                    axis=alt.Axis(format="%"), title=None),
            color=alt.Color("Moteur:N", scale=_echelle_couleurs(donnees), title=None),
            xOffset=alt.XOffset("Moteur:N"),
            tooltip=["Moteur", "Paire de langues", alt.Tooltip("Recouvrement:Q", format=".1%")],
        )
        .properties(height=250, title="Part d'articles communs entre deux formulations")
    )

    return _habiller(graphique, theme)


# ---------------------------------------------------------------------------
# Requêtes appauvries
# ---------------------------------------------------------------------------

def degradation(normal: dict, appauvri: dict, theme: str) -> alt.Chart:
    """
    Compare le MRR avant et après retrait des trois mots les plus rares.

    Un graphique en pentes est plus parlant qu'un histogramme ici : l'œil suit
    la chute, et voit tout de suite laquelle des deux est la plus raide.
    """
    lignes = []
    for cle_moteur in ("semantique", "bm25"):
        if cle_moteur in normal and cle_moteur in appauvri:
            lignes.append({
                "Moteur": _nom_moteur(cle_moteur),
                "Requêtes": "complètes",
                "MRR@10": round(float(normal[cle_moteur].get("mrr@10", 0)), 4),
            })
            lignes.append({
                "Moteur": _nom_moteur(cle_moteur),
                "Requêtes": "appauvries",
                "MRR@10": round(float(appauvri[cle_moteur].get("mrr@10", 0)), 4),
            })

    donnees = pd.DataFrame(lignes)
    base = alt.Chart(donnees).encode(
        # labelAngle=0 est indispensable ici : avec seulement deux valeurs très
        # espacées, Altair fait pivoter les libellés à la verticale par défaut.
        x=alt.X("Requêtes:N", sort=["complètes", "appauvries"], title=None,
                scale=alt.Scale(padding=0.4), axis=alt.Axis(labelAngle=0)),
        y=alt.Y("MRR@10:Q", scale=alt.Scale(domain=[0, 1]), title=None),
        color=alt.Color("Moteur:N", scale=_echelle_couleurs(donnees), title=None),
    )

    graphique = (base.mark_line(strokeWidth=2.5, point=alt.OverlayMarkDef(size=90, filled=True))
                 .encode(tooltip=["Moteur", "Requêtes", alt.Tooltip("MRR@10:Q", format=".3f")])
                 ).properties(
        height=250,
        title="Effet du retrait des trois mots les plus rares de chaque requête",
    )

    return _habiller(graphique, theme)


# ---------------------------------------------------------------------------
# Coût
# ---------------------------------------------------------------------------

def latences(bloc: dict, theme: str) -> alt.Chart:
    """Latence médiane et 95e centile, par moteur."""
    lignes = [
        {
            "Moteur": _nom_moteur(cle_moteur),
            "Mesure": libelle,
            "Millisecondes": round(float(mesures.get(cle, 0.0)), 2),
        }
        for cle_moteur, mesures in bloc.items()
        if isinstance(mesures, dict)
        for cle, libelle in (
            ("latence_mediane_ms", "médiane"),
            ("latence_p95_ms", "95e centile"),
        )
    ]

    donnees = pd.DataFrame(lignes)

    graphique = (
        alt.Chart(donnees)
        .mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3, size=30)
        .encode(
            x=alt.X("Mesure:N", title=None, axis=alt.Axis(labelAngle=0)),
            y=alt.Y("Millisecondes:Q", title="ms"),
            color=alt.Color("Moteur:N", scale=_echelle_couleurs(donnees), title=None),
            xOffset=alt.XOffset("Moteur:N"),
            tooltip=["Moteur", "Mesure", alt.Tooltip("Millisecondes:Q", format=".1f")],
        )
        .properties(height=230, title="Temps de réponse par requête")
    )

    return _habiller(graphique, theme)


def compromis_index(comparaison: list[dict], theme: str) -> alt.Chart:
    """
    Le compromis vitesse / exhaustivité de l'index approximatif.

    Chaque point est une configuration : en abscisse ce qu'elle coûte, en
    ordonnée ce qu'elle retrouve par rapport à l'index exact. La configuration
    idéale serait en haut à gauche.
    """
    donnees = pd.DataFrame([
        {
            "Configuration": f"{ligne.get('index', '?')} (nprobe {ligne.get('nprobe', '-')})",
            "ms par requête": round(float(ligne.get("ms_par_requete", 0)), 4),
            "Rappel vs exact": round(float(ligne.get("rappel_vs_exact", 0)), 4),
            "Type": "exact" if "flat" in str(ligne.get("index", "")) else "approximatif",
        }
        for ligne in comparaison
    ])

    couleurs = alt.Scale(
        domain=["exact", "approximatif"],
        range=[MOTEURS["semantique"]["couleur"], MOTEURS["lexical"]["couleur"]],
    )

    points = (
        alt.Chart(donnees)
        .mark_point(size=170, filled=True, opacity=0.9)
        .encode(
            x=alt.X("ms par requête:Q", scale=alt.Scale(type="log"), title="ms par requête (échelle log)"),
            y=alt.Y("Rappel vs exact:Q", scale=alt.Scale(domain=[0, 1.05]),
                    axis=alt.Axis(format="%"), title="rappel par rapport à l'index exact"),
            color=alt.Color("Type:N", scale=couleurs, title=None),
            tooltip=["Configuration", alt.Tooltip("ms par requête:Q", format=".3f"),
                     alt.Tooltip("Rappel vs exact:Q", format=".1%")],
        )
    )

    etiquettes = points.mark_text(align="left", dx=10, dy=-8, fontSize=10).encode(
        text="Configuration:N",
        color=alt.value(PALETTES.get(theme, PALETTES["sombre"])["texte_faible"]),
    )

    graphique = (points + etiquettes).properties(
        height=280, title="Index exact contre index approximatif"
    )

    return _habiller(graphique, theme)


def stratification(groupes: list[dict], theme: str) -> alt.Chart:
    """
    Qualité selon le recouvrement lexical entre la requête et le bon document.

    C'est le graphique le plus honnête du lot : il montre que le protocole
    « titre vers résumé » ne descend jamais dans le régime où les mots cessent
    de se recouvrir, et donc qu'il ne mesure pas vraiment le sens.
    """
    lignes = [
        {
            # Le taux moyen de mots communs est ce qui définit réellement le
            # groupe : on le met en tête, le nom du groupe suit entre
            # parenthèses. Sans cela, l'axe affiche trois libellés qui se
            # ressemblent et se font tronquer au même endroit.
            "Groupe": f"{groupe['recouvrement_moyen']:.0%} de mots communs",
            "Moteur": _nom_moteur(cle_moteur),
            "MRR@10": round(float(groupe[cle_moteur].get("mrr@10", 0)), 4),
            "Recouvrement lexical": groupe["groupe"],
            "ordre": position,
        }
        for position, groupe in enumerate(groupes)
        for cle_moteur in ("semantique", "bm25")
        if cle_moteur in groupe
    ]

    donnees = pd.DataFrame(lignes)

    graphique = (
        alt.Chart(donnees)
        .mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3, size=26)
        .encode(
            x=alt.X("Groupe:N", sort=alt.EncodingSortField("ordre"), title=None,
                    axis=alt.Axis(labelAngle=0, labelLimit=200, labelPadding=6)),
            y=alt.Y("MRR@10:Q", scale=alt.Scale(domain=[0, 1]), title=None),
            color=alt.Color("Moteur:N", scale=_echelle_couleurs(donnees), title=None),
            xOffset=alt.XOffset("Moteur:N"),
            tooltip=["Recouvrement lexical", "Groupe", "Moteur",
                     alt.Tooltip("MRR@10:Q", format=".3f")],
        )
        .properties(height=250, title="Qualité selon le recouvrement de vocabulaire")
    )

    return _habiller(graphique, theme)
