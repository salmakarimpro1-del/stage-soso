"""
Tests des extensions : fusion hybride, filtres, explication, comparaison.

Comme `test_moteur.py`, ces tests ne chargent aucun modèle et n'ont besoin
d'aucun index : ils vérifient la logique, pas la qualité des résultats. Ils
tournent donc en moins d'une seconde et peuvent être lancés à chaque
modification.

    python -m pytest tests/ -v
"""

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import comparaison, filtres
from src.hybride import fusion_rrf
from src.resultats import regrouper_par_document
from src.surlignage import (
    decouper_en_phrases,
    expliquer_resultats,
    raccourcir_autour,
    surligner,
    taux_recouvrement,
    termes_partages,
)


def _resultat(id_doc: str, rang: int, score: float = 1.0, **extra) -> dict:
    """Un résultat minimal, tel que les moteurs en produisent."""
    return {
        "id_doc": id_doc, "rang": rang, "score": score,
        "titre": f"Titre {id_doc}", "extrait": f"extrait de {id_doc}",
        "auteurs": [], "categories": [], "date": "2025-06-01", "url": "",
        **extra,
    }


def _classement(*ids: str) -> list[dict]:
    return [_resultat(id_doc, rang) for rang, id_doc in enumerate(ids, start=1)]


# ---------------------------------------------------------------------------
# Fusion hybride (RRF)
# ---------------------------------------------------------------------------

def test_un_accord_entre_moteurs_bat_une_premiere_place_isolee():
    """
    Le comportement qui justifie la RRF.

    B est deuxième chez les deux moteurs, A est premier chez un seul et absent
    de l'autre. B doit passer devant : l'accord entre deux méthodes
    indépendantes est un signal de pertinence plus fort qu'un avis unique.
    """
    fusion = fusion_rrf({
        "semantique": _classement("A", "B"),
        "lexical": _classement("C", "B"),
    })

    assert fusion[0]["id_doc"] == "B"
    assert fusion[0]["rang"] == 1


def test_la_fusion_conserve_la_provenance():
    fusion = fusion_rrf({
        "semantique": _classement("A", "B"),
        "lexical": _classement("B", "A"),
    })
    par_document = {r["id_doc"]: r for r in fusion}

    assert set(par_document["A"]["sources"]) == {"semantique", "lexical"}
    assert par_document["A"]["rangs"] == {"semantique": 1, "lexical": 2}
    assert par_document["B"]["rangs"] == {"semantique": 2, "lexical": 1}


def test_un_moteur_muet_ne_casse_pas_la_fusion():
    """
    Le cas des requêtes arabes : BM25 ne renvoie rien.

    La fusion doit alors se réduire au classement du seul moteur qui répond,
    dans le même ordre — et surtout ne pas échouer.
    """
    fusion = fusion_rrf({
        "semantique": _classement("A", "B", "C"),
        "lexical": [],
    })

    assert [r["id_doc"] for r in fusion] == ["A", "B", "C"]
    assert [r["rang"] for r in fusion] == [1, 2, 3]
    assert fusion[0]["sources"] == ["semantique"]


def test_un_poids_nul_exclut_un_moteur():
    fusion = fusion_rrf(
        {"semantique": _classement("A"), "lexical": _classement("B")},
        poids={"lexical": 0.0},
    )
    assert [r["id_doc"] for r in fusion] == ["A"]


def test_la_fusion_respecte_le_nombre_demande():
    fusion = fusion_rrf({"semantique": _classement("A", "B", "C", "D")}, k=2)
    assert len(fusion) == 2


def test_le_score_expose_est_le_score_rrf():
    """
    L'API, l'interface et l'évaluation lisent tous la clé « score ».

    Le moteur hybride doit donc y placer son score de fusion, et non le
    cosinus recopié du moteur sémantique — sinon les résultats seraient
    triés selon une valeur qui n'est pas celle du classement.
    """
    fusion = fusion_rrf({"semantique": _classement("A", "B")})
    assert fusion[0]["score"] == pytest.approx(fusion[0]["score_rrf"])
    assert fusion[0]["score"] > fusion[1]["score"]


# ---------------------------------------------------------------------------
# Filtres sur métadonnées
# ---------------------------------------------------------------------------

def _passage(id_doc: str, categories: list[str], date: str, auteurs=None) -> dict:
    return {
        "id_doc": id_doc, "categories": categories, "date": date,
        "auteurs": auteurs or ["Ada Lovelace"], "titre": "T",
        "texte_affiche": "texte", "position": 0, "url": "",
    }


def test_aucun_critere_ne_construit_aucun_filtre():
    """None permet à l'appelant de sauter tout le sur-échantillonnage."""
    assert filtres.construire() is None
    assert filtres.construire(categories=[], annee_min=None) is None


