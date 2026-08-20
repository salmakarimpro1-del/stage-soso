"""
Script 4 — Évaluer et comparer les deux moteurs.

Produit deux fichiers dans resultats/ :

    evaluation.json          tous les chiffres bruts
    rapport_evaluation.md    des tableaux prêts à coller dans le rapport

Utilisation :
    python scripts/4_evaluer.py
    python scripts/4_evaluer.py --nb-requetes 200     # version rapide
    python scripts/4_evaluer.py --sans-index          # sans le banc d'essai FAISS
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import config
from src.baseline_bm25 import MoteurLexical
from src.collecte import charger_corpus
from src.evaluation import (
    comparer_types_index,
    construire_requetes_appauvries,
    construire_requetes_titres,
    evaluer_coherence_multilingue,
    evaluer_moteur,
    mesurer_latences,
    stratifier_par_recouvrement,
)
from src.moteur import MoteurSemantique


def tableau_markdown(lignes: list[dict], colonnes: list[str]) -> str:
    """Fabrique un tableau Markdown à partir d'une liste de dictionnaires."""
    entete = "| " + " | ".join(colonnes) + " |"
    separateur = "|" + "|".join("---" for _ in colonnes) + "|"
    corps = [
        "| " + " | ".join(str(ligne.get(colonne, "")) for colonne in colonnes) + " |"
        for ligne in lignes
    ]
    return "\n".join([entete, separateur, *corps])


