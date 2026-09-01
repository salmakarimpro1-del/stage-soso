"""
L'interface du moteur de recherche.

Elle ne sait rien de Sentence-BERT ni de FAISS : elle appelle l'API et met en
forme ce qu'elle reçoit. Ce découplage permet de remplacer entièrement le
moteur sans toucher une ligne d'affichage.

L'écran est organisé en cinq vues qui suivent l'ordre d'une soutenance :

    Recherche       le moteur en usage normal
    Duel            les deux approches sur la même question, et leur écart
    Démonstration   le scénario multilingue, prêt à dérouler devant un jury
    Évaluation      les mesures du protocole expérimental
    Architecture    ce qui se passe entre la question et le résultat

La barre de recherche est placée au-dessus des onglets, et non dans chacun :
on pose une question une fois, puis on change de point de vue sans la
retaper. C'est ce qui rend la comparaison immédiate en démonstration.

Lancement (l'API devant déjà tourner dans un autre terminal) :
    streamlit run ui/app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
from src import filtres as module_filtres
from ui import client, composants, graphiques
from ui.theme import MOTEURS, couleur_moteur, css

st.set_page_config(
    page_title="Recherche sémantique arXiv",
    page_icon="◆",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Questions d'amorçage, une par langue, choisies pour montrer les trois cas
# intéressants : vocabulaire présent, paraphrase, et alphabet différent.
EXEMPLES = [
    ("Français", "détection de la fraude bancaire par apprentissage automatique"),
    ("العربية", "كشف الاحتيال المصرفي باستخدام التعلم الآلي"),
    ("English", "machine learning for banking fraud detection"),
    ("Français", "comment protéger la vie privée pendant l'entraînement d'un modèle"),
    ("العربية", "الترجمة الآلية العصبية بين اللغات"),
    ("Français", "réseaux de neurones pour l'imagerie médicale"),
]


# ---------------------------------------------------------------------------
# État de la session
# ---------------------------------------------------------------------------

def initialiser_etat() -> None:
    """Valeurs par défaut, posées une seule fois au premier chargement."""
    defauts = {
        "champ_requete": "",
        "moteur": "semantique",
        "nb_resultats": config.TOP_K,
        "expliquer": True,
        "historique": [],
        "demo_lancee": None,
    }
    for cle, valeur in defauts.items():
        st.session_state.setdefault(cle, valeur)


def poser_requete(texte: str) -> None:
    """
    Remplit la barre de recherche depuis un bouton d'exemple.

    Cette fonction est branchée en `on_click`, et non appelée dans le corps du
    script. La raison est une règle de Streamlit qui coûte cher à découvrir :
    une fois qu'un widget a été instancié pendant un cycle, écrire dans sa clé
    de session n'a plus aucun effet — sans erreur, sans avertissement, le champ
    reste simplement vide. Les fonctions de rappel, elles, s'exécutent avant la
    reconstruction des widgets : c'est le seul moment où l'écriture est prise
    en compte.
    """
    st.session_state["champ_requete"] = texte


def memoriser(requete: str) -> None:
    """Garde les dernières questions posées, sans doublon."""
    historique = st.session_state["historique"]
    if requete and (not historique or historique[0] != requete):
        st.session_state["historique"] = [requete] + [q for q in historique if q != requete][:7]


initialiser_etat()

# Le thème est lu ici, tout en haut, alors que le sélecteur qui le règle se
# trouve dans la barre latérale, plus bas. C'est possible parce que le
# sélecteur porte la clé « choix_theme » : Streamlit restaure l'état des
# widgets AVANT de rejouer le script, la valeur choisie au clic précédent est
# donc déjà disponible. Écrire ce même état après coup, comme le ferait
# `st.session_state[...] = st.segmented_control(...)`, arriverait un cycle
# trop tard — la page ne changerait de thème qu'au clic suivant.
theme_actif = st.session_state.get("choix_theme") or "sombre"
st.markdown(css(theme_actif), unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# En-tête et barre latérale
# ---------------------------------------------------------------------------

disponible, infos = client.etat()
st.markdown(composants.entete(disponible, infos), unsafe_allow_html=True)

with st.sidebar:
    st.markdown("### Réglages")

    st.segmented_control(
        "Thème",
        options=["sombre", "clair"],
        default="sombre",
        key="choix_theme",
        help="Le thème clair est plus lisible sur un vidéoprojecteur.",
    )

    moteur_choisi = st.radio(
        "Moteur de recherche",
        options=["semantique", "lexical", "hybride"],
        format_func=lambda nom: f"{MOTEURS[nom]['icone']}  {MOTEURS[nom]['libelle']} — {MOTEURS[nom]['description']}",
        index=["semantique", "lexical", "hybride"].index(st.session_state["moteur"]),
        help=(
            "Le moteur sémantique compare le sens, le lexical compare les mots, "
            "l'hybride fusionne les deux classements par Reciprocal Rank Fusion."
        ),
    )
    st.session_state["moteur"] = moteur_choisi

    st.session_state["nb_resultats"] = st.slider("Nombre de résultats", 3, 30, st.session_state["nb_resultats"])

    st.session_state["expliquer"] = st.toggle(
        "Expliquer les résultats",
        value=st.session_state["expliquer"],
        help=(
            "Surligne les mots partagés et la phrase du résumé la plus proche "
            "de la question. Coûte un second passage dans le modèle."
        ),
    )

    # --- filtres sur métadonnées ---
    inventaire = client.facettes() if disponible else {"categories": [], "annee_min": None, "annee_max": None}
    categories_disponibles = [c["code"] for c in inventaire.get("categories", [])]
    libelles = {c["code"]: f"{c['code']} — {c.get('libelle', '')} ({c['nb_articles']})"
                for c in inventaire.get("categories", [])}

    with st.expander("Filtres", expanded=False):
        categories_choisies = st.multiselect(
            "Catégories arXiv",
            options=categories_disponibles,
            format_func=lambda code: libelles.get(code, code),
            help="Un article appartenant à l'une des catégories cochées est conservé.",
        )

        annee_min = annee_max = None
        borne_basse, borne_haute = inventaire.get("annee_min"), inventaire.get("annee_max")
        # Un curseur d'années n'a de sens que si le corpus en couvre plusieurs.
        if borne_basse and borne_haute and borne_haute > borne_basse:
            annee_min, annee_max = st.slider(
                "Années de publication",
                min_value=int(borne_basse), max_value=int(borne_haute),
                value=(int(borne_basse), int(borne_haute)),
            )
        elif borne_basse:
            st.caption(f"Corpus entièrement publié en {borne_basse} : filtre par année sans objet.")

        auteur = st.text_input("Auteur", placeholder="fragment de nom") or None

    if st.session_state["historique"]:
        st.markdown("### Questions récentes")
        for position, ancienne in enumerate(st.session_state["historique"][:6]):
            st.button(
                ancienne[:44] + ("…" if len(ancienne) > 44 else ""),
                key=f"hist_{position}",
                width="stretch",
                on_click=poser_requete,
                args=(ancienne,),
            )

    if not disponible:
        st.error("API injoignable")
        st.markdown(
            "Démarre-la dans un autre terminal :\n\n"
            "```\nuvicorn api.main:application\n```\n\n"
            "Si l'index n'existe pas encore :\n\n"
            "```\npython scripts/1_collecter.py\npython scripts/2_indexer.py\n```"
        )

    st.markdown("---")
    st.caption(f"[Documentation de l'API]({config.URL_API}/docs)")


# ---------------------------------------------------------------------------
# Barre de recherche, partagée par les onglets Recherche et Duel
# ---------------------------------------------------------------------------

colonne_champ, colonne_bouton = st.columns([9, 1.4])

with colonne_champ:
    requete = st.text_input(
        "Question",
        key="champ_requete",
        placeholder="Pose ta question en français, en arabe ou en anglais…",
        label_visibility="collapsed",
    )

with colonne_bouton:
    lancer = st.button("Rechercher", type="primary", width="stretch")

# Les exemples ne s'affichent que tant qu'aucune question n'est posée : une
# fois la recherche lancée, ils prendraient la place des résultats.
if not requete.strip():
    colonnes_exemples = st.columns(3)
    for position, (langue, exemple) in enumerate(EXEMPLES):
        with colonnes_exemples[position % 3]:
            st.button(
                f"{langue} · {exemple[:40]}…",
                key=f"ex_{position}",
                width="stretch",
                on_click=poser_requete,
                args=(exemple,),
            )

requete = requete.strip()
if requete:
    memoriser(requete)

parametres_filtres = {
    "categories": tuple(categories_choisies),
    "annee_min": annee_min,
    "annee_max": annee_max,
}


# ---------------------------------------------------------------------------
# Fonctions d'affichage communes
# ---------------------------------------------------------------------------

def afficher_resultats(reponse: dict, moteur: str, exclusifs: set[str] | None = None,
                       rangs_ailleurs: dict | None = None, compacte: bool = False) -> None:
    """Rend une liste de résultats sous forme de cartes."""
    resultats = reponse.get("resultats", [])
    if not resultats:
        st.markdown(
            composants.etat_vide(
                "Aucun résultat.",
                "Pour la baseline BM25, une liste vide signifie qu'aucun mot de la "
                "question n'apparaît dans le corpus.",
            ),
            unsafe_allow_html=True,
        )
        return

    score_maximum = max(float(r["score"]) for r in resultats)

    for resultat in resultats:
        st.markdown(
            composants.carte_resultat(
                resultat,
                moteur=moteur,
                score_maximum=score_maximum,
                compacte=compacte,
                exclusif=bool(exclusifs and resultat["id_doc"] in exclusifs),
                rang_ailleurs=(rangs_ailleurs or {}).get(resultat["id_doc"]),
            ),
            unsafe_allow_html=True,
        )


def lancer_recherche(moteur: str) -> dict | None:
    """Appelle l'API en gérant les erreurs de manière lisible."""
    try:
        return client.rechercher(
            requete,
            k=st.session_state["nb_resultats"],
            moteur=moteur,
            expliquer=st.session_state["expliquer"],
            auteur=auteur,
            **parametres_filtres,
        )
    except client.ErreurAPI as erreur:
        st.error(str(erreur))
        return None


