"""
Le système visuel de l'interface.

Tout ce qui relève de l'apparence est regroupé ici : palette, typographie,
espacements, styles des cartes. Le reste de l'interface ne contient aucune
couleur en dur — même principe que `config.py` pour le moteur.

### Trois couleurs qui veulent dire quelque chose

Chaque moteur possède une couleur, et cette couleur le suit partout : dans les
cartes de résultats, dans les badges du duel, dans les graphiques d'évaluation.
Un jury qui a vu une fois que le violet est le sémantique n'a plus besoin de
lire les légendes.

    violet   sémantique   Sentence-BERT + FAISS
    ambre    lexical      BM25
    émeraude hybride      fusion RRF des deux

### Deux thèmes, une seule définition

Le thème sombre est celui par défaut : il met en valeur les surlignages et
fatigue moins pendant une démonstration. Le thème clair existe pour les
vidéoprojecteurs, sur lesquels un fond noir devient souvent illisible. Les deux
partagent la même feuille de style : seules les variables CSS changent.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Identité des moteurs
# ---------------------------------------------------------------------------

MOTEURS = {
    "semantique": {
        "libelle": "Sémantique",
        "sous_titre": "Sentence-BERT + FAISS",
        "description": "compare le sens",
        "couleur": "#8b5cf6",
        "couleur_2": "#22d3ee",
        "unite_score": "cosinus",
        "icone": "◆",
    },
    "lexical": {
        "libelle": "Lexical",
        "sous_titre": "BM25",
        "description": "compare les mots",
        "couleur": "#f59e0b",
        "couleur_2": "#fbbf24",
        "unite_score": "score BM25",
        "icone": "▦",
    },
    "hybride": {
        "libelle": "Hybride",
        "sous_titre": "fusion RRF",
        "description": "fait voter les deux",
        "couleur": "#10b981",
        "couleur_2": "#34d399",
        "unite_score": "score RRF",
        "icone": "⬢",
    },
}


PALETTES = {
    "sombre": {
        "fond": "#080a0f",
        "fond_voile_1": "rgba(139, 92, 246, 0.16)",
        "fond_voile_2": "rgba(34, 211, 238, 0.10)",
        "surface": "#11141d",
        "surface_haute": "#171b26",
        "surface_douce": "rgba(255, 255, 255, 0.03)",
        "bordure": "#242939",
        "bordure_douce": "rgba(255, 255, 255, 0.07)",
        "texte": "#e9ecf5",
        "texte_doux": "#98a1ba",
        "texte_faible": "#6b748d",
        "surlignage_fond": "rgba(245, 158, 11, 0.24)",
        "surlignage_texte": "#fcd34d",
        "phrase_fond": "rgba(139, 92, 246, 0.13)",
        "ombre": "0 10px 30px rgba(0, 0, 0, 0.45)",
        "succes": "#34d399",
        "alerte": "#fb7185",
        "grille": "rgba(255, 255, 255, 0.06)",
    },
    "clair": {
        "fond": "#f6f7fb",
        "fond_voile_1": "rgba(139, 92, 246, 0.10)",
        "fond_voile_2": "rgba(34, 211, 238, 0.08)",
        "surface": "#ffffff",
        "surface_haute": "#ffffff",
        "surface_douce": "rgba(15, 23, 42, 0.03)",
        "bordure": "#e2e6f0",
        "bordure_douce": "rgba(15, 23, 42, 0.08)",
        "texte": "#0f1729",
        "texte_doux": "#55607a",
        "texte_faible": "#8792ab",
        "surlignage_fond": "rgba(245, 158, 11, 0.28)",
        "surlignage_texte": "#92400e",
        "phrase_fond": "rgba(139, 92, 246, 0.11)",
        "ombre": "0 8px 24px rgba(15, 23, 42, 0.08)",
        "succes": "#059669",
        "alerte": "#e11d48",
        "grille": "rgba(15, 23, 42, 0.08)",
    },
}


def couleur_moteur(nom: str) -> str:
    """Couleur d'identité d'un moteur, gris neutre si le nom est inconnu."""
    return MOTEURS.get(nom, {}).get("couleur", "#94a3b8")


def unite_score(nom: str) -> str:
    """
    Nom de l'unité du score, qui n'est pas la même selon le moteur.

    Détail qui compte : un cosinus vaut entre -1 et 1, un score BM25 n'a pas
    de borne supérieure et un score RRF vaut quelques centièmes. Afficher
    « 0,837 » sans préciser de quoi il s'agit laisserait croire que les trois
    moteurs se comparent chiffre à chiffre, ce qui est faux.
    """
    return MOTEURS.get(nom, {}).get("unite_score", "score")


# ---------------------------------------------------------------------------
# Feuille de style
# ---------------------------------------------------------------------------

def css(theme: str = "sombre") -> str:
    """Produit la feuille de style complète pour le thème demandé."""
    p = PALETTES.get(theme, PALETTES["sombre"])
    semantique = MOTEURS["semantique"]

    return f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;600&display=swap');

:root {{
    --fond: {p["fond"]};
    --surface: {p["surface"]};
    --surface-haute: {p["surface_haute"]};
    --surface-douce: {p["surface_douce"]};
    --bordure: {p["bordure"]};
    --bordure-douce: {p["bordure_douce"]};
    --texte: {p["texte"]};
    --texte-doux: {p["texte_doux"]};
    --texte-faible: {p["texte_faible"]};
    --surlignage-fond: {p["surlignage_fond"]};
    --surlignage-texte: {p["surlignage_texte"]};
    --phrase-fond: {p["phrase_fond"]};
    --ombre: {p["ombre"]};
    --succes: {p["succes"]};
    --alerte: {p["alerte"]};
    --grille: {p["grille"]};
    --semantique: {semantique["couleur"]};
    --semantique-2: {semantique["couleur_2"]};
    --lexical: {MOTEURS["lexical"]["couleur"]};
    --hybride: {MOTEURS["hybride"]["couleur"]};
    --police: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    --mono: 'JetBrains Mono', 'SF Mono', Consolas, monospace;
    --rayon: 14px;
}}

/* --- fond général, avec deux voiles de couleur très diffus ---------------- */

.stApp {{
    background:
        radial-gradient(900px 520px at 12% -8%, {p["fond_voile_1"]}, transparent 62%),
        radial-gradient(760px 460px at 92% 2%, {p["fond_voile_2"]}, transparent 58%),
        var(--fond);
    color: var(--texte);
    font-family: var(--police);
}}

.stApp, .stMarkdown, p, span, label, li {{ font-family: var(--police); }}

/* Le bandeau et le menu par défaut n'apportent rien en démonstration. */
header[data-testid="stHeader"] {{ background: transparent; }}
#MainMenu, footer {{ visibility: hidden; }}

.block-container {{ padding-top: 2.2rem; padding-bottom: 4rem; max-width: 1320px; }}

h1, h2, h3, h4 {{ font-family: var(--police); color: var(--texte); letter-spacing: -0.02em; }}

/* --- barre latérale ------------------------------------------------------ */

[data-testid="stSidebar"] {{
    background: var(--surface);
    border-right: 1px solid var(--bordure);
}}
[data-testid="stSidebar"] .block-container {{ padding-top: 1.6rem; }}

/* --- en-tête du projet --------------------------------------------------- */

.entete {{
    display: flex; align-items: center; justify-content: space-between;
    gap: 1.5rem; flex-wrap: wrap;
    padding: 0 0 1.4rem 0; margin-bottom: 1.6rem;
    border-bottom: 1px solid var(--bordure);
}}
.entete-titre {{
    font-size: 2.05rem; font-weight: 800; letter-spacing: -0.035em; line-height: 1.1;
    background: linear-gradient(100deg, var(--texte) 8%, var(--semantique) 52%, var(--semantique-2) 96%);
    -webkit-background-clip: text; background-clip: text;
    -webkit-text-fill-color: transparent;
    margin: 0;
}}
.entete-sous-titre {{
    color: var(--texte-doux); font-size: 0.92rem; margin-top: 0.35rem; max-width: 46ch;
}}

.bandeau-etat {{ display: flex; gap: 0.5rem; flex-wrap: wrap; align-items: center; }}
.puce {{
    display: inline-flex; align-items: center; gap: 0.45rem;
    background: var(--surface-douce); border: 1px solid var(--bordure);
    border-radius: 999px; padding: 0.34rem 0.78rem;
    font-size: 0.76rem; color: var(--texte-doux); white-space: nowrap;
}}
.puce b {{ color: var(--texte); font-weight: 600; font-variant-numeric: tabular-nums; }}
.puce.mono {{ font-family: var(--mono); font-size: 0.71rem; }}

.point {{ width: 7px; height: 7px; border-radius: 50%; background: var(--succes); }}
.point.vivant {{ animation: battement 2.2s ease-in-out infinite; }}
.point.rouge {{ background: var(--alerte); }}
@keyframes battement {{
    0%, 100% {{ box-shadow: 0 0 0 0 rgba(52, 211, 153, 0.55); }}
    60%      {{ box-shadow: 0 0 0 6px rgba(52, 211, 153, 0); }}
}}

/* --- champ de recherche -------------------------------------------------- */

.stTextInput input {{
    background: var(--surface) !important;
    border: 1px solid var(--bordure) !important;
    border-radius: 12px !important;
    color: var(--texte) !important;
    font-size: 1.02rem !important;
    padding: 0.85rem 1.05rem !important;
    transition: border-color 0.18s ease, box-shadow 0.18s ease;
}}
.stTextInput input:focus {{
    border-color: var(--semantique) !important;
    box-shadow: 0 0 0 3px rgba(139, 92, 246, 0.18) !important;
}}
.stTextInput input::placeholder {{ color: var(--texte-faible) !important; }}

/* Une requête arabe doit s'afficher de droite à gauche. */
.rtl {{ direction: rtl; text-align: right; }}

/* --- boutons ------------------------------------------------------------- */

/* Streamlit impose la couleur du texte de ses boutons d'après son thème de
   base : sans !important, les libellés restent blancs sur fond clair. */
.stButton button {{
    background: var(--surface) !important;
    color: var(--texte-doux) !important;
    border: 1px solid var(--bordure) !important;
    border-radius: 10px;
    font-size: 0.82rem; font-weight: 500; padding: 0.5rem 0.9rem;
    transition: all 0.16s ease; text-align: left;
}}
.stButton button p, .stButton button span {{ color: inherit !important; }}
.stButton button:hover {{
    border-color: var(--semantique) !important;
    color: var(--texte) !important;
    transform: translateY(-1px);
}}
.stButton button[kind="primary"] {{
    background: linear-gradient(100deg, var(--semantique), var(--semantique-2)) !important;
    color: #ffffff !important; border: none !important; font-weight: 600;
}}
.stButton button[kind="primary"]:hover {{ filter: brightness(1.08); }}

/* --- onglets -------------------------------------------------------------
   Streamlit 1.61 identifie ses onglets par data-testid="stTab" ; les versions
   antérieures utilisaient l'attribut BaseWeb. Les deux familles de sélecteurs
   sont conservées pour que la feuille de style survive à une mise à jour. */

.stTabs [data-baseweb="tab-list"], .stTabs [role="tablist"] {{
    gap: 0.35rem; border-bottom: 1px solid var(--bordure); padding-bottom: 0.1rem;
}}
.stTabs [data-testid="stTab"], .stTabs [data-baseweb="tab"] {{
    background: transparent; border-radius: 9px 9px 0 0;
    padding: 0.6rem 1.05rem;
    font-size: 0.88rem; font-weight: 500;
}}
.stTabs [data-testid="stTab"] p, .stTabs [data-baseweb="tab"] p {{
    color: var(--texte-doux) !important;
    font-size: 0.88rem; font-weight: 500;
}}
.stTabs [data-testid="stTab"]:hover p {{ color: var(--texte) !important; }}
.stTabs [data-testid="stTab"][aria-selected="true"],
.stTabs [data-baseweb="tab"][aria-selected="true"] {{
    background: var(--surface-douce);
    border-bottom: 2px solid var(--semantique);
}}
.stTabs [data-testid="stTab"][aria-selected="true"] p,
.stTabs [data-baseweb="tab"][aria-selected="true"] p {{
    color: var(--texte) !important; font-weight: 600;
}}

/* --- carte de résultat --------------------------------------------------- */

.carte {{
    position: relative;
    background: var(--surface);
    border: 1px solid var(--bordure);
    border-left: 3px solid var(--accent, var(--semantique));
    border-radius: var(--rayon);
    padding: 1.05rem 1.25rem 1.1rem;
    margin-bottom: 0.85rem;
    transition: transform 0.16s ease, box-shadow 0.16s ease, border-color 0.16s ease;
    animation: apparition 0.32s ease both;
}}
.carte:hover {{
    transform: translateY(-2px);
    box-shadow: var(--ombre);
    border-color: var(--bordure-douce);
    border-left-color: var(--accent, var(--semantique));
}}
@keyframes apparition {{
    from {{ opacity: 0; transform: translateY(7px); }}
    to   {{ opacity: 1; transform: translateY(0); }}
}}

.carte-tete {{
    display: flex; align-items: flex-start; justify-content: space-between;
    gap: 1rem; margin-bottom: 0.5rem;
}}
.rang {{
    font-family: var(--mono); font-size: 0.72rem; font-weight: 600;
    color: var(--accent, var(--semantique));
    background: color-mix(in srgb, var(--accent, #8b5cf6) 13%, transparent);
    border-radius: 6px; padding: 0.14rem 0.42rem; flex-shrink: 0;
}}
.carte-titre {{
    font-size: 1.02rem; font-weight: 650; line-height: 1.38; margin: 0;
    color: var(--texte); flex: 1;
}}
.carte-titre a {{ color: inherit; text-decoration: none; }}
.carte-titre a:hover {{ color: var(--accent, var(--semantique)); }}

.meta {{
    display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap;
    font-size: 0.76rem; color: var(--texte-faible); margin: 0.45rem 0 0.6rem;
}}
.etiquette {{
    background: var(--surface-douce); border: 1px solid var(--bordure);
    border-radius: 5px; padding: 0.08rem 0.42rem;
    font-size: 0.7rem; color: var(--texte-doux); white-space: nowrap;
}}

/* --- le score et sa jauge ------------------------------------------------ */

.bloc-score {{ text-align: right; flex-shrink: 0; min-width: 92px; }}
.valeur-score {{
    font-family: var(--mono); font-size: 1.12rem; font-weight: 600;
    color: var(--accent, var(--semantique)); line-height: 1;
    font-variant-numeric: tabular-nums;
}}
.unite-score {{ font-size: 0.64rem; color: var(--texte-faible); margin-top: 0.22rem; }}
.jauge {{
    height: 3px; background: var(--surface-douce); border-radius: 2px;
    overflow: hidden; margin-top: 0.42rem;
}}
.jauge-remplissage {{
    height: 100%; border-radius: 2px;
    background: linear-gradient(90deg, var(--accent, var(--semantique)), var(--semantique-2));
    animation: remplir 0.55s cubic-bezier(0.22, 1, 0.36, 1) both;
}}
@keyframes remplir {{ from {{ width: 0 !important; }} }}

/* --- extrait, surlignages ------------------------------------------------ */

.extrait {{
    font-size: 0.875rem; line-height: 1.62; color: var(--texte-doux);
    margin: 0.55rem 0 0;
}}
mark.terme-surligne {{
    background: var(--surlignage-fond); color: var(--surlignage-texte);
    padding: 0.03em 0.22em; border-radius: 3px; font-weight: 550;
}}
.phrase-cle {{
    background: var(--phrase-fond);
    border-left: 2px solid var(--semantique);
    padding: 0.06em 0.4em; border-radius: 0 4px 4px 0;
    color: var(--texte);
}}

/* --- bandeaux d'explication ---------------------------------------------- */

.note {{
    display: flex; align-items: flex-start; gap: 0.55rem;
    font-size: 0.78rem; line-height: 1.5;
    margin-top: 0.75rem; padding: 0.55rem 0.75rem;
    border-radius: 9px; border: 1px solid var(--bordure);
    background: var(--surface-douce); color: var(--texte-doux);
}}
.note b {{ color: var(--texte); font-weight: 600; }}
.note.remarquable {{
    border-color: color-mix(in srgb, var(--semantique) 40%, transparent);
    background: var(--phrase-fond); color: var(--texte);
}}

details.repli {{ margin-top: 0.7rem; }}
details.repli summary {{
    cursor: pointer; font-size: 0.76rem; color: var(--texte-faible);
    list-style: none; user-select: none; padding: 0.16rem 0;
}}
details.repli summary::-webkit-details-marker {{ display: none; }}
details.repli summary:hover {{ color: var(--semantique); }}
details.repli summary::before {{ content: "▸ "; }}
details.repli[open] summary::before {{ content: "▾ "; }}
details.repli .contenu {{
    font-size: 0.83rem; line-height: 1.6; color: var(--texte-doux);
    padding: 0.6rem 0.2rem 0.1rem; border-top: 1px dashed var(--bordure); margin-top: 0.4rem;
}}

/* --- badges de comparaison ----------------------------------------------- */

.badge {{
    display: inline-flex; align-items: center; gap: 0.3rem;
    font-size: 0.68rem; font-weight: 600; border-radius: 999px;
    padding: 0.14rem 0.55rem; white-space: nowrap;
}}
.badge-exclusif {{
    background: color-mix(in srgb, var(--accent, #8b5cf6) 18%, transparent);
    color: var(--accent, var(--semantique));
    border: 1px solid color-mix(in srgb, var(--accent, #8b5cf6) 38%, transparent);
}}
.badge-commun {{
    background: var(--surface-douce); color: var(--texte-faible);
    border: 1px solid var(--bordure);
}}

/* --- panneaux (verdict, vide, erreur) ------------------------------------ */

.panneau {{
    border: 1px solid var(--bordure); border-radius: var(--rayon);
    background: var(--surface); padding: 1.05rem 1.25rem; margin-bottom: 1rem;
}}
.panneau-titre {{
    font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.09em;
    color: var(--texte-faible); font-weight: 600; margin-bottom: 0.5rem;
}}
.panneau-verdict {{
    border-left: 3px solid var(--semantique);
    background: linear-gradient(100deg, var(--phrase-fond), transparent 62%), var(--surface);
    font-size: 0.95rem; line-height: 1.6; color: var(--texte);
}}
.panneau-alerte {{
    border-left: 3px solid var(--alerte);
    background: linear-gradient(100deg, rgba(251, 113, 133, 0.10), transparent 62%), var(--surface);
}}
.panneau-vide {{
    text-align: center; padding: 2.6rem 1.5rem; color: var(--texte-faible);
    border: 1px dashed var(--bordure); background: transparent;
}}

/* --- colonne d'un moteur dans le duel ------------------------------------ */

.tete-colonne {{
    display: flex; align-items: center; gap: 0.55rem;
    padding: 0.65rem 0.9rem; margin-bottom: 0.8rem;
    border-radius: 10px; border: 1px solid var(--bordure);
    border-top: 2px solid var(--accent, var(--semantique));
    background: var(--surface);
}}
.tete-colonne .nom {{ font-weight: 650; font-size: 0.95rem; color: var(--texte); }}
.tete-colonne .detail {{ font-size: 0.73rem; color: var(--texte-faible); margin-left: auto; text-align: right; }}
.tete-colonne .marque {{ color: var(--accent, var(--semantique)); font-size: 1rem; }}

/* --- chiffres clés ------------------------------------------------------- */

.grille-chiffres {{
    display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
    gap: 0.7rem; margin-bottom: 1rem;
}}
.chiffre {{
    background: var(--surface); border: 1px solid var(--bordure);
    border-radius: 11px; padding: 0.75rem 0.9rem;
}}
.chiffre .valeur {{
    font-family: var(--mono); font-size: 1.5rem; font-weight: 600;
    color: var(--accent, var(--texte)); line-height: 1.1; font-variant-numeric: tabular-nums;
}}
.chiffre .legende {{ font-size: 0.72rem; color: var(--texte-faible); margin-top: 0.28rem; line-height: 1.35; }}

/* --- étapes du pipeline (onglet architecture) ---------------------------- */

.chaine {{ display: flex; align-items: stretch; gap: 0.5rem; flex-wrap: wrap; margin: 0.5rem 0 1.2rem; }}
.etape {{
    flex: 1; min-width: 128px;
    background: var(--surface); border: 1px solid var(--bordure);
    border-radius: 11px; padding: 0.7rem 0.8rem;
}}
.etape .numero {{
    font-family: var(--mono); font-size: 0.66rem; color: var(--accent, var(--semantique));
    font-weight: 600;
}}
.etape .nom {{ font-size: 0.85rem; font-weight: 600; margin: 0.2rem 0 0.15rem; color: var(--texte); }}
.etape .quoi {{ font-size: 0.72rem; color: var(--texte-faible); line-height: 1.45; }}
.fleche {{ display: flex; align-items: center; color: var(--texte-faible); font-size: 1.1rem; }}

/* --- couleur du texte des composants Streamlit ---------------------------
   Streamlit peint les libellés de ses widgets d'après SON thème de base, fixé
   à « dark » dans .streamlit/config.toml pour éviter un flash blanc au
   démarrage. En thème clair, ces libellés resteraient donc gris pâle sur fond
   blanc — illisibles, précisément dans le thème prévu pour le vidéoprojecteur.
   On reprend donc la main sur la couleur partout où Streamlit la fixe. */

[data-testid="stSidebar"] *:not(a):not(code),
[data-testid="stWidgetLabel"] *,
.stRadio label, .stCheckbox label, .stSlider label,
[data-baseweb="radio"] div, [data-baseweb="checkbox"] div {{
    color: var(--texte-doux) !important;
}}
[data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3, [data-testid="stSidebar"] h4,
[data-testid="stSidebar"] strong {{
    color: var(--texte) !important;
}}
[data-testid="stSidebar"] a {{ color: var(--semantique) !important; }}

.stMarkdown, .stMarkdown p, .stMarkdown li, .stMarkdown td {{ color: var(--texte-doux); }}
.stMarkdown strong {{ color: var(--texte); }}
h1, h2, h3, h4, h5, h6 {{ color: var(--texte) !important; }}

/* Le curseur du sélecteur de thème garde sa pastille lisible dans les deux
   sens : c'est le seul widget dont on change l'état pour vérifier l'autre. */
[data-testid="stSidebar"] [role="radiogroup"] [aria-checked="true"] *,
[data-testid="stSidebar"] button[aria-pressed="true"] * {{
    color: var(--texte) !important;
}}

/* --- widgets Streamlit ---------------------------------------------------
   Les listes déroulantes, étiquettes et panneaux repliables sont rendus par
   BaseWeb, qui ignore le thème Streamlit. Sans ces règles, le thème clair
   laisserait apparaître des menus sombres, et inversement. */

[data-baseweb="select"] > div, [data-baseweb="input"] {{
    background: var(--surface) !important;
    border-color: var(--bordure) !important;
    color: var(--texte) !important;
}}
[data-baseweb="popover"] [role="listbox"], [data-baseweb="menu"], [data-baseweb="popover"] ul {{
    background: var(--surface-haute) !important;
    border: 1px solid var(--bordure) !important;
}}
[data-baseweb="menu"] li {{ color: var(--texte-doux) !important; }}
[data-baseweb="menu"] li:hover {{ background: var(--surface-douce) !important; color: var(--texte) !important; }}
[data-baseweb="tag"] {{
    background: color-mix(in srgb, var(--semantique) 20%, transparent) !important;
    border: 1px solid color-mix(in srgb, var(--semantique) 40%, transparent) !important;
    color: var(--texte) !important;
}}

[data-testid="stExpander"] details {{
    background: var(--surface); border: 1px solid var(--bordure);
    border-radius: 11px; overflow: hidden;
}}
[data-testid="stExpander"] summary {{ color: var(--texte-doux); font-size: 0.85rem; }}

/* Les encadrés st.warning / st.error / st.info portent leur couleur sur un
   conteneur interne : viser le seul élément externe laisse le fond d'origine. */
[data-testid="stAlert"], [data-testid="stAlert"] > div,
[data-testid="stAlertContainer"], [data-testid="stNotification"] {{
    background: var(--surface) !important;
    border-radius: 11px !important;
    color: var(--texte-doux) !important;
}}
[data-testid="stAlert"] {{
    border: 1px solid var(--bordure) !important;
    border-left: 3px solid var(--alerte) !important;
    overflow: hidden;
}}
[data-testid="stAlert"] p, [data-testid="stAlert"] code {{ color: var(--texte-doux) !important; }}
[data-testid="stAlert"] code {{
    background: var(--surface-douce) !important; color: var(--semantique) !important;
}}

[data-testid="stDataFrame"], [data-testid="stTable"] {{
    border: 1px solid var(--bordure); border-radius: 11px; overflow: hidden;
}}

[data-testid="stCaptionContainer"], .stCaption {{ color: var(--texte-faible) !important; }}

/* --- divers -------------------------------------------------------------- */

.stSlider [data-baseweb="slider"] div[role="slider"] {{ background: var(--semantique) !important; }}
[data-testid="stMetricValue"] {{ font-family: var(--mono); font-size: 1.35rem; }}
[data-testid="stMetricLabel"] {{ color: var(--texte-faible); }}

hr {{ border-color: var(--bordure); }}
code {{ font-family: var(--mono); font-size: 0.82em; }}

.stDataFrame {{ border-radius: 10px; overflow: hidden; }}

/* Le fond des graphiques Altair reste transparent : les couleurs sont
   définies dans ui/graphiques.py pour rester cohérentes avec les cartes. */
.vega-embed {{ background: transparent !important; }}
.vega-embed summary {{ display: none !important; }}
</style>
"""
