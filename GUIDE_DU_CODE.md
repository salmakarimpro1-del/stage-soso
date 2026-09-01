# Guide du code

Ce document suit une donnée depuis l'API d'arXiv jusqu'à l'écran, en passant par
chaque fichier dans l'ordre où il intervient. Il explique **ce que fait chaque
morceau de code et pourquoi il est écrit ainsi**.

Il complète les deux autres documents sans les répéter :

| Document | Répond à la question |
|---|---|
| [README.md](README.md) | Comment j'installe et j'utilise le projet ? |
| **GUIDE_DU_CODE.md** (ce fichier) | Comment le code fonctionne, ligne par ligne ? |
| [plan_apprentissage.html](plan_apprentissage.html) | Comment j'apprends les technologies employées ? |

---

## Le chemin d'une donnée

Tout le projet tient dans ce trajet. Chaque flèche correspond à un fichier.

```
API arXiv
   │  src/collecte.py          télécharge et écrit du JSONL
   ▼
data/brut/corpus_arxiv.jsonl
   │  src/pretraitement.py     nettoie et découpe en passages
   ▼
liste de passages
   │  src/embeddings.py        transforme chaque passage en 384 nombres
   ▼
tableau de vecteurs
   │  src/index_faiss.py       range les vecteurs pour la recherche rapide
   ▼
data/index/index.faiss                        ← fin de la phase hors ligne
   ┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄
question de l'utilisateur                     ← début de la phase en ligne
   │  src/embeddings.py        le MÊME modèle, préfixe différent
   ▼
un vecteur
   │  src/index_faiss.py       trouve les plus proches voisins
   ▼
identifiants de passages
   │  src/resultats.py         regroupe les passages par article
   │                           (et applique les filtres de src/filtres.py)
   ▼
liste d'articles classés
   │  src/surlignage.py        ajoute la phrase clé et les mots partagés
   ▼
liste d'articles justifiés
   │  api/main.py              expose le tout en service web
   ▼
ui/                            affiche
```

Quatre fichiers vivent en dehors de ce trajet, chacun pour une raison précise :

| Fichier | Pourquoi il est à part |
|---|---|
| `src/baseline_bm25.py` | second moteur, parcourt le même chemin en parallèle |
| `src/hybride.py` | ne cherche rien lui-même : il fusionne les classements des deux autres |
| `src/comparaison.py` | ne classe pas, il analyse deux classements déjà produits |
| `src/evaluation.py` | mesure les trois moteurs, hors ligne |

---

## 0. `config.py` — le tableau de bord

**Rôle.** Rassembler tout ce qui se règle. Aucun autre fichier ne contient de
valeur en dur : si un nombre apparaît ailleurs dans le code, c'est un bug de
conception.

**Pourquoi c'est important.** Quand on veut tester une idée — un autre modèle,
des passages plus courts, un index approché — on ne veut pas chercher la valeur
dans sept fichiers. Un seul endroit, une seule modification, on relance.

**Les réglages qui changent vraiment quelque chose :**

| Réglage | Effet si tu le modifies |
|---|---|
| `NOM_MODELE` | change la qualité et la vitesse — **impose de tout réindexer** |
| `TAILLE_CHUNK_MOTS` | passages plus courts = plus précis mais moins de contexte |
| `TYPE_INDEX` | `flat` exact, `ivf` approché mais plus rapide à grande échelle |
| `INCLURE_TITRE_DANS_INDEX` | à `True`, fausse l'évaluation (voir étape 8) |
| `TAILLE_LOT` | baisse-le à 16 si la mémoire sature pendant l'encodage |

---

## 1. `src/collecte.py` — aller chercher les données

**Rôle.** Interroger l'API publique d'arXiv et écrire un fichier JSONL.

### Les fonctions, dans l'ordre

`_texte(element, chemin)` lit le texte d'une balise XML, ou renvoie une chaîne
vide si elle manque. Le tiret bas au début du nom signale par convention une
fonction interne, qui n'a pas vocation à être appelée depuis l'extérieur.

`_analyser_entree(entree)` transforme une balise `<entry>` du XML en
dictionnaire Python. Deux détails :

