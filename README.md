# Moteur de recherche sémantique multilingue

Un moteur qui retrouve des articles scientifiques à partir d'une question posée
en langage naturel — en français, en arabe ou en anglais — sur un corpus arXiv
entièrement anglophone.

La différence avec une recherche classique tient en un exemple réellement
produit par le moteur, sur un corpus de 8 520 articles :

> **Requête :** كشف الاحتيال المصرفي باستخدام التعلم الآلي
> *(« détection de la fraude bancaire par apprentissage automatique »)*
>
> **Premier résultat, score 0,837 :** *Shapley Value-Guided Adaptive Ensemble
> Learning for Explainable Financial Fraud Detection with U.S. Regulatory
> Compliance Validation*

Aucun caractère commun entre la question et l'article : ils ne partagent même
pas l'alphabet. Sur cette requête, la baseline par mots-clés ne renvoie
strictement rien — comme sur les dix-neuf autres requêtes arabes du jeu
d'évaluation.

---

## Les documents du projet

| Document | Ce qu'il contient |
|---|---|
| **README.md** (ce fichier) | installation, utilisation, choix techniques, résultats mesurés |
| [GUIDE_DU_CODE.md](GUIDE_DU_CODE.md) | le code expliqué fichier par fichier, dans l'ordre où la donnée le traverse |
| [plan_apprentissage.html](plan_apprentissage.html) | plan d'apprentissage en 9 modules pour maîtriser les technologies employées |
| [resultats/rapport_evaluation.md](resultats/rapport_evaluation.md) | tous les tableaux de mesures, régénérables |
| `export/*.pdf` | les mêmes documents en PDF (`python scripts/5_exporter_pdf.py`) |
| `lancer.bat` | installe et démarre tout le projet d'un double-clic (Windows) |

---

## Table des matières