def test_filtre_par_categorie():
    filtre = filtres.construire(categories=["cs.CR"])
    assert filtre(_passage("A", ["cs.CR", "cs.LG"], "2025-01-01"))
    assert not filtre(_passage("B", ["cs.CV"], "2025-01-01"))


def test_filtre_par_annee_bornes_incluses():
    filtre = filtres.construire(annee_min=2024, annee_max=2025)
    assert filtre(_passage("A", [], "2024-01-01"))
    assert filtre(_passage("B", [], "2025-12-31"))
    assert not filtre(_passage("C", [], "2023-12-31"))
    assert not filtre(_passage("D", [], "2026-01-01"))


def test_filtre_par_auteur_insensible_a_la_casse():
    filtre = filtres.construire(auteur="lovelace")
    assert filtre(_passage("A", [], "2025-01-01", auteurs=["Ada Lovelace"]))
    assert not filtre(_passage("B", [], "2025-01-01", auteurs=["Alan Turing"]))


def test_une_date_illisible_ne_fait_pas_tomber_la_recherche():
    assert filtres.extraire_annee("") is None
    assert filtres.extraire_annee("date inconnue") is None
    assert filtres.extraire_annee("2025-03-14T09:12:00Z") == 2025


def test_le_vivier_s_elargit_quand_un_filtre_est_actif():
    sans = filtres.taille_vivier(10, filtre_actif=False, multiplicateur_base=3)
    avec = filtres.taille_vivier(10, filtre_actif=True, multiplicateur_base=3)

    assert sans == 30
    assert avec > sans
    # Le plafond évite de parcourir tout l'index sur un k élevé.
    assert filtres.taille_vivier(100, True, 3) <= filtres.VIVIER_MAXIMUM


def test_l_inventaire_compte_des_articles_et_non_des_passages():
    """Un article découpé en trois passages ne doit compter qu'une fois."""
    passages = [
        _passage("A", ["cs.LG"], "2025-01-01"),
        _passage("A", ["cs.LG"], "2025-01-01"),
        _passage("B", ["cs.LG", "cs.CV"], "2024-01-01"),
    ]
    inventaire = filtres.inventorier(passages)
    comptes = {c["code"]: c["nb_articles"] for c in inventaire["categories"]}

    assert comptes["cs.LG"] == 2
    assert comptes["cs.CV"] == 1
    assert (inventaire["annee_min"], inventaire["annee_max"]) == (2024, 2025)


def test_le_filtre_s_applique_avant_la_troncature_a_k():
    """
    Un article écarté doit libérer sa place, pas laisser un trou.

    C'est toute la différence entre filtrer avant et après le classement :
    filtrer après renverrait ici un seul résultat.
    """
    passages = [
        _passage("A", ["cs.CV"], "2025-01-01"),
        _passage("B", ["cs.CR"], "2025-01-01"),
        _passage("C", ["cs.CR"], "2025-01-01"),
    ]
    filtre = filtres.construire(categories=["cs.CR"])
    resultats = regrouper_par_document([0.9, 0.8, 0.7], [0, 1, 2], passages, k=2, filtre=filtre)

    assert [r["id_doc"] for r in resultats] == ["B", "C"]
    assert [r["rang"] for r in resultats] == [1, 2]


# ---------------------------------------------------------------------------
# Explication des résultats
# ---------------------------------------------------------------------------

def test_decoupage_en_phrases():
    # Les phrases doivent dépasser LONGUEUR_MINIMALE_PHRASE, sinon elles sont
    # volontairement recollées à la précédente (voir le test suivant).
    phrases = decouper_en_phrases(
        "La première phrase du résumé introduit le sujet. "
        "La deuxième décrit la méthode employée. "
        "La troisième annonce les résultats obtenus."
    )
    assert len(phrases) == 3
    assert phrases[0] == "La première phrase du résumé introduit le sujet."


def test_un_fragment_trop_court_est_recolle_au_precedent():
    """« Fig. » isolé ne doit jamais être présenté comme la justification."""
    phrases = decouper_en_phrases("Une phrase suffisamment longue pour compter. Fig.")
    assert len(phrases) == 1
    assert phrases[0].endswith("Fig.")


def test_termes_partages_ignore_les_mots_vides():
    partages = termes_partages(
        "the detection of banking fraud",
        "This paper studies fraud in banking systems.",
    )
    assert "fraud" in partages
    assert "banking" in partages
    assert "the" not in partages and "of" not in partages


def test_aucun_terme_partage_entre_deux_alphabets():
    """Le cas qui démontre l'apport sémantique : pas un mot en commun."""
    assert termes_partages("كشف الاحتيال المصرفي", "banking fraud detection") == []
    assert taux_recouvrement("كشف الاحتيال المصرفي", "banking fraud detection") == 0.0