- l'identifiant arrive sous la forme `http://arxiv.org/abs/2401.12345v1` ; on ne
  garde que `2401.12345`, sans le numéro de version, pour que deux versions du
  même article ne comptent pas comme deux articles ;
- la fonction renvoie `None` si le titre ou le résumé manque, et l'appelant
  filtre ces valeurs. Rejeter tôt une donnée incomplète évite de la traîner
  jusqu'à l'index.

`interroger_arxiv(categorie, debut, nombre)` récupère une page de résultats. Le
`for tentative in range(...)` implémente une **relance avec attente croissante** :
en cas d'erreur réseau, on patiente de plus en plus longtemps avant de
réessayer. Sans cela, une coupure de trois secondes ferait échouer une collecte
de vingt minutes.

`collecter(...)` orchestre : elle boucle sur les catégories, pagine, dédoublonne
via l'ensemble `vus`, et écrit au fur et à mesure. **Le fichier s'écrit ligne
par ligne, pas à la fin** : si la collecte s'interrompt, ce qui a été téléchargé
est conservé.

`charger_corpus(fichier)` relit le JSONL. Elle lève une erreur explicite qui
indique la commande à lancer, plutôt qu'un `FileNotFoundError` brut.

### Le format JSONL

Un objet JSON par ligne, sans tableau englobant. On peut lire le fichier
ligne par ligne sans le charger entièrement, et l'inspecter avec un simple
éditeur de texte. Un tableau JSON classique obligerait à tout charger d'un coup.

---

## 2. `src/pretraitement.py` — préparer le texte

**Rôle.** Nettoyer, puis découper en passages.

`nettoyer_texte(texte)` applique trois expressions régulières : les commandes
LaTeX (`\textit{mot}` devient `mot`), les formules mathématiques entre `$`
(remplacées par une espace), les espaces multiples (réduits à un). On ne nettoie
volontairement pas plus : un résumé scientifique privé de ses termes techniques
n'a plus de sens.

`decouper_en_passages(texte, taille, chevauchement)` fait glisser une fenêtre
de mots. Le pas vaut `taille - chevauchement`, ce qui produit des passages qui
se recouvrent. **Pourquoi ce recouvrement ?** Si une phrase importante tombe
pile sur une frontière, elle serait coupée en deux et perdrait son sens dans les
deux passages. Avec le chevauchement, elle apparaît entière dans l'un des deux.

`preparer_passages(corpus)` produit la liste finale. Deux points méritent
attention.

**Le lien passage → document.** Chaque passage garde son `id_doc`. C'est ce qui
permettra, à l'étape 6, de ne pas afficher trois fois le même article.

**La position dans la liste est l'identifiant.** Le passage numéro 42 de la
liste sera le vecteur numéro 42 dans FAISS. FAISS ne stocke que des vecteurs et
des entiers : il ne connaît aucun texte. C'est cette correspondance de position
qui relie les deux — et c'est pourquoi `moteur.py` vérifie au chargement que
l'index et la liste ont exactement la même longueur.

---

## 3. `src/embeddings.py` — du texte vers des nombres

**Rôle.** Encapsuler Sentence-BERT. C'est le seul fichier du projet qui sait
qu'un modèle de langue existe.

`Encodeur.modele` est une **propriété avec chargement paresseux** : le modèle
n'est chargé qu'à la première utilisation, pas à la construction de l'objet. On
peut donc créer un `Encodeur` sans payer les quinze secondes de chargement.
C'est le bon comportement pour un script — et c'est justement pourquoi l'API
appelle explicitement `prechauffer()` au démarrage, pour que ce coût ne tombe
pas sur le premier utilisateur.

`_encoder(textes, prefixe, barre)` fait le travail. Deux paramètres décident de
la justesse du résultat.

**`prefixe`.** Le modèle E5 a été entraîné avec `query:` devant les questions et
`passage:` devant les documents. Il distingue ainsi deux rôles qui n'occupent
pas la même géométrie dans l'espace. **Les oublier dégrade nettement la qualité
sans provoquer la moindre erreur** — c'est le bug le plus difficile à repérer du
projet.

