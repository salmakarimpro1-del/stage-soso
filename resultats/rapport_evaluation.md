# Résultats de l'évaluation

## Configuration

- Modèle : `intfloat/multilingual-e5-small` (384 dimensions)
- Index : flat
- Corpus : 8569 articles, 10897 passages

## Protocole 1 — titre vers résumé

Le titre d'un article sert de requête ; le bon résultat est l'article lui-même. Le titre n'est pas indexé, ce qui écarte toute correspondance exacte en faveur de BM25.

| Moteur | Recall@1 | Recall@5 | Recall@10 | MRR@10 | nDCG@10 |
|---|---|---|---|---|---|
| Sémantique (SBERT + FAISS) | 0.896 | 0.956 | 0.964 | 0.922 | 0.932 |
| Lexical (BM25) | 0.930 | 0.984 | 0.990 | 0.953 | 0.962 |

## Protocole 1 bis — selon le recouvrement lexical

Les mêmes 500 requêtes, réparties en trois groupes selon la part des mots de la requête effectivement présents dans le document attendu. C'est la quantité dont BM25 dépend entièrement.

| Groupe | Requêtes | Recouvrement | Sémantique MRR@10 | BM25 MRR@10 | Écart |
|---|---|---|---|---|---|
| faible recouvrement | 166 | 0.63 | 0.827 | 0.877 | -0.050 |
| recouvrement moyen | 166 | 0.83 | 0.960 | 0.988 | -0.028 |
| fort recouvrement | 168 | 0.96 | 0.978 | 0.994 | -0.016 |

Même le tiers le plus difficile partage encore les deux tiers de son vocabulaire avec le bon document : ce protocole n'atteint jamais le régime où la correspondance de mots cesse de fonctionner.

## Protocole 1 ter — requêtes privées de leurs mots rares

Pour atteindre ce régime, les trois mots les plus rares de chaque titre sont retirés. Il ne reste que du vocabulaire courant : le sujet sans sa signature lexicale.

- Avant : *VectraYX-Vision-1B: A Sub-2B Spanish/LATAM Cybersecurity Vision-Language Model with Structured Visual Reasoning and Native Tool Use*
- Après : *vision 1b a sub 2b cybersecurity vision language model with structured visual reasoning and native tool use*

| Moteur | MRR@10 normal | MRR@10 appauvri | Variation | Recall@10 |
|---|---|---|---|---|
| Sémantique | 0.922 | 0.564 | -0.357 | 0.716 |
| Lexical (BM25) | 0.953 | 0.645 | -0.308 | 0.800 |

Résultat contraire à l'hypothèse de départ : le moteur sémantique chute davantage. Les mots rares ne portaient pas seulement la signature lexicale, ils portaient le sujet. Un modèle dense, qui compresse la requête entière dans un vecteur unique, est plus sensible à cette dégradation que BM25, lequel ignore simplement les termes sans correspondance.

## Protocole 2 — cohérence multilingue

La même question est posée en français, en arabe et en anglais sur un corpus entièrement anglophone. On mesure la part d'articles communs entre les résultats de deux langues.

| Moteur | Recouvrement fr/en | Recouvrement ar/en | Recouvrement fr/ar | Requêtes ar sans résultat |
|---|---|---|---|---|
| Sémantique | 0.445 | 0.130 | 0.205 | 0 |
| Lexical (BM25) | 0.035 | 0.000 | 0.000 | 20 |

### Détail par question (moteur sémantique)

| Thème | fr/en | ar/en | 1er résultat (requête française) |
|---|---|---|---|
| fraude bancaire | 0.70 | 0.10 | Amortised Post-Hoc Explanation with Exact Preservation for Dynamic Gra |
| traduction automatique | 0.60 | 0.50 | EMBER: Autonomous Cognitive Behaviour from Learned Spiking Neural Netw |
| imagerie médicale | 0.30 | 0.40 | GARLIC: Graph Attention-based Relational Learning of Multivariate Time |
| conduite autonome | 0.80 | 0.10 | Mask What Matters: Saliency-Guided Video Self-Supervised Learning for  |
| attaques adverses | 0.30 | 0.00 | NERO-Net: A Neuroevolutionary Approach for the Design of Adversarially |
| apprentissage fédéré | 0.60 | 0.00 | Federated Prompt Learning: A Unified Framework, Empirical Analysis, an |
| raisonnement des LLM | 0.10 | 0.10 | Behavioral Reprogramming of Open-Weights Models: Cognitive Plasticity  |
| recommandation | 0.30 | 0.00 | Recommendation as Generation: Unifying Personalized Video Generation a |
| désinformation | 0.30 | 0.00 | Candidate-Fate Accounting for Transparent Sensor Diagnostic Pipeline S |
| reconnaissance vocale | 0.50 | 0.00 | A Speech Corpus for Mizo Automatic Speech Recognition: Whisper and Sra |
| apprentissage par renforcement | 0.20 | 0.30 | Decentralized Multi-Player Q-Learning in Episodic Markov Decision Proc |
| compression de modèles | 0.40 | 0.00 | Multi-Level Resistive Synapses for On-Chip Neural Networks: A Physics- |
| anomalies réseau | 0.60 | 0.10 | Unsupervised Anomaly Detection in NSL-KDD Using -VAE: A Latent Space a |
| modèles de diffusion | 0.50 | 0.20 | In-Loop Model Adaptation with Coupled Latent-Noise Guidance for High-F |
| réseaux sur graphes | 0.20 | 0.00 | A Case for Hypergraphs to Model and Map SNNs on Neuromorphic Hardware |
| analyse de sentiment | 0.50 | 0.10 | When AI Rewrites, Classifiers Relax: Uncertainty-Aware Sentiment Analy |
| séries temporelles | 0.50 | 0.00 | LiveHouse-TS: An Open-world Living Benchmark for Time Series Foundatio |
| confidentialité différentielle | 0.30 | 0.40 | End-to-End Differential Privacy in Training Deep Neural Network Classi |
| segmentation d'images | 0.60 | 0.10 | Distractor-Aware Video Object Segmentation |
| recherche dense | 0.60 | 0.20 | ARMOR: Adaptive Retriever Optimization for Low-Resource Telecom Questi |

## Protocole 3 — latences

| Moteur | Médiane (ms) | Moyenne (ms) | p95 (ms) | Max (ms) |
|---|---|---|---|---|
| Sémantique | 83.35 | 90.62 | 107.24 | 516.41 |
| Lexical (BM25) | 116.68 | 161.59 | 235.99 | 2713.55 |

## Protocole 3 bis — index exact contre index approximatif

Le rappel est mesuré par rapport à l'index exact, pris comme référence : c'est la part des bons voisins que l'approximation retrouve.

| Index | nprobe | Construction (s) | ms / requête | Rappel vs exact |
|---|---|---|---|---|
| flat (exact) | - | 0.01 | 1.311 | 1.000 |
| ivf (approché) | 1 | 0.42 | 0.126 | 0.325 |
| ivf (approché) | 5 | 0.43 | 0.074 | 0.623 |
| ivf (approché) | 10 | 0.33 | 0.124 | 0.761 |
| ivf (approché) | 20 | 0.77 | 0.449 | 0.862 |