def main() -> None:
    analyseur = argparse.ArgumentParser(description="Évaluation des moteurs")
    analyseur.add_argument("--nb-requetes", type=int, default=500)
    analyseur.add_argument("-k", type=int, default=10)
    analyseur.add_argument("--sans-index", action="store_true",
                           help="ne pas comparer index exact et index approximatif")
    arguments = analyseur.parse_args()

    print("=" * 70)
    print("ÉVALUATION")
    print("=" * 70)

    corpus = charger_corpus()
    semantique = MoteurSemantique(verbeux=False).charger()
    lexical = MoteurLexical(verbeux=False).charger()

    print(f"Corpus   : {len(corpus)} articles")
    print(f"Index    : {semantique.nb_passages} passages, {semantique.nb_documents} articles")
    print(f"Modèle   : {config.NOM_MODELE}")

    rapport: dict = {
        "configuration": {
            "modele": config.NOM_MODELE,
            "dimension": config.DIMENSION,
            "type_index": config.TYPE_INDEX,
            "nb_documents": semantique.nb_documents,
            "nb_passages": semantique.nb_passages,
            "k": arguments.k,
        }
    }

    # ------------------------------------------------------------------
    # Protocole 1 : titre vers résumé
    # ------------------------------------------------------------------
    print("\n--- Protocole 1 : titre vers résumé ---")
    requetes, attendus = construire_requetes_titres(corpus, nb_requetes=arguments.nb_requetes)
    print(f"{len(requetes)} requêtes générées automatiquement")

    print("  moteur sémantique ...")
    resultat_semantique = evaluer_moteur(semantique, requetes, attendus, k=arguments.k)
    print("  baseline BM25 ...")
    resultat_lexical = evaluer_moteur(lexical, requetes, attendus, k=arguments.k)

    rapport["titre_vers_resume"] = {
        "semantique": resultat_semantique,
        "bm25": resultat_lexical,
    }

    for nom, mesures in (("Sémantique", resultat_semantique), ("BM25", resultat_lexical)):
        print(f"  {nom:<12} recall@1={mesures['recall@1']:.3f}  "
              f"recall@10={mesures['recall@10']:.3f}  "
              f"MRR={mesures[f'mrr@{arguments.k}']:.3f}")

    # ------------------------------------------------------------------
    # Protocole 1 bis : selon le recouvrement lexical
    # ------------------------------------------------------------------
    print("\n--- Protocole 1 bis : selon le recouvrement lexical ---")
    groupes = stratifier_par_recouvrement(requetes, attendus, corpus)
    stratification = []

    for groupe in groupes:
        mesures_sem = evaluer_moteur(
            semantique, groupe["requetes"], groupe["attendus"], k=arguments.k)
        mesures_lex = evaluer_moteur(
            lexical, groupe["requetes"], groupe["attendus"], k=arguments.k)

        stratification.append({
            "groupe": groupe["nom"],
            "nb_requetes": len(groupe["requetes"]),
            "recouvrement_moyen": groupe["recouvrement_moyen"],
            "recouvrement_min": groupe["recouvrement_min"],
            "recouvrement_max": groupe["recouvrement_max"],
            "semantique": mesures_sem,
            "bm25": mesures_lex,
        })

        print(f"  {groupe['nom']:<22} recouvrement={groupe['recouvrement_moyen']:.2f}  "
              f"sémantique MRR={mesures_sem[f'mrr@{arguments.k}']:.3f}  "
              f"BM25 MRR={mesures_lex[f'mrr@{arguments.k}']:.3f}")

    rapport["stratification_lexicale"] = stratification

    # ------------------------------------------------------------------
    # Protocole 1 ter : requêtes appauvries
    # ------------------------------------------------------------------
    print("\n--- Protocole 1 ter : requêtes privées de leurs mots rares ---")
    appauvries, attendus_app, origines = construire_requetes_appauvries(
        corpus, nb_requetes=arguments.nb_requetes)
    print(f"  exemple  avant : {origines[0][:72]}")
    print(f"           après : {appauvries[0][:72]}")

    app_semantique = evaluer_moteur(semantique, appauvries, attendus_app, k=arguments.k)
    app_lexical = evaluer_moteur(lexical, appauvries, attendus_app, k=arguments.k)

    rapport["requetes_appauvries"] = {
        "nb_mots_retires": 3,
        "exemple_avant": origines[0],
        "exemple_apres": appauvries[0],
        "semantique": app_semantique,
        "bm25": app_lexical,
    }

    for nom, mesures, reference in (
        ("Sémantique", app_semantique, resultat_semantique),
        ("BM25", app_lexical, resultat_lexical),
    ):
        chute = mesures[f"mrr@{arguments.k}"] - reference[f"mrr@{arguments.k}"]
        print(f"  {nom:<12} MRR={mesures[f'mrr@{arguments.k}']:.3f}  "
              f"recall@10={mesures['recall@10']:.3f}  (variation {chute:+.3f})")

    # ------------------------------------------------------------------
    # Protocole 2 : cohérence multilingue
    # ------------------------------------------------------------------
    print("\n--- Protocole 2 : cohérence multilingue ---")
    with open(config.FICHIER_REQUETES_MULTI, encoding="utf-8") as entree:
        triplets = json.load(entree)["triplets"]
    print(f"{len(triplets)} questions posées en français, arabe et anglais")

    multi_semantique = evaluer_coherence_multilingue(semantique, triplets, k=arguments.k)
    multi_lexical = evaluer_coherence_multilingue(lexical, triplets, k=arguments.k)

    rapport["coherence_multilingue"] = {
        "semantique": multi_semantique,
        "bm25": multi_lexical,
    }

    for nom, mesures in (("Sémantique", multi_semantique), ("BM25", multi_lexical)):
        print(f"  {nom:<12} recouvrement fr/en={mesures['recouvrement_moyen_fr_en']:.3f}  "
              f"ar/en={mesures['recouvrement_moyen_ar_en']:.3f}  "
              f"(requêtes arabes sans résultat : {mesures['requetes_sans_resultat_ar']})")

    # ------------------------------------------------------------------
    # Protocole 3 : latences
    # ------------------------------------------------------------------
    print("\n--- Protocole 3 : latences ---")
    echantillon = requetes[:100]
    latence_semantique = mesurer_latences(semantique, echantillon, k=arguments.k)
    latence_lexical = mesurer_latences(lexical, echantillon, k=arguments.k)

    rapport["latences"] = {
        "semantique": latence_semantique,
        "bm25": latence_lexical,
    }
    print(f"  Sémantique   médiane={latence_semantique['latence_mediane_ms']} ms  "
          f"p95={latence_semantique['latence_p95_ms']} ms")
    print(f"  BM25         médiane={latence_lexical['latence_mediane_ms']} ms  "
          f"p95={latence_lexical['latence_p95_ms']} ms")

    # ------------------------------------------------------------------
    # Protocole 3 bis : index exact contre index approximatif
    # ------------------------------------------------------------------
    if not arguments.sans_index and Path(config.FICHIER_VECTEURS).exists():
        print("\n--- Protocole 3 bis : index exact contre index approximatif ---")
        import numpy as np

        vecteurs = np.load(config.FICHIER_VECTEURS)
        vecteurs_requetes = semantique.encodeur.encoder_requetes(requetes[:200])
        tableau_index = comparer_types_index(vecteurs, vecteurs_requetes, k=arguments.k)
        rapport["comparaison_index"] = tableau_index

        for ligne in tableau_index:
            print(f"  {ligne['index']:<16} nprobe={str(ligne['nprobe']):<4} "
                  f"{ligne['ms_par_requete']:>7} ms/requête   "
                  f"rappel={ligne['rappel_vs_exact']:.3f}")

    # ------------------------------------------------------------------
    # Écriture des fichiers
    # ------------------------------------------------------------------
    config.DOSSIER_RESULTATS.mkdir(parents=True, exist_ok=True)

    fichier_json = config.DOSSIER_RESULTATS / "evaluation.json"
    with open(fichier_json, "w", encoding="utf-8") as sortie:
        json.dump(rapport, sortie, ensure_ascii=False, indent=2)

    fichier_md = config.DOSSIER_RESULTATS / "rapport_evaluation.md"
    with open(fichier_md, "w", encoding="utf-8") as sortie:
        ecrire_rapport(sortie, rapport, arguments.k)

    print(f"\nRésultats bruts   : {fichier_json}")
    print(f"Rapport lisible   : {fichier_md}")