**`normalize_embeddings=True`.** Chaque vecteur est ramené à une longueur de 1.
Le produit scalaire entre deux vecteurs normalisés vaut alors exactement leur
cosinus. On mesure ainsi un angle — le sens — et non une longueur — la taille du
texte. Sans cela, les textes longs obtiendraient mécaniquement de meilleurs
scores.

Enfin, `np.ascontiguousarray(... astype("float32"))` : FAISS n'accepte que du
`float32` rangé de façon contiguë en mémoire. Lui passer autre chose provoque
soit une erreur, soit des résultats silencieusement faux.

---

## 4. `src/index_faiss.py` — ranger les vecteurs

**Rôle.** Construire, interroger, sauvegarder l'index.

`construire(vecteurs)` crée l'une des deux structures.

**`IndexFlatIP`** compare la requête à tous les vecteurs. Le résultat est exact.
Sur 10 832 vecteurs, une recherche prend 0,1 milliseconde. `IP` signifie *inner
product* : comme nos vecteurs sont normalisés, ce produit scalaire est le
cosinus.

**`IndexIVFFlat`** regroupe d'abord les vecteurs en quartiers, puis ne fouille
que les plus prometteurs. Il faut donc un entraînement (`train`) avant d'insérer
les données — étape absente de l'index exact. Le calcul
`min(NB_CLUSTERS_IVF, nb_vecteurs // 39)` respecte la règle de FAISS, qui
demande environ 39 vecteurs d'entraînement par quartier ; sans cette précaution,
un petit corpus provoque un avertissement et un index de mauvaise qualité.

`rechercher(vecteurs, k)` renvoie deux tableaux : les scores et les
identifiants. **Un identifiant vaut `-1` quand FAISS n'a pas trouvé assez de
voisins** ; l'étape 6 filtre ces valeurs, faute de quoi on lirait `passages[-1]`,
c'est-à-dire le dernier passage du corpus, sans aucun rapport.

`sauvegarder` / `charger` écrivent l'index sur disque. Sans cette persistance,
il faudrait réencoder tout le corpus à chaque démarrage : douze minutes d'attente
avant la première recherche.

---

## 5. `src/moteur.py` — l'assemblage

**Rôle.** La classe que tout le reste utilise. Elle expose deux méthodes qui
correspondent exactement aux deux phases du système.

### `indexer(corpus)` — la phase hors ligne

Enchaîne : préparation des passages → encodage → construction de l'index →
sauvegarde. Elle renvoie un dictionnaire de statistiques (durées, volumes) qui
finit dans `resultats/statistiques_indexation.json` — ces chiffres sont
directement utilisables dans un rapport.

`_sauvegarder` écrit quatre fichiers. Le troisième, `vecteurs.npy`, mérite une
explication : conserver les vecteurs bruts permet de reconstruire un index avec
d'autres réglages **sans réencoder le corpus**. C'est ce qui rend le banc
d'essai « index exact contre index approché » quasi instantané au lieu de coûter
douze minutes par variante.

### `charger()` — reprendre le travail déjà fait

Relit l'index et la table des passages, puis **vérifie que les deux ont la même
longueur**. Cette vérification attrape le cas où l'on a modifié le corpus sans
reconstruire l'index : sans elle, le moteur renverrait des articles qui ne
correspondent pas aux vecteurs trouvés, sans jamais planter.

### `chercher(requete, k)` — la phase en ligne

Trois lignes utiles :

```python
vecteur = self.encodeur.encoder_requete(requete)
scores, identifiants = self.index.rechercher(vecteur, k * MULTIPLICATEUR_PASSAGES)
return regrouper_par_document(scores[0], identifiants[0], self.passages, k)
```

On demande **trois fois plus de passages que d'articles voulus**, parce que
plusieurs passages peuvent appartenir au même article : après regroupement, il
en resterait moins de dix si l'on n'en demandait que dix.

`chercher_lot(requetes, k)` fait la même chose pour plusieurs requêtes à la
fois. Encoder 500 requêtes d'un coup est nettement plus rapide que 500 appels
successifs, car le modèle exploite mieux le processeur. C'est ce que
l'évaluation utilise.

---

## 6. `src/resultats.py` — des passages aux articles

**Rôle.** Une seule fonction, mais elle décide de ce que voit l'utilisateur.

