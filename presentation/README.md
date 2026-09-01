# Le support de soutenance

Deux formats, un seul contenu.

| Fichier | Quand l'utiliser |
|---|---|
| [`../soutenance.pptx`](../soutenance.pptx) | PowerPoint. Le format attendu par la plupart des jurys, modifiable slide par slide. Les notes de l'orateur sont dans le volet Commentaires. |
| [`../soutenance.html`](../soutenance.html) | La même présentation dans le navigateur, sans rien installer. Touche `N` pour les notes, `O` pour la vue d'ensemble. |

Les deux contiennent les mêmes 26 diapositives et les mêmes notes. Tous les
chiffres proviennent de `resultats/evaluation.json` : aucune valeur n'est saisie
à la main.

## Régénérer le PowerPoint

Le fichier `.pptx` est versionné : il n'y a rien à lancer pour l'utiliser. Cette
commande ne sert qu'à le reconstruire après avoir modifié le contenu.

```bash
npm install pptxgenjs sharp
node presentation/generer_pptx.js soutenance.pptx
```

C'est la seule partie du projet qui demande Node plutôt que Python. La raison
est simple : `pptxgenjs` produit des graphiques PowerPoint **natifs** —
sélectionnables, modifiables, avec leurs données — là où les bibliothèques
Python auraient inséré des images de graphiques.

## Régénérer le PDF

Une diapositive par page, au format paysage, à partir de la version HTML :

```bash
python scripts/5_exporter_pdf.py
```