def test_surlignage_echappe_le_html_avant_de_baliser():
    """
    Un résumé arXiv contient des chevrons et des esperluettes.

    Les laisser passer casserait la mise en page, et ouvrirait une injection
    HTML dans l'interface.
    """
    rendu = surligner("<script>alert(1)</script> fraud", termes=["fraud"])
    assert "<script>" not in rendu
    assert "&lt;script&gt;" in rendu
    assert "<mark" in rendu


def test_surlignage_ne_marque_que_des_mots_entiers():
    """« al » ne doit pas être surligné à l'intérieur d'« evaluation »."""
    rendu = surligner("evaluation of the model", termes=["eval"])
    assert "<mark" not in rendu


def test_surlignage_de_la_phrase_cle():
    texte = "Première phrase. La phrase importante ici. Dernière phrase."
    rendu = surligner(texte, phrase="La phrase importante ici.")
    assert 'class="phrase-cle"' in rendu


def test_raccourcir_garde_la_phrase_cle_dans_la_fenetre():
    """
    Couper les 60 premiers caractères ferait disparaître précisément la
    phrase que l'on voulait montrer.
    """
    texte = "bla " * 60 + "PHRASE CIBLE. " + "bla " * 60
    extrait = raccourcir_autour(texte, "PHRASE CIBLE.", longueur=100)

    assert "PHRASE CIBLE." in extrait
    assert len(extrait) < len(texte)


class EncodeurFactice:
    """
    Encodeur de test : projette un texte sur deux dimensions selon qu'il
    contient ou non le mot « cible ». Aucun modèle n'est chargé.
    """

    def encoder_requete(self, texte: str) -> np.ndarray:
        return np.array([[1.0, 0.0]], dtype="float32")

    def encoder_documents(self, textes: list[str], barre: bool = False) -> np.ndarray:
        return np.array(
            [[1.0, 0.0] if "cible" in t else [0.0, 1.0] for t in textes],
            dtype="float32",
        )


def test_explication_designe_la_phrase_la_plus_proche():
    resultats = [
        _resultat("A", 1, extrait="Phrase sans rapport ici. La phrase cible est celle-ci.")
    ]
    expliquer_resultats("question", resultats, EncodeurFactice())

    assert resultats[0]["phrase_cle"] == "La phrase cible est celle-ci."
    assert resultats[0]["score_phrase"] == pytest.approx(1.0)


def test_l_explication_lexicale_couvre_tous_les_resultats():
    """
    La phrase clé coûte un appel au modèle, les mots partagés non.

    On plafonne donc la première, mais la seconde — qui porte le signal
    « aucun mot en commun » — doit rester calculée partout.
    """
    resultats = [_resultat(f"D{i}", i, extrait="Une phrase cible ici.") for i in range(1, 6)]
    expliquer_resultats("question", resultats, EncodeurFactice(), nb_maximum=2)

    assert all("sans_recouvrement_lexical" in r for r in resultats)
    assert sum("phrase_cle" in r for r in resultats) == 2


# ---------------------------------------------------------------------------
# Comparaison de deux classements
# ---------------------------------------------------------------------------

def test_analyse_des_exclusivites():
    analyse = comparaison.analyser({
        "semantique": _classement("A", "B", "C"),
        "lexical": _classement("B", "D", "E"),
    })

    assert analyse["nb_communs"] == 1
    assert [u["id_doc"] for u in analyse["uniques"]["semantique"]] == ["A", "C"]
    assert [u["id_doc"] for u in analyse["uniques"]["lexical"]] == ["D", "E"]
    # Le taux est arrondi à trois décimales pour l'affichage.
    assert analyse["recouvrement"] == pytest.approx(1 / 3, abs=1e-3)


def test_analyse_signale_un_moteur_muet():
    analyse = comparaison.analyser({
        "semantique": _classement("A", "B"),
        "lexical": [],
    })

    assert analyse["moteurs_muets"] == ["lexical"]
    assert "aucun résultat" in comparaison.verdict(analyse)


def test_analyse_mesure_le_deplacement_d_un_article():
    analyse = comparaison.analyser({
        "semantique": _classement("A", "B", "C"),
        "lexical": _classement("C", "B", "A"),
    })
    deplacements = {c["id_doc"]: c["deplacement"] for c in analyse["communs"]}

    assert deplacements["A"] == 2      # rang 1 puis rang 3
    assert deplacements["B"] == 0      # rang 2 dans les deux
    assert [c["id_doc"] for c in analyse["reclassements_notables"]] == []


def test_recouvrement_total_produit_le_bon_verdict():
    analyse = comparaison.analyser({
        "semantique": _classement("A", "B"),
        "lexical": _classement("A", "B"),
    })
    assert analyse["recouvrement"] == 1.0
    assert "mêmes articles" in comparaison.verdict(analyse)
