"""
Configuration centrale du moteur de recherche sémantique.

Tous les paramètres modifiables du projet sont regroupés ici : si tu veux
changer le modèle, la taille du corpus ou le type d'index, c'est le seul
fichier à toucher. Aucun autre module ne contient de valeur en dur.
"""

from pathlib import Path

# ---------------------------------------------------------------------------
# Chemins du projet
# ---------------------------------------------------------------------------

RACINE = Path(__file__).resolve().parent

DOSSIER_DONNEES = RACINE / "data"
DOSSIER_BRUT = DOSSIER_DONNEES / "brut"       # corpus téléchargé depuis arXiv
DOSSIER_INDEX = DOSSIER_DONNEES / "index"     # index FAISS + métadonnées
DOSSIER_EVAL = RACINE / "eval"                # jeux de requêtes d'évaluation
DOSSIER_RESULTATS = RACINE / "resultats"      # tableaux de résultats produits

FICHIER_CORPUS = DOSSIER_BRUT / "corpus_arxiv.jsonl"
FICHIER_INDEX = DOSSIER_INDEX / "index.faiss"
FICHIER_PASSAGES = DOSSIER_INDEX / "passages.json"
# Les vecteurs sont conservés à part : cela permet de reconstruire un index
# avec d'autres réglages (flat / ivf) sans ré-encoder tout le corpus.
FICHIER_VECTEURS = DOSSIER_INDEX / "vecteurs.npy"
FICHIER_BM25 = DOSSIER_INDEX / "bm25.pkl"
FICHIER_REQUETES_MULTI = DOSSIER_EVAL / "requetes_multilingues.json"

# ---------------------------------------------------------------------------
# Corpus : quels articles on télécharge depuis arXiv
# ---------------------------------------------------------------------------

# Catégories arXiv interrogées. cs.LG = machine learning, cs.CL = traitement
# du langage, cs.CV = vision, cs.CR = sécurité, cs.IR = recherche
# d'information, cs.NE = réseaux de neurones, stat.ML = statistiques.
CATEGORIES_ARXIV = [
    "cs.LG",
    "cs.CL",
    "cs.CV",
    "cs.AI",
    "cs.CR",
    "cs.IR",
    "cs.NE",
    "stat.ML",
]

# Nombre d'articles téléchargés par catégorie.
# 1250 x 8 catégories = 10 000 articles, soit environ 5 minutes de
# téléchargement. Monte à 6250 pour atteindre 50 000 articles (~25 min).
NB_DOCS_PAR_CATEGORIE = 1250

# L'API arXiv impose 3 secondes entre deux requêtes. Ne pas descendre plus bas.
DELAI_ENTRE_REQUETES = 3.0
TAILLE_PAGE_ARXIV = 200        # nombre de résultats par appel API
NB_TENTATIVES = 3              # relances en cas d'erreur réseau

# ---------------------------------------------------------------------------
# Modèle d'embeddings
# ---------------------------------------------------------------------------

# multilingual-e5-small : 118 M de paramètres, 384 dimensions, gère une
# centaine de langues dont le français et l'arabe. Choisi parce qu'il tourne
# confortablement sur un CPU sans carte graphique.
#
# Pour une machine plus puissante, remplacer par :
#   "intfloat/multilingual-e5-base"  (768 dimensions, environ 3x plus lent)
NOM_MODELE = "intfloat/multilingual-e5-small"
DIMENSION = 384

# La famille E5 exige des préfixes : le modèle a été entraîné avec eux et se
# dégrade nettement si on les oublie. Une requête et un document ne reçoivent
# volontairement PAS le même préfixe.
PREFIXE_REQUETE = "query: "
PREFIXE_DOCUMENT = "passage: "

# Nombre de textes encodés simultanément. Baisser à 16 si la mémoire sature.
TAILLE_LOT = 64

# ---------------------------------------------------------------------------
# Découpage des documents (chunking)
# ---------------------------------------------------------------------------

# Un résumé arXiv fait 150 à 250 mots et tient donc dans un seul morceau.
# Le découpage reste implémenté pour pouvoir indexer des textes longs
# (articles complets, PDF) sans changer une ligne du reste du code.
TAILLE_CHUNK_MOTS = 220
CHEVAUCHEMENT_MOTS = 40

# Faut-il coller le titre devant chaque passage avant de l'encoder ?
#
# ATTENTION, choix méthodologique important : l'évaluation automatique utilise
# le titre d'un article comme requête. Si le titre était aussi dans le texte
# indexé, BM25 le retrouverait par simple correspondance exacte et la
# comparaison entre les deux moteurs n'aurait plus aucun sens (on parle de
# fuite de données). On indexe donc le résumé seul, le titre restant une
# métadonnée d'affichage.
INCLURE_TITRE_DANS_INDEX = False

# ---------------------------------------------------------------------------
# Index FAISS
# ---------------------------------------------------------------------------

# "flat" : comparaison exhaustive, résultat exact. Parfait jusqu'à environ
#          un million de vecteurs, c'est la valeur par défaut.
# "ivf"  : les vecteurs sont pré-regroupés en clusters et seuls les clusters
#          les plus prometteurs sont fouillés. Plus rapide, mais approximatif.
TYPE_INDEX = "flat"

NB_CLUSTERS_IVF = 100   # nombre de quartiers construits
NB_SONDES_IVF = 10      # quartiers fouillés à chaque recherche

# ---------------------------------------------------------------------------
# Recherche
# ---------------------------------------------------------------------------

TOP_K = 10              # nombre de résultats renvoyés par défaut
MULTIPLICATEUR_PASSAGES = 3   # on récupère 3*k passages avant de regrouper
                              # par document, car plusieurs passages peuvent
                              # appartenir au même article

# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

HOTE_API = "127.0.0.1"
PORT_API = 8000
URL_API = f"http://{HOTE_API}:{PORT_API}"
