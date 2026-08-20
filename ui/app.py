"""
Interface graphique du moteur de recherche.

Volontairement, cette interface ne sait rien de Sentence-BERT ni de FAISS :
elle ne fait qu'appeler l'API. C'est ce découplage qui rend l'architecture
propre — on peut changer entièrement le moteur sans toucher à l'affichage.

Lancement (dans un second terminal, l'API devant déjà tourner) :
    streamlit run ui/app.py
"""

import sys
from pathlib import Path

import requests
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config

EXEMPLES = [
    ("Français", "détection de la fraude bancaire par apprentissage automatique"),
    ("العربية", "كشف الاحتيال المصرفي باستخدام التعلم الآلي"),
    ("English", "machine learning for banking fraud detection"),
    ("Français", "réseaux de neurones pour l'imagerie médicale"),
    ("العربية", "الترجمة الآلية العصبية بين اللغات"),
    ("Français", "comment protéger la vie privée pendant l'entraînement d'un modèle"),
]

st.set_page_config(page_title="Recherche sémantique arXiv", page_icon="🔎", layout="wide")


# ---------------------------------------------------------------------------
# Accès à l'API
# ---------------------------------------------------------------------------

def api_disponible() -> tuple[bool, dict]:
    try:
        reponse = requests.get(f"{config.URL_API}/statistiques", timeout=5)
        reponse.raise_for_status()
        return True, reponse.json()
    except Exception:
        return False, {}


def rechercher(requete: str, k: int, moteur: str) -> dict | None:
    try:
        reponse = requests.get(
            f"{config.URL_API}/recherche",
            params={"q": requete, "k": k, "moteur": moteur},
            timeout=30,
        )
        reponse.raise_for_status()
        return reponse.json()
    except Exception as erreur:
        st.error(f"Erreur pendant la recherche : {erreur}")
        return None


# ---------------------------------------------------------------------------
# Affichage
# ---------------------------------------------------------------------------

def afficher_resultats(reponse: dict) -> None:
    if not reponse or not reponse["resultats"]:
        st.warning("Aucun résultat pour cette requête.")
        return

    st.caption(f"{reponse['nb_resultats']} articles trouvés en {reponse['duree_ms']} ms")

    for resultat in reponse["resultats"]:
        with st.container(border=True):
            colonne_texte, colonne_score = st.columns([6, 1])

            with colonne_texte:
                st.markdown(f"**{resultat['rang']}. [{resultat['titre']}]({resultat['url']})**")
                auteurs = ", ".join(resultat["auteurs"][:4])
                if len(resultat["auteurs"]) > 4:
                    auteurs += " et al."
                st.caption(
                    f"{auteurs} · {resultat['date']} · "
                    f"{', '.join(resultat['categories'][:3])}"
                )
                st.write(resultat["extrait"][:400] + ("..." if len(resultat["extrait"]) > 400 else ""))

            with colonne_score:
                st.metric("Score", f"{resultat['score']:.3f}")


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------

st.title("Recherche sémantique dans arXiv")
st.caption(
    "Pose ta question en français, en arabe ou en anglais : le moteur cherche "
    "par le sens, pas par les mots."
)

disponible, infos = api_disponible()

with st.sidebar:
    st.header("Paramètres")

    if disponible:
        st.success("API connectée")
        st.metric("Articles indexés", f"{infos.get('nb_articles', 0):,}".replace(",", " "))
        st.metric("Passages indexés", f"{infos.get('nb_passages', 0):,}".replace(",", " "))
        st.caption(f"Modèle : `{infos.get('modele', '')}`")
        st.caption(f"Index : {infos.get('type_index', '')} · "
                   f"{infos.get('dimension', 0)} dimensions")
    else:
        st.error("API injoignable")
        st.markdown(
            "Démarre-la dans un autre terminal :\n\n"
            "```\nuvicorn api.main:application\n```"
        )

    nombre_resultats = st.slider("Nombre de résultats", 3, 30, config.TOP_K)

    mode = st.radio(
        "Moteur",
        ["Sémantique", "Lexical (BM25)", "Comparer les deux"],
        help=(
            "Le moteur sémantique compare le sens. Le moteur lexical compare "
            "les mots. La comparaison montre la différence sur la même requête."
        ),
    )

st.subheader("Exemples")
colonnes = st.columns(3)
for position, (langue, exemple) in enumerate(EXEMPLES):
    with colonnes[position % 3]:
        if st.button(f"{langue} — {exemple[:38]}...", key=f"exemple_{position}",
                     use_container_width=True):
            st.session_state["requete"] = exemple

requete = st.text_input(
    "Ta question",
    value=st.session_state.get("requete", ""),
    placeholder="par exemple : comment détecter des transactions frauduleuses",
)

if st.button("Rechercher", type="primary") or requete:
    if not disponible:
        st.stop()

    if requete.strip():
        if mode == "Comparer les deux":
            gauche, droite = st.columns(2)
            with gauche:
                st.subheader("Sémantique")
                st.caption("Sentence-BERT + FAISS — compare le sens")
                afficher_resultats(rechercher(requete, nombre_resultats, "semantique"))
            with droite:
                st.subheader("Lexical")
                st.caption("BM25 — compare les mots")
                afficher_resultats(rechercher(requete, nombre_resultats, "lexical"))
        else:
            nom_moteur = "semantique" if mode == "Sémantique" else "lexical"
            afficher_resultats(rechercher(requete, nombre_resultats, nom_moteur))