def lancer_duel(moteurs: tuple[str, ...]) -> dict | None:
    try:
        return client.comparer(
            requete,
            k=st.session_state["nb_resultats"],
            moteurs=moteurs,
            expliquer=st.session_state["expliquer"],
            **parametres_filtres,
        )
    except client.ErreurAPI as erreur:
        st.error(str(erreur))
        return None


onglet_recherche, onglet_duel, onglet_demo, onglet_eval, onglet_archi = st.tabs(
    ["Recherche", "Duel des moteurs", "Démonstration", "Évaluation", "Architecture"]
)


# ---------------------------------------------------------------------------
# Onglet 1 — Recherche
# ---------------------------------------------------------------------------

with onglet_recherche:
    if not disponible:
        st.markdown(
            composants.etat_vide(
                "L'API n'est pas démarrée.",
                "Lance <code>uvicorn api.main:application</code> dans un autre terminal.",
            ),
            unsafe_allow_html=True,
        )
    elif not requete:
        st.markdown(
            composants.etat_vide(
                "Pose une question pour lancer une recherche.",
                "Les exemples ci-dessus couvrent les trois langues du projet.",
            ),
            unsafe_allow_html=True,
        )
    else:
        moteur = st.session_state["moteur"]
        with st.spinner("Recherche en cours…"):
            reponse = lancer_recherche(moteur)

        if reponse:
            identite = MOTEURS[moteur]
            duree_totale = reponse["duree_ms"] + reponse.get("duree_explication_ms", 0)
            entrees = [
                (str(reponse["nb_resultats"]), "articles trouvés", couleur_moteur(moteur)),
                (f"{reponse['duree_ms']:.0f} ms", f"recherche {identite['sous_titre']}", couleur_moteur(moteur)),
            ]
            if reponse.get("duree_explication_ms"):
                entrees.append(
                    (f"{reponse['duree_explication_ms']:.0f} ms", "explication des résultats", "var(--texte-doux)")
                )
            nb_sans_recouvrement = sum(
                1 for r in reponse["resultats"] if r.get("sans_recouvrement_lexical")
            )
            if nb_sans_recouvrement and moteur != "lexical":
                entrees.append(
                    (str(nb_sans_recouvrement), "trouvés sans aucun mot en commun",
                     MOTEURS["semantique"]["couleur"])
                )

            st.markdown(composants.chiffres(entrees), unsafe_allow_html=True)
            afficher_resultats(reponse, moteur)