`regrouper_par_document(scores, identifiants, passages, k)` parcourt les
passages trouvés et ne garde, pour chaque article, que **son meilleur passage**.
C'est la stratégie dite *max pooling*.

Sans elle, un article découpé en trois passages tous pertinents occuperait trois
des dix places du classement, et l'utilisateur verrait sept articles au lieu de
dix.

Cette fonction est **partagée par le moteur sémantique et par BM25**. Ce n'est
pas un détail d'organisation : cela garantit que les deux moteurs sont comparés
à traitement identique. Si chacun regroupait ses résultats à sa façon,
l'évaluation mesurerait aussi la différence entre les deux regroupements.

---

## 7. `src/baseline_bm25.py` — le point de comparaison

**Rôle.** Un moteur par mots-clés, exposant exactement la même interface que le
moteur sémantique — mêmes noms de méthodes, même format de sortie. C'est ce qui
permet à l'évaluation de traiter les deux sans savoir lequel elle manipule.

**Pourquoi implémenter un moteur « à l'ancienne » dans un projet sur la
recherche sémantique ?** Parce que sans point de comparaison, « notre moteur
donne de bons résultats » n'a aucune valeur. Et parce que les mesures ont montré
que BM25 gagne sur les requêtes anglaises : sans lui, ce projet aurait conclu
l'inverse de la vérité.

`tokeniser(texte)` découpe sur `\w+` en minuscules. `\w` couvre en Python
l'alphabet latin accentué **et** l'alphabet arabe, ce qui permet d'utiliser le
même découpage pour les trois langues du projet.

Dans `chercher`, la ligne à comprendre :

```python
indices = np.argpartition(-scores, nb_a_prendre - 1)[:nb_a_prendre]
```

`argpartition` isole les trente meilleurs scores **sans trier les 10 800
autres**, puis on ne trie que ce petit sous-ensemble. La première version du
code triait tout le tableau et prenait 51 ms par requête, contre 17 ms pour le
moteur sémantique — un écart entièrement dû à une paresse d'implémentation, pas
à la méthode. Corriger cela était nécessaire pour que la comparaison des
latences veuille dire quelque chose.

---

## 8. `src/evaluation.py` — mesurer

**Rôle.** Les métriques et les cinq protocoles. C'est le fichier qui transforme
une démonstration en travail défendable.

### Les métriques

`rang_du_document` trouve la position du bon document, ou `None` s'il est
absent. Les trois métriques en découlent :

- `recall_at_k(rang, k)` : 1 si le bon document est dans les k premiers, sinon 0.
- `reciprocal_rank(rang, k)` : `1/rang`. Être premier vaut 1, deuxième 0,5.
  Moyennée, cette valeur donne le MRR — la métrique de référence quand il n'y a
  qu'un seul bon document.
- `ndcg_at_k(rang, k)` : `1 / log2(rang + 1)`. Le gain décroît
  logarithmiquement, ce qui traduit qu'un utilisateur regarde surtout le haut de
  la liste.

### Protocole 1 — titre vers résumé

`construire_requetes_titres` tire des articles au hasard et utilise leur titre
comme requête : le bon résultat est connu d'avance. On obtient 500 requêtes
annotées sans travail manuel. La graine aléatoire est fixe, donc les résultats
sont reproductibles à l'identique.

