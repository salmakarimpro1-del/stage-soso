"""
Tests automatiques du projet.

Ces tests ne téléchargent aucun modèle et ne nécessitent pas d'index : ils
vérifient la logique du code, pas la qualité des résultats (celle-ci est
mesurée par scripts/4_evaluer.py).

Lancement :
    python -m pytest tests/ -v
"""

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.baseline_bm25 import tokeniser
from src.evaluation import ndcg_at_k, rang_du_document, recall_at_k, reciprocal_rank, recouvrement
from src.index_faiss import IndexVectoriel
from src.pretraitement import decouper_en_passages, nettoyer_texte, preparer_passages
from src.resultats import regrouper_par_document, resumer_extrait


# ---------------------------------------------------------------------------
# Prétraitement
# ---------------------------------------------------------------------------

def test_nettoyage_supprime_les_espaces_multiples():
    assert nettoyer_texte("un   texte\n\navec  des sauts") == "un texte avec des sauts"


def test_nettoyage_simplifie_le_latex():
    assert nettoyer_texte(r"un \textit{mot} important") == "un mot important"
    assert "$" not in nettoyer_texte(r"la valeur $x_{i}$ est nulle")


def test_nettoyage_accepte_le_vide():
    assert nettoyer_texte("") == ""


def test_texte_court_reste_en_un_seul_passage():
    texte = " ".join(["mot"] * 50)
    assert len(decouper_en_passages(texte, taille=100, chevauchement=20)) == 1


def test_texte_long_est_decoupe_avec_chevauchement():
    texte = " ".join(str(i) for i in range(100))
    passages = decouper_en_passages(texte, taille=40, chevauchement=10)

    assert len(passages) > 1
    # Le chevauchement garantit que la fin d'un passage réapparaît au début
    # du suivant : aucune idée n'est coupée nette.
    fin_premier = passages[0].split()[-10:]
    debut_second = passages[1].split()[:10]
    assert fin_premier == debut_second


def test_chevauchement_trop_grand_est_refuse():
    with pytest.raises(ValueError):
        decouper_en_passages("un texte", taille=10, chevauchement=10)


def test_preparation_relie_chaque_passage_a_son_document():
    corpus = [
        {"id": "2401.001", "titre": "Titre A", "resume": " ".join(["mot"] * 500)},
        {"id": "2401.002", "titre": "Titre B", "resume": "un résumé très court"},
    ]
    passages = preparer_passages(corpus)

    assert len(passages) > 2                       # le premier a été découpé
    assert {p["id_doc"] for p in passages} == {"2401.001", "2401.002"}
    # Les identifiants doivent suivre exactement la position dans la liste,
    # car c'est ce qui relie les vecteurs FAISS aux textes.
    assert [p["id_passage"] for p in passages] == list(range(len(passages)))


def test_document_sans_resume_est_ignore():
    assert preparer_passages([{"id": "x", "titre": "T", "resume": ""}]) == []


# ---------------------------------------------------------------------------
# Tokenisation multilingue
# ---------------------------------------------------------------------------

def test_tokenisation_gere_le_francais_et_l_arabe():
    assert tokeniser("Détection de FRAUDE !") == ["détection", "de", "fraude"]
    assert tokeniser("كشف الاحتيال") == ["كشف", "الاحتيال"]


# ---------------------------------------------------------------------------
# Index FAISS
# ---------------------------------------------------------------------------

def test_index_retrouve_le_vecteur_identique():
    générateur = np.random.default_rng(0)
    vecteurs = générateur.normal(size=(200, 16)).astype("float32")
    vecteurs /= np.linalg.norm(vecteurs, axis=1, keepdims=True)

    index = IndexVectoriel(dimension=16, type_index="flat")
    index.construire(vecteurs, verbeux=False)

    # En cherchant un vecteur du corpus, il doit se retrouver lui-même en tête
    # avec un score de 1 (cosinus d'un vecteur avec lui-même).
    scores, identifiants = index.rechercher(vecteurs[42:43], k=5)
    assert identifiants[0][0] == 42
    assert scores[0][0] == pytest.approx(1.0, abs=1e-4)