# ---------------------------------------------------------------------------
# Onglet 2 — Duel
# ---------------------------------------------------------------------------

with onglet_duel:
    st.markdown(
        "La même question, soumise aux deux approches. "
        "Ce qui compte n'est pas la ressemblance des deux colonnes, mais ce que "
        "chacune est **seule** à trouver."
    )

    avec_hybride = st.checkbox(
        "Ajouter le moteur hybride (fusion RRF)",
        value=False,
        help="Fusionne les deux classements précédents. Trois colonnes au lieu de deux.",
    )
    moteurs_duel = ("semantique", "lexical", "hybride") if avec_hybride else ("semantique", "lexical")

    if not disponible or not requete:
        st.markdown(
            composants.etat_vide("Pose une question pour comparer les moteurs."),
            unsafe_allow_html=True,
        )
    else:
        with st.spinner("Interrogation des moteurs…"):
            duel = lancer_duel(moteurs_duel)

        if duel:
            analyse = duel["analyse"]

            st.markdown(
                composants.panneau(composants.markdown_leger(duel["verdict"]), titre="verdict", variante=(
                    "alerte" if analyse.get("moteurs_muets") else "verdict"
                )),
                unsafe_allow_html=True,
            )

            entrees = [
                (f"{analyse['recouvrement']:.0%}", "d'articles communs aux deux classements", "var(--texte)"),
                (str(analyse["nb_communs"]), "articles trouvés par tous les moteurs", "var(--texte-doux)"),
            ]
            for nom in moteurs_duel:
                entrees.append((
                    str(analyse["nb_uniques"].get(nom, 0)),
                    f"trouvés uniquement par {MOTEURS[nom]['libelle'].lower()}",
                    couleur_moteur(nom),
                ))
            st.markdown(composants.chiffres(entrees), unsafe_allow_html=True)

            # Pour chaque document, son rang chez les autres moteurs : c'est ce
            # qui permet d'afficher « #3 chez lexical » sous un résultat commun.
            rangs_par_document: dict[str, dict[str, int]] = {}
            for entree in analyse["communs"]:
                rangs_par_document[entree["id_doc"]] = entree["rangs"]

            colonnes = st.columns(len(moteurs_duel))
            for colonne, nom in zip(colonnes, moteurs_duel):
                with colonne:
                    resultats = duel["resultats"].get(nom, [])
                    st.markdown(composants.tete_colonne(nom, len(resultats)), unsafe_allow_html=True)

                    exclusifs = {u["id_doc"] for u in analyse["uniques"].get(nom, [])}
                    rangs_ailleurs = {
                        id_doc: {m: r for m, r in rangs.items() if m != nom}
                        for id_doc, rangs in rangs_par_document.items()
                    }
                    afficher_resultats(
                        {"resultats": resultats},
                        moteur=nom,
                        exclusifs=exclusifs,
                        rangs_ailleurs=rangs_ailleurs,
                        compacte=len(moteurs_duel) > 2,
                    )