1. [Comment ça marche](#1-comment-ça-marche)
2. [Installation](#2-installation)
3. [Utilisation en cinq commandes](#3-utilisation-en-cinq-commandes)
4. [Structure du projet](#4-structure-du-projet)
5. [Choix techniques et justifications](#5-choix-techniques-et-justifications)
6. [Méthodologie d'évaluation](#6-méthodologie-dévaluation)
7. [Résultats mesurés](#7-résultats-mesurés)
8. [Problèmes fréquents](#8-problèmes-fréquents)
9. [Pistes d'extension](#9-pistes-dextension)

---

## 1. Comment ça marche

### L'idée en une image mentale

Chaque ville a une latitude et une longitude : deux nombres qui encodent sa
position. Deux villes proches ont des coordonnées proches.

Ce projet fait la même chose avec le **sens** : chaque texte reçoit 384 nombres
(un *embedding*) calculés par un réseau de neurones, dans un espace où deux
textes qui veulent dire la même chose se retrouvent au même endroit — même
s'ils n'ont aucun mot en commun, même s'ils sont écrits dans des langues
différentes.

Chercher revient alors à une opération géométrique : calculer quels vecteurs de
documents sont les plus proches du vecteur de la question.

### Les deux phases du système

**Phase 1 — indexation** (hors ligne, une seule fois, quelques minutes)

```
articles arXiv → nettoyage → découpage en passages
              → Sentence-BERT → vecteurs → index FAISS écrit sur disque
```

**Phase 2 — recherche** (en ligne, à chaque requête, quelques millisecondes)

```
question → le MÊME Sentence-BERT → vecteur
        → FAISS trouve les plus proches voisins → articles classés
```

Le mot le plus important de ce schéma est « même ». Indexer avec un modèle et
chercher avec un autre produit des résultats aléatoires, sans aucun message
d'erreur : c'est le piège numéro un du domaine.

### Les briques

| Brique | Rôle | Pourquoi celle-ci |
|---|---|---|
| `multilingual-e5-small` | texte → 384 nombres | 100 langues dont l'arabe, tourne sur CPU |
| FAISS | trouver les vecteurs les plus proches | des millisecondes là où Python naïf prend des secondes |
| BM25 | moteur de comparaison par mots-clés | référence du domaine, sert de point de comparaison |
| FastAPI | exposer le moteur en service web | découple le moteur de l'interface, documentation automatique |
| Streamlit | interface de démonstration | une interface correcte en quelques dizaines de lignes |

---

## 2. Installation

Prérequis : Python 3.10 ou plus récent. Aucune carte graphique nécessaire.

### La voie courte : `lancer.bat`

Sous Windows, un double-clic sur **`lancer.bat`** suffit. Le script enchaîne
tout ce que décrivent les sections 2 et 3 : environnement virtuel, dépendances,
corpus, index, puis l'API et l'interface. Chaque étape déjà faite est sautée,
donc le premier lancement est long (de vingt minutes à une heure et demie, le
temps d'encoder le corpus) et les suivants prennent une vingtaine de secondes.

L'environnement virtuel est créé dans `%USERPROFILE%\.venvs\soso-stage`,
volontairement hors du dossier du projet : PyTorch pèse plusieurs Go, et un
projet rangé dans un dossier synchronisé y perdrait un temps considérable.

### La voie manuelle

```bash
python -m pip install -r requirements.txt
```

Environ 500 Mo de dépendances (PyTorch en représente l'essentiel). Au premier
lancement, le modèle télécharge encore 470 Mo, puis reste en cache.

Pour vérifier que tout est en place :

```bash
python -m pytest tests/ -v
```

---

## 3. Utilisation en cinq commandes

### Étape 1 — construire le corpus

```bash
python scripts/1_collecter.py
```

Télécharge 10 000 résumés d'articles arXiv (8 catégories informatique et
statistiques) via l'API publique, en respectant le délai de 3 secondes qu'elle
impose. Durée : environ 5 minutes.

Pour un test rapide : `python scripts/1_collecter.py --par-categorie 200`
Pour un corpus complet : `python scripts/1_collecter.py --par-categorie 6250`

### Étape 2 — construire les index

```bash
python scripts/2_indexer.py
```

Encode tous les passages et construit les deux index (sémantique et lexical).
Durée mesurée : 12 minutes sur CPU pour 8 520 articles (10 832 passages). À ne
relancer que si le corpus ou le modèle change.

### Étape 3 — chercher depuis le terminal

```bash
python scripts/3_chercher.py
```

Mode interactif. Pour comparer directement les deux moteurs sur une requête :

```bash
python scripts/3_chercher.py -q "détection de fraude bancaire" --comparer
```

### Étape 4 — évaluer

```bash
python scripts/4_evaluer.py
```

Produit `resultats/rapport_evaluation.md` avec tous les tableaux de mesures.

### Étape 5 — exporter la documentation en PDF (facultatif)

```bash
python scripts/5_exporter_pdf.py
```

Produit `export/dossier_technique.pdf` (README, guide du code et rapport
d'évaluation réunis) et `export/plan_apprentissage.pdf`. Le rendu passe par
Chrome ou Edge en mode sans interface : rien de plus à installer.

### L'interface graphique

Dans un premier terminal :

```bash
uvicorn api.main:application
```

La documentation interactive de l'API est alors sur <http://127.0.0.1:8000/docs>.

Dans un second terminal :

```bash
streamlit run ui/app.py
```

---

## 4. Structure du projet

```
.
├── config.py                  tous les réglages, seul fichier à modifier
├── requirements.txt
├── README.md                  installation, usage, résultats
├── GUIDE_DU_CODE.md           le code expliqué fichier par fichier
├── plan_apprentissage.html    plan d'apprentissage en 9 modules
├── lancer.bat                 lancement complet en un clic (Windows)
│
├── src/                       le cœur du moteur
│   ├── collecte.py            téléchargement depuis l'API arXiv
│   ├── pretraitement.py       nettoyage et découpage en passages
│   ├── embeddings.py          Sentence-BERT : texte → vecteurs
│   ├── index_faiss.py         construction et interrogation de l'index
│   ├── moteur.py              assemblage : indexer() et chercher()
│   ├── baseline_bm25.py       moteur lexical de comparaison
│   ├── resultats.py           regroupement des passages par article
│   └── evaluation.py          métriques et protocoles de mesure
│
├── scripts/                   les étapes, dans l'ordre d'exécution
│   ├── 1_collecter.py
│   ├── 2_indexer.py
│   ├── 3_chercher.py
│   ├── 4_evaluer.py
│   └── 5_exporter_pdf.py
│
├── api/main.py                service web FastAPI
├── ui/app.py                  interface Streamlit
├── eval/                      jeu de requêtes multilingues
├── tests/                     19 tests automatiques
├── data/                      corpus et index (non versionnés)
├── resultats/                 mesures produites par les scripts
└── export/                    documentation en PDF (non versionnée)
```

Le découpage suit une règle simple : chaque fichier de `src/` fait une seule
chose et ignore comment les autres fonctionnent. `embeddings.py` est le seul
module qui sait qu'un modèle de langue existe ; `index_faiss.py` est le seul qui
connaît FAISS. On peut donc remplacer l'un sans toucher à l'autre.

---

## 5. Choix techniques et justifications

### Le modèle : `intfloat/multilingual-e5-small`

Trois raisons.

**Le multilingue est structurel, pas décoratif.** Le modèle a été entraîné sur
des paires de phrases traduites : « fraud detection », « détection de fraude »
et « كشف الاحتيال » se retrouvent au même endroit de l'espace vectoriel. Ce
n'est pas de la traduction, c'est un espace partagé — d'où la possibilité de
chercher en français dans un corpus anglais.

**Il tient sur un CPU.** 118 millions de paramètres, 384 dimensions. Mesure
réelle sur un portable sans carte graphique (Intel Iris Xe) : 10 832 passages
encodés en 12 minutes, soit environ 15 passages par seconde, pour un index de
16 Mo. C'est l'étape la plus lente du projet, et elle n'est faite qu'une fois.

**Il est entraîné pour la recherche.** Beaucoup de modèles de phrases sont
optimisés pour mesurer la similarité entre deux phrases de même nature. E5 est
entraîné spécifiquement sur des paires question/document, ce qui est exactement
notre cas d'usage.

Contrepartie à connaître : la famille E5 exige les préfixes `query:` et
`passage:`. Les oublier dégrade nettement la qualité, sans provoquer la moindre
erreur visible. C'est géré dans `src/embeddings.py`.

### L'index : `IndexFlatIP` par défaut

Comparaison exhaustive, donc résultat exact. Sur 10 000 vecteurs, une recherche
prend environ une milliseconde : l'approximation n'apporterait rien.

L'index approximatif `IVFFlat` est également implémenté, et le script
d'évaluation mesure précisément ce que l'on gagne en vitesse et ce que l'on perd
en exhaustivité. C'est le compromis central de la recherche vectorielle à grande
échelle, et le mesurer vaut mieux que le citer.

Les vecteurs sont normalisés à une longueur de 1, ce qui rend le produit
scalaire égal à la similarité cosinus : on mesure ainsi un angle (le sens) et
non une longueur (la taille du texte).

### Le découpage en passages

Les résumés arXiv font 150 à 250 mots et tiennent dans un seul passage. Le
découpage avec chevauchement reste implémenté pour pouvoir indexer des documents
longs (articles complets, PDF) sans changer une ligne du reste du code.

Comme l'index contient des passages et non des articles, les résultats sont
regroupés par article en conservant le meilleur score de ses passages — sinon un
même article occuperait plusieurs places du classement.

---

## 6. Méthodologie d'évaluation

Une démonstration réussie peut toujours être une coïncidence. Trois protocoles
mesurent ce que les moteurs retrouvent réellement.

### Protocole 1 — titre vers résumé

Le titre d'un article tiré au hasard sert de requête ; le bon résultat est connu
d'avance, c'est l'article lui-même. On obtient ainsi 500 requêtes annotées sans
aucun travail manuel.

**Précaution indispensable :** le titre n'est pas indexé (voir
`INCLURE_TITRE_DANS_INDEX` dans `config.py`). S'il l'était, BM25 gagnerait par
simple correspondance exacte et la comparaison n'aurait plus aucun sens. C'est
une fuite de données classique, et l'éviter fait partie du travail.

Métriques : Recall@1, @5, @10, MRR et nDCG.

### Protocole 2 — cohérence multilingue

La même question est posée en français, en arabe et en anglais. Si l'espace
vectoriel est réellement indépendant de la langue, les trois formulations
doivent renvoyer approximativement les mêmes articles. On mesure la part
d'articles communs entre deux langues, sur 20 questions.

Ce protocole ne demande aucune annotation et attaque directement l'argument
central du projet. BM25 y obtient un score proche de zéro sur les requêtes
françaises et arabes — non par mauvais réglage, mais par impossibilité
structurelle.

### Protocole 3 — coût

Latence médiane et 95e centile, durée de construction, taille de l'index, et
comparaison entre index exact et index approximatif à différents niveaux de
fouille.

---

## 7. Résultats mesurés

Configuration : 8 520 articles, 10 832 passages, `multilingual-e5-small`
(384 dimensions), index exact, ordinateur portable sans carte graphique.
Tous les chiffres ci-dessous sont reproductibles avec
`python scripts/4_evaluer.py`.

### Requêtes monolingues — BM25 gagne

500 titres tirés au sort servent de requêtes ; le bon résultat est l'article
dont ils proviennent.

| Moteur | Recall@1 | Recall@10 | MRR@10 |
|---|---|---|---|
| Sémantique | 0,914 | 0,966 | 0,930 |
| BM25 | **0,922** | **0,988** | **0,946** |

Ce n'est pas un défaut d'implémentation : c'est le terrain de jeu naturel de
BM25. Un titre partage avec son résumé des termes techniques rares — un nom de
méthode, un acronyme — et faire correspondre des termes rares est précisément
ce que BM25 fait le mieux.

En répartissant les mêmes requêtes en trois groupes selon leur recouvrement
lexical, l'écart ne se referme jamais : même le tiers le plus difficile partage
encore 65 % de son vocabulaire avec le bon document. **Ce protocole ne descend
jamais dans le régime où la correspondance de mots cesse de fonctionner** — il
mesure du lexical, pas du sens. Le reconnaître vaut mieux que de présenter ses
chiffres comme une validation du moteur sémantique.

### Requêtes dégradées — le moteur sémantique résiste moins bien

Pour atteindre ce régime, les trois mots les plus rares de chaque titre ont été
retirés. L'hypothèse était que BM25, privé de sa signature lexicale, chuterait
davantage. C'est l'inverse qui se produit.

| Moteur | MRR@10 normal | MRR@10 appauvri | Variation |
|---|---|---|---|
| Sémantique | 0,930 | 0,578 | **−0,353** |
| BM25 | 0,946 | 0,677 | −0,269 |

L'exemple explique le résultat : *Discovering Conceptual Metaphors Across Topics
and Media Types* devient *conceptual across and media types*. Les mots rares
n'étaient pas seulement discriminants, ils portaient le sujet. Leur retrait
dégrade le sens autant que le lexique — et un modèle dense y est plus sensible,
parce qu'il compresse la requête entière, mots vides compris, dans un vecteur
unique. BM25 se contente d'ignorer les termes qui ne correspondent à rien.

### Requêtes multilingues — le moteur sémantique est seul à fonctionner

Vingt questions posées en français, en arabe et en anglais sur un corpus
entièrement anglophone. On mesure la part d'articles communs entre les
résultats de deux langues.

| Moteur | fr/en | ar/en | Requêtes arabes sans résultat |
|---|---|---|---|
| Sémantique | 0,450 | 0,130 | 0 / 20 |
| BM25 | 0,030 | 0,000 | **20 / 20** |

Voici l'apport réel du projet. BM25 ne renvoie rien du tout sur les vingt
requêtes arabes — non par mauvais réglage, mais parce qu'aucun mot arabe
n'existe dans le corpus. Le recouvrement de 0,45 en français doit se lire avec
prudence : sur un corpus aussi dense en sujets proches, deux formulations
peuvent renvoyer des articles différents et tous deux pertinents. Le
recouvrement varie d'ailleurs beaucoup selon le thème, de 0,80 pour la conduite
autonome à 0,10 pour le raisonnement des grands modèles de langue, où la
littérature est pléthorique.

Le score arabe (0,13) est nettement plus faible que le français (0,45) : la
qualité multilingue de `e5-small` n'est pas uniforme entre les langues. C'est
une limite à énoncer, et un levier à tester — `multilingual-e5-base` devrait
réduire cet écart.

### Latence et index

| Moteur | Médiane | p95 |
|---|---|---|
| Sémantique | 17,2 ms | 22,3 ms |
| BM25 | 37,0 ms | 67,2 ms |

Le temps du moteur sémantique est presque entièrement consacré à l'encodage de
la requête ; la recherche FAISS elle-même ne coûte que 0,1 ms.

| Index | nprobe | ms / requête | Rappel vs exact |
|---|---|---|---|
| flat (exact) | — | 0,108 | 1,000 |
| ivf | 1 | 0,007 | 0,309 |
| ivf | 10 | 0,013 | 0,738 |
| ivf | 20 | 0,022 | 0,859 |

À 10 832 vecteurs, l'index approximatif fait perdre 14 % de rappel pour gagner
un dixième de milliseconde sur une requête qui en prend 17. **L'approximation
ne se justifie pas à cette échelle** — il faut la garder pour le jour où le
corpus atteindra le million de documents.

### Ce qu'il faut en conclure

La thèse défendable de ce projet n'est pas « le sémantique bat le lexical ».
Les mesures disent autre chose, de plus solide :

> Là où les mots se recouvrent, BM25 reste légèrement meilleur, gratuit et
> instantané. Là où ils ne se recouvrent pas — autre langue, autre vocabulaire —
> le moteur sémantique est le seul à fonctionner, tandis que BM25 ne renvoie
> rien.

C'est exactement pour cette raison que la recherche hybride, qui combine les
deux classements, est devenue le standard en production. Elle n'est pas un
bonus du projet : elle en est la conclusion logique.

---

## 8. Problèmes fréquents

**« Corpus introuvable »** — lancer `python scripts/1_collecter.py` d'abord.
Les scripts sont numérotés dans l'ordre où ils doivent être exécutés.

**« Index et passages désynchronisés »** — le corpus a changé sans que l'index
soit reconstruit. Relancer `python scripts/2_indexer.py`.

**Le premier lancement est très lent** — c'est le téléchargement du modèle
(470 Mo). Les fois suivantes, le chargement prend deux à trois secondes.

**L'interface affiche « API injoignable »** — l'API doit tourner dans un autre
terminal : `uvicorn api.main:application`.

**Manque de mémoire pendant l'indexation** — baisser `TAILLE_LOT` à 16 dans
`config.py`.

**Des résultats incohérents après avoir changé de modèle** — l'index a été
construit avec l'ancien modèle. Toujours reconstruire l'index après avoir
modifié `NOM_MODELE`.

---

## 9. Pistes d'extension

Par ordre de rapport qualité/effort :

1. **Recherche hybride** — fusionner les classements sémantique et BM25 par
   Reciprocal Rank Fusion. Souvent meilleur que chacun pris séparément, et les
   deux moteurs sont déjà en place.
2. **Reranking** — repasser les 50 premiers résultats dans un cross-encoder, qui
   lit la requête et le document ensemble au lieu de comparer deux vecteurs
   calculés séparément. Gain net de précision, coût en latence.
3. **Filtres sur métadonnées** — restreindre par catégorie arXiv, par date, par
   auteur. Les métadonnées sont déjà stockées avec chaque passage.
4. **Réponse générée** — brancher un modèle de langue sur les résultats pour
   produire une synthèse citant ses sources (RAG).
5. **Passage à l'échelle** — indexer 500 000 articles, mesurer où l'index exact
   cesse d'être tenable et à partir de quand l'approximation devient nécessaire.