def test_index_refuse_une_mauvaise_dimension():
    index = IndexVectoriel(dimension=16, type_index="flat")
    with pytest.raises(ValueError):
        index.construire(np.zeros((10, 8), dtype="float32"), verbeux=False)


def test_index_sauvegarde_et_rechargement(tmp_path):
    générateur = np.random.default_rng(1)
    vecteurs = générateur.normal(size=(50, 8)).astype("float32")
    vecteurs /= np.linalg.norm(vecteurs, axis=1, keepdims=True)

    chemin = tmp_path / "index.faiss"
    index = IndexVectoriel(dimension=8, type_index="flat")
    index.construire(vecteurs, verbeux=False)
    index.sauvegarder(chemin)

    recharge = IndexVectoriel.charger(chemin)
    assert recharge.nb_vecteurs == 50

    avant = index.rechercher(vecteurs[:1], k=3)[1]
    apres = recharge.rechercher(vecteurs[:1], k=3)[1]
    assert (avant == apres).all()


# ---------------------------------------------------------------------------
# Regroupement des résultats
# ---------------------------------------------------------------------------

def _passage(identifiant: int, id_doc: str) -> dict:
    return {
        "id_passage": identifiant, "id_doc": id_doc, "position": 0,
        "texte_indexe": "texte", "texte_affiche": "texte", "titre": f"Titre {id_doc}",
        "auteurs": [], "categories": [], "date": "2024-01-01", "url": "",
    }


def test_les_passages_d_un_meme_article_sont_fusionnes():
    passages = [_passage(0, "A"), _passage(1, "A"), _passage(2, "B")]
    resultats = regrouper_par_document([0.9, 0.8, 0.7], [0, 1, 2], passages, k=10)

    assert len(resultats) == 2                    # A n'apparaît qu'une fois
    assert resultats[0]["id_doc"] == "A"
    assert resultats[0]["score"] == pytest.approx(0.9)   # son meilleur passage
    assert [r["rang"] for r in resultats] == [1, 2]


def test_les_identifiants_invalides_sont_ignores():
    passages = [_passage(0, "A")]
    resultats = regrouper_par_document([0.9, 0.5], [0, -1], passages, k=10)
    assert len(resultats) == 1


def test_extrait_raccourci_sans_couper_un_mot():
    resume = resumer_extrait("un texte assez long pour être coupé", longueur=12)
    assert resume.endswith("...")
    assert "coupé" not in resume


# ---------------------------------------------------------------------------
# Métriques d'évaluation
# ---------------------------------------------------------------------------

def test_rang_du_document():
    resultats = [{"id_doc": "A"}, {"id_doc": "B"}, {"id_doc": "C"}]
    assert rang_du_document(resultats, "A") == 1
    assert rang_du_document(resultats, "C") == 3
    assert rang_du_document(resultats, "Z") is None


def test_recall_et_mrr():
    assert recall_at_k(1, 10) == 1.0
    assert recall_at_k(11, 10) == 0.0
    assert recall_at_k(None, 10) == 0.0

    assert reciprocal_rank(1) == 1.0
    assert reciprocal_rank(4) == 0.25
    assert reciprocal_rank(None) == 0.0
    # Au-delà du rang k, le document ne compte plus (définition du MRR@k).
    assert reciprocal_rank(12, k=10) == 0.0
    assert reciprocal_rank(3, k=10) == pytest.approx(1 / 3)


def test_ndcg_decroit_avec_le_rang():
    assert ndcg_at_k(1, 10) == pytest.approx(1.0)
    assert ndcg_at_k(2, 10) > ndcg_at_k(5, 10) > 0
    assert ndcg_at_k(20, 10) == 0.0


def test_recouvrement_entre_deux_listes():
    assert recouvrement(["a", "b", "c"], ["a", "b", "c"]) == 1.0
    assert recouvrement(["a", "b"], ["c", "d"]) == 0.0
    assert recouvrement(["a", "b"], ["b", "z"]) == pytest.approx(0.5)
    assert recouvrement([], ["a"]) == 0.0