# ---------------------------------------------------------------------------
# Onglet 3 — Démonstration
# ---------------------------------------------------------------------------

with onglet_demo:
    st.markdown(
        "Le scénario de soutenance. La même question est posée dans les trois "
        "langues du projet, sur un corpus **entièrement anglophone**. "
        "Les questions viennent du jeu d'évaluation, écrit avant les mesures : "
        "elles ne sont pas choisies pour flatter le moteur."
    )

    triplets = client.exemples() if disponible else []

    if not triplets:
        st.markdown(
            composants.etat_vide(
                "Jeu de questions multilingues indisponible.",
                "Il est lu depuis <code>eval/requetes_multilingues.json</code> via l'API.",
            ),
            unsafe_allow_html=True,
        )
    else:
        themes = [t["theme"] for t in triplets]
        theme_choisi = st.selectbox("Sujet de la démonstration", themes, index=0)
        triplet = next(t for t in triplets if t["theme"] == theme_choisi)

        colonnes_langues = st.columns(3)
        for colonne, (code, langue) in zip(
            colonnes_langues, [("fr", "Français"), ("ar", "العربية"), ("en", "English")]
        ):
            with colonne:
                classe = "rtl" if code == "ar" else ""
                st.markdown(
                    f'<div class="panneau" style="padding:0.75rem 0.9rem; min-height:104px;">'
                    f'<div class="panneau-titre">{langue}</div>'
                    f'<div class="{classe}" style="font-size:0.9rem; color:var(--texte); line-height:1.5;">'
                    f'{triplet[code]}</div></div>',
                    unsafe_allow_html=True,
                )

        if st.button("Dérouler la démonstration", type="primary"):
            st.session_state["demo_lancee"] = theme_choisi

        if st.session_state["demo_lancee"] == theme_choisi:
            resume_lignes = []

            # Le second libellé est celui du tableau récapitulatif : un texte
            # arabe placé dans une cellule alignée à gauche s'y affiche à
            # l'envers. Les panneaux, eux, gardent le nom dans sa langue.
            for code, langue, libelle_tableau in [
                ("fr", "Français", "Français"),
                ("ar", "العربية", "Arabe"),
                ("en", "English", "Anglais"),
            ]:
                question = triplet[code]
                with st.spinner(f"Recherche en {langue}…"):
                    try:
                        duel = client.comparer(
                            question,
                            k=st.session_state["nb_resultats"],
                            moteurs=("semantique", "lexical"),
                            expliquer=True,
                        )
                    except client.ErreurAPI as erreur:
                        st.error(str(erreur))
                        break

                nb_semantique = len(duel["resultats"]["semantique"])
                nb_lexical = len(duel["resultats"]["lexical"])
                resume_lignes.append({
                    "Langue": libelle_tableau,
                    "Sémantique": nb_semantique,
                    "BM25": nb_lexical,
                    "Recouvrement": f"{duel['analyse']['recouvrement']:.0%}",
                })

                st.markdown("---")
                st.markdown(composants.rappel_requete(question), unsafe_allow_html=True)
                st.markdown(
                    composants.panneau(composants.markdown_leger(duel["verdict"]), titre=f"verdict — {langue}", variante=(
                        "alerte" if duel["analyse"].get("moteurs_muets") else "verdict"
                    )),
                    unsafe_allow_html=True,
                )

                gauche, droite = st.columns(2)
                for colonne, nom in ((gauche, "semantique"), (droite, "lexical")):
                    with colonne:
                        resultats = duel["resultats"][nom][:3]
                        st.markdown(composants.tete_colonne(nom, len(resultats)), unsafe_allow_html=True)
                        afficher_resultats({"resultats": resultats}, moteur=nom, compacte=True)

            if resume_lignes:
                st.markdown("---")
                st.markdown("#### Ce que la démonstration a montré")
                st.dataframe(resume_lignes, width="stretch", hide_index=True)
                st.markdown(
                    composants.panneau(
                        "Sur un corpus entièrement anglophone, la baseline lexicale ne "
                        "renvoie rien dès que la question change d'alphabet : aucun mot "
                        "arabe n'existe dans le corpus, donc aucun score n'est calculable. "
                        "Le moteur sémantique répond dans les trois langues, parce que les "
                        "trois formulations sont projetées dans le même espace vectoriel. "
                        "C'est la condition de validation n°7 du cahier des charges, "
                        "vérifiée en direct.",
                        titre="à dire au jury",
                        variante="verdict",
                    ),
                    unsafe_allow_html=True,
                )