**La précaution qui compte.** Le titre n'est pas indexé (`INCLURE_TITRE_DANS_INDEX
= False`). S'il l'était, BM25 le retrouverait par correspondance exacte et
gagnerait pour une raison qui n'a rien à voir avec sa qualité. C'est une fuite
de données, et l'éviter fait partie du travail scientifique.

### Protocole 1 bis — stratification

`stratifier_par_recouvrement` répartit les mêmes requêtes en trois groupes selon
la part de leurs mots présents dans le document attendu. Résultat mesuré : même
le tiers le plus difficile partage encore 65 % de son vocabulaire. **Ce
protocole n'atteint donc jamais le régime où le lexical échoue** — le constater
et le dire vaut mieux que présenter ses chiffres comme une validation.

### Protocole 1 ter — requêtes appauvries

`construire_requetes_appauvries` retire de chaque titre ses trois mots les plus
rares dans le corpus. L'hypothèse était que BM25, privé de sa signature
lexicale, chuterait davantage. **C'est l'inverse qui s'est produit** : le moteur
sémantique perd 0,353 de MRR contre 0,269 pour BM25. Les mots rares ne portaient
pas seulement la discrimination lexicale, ils portaient le sujet.

### Protocole 2 — cohérence multilingue

`evaluer_coherence_multilingue` pose la même question en trois langues et mesure
la part de résultats communs. Aucune annotation n'est nécessaire, et la mesure
attaque directement l'argument central du projet. C'est le seul protocole où le
moteur sémantique écrase BM25 — qui ne renvoie rien du tout sur les vingt
requêtes arabes.

### Protocole 3 — latence et index

`mesurer_latences` chronomètre des recherches une par une et rapporte la médiane
et le 95e centile plutôt que la moyenne, convention pour un service en ligne :
la moyenne masque les cas lents.

`comparer_types_index` prend l'index exact comme référence de vérité et mesure
quelle part de ses bons voisins l'index approché retrouve, à différents niveaux
de fouille.

---

## 9. `api/main.py` — exposer le moteur

**Rôle.** Transformer une bibliothèque Python en service web.

`cycle_de_vie` est un **gestionnaire de contexte asynchrone** enregistré comme
`lifespan` : ce qui précède le `yield` s'exécute au démarrage, ce qui suit à
l'arrêt. C'est là que les index sont chargés, **une seule fois pour toute la
durée de vie du serveur**. Charger dans la route ferait payer le chargement à
chaque requête.

C'est aussi là qu'on appelle `prechauffer()`. Sans cet appel, le modèle se
chargerait paresseusement à la première recherche : le tout premier utilisateur
attendrait quinze secondes — comportement mesuré, puis corrigé.

Les classes `Resultat`, `ReponseRecherche` et `DemandeRecherche` sont des
**modèles Pydantic**. Elles servent trois usages à la fois : valider les entrées,
formater les sorties, et générer la documentation interactive de `/docs`. Écrire
le schéma une fois suffit.

`_chercher` contient la logique commune aux routes GET et POST : on l'écrit une
fois et les deux routes l'appellent.

**Les routes, et ce qu'elles servent à autre chose qu'à chercher :**

| Route | Ce qu'elle apporte |
|---|---|
| `/recherche` | un moteur, k résultats, filtres et explications facultatives |
| `/comparer` | plusieurs moteurs d'un coup, **plus l'analyse de leurs écarts** |
| `/facettes` | les catégories et années réellement présentes dans l'index |
| `/exemples` | le jeu de questions multilingues, lu depuis `eval/` |
| `/metriques` | le fichier produit par `scripts/4_evaluer.py`, servi tel quel |

Deux choix méritent d'être signalés.

`/facettes` est calculée **une fois au démarrage**, pas à chaque appel : c'est
un parcours de tout l'index. Elle permet à l'interface de ne proposer que des
filtres qui ont des résultats — proposer une catégorie vide serait une impasse.

`/metriques` **ne recalcule jamais rien**. Elle se contente de servir le fichier
d'évaluation. Un graphique qui recalculerait ses chiffres à l'affichage pourrait
montrer autre chose que le rapport écrit, et c'est exactement le genre d'écart
qu'un jury repère.

---

## 10. `src/hybride.py` — faire voter les deux moteurs

**Rôle.** Fusionner les classements du moteur sémantique et de BM25 en un seul.

**Le problème à résoudre.** Un score BM25 vaut entre 0 et 40, sans borne haute.
Un cosinus vaut entre −1 et 1. Les additionner reviendrait à laisser BM25
décider seul. Normaliser les scores ne marche pas non plus : la normalisation
dépendrait du lot renvoyé, donc de la requête, et deux requêtes ne seraient
plus comparables.

**La solution.** La *Reciprocal Rank Fusion* n'utilise que les **rangs**, qui
sont dans la même unité par construction :

```python
score_rrf = somme sur chaque moteur de  poids / (60 + rang)
```

Un document deuxième chez les deux moteurs passe ainsi devant un document
premier chez un seul. C'est voulu : l'accord entre deux méthodes indépendantes
vaut mieux qu'un avis unique.

**Deux détails d'implémentation qui comptent :**

- `PROFONDEUR_FUSION = 50` — on demande cinquante candidats à chaque moteur
  avant de fusionner, pas dix. Fusionner seulement les dix premiers perdrait
  les documents classés quinzièmes par les deux, qui sont précisément ceux que
  la fusion sait faire remonter.
- **Le score n'est pas arrondi.** Les scores RRF valent quelques centièmes et
  se distinguent à la cinquième décimale. Un arrondi placé dans le moteur
  rendrait des documents artificiellement ex æquo ; c'est à l'affichage de
  choisir son format.

`MoteurHybride` expose `chercher` et `chercher_lot` avec la même signature que
les deux autres moteurs. Conséquence : l'API, l'interface et le script
d'évaluation l'utilisent sans une seule ligne de code spécifique.

---

## 11. `src/filtres.py` — restreindre sans casser le classement

**Rôle.** Filtrer par catégorie arXiv, par année, par auteur.

**Le piège.** Filtrer les dix premiers résultats est faux. Si aucun des dix ne
relève de la catégorie demandée, la recherche ne renvoie rien — alors que le
corpus contient peut-être cent articles pertinents un peu plus loin.

**L'ordre correct** est donc : demander un vivier vingt fois plus large,
écarter, puis garder les k premiers survivants. C'est ce que fait
`taille_vivier()`, et le filtre lui-même s'applique dans
`regrouper_par_document` — donc pour les trois moteurs à l'identique. Un filtre
qui ne s'appliquerait qu'à l'un d'eux invaliderait toute comparaison.

Limite à connaître et à énoncer : sur un filtre très sélectif, même un vivier
élargi peut ne pas contenir assez de survivants. Le plafond `VIVIER_MAXIMUM`
est un compromis entre exhaustivité et latence, pas une garantie.

---

## 12. `src/surlignage.py` — pourquoi ce résultat ?

**Rôle.** Rendre un score vérifiable à l'œil nu.

Deux justifications, de coûts très différents :

| Justification | Comment | Coût |
|---|---|---|
| **mots partagés** | intersection des mots significatifs question / document | nul |
| **phrase clé** | chaque phrase du résumé est encodée, on garde la plus proche | un appel au modèle |

La seconde est la seule qui fonctionne quand il n'y a aucun mot en commun —
c'est-à-dire précisément dans le cas qui justifie le projet. Le modèle désigne
lui-même ce qui, dans le document, a déclenché le rapprochement.

**Le coût est réel et mesuré** : sur un CPU sans carte graphique, encoder les
78 phrases de dix résumés prend environ trois secondes, contre cent
millisecondes pour la recherche. L'explicabilité coûte trente fois la
recherche. D'où `NB_EXPLICATIONS_PAR_DEFAUT = 5` : la phrase clé n'est calculée
que pour les résultats réellement lus, tandis que les mots partagés — gratuits —
restent calculés pour tous.

**Toutes les phrases sont encodées en un seul lot.** Encoder résultat par
résultat multiplierait par dix le nombre d'appels au modèle pour la même
quantité de texte.

**`surligner()` échappe le HTML avant d'ajouter la moindre balise.** Un résumé
arXiv contient des chevrons et des esperluettes : les laisser passer casserait
la mise en page, et ouvrirait une injection HTML dans l'interface.

---

## 13. `src/comparaison.py` — ce qu'un moteur est seul à trouver

**Rôle.** Analyser deux classements portant sur la même requête.

Afficher deux listes côte à côte est la forme minimale de la comparaison, et la
moins informative : deux colonnes de dix titres se ressemblent toujours un peu,
et l'œil ne sait pas où regarder. Ce module calcule ce que les listes ne
montrent pas d'elles-mêmes — les exclusivités de chaque moteur, le taux de
recouvrement, les articles fortement reclassés — puis `verdict()` rédige la
phrase correspondante à partir des résultats réels.

Le cas le plus parlant sort tout seul : quand `moteurs_muets` n'est pas vide,
un moteur n'a rien renvoyé du tout. C'est la situation des requêtes arabes, et
la condition de validation n°7 du cahier des charges.

---

## 14. `ui/` — l'interface

**Rôle.** Afficher. Ce dossier ne sait rien de Sentence-BERT ni de FAISS : il
appelle l'API. C'est ce découplage qui permet de changer entièrement le moteur
sans toucher à l'affichage.

| Fichier | Responsabilité unique |
|---|---|
| `app.py` | assemble les cinq vues, gère l'état de la session |
| `theme.py` | palette, typographie, feuille de style — **le seul endroit avec une couleur** |
| `composants.py` | cartes de résultats, panneaux, badges — du HTML, rien d'autre |
| `graphiques.py` | les courbes de l'onglet Évaluation |
| `client.py` | **le seul fichier qui fait un appel réseau** |

**Le modèle d'exécution de Streamlit déroute au début** : à chaque interaction,
le script entier se relance du haut vers le bas. Rien ne survit d'un clic à
l'autre, sauf ce qui est rangé dans `st.session_state`.

Trois pièges rencontrés dans ce projet, qui ne produisent aucune erreur :

1. **Écrire dans la clé d'un widget déjà instancié n'a aucun effet.** Les
   boutons d'exemple passent donc par `on_click=` : les fonctions de rappel
   s'exécutent avant la reconstruction des widgets, c'est le seul moment où
   l'écriture est prise en compte. Sans cela, cliquer sur un exemple ne
   remplissait tout simplement pas la barre de recherche.
2. **Une ligne vide dans un bloc HTML le referme.** Streamlit interprète
   d'abord la chaîne comme du Markdown : une partie facultative laissée vide
   produit une ligne blanche, et la balise fermante suivante s'affiche en clair
   à l'écran. D'où `_bloc()` dans `composants.py`, qui supprime les lignes vides.
3. **Un état lu en haut du script doit être la clé du widget qui le règle.**
   Le sélecteur de thème se trouve dans la barre latérale, mais la feuille de
   style est injectée bien avant. Il porte donc la clé `choix_theme` :
   Streamlit restaure l'état des widgets avant de rejouer le script, la valeur
   est donc déjà disponible en haut. Écrire cet état après coup ferait changer
   le thème un clic trop tard.

---

## 15. `tests/` — le filet de sécurité

Quarante-sept tests répartis en deux fichiers, qui ne téléchargent aucun modèle
et n'ont besoin d'aucun index : ils vérifient la logique, pas la qualité des
résultats — celle-ci est mesurée par `scripts/4_evaluer.py`. L'ensemble tourne
en moins d'une seconde.

- `test_moteur.py` — le cœur : prétraitement, index, regroupement, métriques.
- `test_extensions.py` — fusion RRF, filtres, explication, comparaison.

L'encodeur y est remplacé par une classe factice de dix lignes qui projette un
texte sur deux dimensions. Tester la logique d'explication ne demande pas un
vrai modèle : il suffit que les vecteurs soient prévisibles.

Ce qu'ils protègent réellement :

| Test | Bug qu'il attrape |
|---|---|
| `test_texte_long_est_decoupe_avec_chevauchement` | un chevauchement cassé qui couperait les idées en deux |
| `test_preparation_relie_chaque_passage_a_son_document` | la correspondance position ↔ identifiant FAISS rompue |
| `test_index_retrouve_le_vecteur_identique` | une erreur de normalisation ou de métrique |
| `test_les_passages_d_un_meme_article_sont_fusionnes` | un article occupant plusieurs places du classement |
| `test_les_identifiants_invalides_sont_ignores` | le `-1` de FAISS lu comme dernier passage du corpus |
| `test_ndcg_decroit_avec_le_rang` | une métrique fausse, donc une évaluation fausse |
| `test_un_accord_entre_moteurs_bat_une_premiere_place_isolee` | une fusion RRF qui ne fusionnerait rien |
| `test_un_moteur_muet_ne_casse_pas_la_fusion` | une exception sur toutes les requêtes arabes |
| `test_le_filtre_s_applique_avant_la_troncature_a_k` | un filtre qui renverrait des trous au lieu de résultats |
| `test_surlignage_echappe_le_html_avant_de_baliser` | une injection HTML venue d'un résumé arXiv |
| `test_l_explication_lexicale_couvre_tous_les_resultats` | le signal « aucun mot en commun » perdu au-delà du 5e résultat |

**Pour vérifier qu'un test sert à quelque chose, casse le code exprès.** Si
aucun test ne tombe, le test ne protège rien.

---

## Les cinq décisions qui expliquent tout le reste

1. **Le même modèle indexe et cherche.** Deux modèles différents produisent deux
   espaces sans rapport, donc des résultats aléatoires — sans message d'erreur.
2. **Les vecteurs sont normalisés.** C'est ce qui rend le produit scalaire égal
   au cosinus et permet d'utiliser l'index le plus rapide.
3. **On indexe des passages, on affiche des articles.** D'où le regroupement, et
   d'où le fait de demander plus de passages que d'articles souhaités.
4. **Le titre n'est pas indexé.** Sans cela, l'évaluation se mesure elle-même.
5. **Les deux moteurs partagent le même code de regroupement.** Sans cela, la
   comparaison mesurerait autre chose que ce qu'elle prétend mesurer.

---

## Recettes de modification

### Changer de modèle d'embeddings

1. Modifier `NOM_MODELE` et `DIMENSION` dans `config.py`.
2. Relancer `python scripts/2_indexer.py` — **obligatoire**, l'ancien index
   n'est plus compatible.
3. Relancer `python scripts/4_evaluer.py` pour comparer les chiffres.

Attention aux préfixes : ils sont propres à la famille E5. Un modèle
`paraphrase-multilingual-MiniLM` n'en veut pas — il faudrait alors vider
`PREFIXE_REQUETE` et `PREFIXE_DOCUMENT`.

### Ajouter un champ aux résultats

1. L'extraire dans `_analyser_entree` (`src/collecte.py`).
2. Le recopier dans `preparer_passages` (`src/pretraitement.py`).
3. Le recopier dans `regrouper_par_document` (`src/resultats.py`).
4. L'ajouter au modèle `Resultat` (`api/main.py`).
5. L'afficher dans `ui/app.py`.

Le champ doit traverser les cinq étapes : c'est le prix du découplage.

### Ajouter un critère de filtrage

Les filtres existent déjà (catégorie, année, auteur) : voir `src/filtres.py`.
Pour en ajouter un — la revue de publication, le nombre de citations —, trois
endroits suffisent :

1. stocker l'information dans chaque passage, dans `preparer_passages` ;
2. ajouter le test correspondant dans `filtres.construire()` ;
3. exposer le paramètre dans `api/main.py`, puis dans la barre latérale.

Rien à toucher dans les moteurs : ils reçoivent le filtre déjà construit et le
transmettent à `regrouper_par_document`.

### Changer le poids d'un moteur dans la fusion

`MoteurHybride(semantique, lexical, poids_semantique=2.0)` fait peser le
sémantique double dans le vote. Un poids nul exclut un moteur — pratique pour
vérifier que la fusion se réduit bien au classement de l'autre.

### Changer de corpus

Seul `src/collecte.py` connaît arXiv. Pour indexer autre chose — des PDF, une
base de FAQ, des offres d'emploi — il suffit d'écrire une fonction qui produit
la même structure : une liste de dictionnaires avec les clés `id`, `titre`,
`resume`. Tout le reste du projet fonctionne sans modification.

---

## Glossaire

| Terme | Définition courte |
|---|---|
| **Embedding** | la liste de nombres qui représente le sens d'un texte |
| **Passage** | un morceau de document, unité réellement indexée |
| **Cosinus** | mesure d'angle entre deux vecteurs, entre −1 et 1 |
| **Normaliser** | ramener un vecteur à une longueur de 1 |
| **BM25** | méthode de recherche par mots-clés, référence depuis 1994 |
| **Recall@k** | le bon document est-il dans les k premiers résultats ? |
| **MRR** | moyenne de 1/rang du bon document |
| **nDCG** | métrique de classement pondérée par la position |
| **qrels** | annotations de pertinence servant de vérité de référence |
| **nprobe** | nombre de quartiers fouillés par l'index approché |
| **Fuite de données** | information de la réponse présente dans la question |
| **Bi-encodeur** | requête et document encodés séparément — notre cas |
| **Cross-encoder** | requête et document lus ensemble : plus juste, plus lent |
