"""
Script 5 — Exporter la documentation en PDF.

Produit deux documents dans export/ :

    dossier_technique.pdf    le README complet, suivi du rapport d'évaluation
                             détaillé en annexe
    plan_apprentissage.pdf   le plan d'apprentissage en neuf modules

Le rendu passe par Chrome (ou Edge) en mode sans interface, qui applique
les feuilles de style d'impression et conserve les liens cliquables. Aucune
dépendance supplémentaire à installer : le navigateur est déjà présent sur
la machine.

Utilisation :
    python scripts/5_exporter_pdf.py
"""

import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import config

DOSSIER_EXPORT = config.RACINE / "export"

# Emplacements habituels des navigateurs sur Windows.
NAVIGATEURS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]


# ---------------------------------------------------------------------------
# Gabarit de la documentation
# ---------------------------------------------------------------------------

GABARIT = """<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>{titre}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500&family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,500;0,6..72,600;1,6..72,400&display=swap">
<style>
:root{{
  --ground:#FFFFFF; --ink:#151A18; --ink-soft:#4C5653; --ink-faint:#7A837F;
  --rule:#C9D0C6; --rule-soft:#E1E6DE; --accent:#0F544C; --accent-tint:#E8F0ED;
}}
@page{{ size:A4; margin:18mm 16mm 16mm; }}
*{{box-sizing:border-box}}
body{{
  margin:0; background:var(--ground); color:var(--ink);
  font-family:"IBM Plex Sans","Segoe UI",sans-serif;
  font-size:10.4pt; line-height:1.58;
  -webkit-print-color-adjust:exact; print-color-adjust:exact;
}}
.page{{max-width:none;padding:0}}

.couverture{{
  border-bottom:1px solid var(--rule); padding-bottom:26px; margin-bottom:30px;
  break-after:page;
}}
.couverture .eyebrow{{
  font-family:"IBM Plex Mono",monospace; font-size:9pt; letter-spacing:.14em;
  text-transform:uppercase; color:var(--ink-faint); margin:0 0 16px;
}}
.couverture h1{{
  font-family:Newsreader,Georgia,serif; font-weight:500; font-size:34pt;
  line-height:1.04; letter-spacing:-.015em; margin:0 0 18px; max-width:16ch;
}}
.couverture p{{font-family:Newsreader,Georgia,serif;font-size:12.5pt;
  line-height:1.5;color:var(--ink-soft);max-width:54ch;margin:0}}
.couverture dl{{display:grid;grid-template-columns:repeat(4,1fr);gap:0;margin:32px 0 0;
  border-top:1px solid var(--rule-soft);padding-top:14px}}
.couverture dl>div{{padding-right:18px;border-right:1px solid var(--rule-soft)}}
.couverture dl>div:last-child{{border-right:0;padding-right:0}}
.couverture dt{{font-family:"IBM Plex Mono",monospace;font-size:8.5pt;letter-spacing:.12em;
  text-transform:uppercase;color:var(--ink-faint);margin-bottom:3px}}
.couverture dd{{margin:0;font-size:10.5pt;font-variant-numeric:tabular-nums}}

h1,h2,h3,h4{{font-family:Newsreader,Georgia,serif;font-weight:500;
  color:var(--ink);text-wrap:balance;break-after:avoid}}
h1{{font-size:24pt;line-height:1.1;margin:0 0 14px}}
h2{{font-size:17pt;line-height:1.15;margin:0 0 12px;padding-top:4px;break-before:page}}
h2:first-of-type{{break-before:auto}}
h3{{font-size:13pt;margin:22px 0 8px}}
h4{{font-size:11.5pt;margin:18px 0 6px}}
p{{margin:0 0 11px;max-width:74ch}}
ul,ol{{margin:0 0 12px;padding-left:20px;max-width:74ch}}
li{{margin-bottom:5px;break-inside:avoid}}
strong{{font-weight:500}}
a{{color:var(--accent);text-decoration:underline;text-decoration-thickness:.5px}}
hr{{border:0;border-top:1px solid var(--rule-soft);margin:22px 0}}

blockquote{{
  margin:16px 0; padding:2px 0 2px 18px; border-left:2px solid var(--accent);
  font-family:Newsreader,Georgia,serif; font-size:11.5pt; line-height:1.5;
  color:var(--ink-soft); break-inside:avoid; max-width:64ch;
}}
blockquote p{{margin:0 0 6px}}
blockquote p:last-child{{margin:0}}

code{{font-family:"IBM Plex Mono",monospace;font-size:8.9pt;
  background:var(--rule-soft);padding:1px 4px;border-radius:2px}}
pre{{background:var(--rule-soft);padding:11px 14px;border-radius:3px;
  overflow-x:auto;margin:0 0 13px;break-inside:avoid}}
pre code{{background:none;padding:0;font-size:8.7pt;line-height:1.5}}

table{{border-collapse:collapse;width:100%;font-size:9.3pt;margin:0 0 15px;
  break-inside:avoid;font-variant-numeric:tabular-nums}}
th,td{{text-align:left;padding:7px 13px 7px 0;border-bottom:1px solid var(--rule-soft);
  vertical-align:top}}
th{{font-family:"IBM Plex Mono",monospace;font-size:8.4pt;letter-spacing:.09em;
  text-transform:uppercase;color:var(--ink-faint);font-weight:400;
  border-bottom:1px solid var(--rule)}}

.annexe{{break-before:page;border-top:1px solid var(--rule);padding-top:26px;margin-top:30px}}
.annexe>.marque{{font-family:"IBM Plex Mono",monospace;font-size:9pt;letter-spacing:.14em;
  text-transform:uppercase;color:var(--accent);margin:0 0 10px}}
.annexe h1{{break-before:auto}}
.annexe h2{{font-size:14pt;break-before:auto;margin-top:22px}}
</style>
</head>
<body>
<div class="page">
{contenu}
</div>
</body>
</html>
"""