# ---------------------------------------------------------------------------
# Onglet 4 — Évaluation
# ---------------------------------------------------------------------------

with onglet_eval:
    mesures = client.metriques() if disponible else None
    theme = theme_actif

    if not mesures:
        st.markdown(
            composants.etat_vide(
                "Aucune évaluation disponible.",
                "Lance <code>python scripts/4_evaluer.py</code> pour la produire.",
            ),
            unsafe_allow_html=True,
        )
    else:
        configuration = mesures.get("configuration", {})

        # Les mesures ont pu être produites sur un corpus différent de celui
        # actuellement chargé. Le signaler évite de présenter des chiffres qui
        # ne correspondent pas à l'index de la démonstration.
        nb_evalues = configuration.get("nb_documents")
        nb_charges = infos.get("nb_articles")
        if nb_evalues and nb_charges and nb_evalues != nb_charges:
            st.warning(
                f"Ces mesures ont été produites sur un corpus de "
                f"{composants.formater_nombre(nb_evalues)} articles, alors que l'index "
                f"actuellement chargé en contient {composants.formater_nombre(nb_charges)}. "
                "Relance `python scripts/4_evaluer.py` pour les mettre à jour."
            )

        st.markdown(
            composants.chiffres([
                (composants.formater_nombre(configuration.get("nb_documents", "?")), "articles évalués", "var(--texte)"),
                (composants.formater_nombre(configuration.get("nb_passages", "?")), "passages indexés", "var(--texte-doux)"),
                (str(configuration.get("dimension", "?")), "dimensions par vecteur", MOTEURS["semantique"]["couleur"]),
                (str(configuration.get("k", "?")), "résultats par requête (k)", "var(--texte-doux)"),
            ]),
            unsafe_allow_html=True,
        )

        # --- le graphique central : la cohérence multilingue ---
        if "coherence_multilingue" in mesures:
            st.markdown("#### Le résultat qui justifie le projet")
            st.markdown(
                "La même question posée en trois langues doit renvoyer les mêmes "
                "articles si l'espace vectoriel est réellement indépendant de la langue."
            )
            st.altair_chart(
                graphiques.coherence_multilingue(mesures["coherence_multilingue"], theme),
                width="stretch",
            )

            bm25 = mesures["coherence_multilingue"].get("bm25", {})
            sans_resultat = bm25.get("requetes_sans_resultat_ar", 0)
            total = bm25.get("nb_triplets", 0)
            if total:
                st.markdown(
                    composants.panneau(
                        f"BM25 ne renvoie <b>aucun résultat</b> sur {sans_resultat} des "
                        f"{total} requêtes arabes. Ce n'est pas un défaut de réglage : "
                        "aucun mot arabe n'apparaît dans un corpus anglophone, donc aucun "
                        "score n'est calculable. Sur ce terrain, les deux approches ne se "
                        "comparent pas — une seule fonctionne.",
                        titre="lecture",
                        variante="verdict",
                    ),
                    unsafe_allow_html=True,
                )

        # --- protocole titre vers résumé ---
        if "titre_vers_resume" in mesures:
            st.markdown("---")
            st.markdown("#### Protocole « titre vers résumé »")
            st.markdown(
                "Le titre d'un article sert de requête ; le bon résultat est l'article "
                "lui-même. Le titre n'étant pas indexé, BM25 ne peut pas gagner par "
                "simple correspondance exacte."
            )
            st.altair_chart(
                graphiques.qualite_classement(mesures["titre_vers_resume"], theme),
                width="stretch",
            )
            st.caption(
                "BM25 devance légèrement le moteur sémantique : c'est son terrain naturel. "
                "Un titre partage avec son résumé des termes techniques rares, et faire "
                "correspondre des termes rares est précisément ce que BM25 fait le mieux."
            )

        if mesures.get("stratification_lexicale"):
            st.altair_chart(
                graphiques.stratification(mesures["stratification_lexicale"], theme),
                width="stretch",
            )
            st.caption(
                "Même dans le tiers le plus difficile, la requête partage encore une "
                "large part de son vocabulaire avec le bon document : ce protocole ne "
                "descend jamais dans le régime où la correspondance de mots cesse de "
                "fonctionner. Il mesure du lexical, pas du sens."
            )

        if "requetes_appauvries" in mesures and "titre_vers_resume" in mesures:
            st.markdown("---")
            st.markdown("#### Requêtes appauvries")
            st.altair_chart(
                graphiques.degradation(
                    mesures["titre_vers_resume"], mesures["requetes_appauvries"], theme
                ),
                width="stretch",
            )
            appauvries = mesures["requetes_appauvries"]
            st.caption(
                f"Exemple de transformation : « {appauvries.get('exemple_avant', '')[:90]}… » "
                f"devient « {appauvries.get('exemple_apres', '')[:70]}… ». "
                "Les mots rares ne portaient pas seulement la signature lexicale, ils "
                "portaient le sujet : leur retrait dégrade le sens autant que le lexique."
            )

        # --- coût ---
        st.markdown("---")
        st.markdown("#### Coût")
        colonne_gauche, colonne_droite = st.columns(2)
        with colonne_gauche:
            if "latences" in mesures:
                st.altair_chart(graphiques.latences(mesures["latences"], theme), width="stretch")
        with colonne_droite:
            if mesures.get("comparaison_index"):
                st.altair_chart(
                    graphiques.compromis_index(mesures["comparaison_index"], theme),
                    width="stretch",
                )

        with st.expander("Voir les mesures détaillées"):
            st.json(mesures, expanded=False)