def ecrire_rapport(sortie, rapport: dict, k: int) -> None:
    """Rédige le rapport Markdown des résultats."""
    configuration = rapport["configuration"]

    sortie.write("# Résultats de l'évaluation\n\n")
    sortie.write("## Configuration\n\n")
    sortie.write(f"- Modèle : `{configuration['modele']}` ({configuration['dimension']} dimensions)\n")
    sortie.write(f"- Index : {configuration['type_index']}\n")
    sortie.write(f"- Corpus : {configuration['nb_documents']} articles, "
                 f"{configuration['nb_passages']} passages\n\n")

    sortie.write("## Protocole 1 — titre vers résumé\n\n")
    sortie.write("Le titre d'un article sert de requête ; le bon résultat est l'article "
                 "lui-même. Le titre n'est pas indexé, ce qui écarte toute correspondance "
                 "exacte en faveur de BM25.\n\n")

    lignes = []
    for nom, cle in (("Sémantique (SBERT + FAISS)", "semantique"), ("Lexical (BM25)", "bm25")):
        mesures = rapport["titre_vers_resume"][cle]
        lignes.append({
            "Moteur": nom,
            "Recall@1": f"{mesures['recall@1']:.3f}",
            "Recall@5": f"{mesures['recall@5']:.3f}",
            "Recall@10": f"{mesures['recall@10']:.3f}",
            f"MRR@{k}": f"{mesures[f'mrr@{k}']:.3f}",
            f"nDCG@{k}": f"{mesures[f'ndcg@{k}']:.3f}",
        })
    sortie.write(tableau_markdown(
        lignes, ["Moteur", "Recall@1", "Recall@5", "Recall@10", f"MRR@{k}", f"nDCG@{k}"]))
    sortie.write("\n\n")

    if "stratification_lexicale" in rapport:
        sortie.write("## Protocole 1 bis — selon le recouvrement lexical\n\n")
        sortie.write("Les mêmes 500 requêtes, réparties en trois groupes selon la part "
                     "des mots de la requête effectivement présents dans le document "
                     "attendu. C'est la quantité dont BM25 dépend entièrement.\n\n")

        lignes = []
        for groupe in rapport["stratification_lexicale"]:
            lignes.append({
                "Groupe": groupe["groupe"],
                "Requêtes": groupe["nb_requetes"],
                "Recouvrement": f"{groupe['recouvrement_moyen']:.2f}",
                f"Sémantique MRR@{k}": f"{groupe['semantique'][f'mrr@{k}']:.3f}",
                f"BM25 MRR@{k}": f"{groupe['bm25'][f'mrr@{k}']:.3f}",
                "Écart": f"{groupe['semantique'][f'mrr@{k}'] - groupe['bm25'][f'mrr@{k}']:+.3f}",
            })
        sortie.write(tableau_markdown(lignes, [
            "Groupe", "Requêtes", "Recouvrement",
            f"Sémantique MRR@{k}", f"BM25 MRR@{k}", "Écart"]))
        sortie.write("\n\nMême le tiers le plus difficile partage encore les deux tiers de "
                     "son vocabulaire avec le bon document : ce protocole n'atteint jamais "
                     "le régime où la correspondance de mots cesse de fonctionner.\n\n")

    if "requetes_appauvries" in rapport:
        appauvries = rapport["requetes_appauvries"]
        sortie.write("## Protocole 1 ter — requêtes privées de leurs mots rares\n\n")
        sortie.write("Pour atteindre ce régime, les trois mots les plus rares de chaque "
                     "titre sont retirés. Il ne reste que du vocabulaire courant : le "
                     "sujet sans sa signature lexicale.\n\n")
        sortie.write(f"- Avant : *{appauvries['exemple_avant']}*\n")
        sortie.write(f"- Après : *{appauvries['exemple_apres']}*\n\n")

        lignes = []
        for nom, cle in (("Sémantique", "semantique"), ("Lexical (BM25)", "bm25")):
            mesures = appauvries[cle]
            reference = rapport["titre_vers_resume"][cle]
            lignes.append({
                "Moteur": nom,
                f"MRR@{k} normal": f"{reference[f'mrr@{k}']:.3f}",
                f"MRR@{k} appauvri": f"{mesures[f'mrr@{k}']:.3f}",
                "Variation": f"{mesures[f'mrr@{k}'] - reference[f'mrr@{k}']:+.3f}",
                "Recall@10": f"{mesures['recall@10']:.3f}",
            })
        sortie.write(tableau_markdown(lignes, [
            "Moteur", f"MRR@{k} normal", f"MRR@{k} appauvri", "Variation", "Recall@10"]))
        sortie.write("\n\nRésultat contraire à l'hypothèse de départ : le moteur sémantique "
                     "chute davantage. Les mots rares ne portaient pas seulement la "
                     "signature lexicale, ils portaient le sujet. Un modèle dense, qui "
                     "compresse la requête entière dans un vecteur unique, est plus "
                     "sensible à cette dégradation que BM25, lequel ignore simplement "
                     "les termes sans correspondance.\n\n")

    sortie.write("## Protocole 2 — cohérence multilingue\n\n")
    sortie.write("La même question est posée en français, en arabe et en anglais sur un "
                 "corpus entièrement anglophone. On mesure la part d'articles communs "
                 "entre les résultats de deux langues.\n\n")

    lignes = []
    for nom, cle in (("Sémantique", "semantique"), ("Lexical (BM25)", "bm25")):
        mesures = rapport["coherence_multilingue"][cle]
        lignes.append({
            "Moteur": nom,
            "Recouvrement fr/en": f"{mesures['recouvrement_moyen_fr_en']:.3f}",
            "Recouvrement ar/en": f"{mesures['recouvrement_moyen_ar_en']:.3f}",
            "Recouvrement fr/ar": f"{mesures['recouvrement_moyen_fr_ar']:.3f}",
            "Requêtes ar sans résultat": mesures["requetes_sans_resultat_ar"],
        })
    sortie.write(tableau_markdown(lignes, [
        "Moteur", "Recouvrement fr/en", "Recouvrement ar/en",
        "Recouvrement fr/ar", "Requêtes ar sans résultat"]))
    sortie.write("\n\n")

    sortie.write("### Détail par question (moteur sémantique)\n\n")
    lignes = [
        {
            "Thème": detail["theme"],
            "fr/en": f"{detail['recouvrement_fr_en']:.2f}",
            "ar/en": f"{detail['recouvrement_ar_en']:.2f}",
            "1er résultat (requête française)": detail["titre_premier_fr"][:70],
        }
        for detail in rapport["coherence_multilingue"]["semantique"]["detail"]
    ]
    sortie.write(tableau_markdown(
        lignes, ["Thème", "fr/en", "ar/en", "1er résultat (requête française)"]))
    sortie.write("\n\n")

    sortie.write("## Protocole 3 — latences\n\n")
    lignes = []
    for nom, cle in (("Sémantique", "semantique"), ("Lexical (BM25)", "bm25")):
        mesures = rapport["latences"][cle]
        lignes.append({
            "Moteur": nom,
            "Médiane (ms)": mesures["latence_mediane_ms"],
            "Moyenne (ms)": mesures["latence_moyenne_ms"],
            "p95 (ms)": mesures["latence_p95_ms"],
            "Max (ms)": mesures["latence_max_ms"],
        })
    sortie.write(tableau_markdown(
        lignes, ["Moteur", "Médiane (ms)", "Moyenne (ms)", "p95 (ms)", "Max (ms)"]))
    sortie.write("\n\n")

    if "comparaison_index" in rapport:
        sortie.write("## Protocole 3 bis — index exact contre index approximatif\n\n")
        sortie.write("Le rappel est mesuré par rapport à l'index exact, pris comme "
                     "référence : c'est la part des bons voisins que l'approximation "
                     "retrouve.\n\n")
        lignes = [
            {
                "Index": ligne["index"],
                "nprobe": ligne["nprobe"],
                "Construction (s)": ligne["construction_s"],
                "ms / requête": ligne["ms_par_requete"],
                "Rappel vs exact": f"{ligne['rappel_vs_exact']:.3f}",
            }
            for ligne in rapport["comparaison_index"]
        ]
        sortie.write(tableau_markdown(lignes, [
            "Index", "nprobe", "Construction (s)", "ms / requête", "Rappel vs exact"]))
        sortie.write("\n")


if __name__ == "__main__":
    main()