COUVERTURE = """<header class="couverture">
  <p class="eyebrow">Dossier technique — projet de fin d'année</p>
  <h1>Moteur de recherche sémantique multilingue</h1>
  <p>Retrouver des articles scientifiques à partir d'une question en langage
  naturel — en français, en arabe ou en anglais — dans un corpus entièrement
  anglophone.</p>
  <dl>
    <div><dt>Corpus</dt><dd>8 520 articles</dd></div>
    <div><dt>Modèle</dt><dd>e5-small, 384 d</dd></div>
    <div><dt>Index</dt><dd>FAISS exact</dd></div>
    <div><dt>Latence médiane</dt><dd>17 ms</dd></div>
  </dl>
</header>
"""


def trouver_navigateur() -> str:
    """Renvoie le chemin du premier navigateur trouvé, ou lève une erreur."""
    for chemin in NAVIGATEURS:
        if Path(chemin).exists():
            return chemin
    raise FileNotFoundError(
        "Aucun navigateur trouvé pour produire le PDF.\n"
        "Installe Chrome ou Edge, ou ajoute son chemin dans NAVIGATEURS."
    )


def construire_documentation() -> Path:
    """Assemble le README et le rapport d'évaluation en une page HTML."""
    import markdown

    extensions = ["tables", "fenced_code", "sane_lists", "attr_list"]

    readme = (config.RACINE / "README.md").read_text(encoding="utf-8")
    # Le titre et l'accroche sont déjà dans la couverture : on retire la
    # première section du README pour ne pas les répéter.
    corps_readme = readme.split("---", 1)[1] if "---" in readme else readme
    html_readme = markdown.markdown(corps_readme, extensions=extensions)

    morceaux = [COUVERTURE, html_readme]

    fichier_guide = config.RACINE / "GUIDE_DU_CODE.md"
    if fichier_guide.exists():
        guide = fichier_guide.read_text(encoding="utf-8")
        # Le tableau comparant les trois documents n'a de sens que dans le
        # dépôt, où ce sont trois fichiers distincts. Dans le PDF, où tout est
        # réuni, on le retire.
        if "## Le chemin d'une donnée" in guide:
            guide = "# Guide du code\n\n## Le chemin d'une donnée" + guide.split(
                "## Le chemin d'une donnée", 1)[1]
        morceaux.append(
            '<section class="annexe"><p class="marque">Deuxième partie</p>'
            + markdown.markdown(guide, extensions=extensions)
            + "</section>"
        )

    fichier_rapport = config.DOSSIER_RESULTATS / "rapport_evaluation.md"
    if fichier_rapport.exists():
        html_rapport = markdown.markdown(
            fichier_rapport.read_text(encoding="utf-8"), extensions=extensions)
        morceaux.append(
            '<section class="annexe"><p class="marque">Annexe</p>'
            + html_rapport
            + "</section>"
        )
    else:
        print("  (rapport d'évaluation absent : annexe ignorée)")

    DOSSIER_EXPORT.mkdir(parents=True, exist_ok=True)
    destination = DOSSIER_EXPORT / "dossier_technique.html"
    destination.write_text(
        GABARIT.format(titre="Moteur de recherche sémantique multilingue",
                       contenu="\n".join(morceaux)),
        encoding="utf-8",
    )
    return destination


def imprimer_en_pdf(navigateur: str, source: Path, destination: Path) -> bool:
    """Rend une page HTML en PDF via le navigateur sans interface."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        destination.unlink()

    commande = [
        navigateur,
        "--headless=new",
        "--disable-gpu",
        "--no-pdf-header-footer",
        "--run-all-compositor-stages-before-draw",
        "--virtual-time-budget=20000",
        f"--print-to-pdf={destination}",
        source.as_uri(),
    ]

    depart = time.perf_counter()
    resultat = subprocess.run(commande, capture_output=True, timeout=180)
    duree = time.perf_counter() - depart

    if not destination.exists():
        print(f"  échec : {resultat.stderr.decode('utf-8', 'replace')[:300]}")
        return False

    taille = destination.stat().st_size / 1024
    print(f"  {destination.name}  —  {taille:.0f} Ko en {duree:.1f} s")
    return True


def main() -> None:
    print("=" * 70)
    print("EXPORT PDF")
    print("=" * 70)

    navigateur = trouver_navigateur()
    print(f"Navigateur : {navigateur}\n")

    print("Assemblage de la documentation ...")
    source_doc = construire_documentation()

    print("\nRendu des PDF ...")
    succes = imprimer_en_pdf(
        navigateur, source_doc, DOSSIER_EXPORT / "dossier_technique.pdf")

    plan = config.RACINE / "plan_apprentissage.html"
    if plan.exists():
        succes = imprimer_en_pdf(
            navigateur, plan, DOSSIER_EXPORT / "plan_apprentissage.pdf") and succes
    else:
        print("  plan_apprentissage.html introuvable, ignoré")

    if succes:
        print(f"\nPDF disponibles dans {DOSSIER_EXPORT}")
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