# ---------------------------------------------------------------------------
# Onglet 5 — Architecture
# ---------------------------------------------------------------------------

with onglet_archi:
    st.markdown("#### Chaîne d'indexation — hors ligne, une seule fois")
    st.markdown(
        '<div class="chaine">'
        '<div class="etape" style="--accent:var(--semantique)"><div class="numero">01</div>'
        '<div class="nom">Corpus arXiv</div><div class="quoi">résumés téléchargés par l\'API publique</div></div>'
        '<div class="fleche">→</div>'
        '<div class="etape" style="--accent:var(--semantique)"><div class="numero">02</div>'
        '<div class="nom">Prétraitement</div><div class="quoi">LaTeX simplifié, espaces normalisés, découpage en passages</div></div>'
        '<div class="fleche">→</div>'
        '<div class="etape" style="--accent:var(--semantique)"><div class="numero">03</div>'
        '<div class="nom">Embeddings</div><div class="quoi">multilingual-e5-small, préfixe <code>passage:</code></div></div>'
        '<div class="fleche">→</div>'
        '<div class="etape" style="--accent:var(--semantique)"><div class="numero">04</div>'
        '<div class="nom">Index FAISS</div><div class="quoi">vecteurs normalisés, produit scalaire = cosinus</div></div>'
        '</div>',
        unsafe_allow_html=True,
    )

    st.markdown("#### Chaîne de recherche — en ligne, à chaque question")
    st.markdown(
        '<div class="chaine">'
        '<div class="etape" style="--accent:var(--semantique-2)"><div class="numero">01</div>'
        '<div class="nom">Question</div><div class="quoi">français, arabe ou anglais</div></div>'
        '<div class="fleche">→</div>'
        '<div class="etape" style="--accent:var(--semantique-2)"><div class="numero">02</div>'
        '<div class="nom">Le <b>même</b> encodeur</div><div class="quoi">préfixe <code>query:</code> cette fois</div></div>'
        '<div class="fleche">→</div>'
        '<div class="etape" style="--accent:var(--semantique-2)"><div class="numero">03</div>'
        '<div class="nom">Plus proches voisins</div><div class="quoi">FAISS, quelques dixièmes de milliseconde</div></div>'
        '<div class="fleche">→</div>'
        '<div class="etape" style="--accent:var(--semantique-2)"><div class="numero">04</div>'
        '<div class="nom">Regroupement</div><div class="quoi">un article n\'apparaît qu\'une fois, à son meilleur score</div></div>'
        '</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        composants.panneau(
            "Le mot décisif de ces deux schémas est « même ». Indexer avec un modèle "
            "et chercher avec un autre place les deux ensembles de vecteurs dans des "
            "espaces différents : les résultats deviennent aléatoires, sans qu'aucune "
            "erreur ne s'affiche. C'est le piège numéro un du domaine.",
            titre="le point critique",
            variante="verdict",
        ),
        unsafe_allow_html=True,
    )

    st.markdown("#### Les trois moteurs")
    colonnes_moteurs = st.columns(3)
    descriptions = {
        "semantique": (
            "Encode la question et les documents dans un même espace de 384 dimensions, "
            "puis mesure des angles. Trouve un document sans partager un seul mot avec "
            "lui — y compris dans une autre langue."
        ),
        "lexical": (
            "Pondère les mots partagés : un terme rare compte plus qu'un terme fréquent, "
            "un document long est pénalisé. Rapide, gratuit, sans modèle. Renvoie une "
            "liste vide si aucun mot ne correspond."
        ),
        "hybride": (
            "Fusionne les deux classements par Reciprocal Rank Fusion, qui n'utilise que "
            "les rangs — un score BM25 et un cosinus n'étant pas comparables. Un document "
            "bien classé par les deux passe devant un document premier chez un seul."
        ),
    }
    for colonne, nom in zip(colonnes_moteurs, ("semantique", "lexical", "hybride")):
        with colonne:
            identite = MOTEURS[nom]
            st.markdown(
                f'<div class="panneau" style="border-left:3px solid {identite["couleur"]}; height:100%;">'
                f'<div style="font-size:1.4rem; color:{identite["couleur"]};">{identite["icone"]}</div>'
                f'<div style="font-weight:650; margin:0.3rem 0 0.1rem;">{identite["libelle"]}</div>'
                f'<div class="panneau-titre">{identite["sous_titre"]}</div>'
                f'<div style="font-size:0.83rem; line-height:1.6; color:var(--texte-doux);">'
                f'{descriptions[nom]}</div></div>',
                unsafe_allow_html=True,
            )

    st.markdown("#### Ce qui tourne derrière")
    st.dataframe(
        [
            {"Composant": "Modèle d'embeddings", "Choix": infos.get("modele", config.NOM_MODELE),
             "Rôle": "texte → 384 nombres, une centaine de langues"},
            {"Composant": "Index vectoriel", "Choix": f"FAISS {infos.get('type_index', config.TYPE_INDEX)}",
             "Rôle": "plus proches voisins exacts par produit scalaire"},
            {"Composant": "Baseline lexicale", "Choix": "rank-bm25 (BM25Okapi)",
             "Rôle": "point de comparaison, référence du domaine"},
            {"Composant": "Fusion", "Choix": "Reciprocal Rank Fusion (K = 60)",
             "Rôle": "combine deux classements sans normaliser les scores"},
            {"Composant": "API", "Choix": "FastAPI + Uvicorn",
             "Rôle": "index chargé une fois, servi à toutes les requêtes"},
            {"Composant": "Interface", "Choix": "Streamlit",
             "Rôle": "cette page — ne connaît que l'API"},
        ],
        width="stretch",
        hide_index=True,
    )
