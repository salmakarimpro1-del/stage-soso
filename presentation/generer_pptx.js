/* ===========================================================================
   Génère soutenance.pptx — support de soutenance, 26 diapositives.

   Le contenu et la palette reprennent soutenance.html : le violet désigne le
   moteur sémantique, l'ambre la baseline BM25, l'émeraude la fusion hybride,
   dans les diapositives comme dans l'application.

   Tous les chiffres proviennent de resultats/evaluation.json.
   =========================================================================== */

const pptxgen = require('pptxgenjs');
const sharp = require('sharp');
const path = require('path');

const SORTIE = process.argv[2] || 'soutenance.pptx';

// --- palette (sans dièse : pptxgenjs corrompt le fichier sinon) -------------
const C = {
  fond: '080A0F',
  surface: '141822',
  surfaceHaute: '1B2130',
  bordure: '2A3145',
  texte: 'E9ECF5',
  texteDoux: '9AA3BC',
  texteFaible: '727C96',
  semantique: '8B5CF6',
  cyan: '22D3EE',
  lexical: 'F59E0B',
  hybride: '10B981',
  alerte: 'FB7185',
};

const POLICE = 'Calibri';
const MONO = 'Consolas';

// --- géométrie --------------------------------------------------------------
const L = 13.333, H = 7.5;
const MARGE = 0.62;
const LARG = L - 2 * MARGE;      // 12.09
const Y_SECTION = 0.46;
const Y_TITRE = 0.78;
const Y_CONTENU = 1.92;
const Y_PIED = 6.98;

const pres = new pptxgen();
pres.layout = 'LAYOUT_WIDE';     // à faire AVANT d'ajouter la moindre diapositive
pres.author = 'Salma Karim';
pres.title = 'Moteur de recherche sémantique — soutenance';

let fondImage = null;   // rempli par preparerFond()
let numero = 0;

/* ---------------------------------------------------------------------------
   Fond : un dégradé radial discret, rendu en image.
   pptxgenjs ne sait pas produire de dégradé ; on le rastérise donc à part.
   --------------------------------------------------------------------------- */
async function preparerFond() {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080">
    <defs>
      <radialGradient id="a" cx="10%" cy="0%" r="70%">
        <stop offset="0%" stop-color="#8B5CF6" stop-opacity="0.22"/>
        <stop offset="100%" stop-color="#8B5CF6" stop-opacity="0"/>
      </radialGradient>
      <radialGradient id="b" cx="93%" cy="6%" r="60%">
        <stop offset="0%" stop-color="#22D3EE" stop-opacity="0.14"/>
        <stop offset="100%" stop-color="#22D3EE" stop-opacity="0"/>
      </radialGradient>
    </defs>
    <rect width="1920" height="1080" fill="#080A0F"/>
    <rect width="1920" height="1080" fill="url(#a)"/>
    <rect width="1920" height="1080" fill="url(#b)"/>
  </svg>`;
  // 1280x720 suffit largement : le fond est un dégradé lisse, sans détail.
  // pptxgenjs recopie l'image sur CHAQUE diapositive, donc chaque kilo-octet
  // économisé ici l'est vingt-six fois.
  const buf = await sharp(Buffer.from(svg))
    .resize(1280, 720)
    .png({ compressionLevel: 9, quality: 90 })
    .toBuffer();
  fondImage = 'image/png;base64,' + buf.toString('base64');
}

/* ---------------------------------------------------------------------------
   Briques d'affichage
   --------------------------------------------------------------------------- */

function nouvelleDiapo(notes) {
  numero += 1;
  const s = pres.addSlide();
  s.background = { data: fondImage };
  if (notes) s.addNotes(notes);
  return s;
}

function pied(s, titreCourt) {
  s.addText(titreCourt, {
    x: MARGE, y: Y_PIED, w: 8, h: 0.3, isTextBox: true, margin: 0,
    fontSize: 9, color: C.texteFaible, fontFace: POLICE, valign: 'middle',
  });
  s.addText(String(numero).padStart(2, '0') + ' / 26', {
    x: L - MARGE - 2, y: Y_PIED, w: 2, h: 0.3, isTextBox: true, margin: 0,
    fontSize: 9, color: C.texteFaible, fontFace: MONO, align: 'right', valign: 'middle',
  });
}

// Pastille de couleur : le motif répété du support (jamais de bande d'accent).
function pastille(s, x, y, couleur, diametre = 0.15) {
  s.addShape(pres.ShapeType.ellipse, {
    x, y, w: diametre, h: diametre, fill: { color: couleur }, line: { width: 0 },
  });
}

function enTete(s, section, titre, couleurSection = C.semantique) {
  pastille(s, MARGE, Y_SECTION + 0.045, couleurSection, 0.13);
  s.addText(section.toUpperCase(), {
    x: MARGE + 0.24, y: Y_SECTION - 0.04, w: LARG - 0.24, h: 0.3, isTextBox: true, margin: 0,
    fontSize: 10.5, bold: true, color: couleurSection, fontFace: POLICE,
    charSpacing: 1.6, valign: 'middle',
  });
  s.addText(titre, {
    x: MARGE, y: Y_TITRE, w: LARG, h: 0.95, isTextBox: true, margin: 0,
    fontSize: 34, bold: true, color: C.texte, fontFace: POLICE, valign: 'top',
  });
}

// Titre composé de fragments colorés (pour souligner un mot sans surlignage).
function enTeteRiche(s, section, fragments, couleurSection = C.semantique) {
  pastille(s, MARGE, Y_SECTION + 0.045, couleurSection, 0.13);
  s.addText(section.toUpperCase(), {
    x: MARGE + 0.24, y: Y_SECTION - 0.04, w: LARG - 0.24, h: 0.3, isTextBox: true, margin: 0,
    fontSize: 10.5, bold: true, color: couleurSection, fontFace: POLICE,
    charSpacing: 1.6, valign: 'middle',
  });
  s.addText(fragments.map(f => ({
    text: f.t, options: { fontSize: 34, bold: true, color: f.c || C.texte, fontFace: POLICE },
  })), {
    x: MARGE, y: Y_TITRE, w: LARG, h: 0.95, isTextBox: true, margin: 0, valign: 'top',
  });
}

function ombre() {
  // Objet neuf à chaque appel : pptxgenjs modifie les options sur place.
  return { type: 'outer', color: '000000', blur: 10, offset: 3, angle: 90, opacity: 0.35 };
}

/**
 * Carte de contenu. `accent` colore la pastille et le titre — jamais un liseré
 * latéral, qui ferait « gabarit automatique ».
 */
function carte(s, o) {
  s.addShape(pres.ShapeType.roundRect, {
    x: o.x, y: o.y, w: o.w, h: o.h, rectRadius: 0.08,
    fill: { color: o.fond || C.surface },
    line: { color: o.bordure || C.bordure, width: 1 },
    shadow: ombre(),
  });

  let curseur = o.y + 0.2;
  const xTexte = o.x + 0.26;
  const wTexte = o.w - 0.52;

  if (o.sur) {
    s.addText(o.sur.toUpperCase(), {
      x: xTexte, y: curseur, w: wTexte, h: 0.22, isTextBox: true, margin: 0,
      fontSize: 9, bold: true, color: C.texteFaible, fontFace: POLICE,
      charSpacing: 1.2, valign: 'middle',
    });
    curseur += 0.26;
  }

  if (o.titre) {
    if (o.accent) {
      pastille(s, xTexte, curseur + 0.075, o.accent, 0.13);
    }
    s.addText(o.titre, {
      x: o.accent ? xTexte + 0.22 : xTexte, y: curseur,
      w: o.accent ? wTexte - 0.22 : wTexte, h: o.hTitre || 0.32, isTextBox: true, margin: 0,
      fontSize: o.tailleTitre || 15, bold: true, color: C.texte, fontFace: POLICE, valign: 'top',
    });
    // hTitre permet de reserver la place d'un titre qui passe a la ligne :
    // sans lui, le texte du dessous vient chevaucher la seconde ligne.
    curseur += o.hTitre || ((o.tailleTitre && o.tailleTitre > 15) ? 0.42 : 0.34);
  }

  if (o.texte) {
    s.addText(o.texte, {
      x: xTexte, y: curseur, w: wTexte, h: o.y + o.h - curseur - 0.16,
      isTextBox: true, margin: 0,
      fontSize: o.taille || 12, color: C.texteDoux, fontFace: POLICE,
      lineSpacingMultiple: 1.22, valign: 'top',
    });
  }

  if (o.liste) {
    s.addText(o.liste.map((item, i) => ({
      text: item.t !== undefined ? item.t : item,
      options: {
        bullet: true, breakLine: i < o.liste.length - 1,
        color: (item.c) || C.texteDoux, bold: !!item.g,
        paraSpaceAfter: 6,
      },
    })), {
      x: xTexte, y: curseur, w: wTexte, h: o.y + o.h - curseur - 0.16,
      isTextBox: true, margin: 0,
      fontSize: o.taille || 12, fontFace: POLICE, lineSpacingMultiple: 1.15, valign: 'top',
    });
  }
}

/** Grand chiffre isolé : le format qui se lit depuis le fond de la salle. */
function chiffre(s, o) {
  s.addShape(pres.ShapeType.roundRect, {
    x: o.x, y: o.y, w: o.w, h: o.h || 1.1, rectRadius: 0.08,
    fill: { color: C.surface }, line: { color: C.bordure, width: 1 }, shadow: ombre(),
  });
  s.addText(o.valeur, {
    x: o.x + 0.2, y: o.y + 0.14, w: o.w - 0.4, h: 0.5, isTextBox: true, margin: 0,
    fontSize: o.taille || 28, bold: true, color: o.accent || C.texte,
    fontFace: MONO, valign: 'middle',
  });
  s.addText(o.legende, {
    x: o.x + 0.2, y: o.y + 0.64, w: o.w - 0.4, h: (o.h || 1.1) - 0.78, isTextBox: true, margin: 0,
    fontSize: 10, color: C.texteFaible, fontFace: POLICE, lineSpacingMultiple: 1.1, valign: 'top',
  });
}

/** Encadré de mise en relief : fond légèrement plus clair, pastille d'accent. */
function encadre(s, o) {
  s.addShape(pres.ShapeType.roundRect, {
    x: o.x, y: o.y, w: o.w, h: o.h, rectRadius: 0.08,
    fill: { color: o.fond || C.surfaceHaute },
    line: { color: o.accent || C.semantique, width: 1.25 },
    shadow: ombre(),
  });
  let curseur = o.y + 0.2;
  if (o.sur) {
    pastille(s, o.x + 0.26, curseur + 0.03, o.accent || C.semantique, 0.13);
    s.addText(o.sur.toUpperCase(), {
      x: o.x + 0.48, y: curseur - 0.03, w: o.w - 0.74, h: 0.24, isTextBox: true, margin: 0,
      fontSize: 9, bold: true, color: o.accent || C.semantique, fontFace: POLICE,
      charSpacing: 1.2, valign: 'middle',
    });
    curseur += 0.3;
  }
  s.addText(o.texte, {
    x: o.x + 0.26, y: curseur, w: o.w - 0.52, h: o.y + o.h - curseur - 0.16,
    isTextBox: true, margin: 0,
    fontSize: o.taille || 12.5, color: C.texte, fontFace: POLICE,
    lineSpacingMultiple: 1.25, valign: 'top',
  });
}

/** Maillon d'une chaîne de traitement. */
function maillon(s, o) {
  s.addShape(pres.ShapeType.roundRect, {
    x: o.x, y: o.y, w: o.w, h: o.h, rectRadius: 0.07,
    fill: { color: C.surface }, line: { color: C.bordure, width: 1 }, shadow: ombre(),
  });
  s.addText(o.num, {
    x: o.x + 0.16, y: o.y + 0.12, w: o.w - 0.32, h: 0.2, isTextBox: true, margin: 0,
    fontSize: 8.5, bold: true, color: o.accent, fontFace: MONO, valign: 'middle',
  });
  s.addText(o.nom, {
    x: o.x + 0.16, y: o.y + 0.33, w: o.w - 0.32, h: 0.3, isTextBox: true, margin: 0,
    fontSize: 12, bold: true, color: C.texte, fontFace: POLICE, valign: 'top',
  });
  s.addText(o.det, {
    x: o.x + 0.16, y: o.y + 0.63, w: o.w - 0.32, h: o.h - 0.75, isTextBox: true, margin: 0,
    fontSize: 9.5, color: C.texteFaible, fontFace: POLICE, lineSpacingMultiple: 1.1, valign: 'top',
  });
}

function chaine(s, y, hauteur, etapes) {
  const gap = 0.34;
  const w = (LARG - gap * (etapes.length - 1)) / etapes.length;
  etapes.forEach((e, i) => {
    const x = MARGE + i * (w + gap);
    maillon(s, { x, y, w, h: hauteur, ...e });
    if (i < etapes.length - 1) {
      s.addText('▶', {
        x: x + w, y: y + hauteur / 2 - 0.15, w: gap, h: 0.3, isTextBox: true, margin: 0,
        fontSize: 11, color: C.texteFaible, fontFace: POLICE, align: 'center', valign: 'middle',
      });
    }
  });
}

/** Tableau sobre : pas de quadrillage, une ligne de séparation par rangée. */
function tableau(s, o) {
  const lignes = [
    o.entetes.map(t => ({
      text: t,
      options: {
        bold: true, color: C.texteFaible, fontSize: 9.5, fontFace: POLICE,
        charSpacing: 1, fill: { color: C.fond },
        align: t.__align || 'left',
      },
    })),
    ...o.rangees.map(r => r.map(cellule => {
      const est = typeof cellule === 'object' && cellule !== null;
      return {
        text: est ? cellule.t : cellule,
        options: {
          color: est && cellule.c ? cellule.c : C.texteDoux,
          bold: est ? !!cellule.g : false,
          fontSize: o.taille || 11.5,
          fontFace: est && cellule.m ? MONO : POLICE,
          align: est && cellule.a ? cellule.a : 'left',
          fill: { color: C.surface },
        },
      };
    })),
  ];

  s.addTable(lignes, {
    x: o.x, y: o.y, w: o.w, colW: o.colonnes,
    border: [
      { type: 'none' }, { type: 'none' },
      { type: 'solid', color: C.bordure, pt: 1 }, { type: 'none' },
    ],
    rowH: o.hauteurLigne || 0.34,
    margin: [4, 8, 4, 8],
    valign: 'middle',
  });
}

/** Histogramme groupé, aux couleurs des moteurs. */
function histogramme(s, o) {
  s.addShape(pres.ShapeType.roundRect, {
    x: o.x, y: o.y, w: o.w, h: o.h, rectRadius: 0.08,
    fill: { color: C.surface }, line: { color: C.bordure, width: 1 }, shadow: ombre(),
  });
  s.addChart(pres.ChartType.bar, o.series, {
    x: o.x + 0.14, y: o.y + 0.12, w: o.w - 0.28, h: o.h - 0.24,
    barDir: 'col', barGapWidthPct: 55, barGrouping: 'clustered',
    chartColors: o.couleurs,
    showLegend: true, legendPos: 't', legendColor: C.texteDoux, legendFontSize: 10,
    showValue: true, dataLabelPosition: 'outEnd', dataLabelColor: C.texteDoux,
    dataLabelFontSize: 9, dataLabelFormatCode: o.format || '0.00',
    valAxisMaxVal: o.max !== undefined ? o.max : 1,
    valAxisMinVal: 0,
    valAxisLabelColor: C.texteFaible, valAxisLabelFontSize: 9,
    valAxisLabelFormatCode: o.formatAxe || '0.0',
    catAxisLabelColor: C.texteDoux, catAxisLabelFontSize: 9.5,
    valGridLine: { color: C.bordure, size: 1 },
    catGridLine: { style: 'none' },
    valAxisLineShow: false, catAxisLineShow: false,
    plotArea: { fill: { color: C.surface } },
    chartArea: { fill: { color: C.surface }, border: { pt: 0, color: C.surface } },
  });
}

/* ===========================================================================
   Les 26 diapositives
   =========================================================================== */

async function construire() {
  await preparerFond();

  // ---- 01 — titre --------------------------------------------------------
  {
    const s = nouvelleDiapo(
      "Bonjour. Je vais vous présenter la conception et le développement d'un moteur de recherche sémantique appliqué à un corpus d'articles scientifiques.\n\n" +
      "Le fil conducteur tient en une phrase : je ne vais pas essayer de vous montrer que le sémantique bat le lexical — les mesures disent autre chose, de plus solide. Je vais vous montrer où chacun gagne, et pourquoi cela mène à les combiner.");
    pastille(s, MARGE, 1.62, C.semantique, 0.15);
    s.addText("PROJET DE FIN D'ANNÉE  ·  INFORMATIQUE & INTELLIGENCE ARTIFICIELLE", {
      x: MARGE + 0.26, y: 1.55, w: LARG, h: 0.3, isTextBox: true, margin: 0,
      fontSize: 11, bold: true, color: C.semantique, fontFace: POLICE, charSpacing: 1.6, valign: 'middle',
    });
    s.addText([
      { text: "Conception et développement d'un\n", options: { color: C.texte } },
      { text: 'moteur de recherche sémantique\n', options: { color: C.semantique } },
      { text: 'basé sur le NLP', options: { color: C.texte } },
    ], {
      x: MARGE, y: 2.05, w: LARG, h: 2.1, isTextBox: true, margin: 0,
      fontSize: 44, bold: true, fontFace: POLICE, lineSpacingMultiple: 1.06, valign: 'top',
    });
    s.addText("Retrouver un article scientifique à partir d'une question posée en français, en arabe ou en anglais — sur un corpus entièrement anglophone.", {
      x: MARGE, y: 4.55, w: 8.4, h: 0.7, isTextBox: true, margin: 0,
      fontSize: 14.5, color: C.texteDoux, fontFace: POLICE, lineSpacingMultiple: 1.25, valign: 'top',
    });

    const infos = [
      ['Étudiante', 'Salma Karim'],
      ['Encadrant', 'M. Achraf Zahid'],
      ['Année universitaire', '2026 – 2027'],
    ];
    infos.forEach((info, i) => {
      const x = MARGE + i * 3.1;
      s.addText(info[0], {
        x, y: 5.42, w: 2.9, h: 0.24, isTextBox: true, margin: 0,
        fontSize: 10, color: C.texteFaible, fontFace: POLICE, valign: 'middle',
      });
      s.addText(info[1], {
        x, y: 5.66, w: 2.9, h: 0.3, isTextBox: true, margin: 0,
        fontSize: 14, bold: true, color: C.texte, fontFace: POLICE, valign: 'middle',
      });
    });
    pied(s, 'Page de titre');
  }

  // ---- 02 — le problème --------------------------------------------------
  {
    const s = nouvelleDiapo(
      "Je commence par le résultat, pas par la théorie.\n\n" +
      "Voici une question posée en arabe. Voici le premier article renvoyé, en anglais. Les deux ne partagent pas un seul caractère — ils ne partagent même pas l'alphabet.\n\n" +
      "Un moteur qui compare des mots est structurellement incapable de faire ce rapprochement. Ce n'est pas une question de réglage : le score est nul, il n'y a rien à optimiser.\n\n" +
      "Toute la question du projet est là : comment chercher par le sens plutôt que par les mots.");
    enTete(s, 'Le problème', 'Une question. Un résultat. Zéro mot en commun.');

    carte(s, {
      x: MARGE, y: Y_CONTENU, w: 5.85, h: 1.7, sur: 'la question posée',
      titre: 'كشف الاحتيال المصرفي باستخدام التعلم الآلي', tailleTitre: 17,
      texte: "« détection de la fraude bancaire par apprentissage automatique »", taille: 11.5,
    });
    chiffre(s, { x: MARGE, y: 3.92, w: 2.8, h: 1.25, valeur: '0,837', legende: 'similarité cosinus du 1er résultat', accent: C.semantique });
    chiffre(s, { x: MARGE + 3.05, y: 3.92, w: 2.8, h: 1.25, valeur: '0', legende: 'résultat renvoyé par la baseline BM25', accent: C.lexical });

    carte(s, {
      x: MARGE + 6.24, y: Y_CONTENU, w: 5.85, h: 2.15, accent: C.semantique,
      sur: 'premier résultat — corpus anglophone',
      titre: 'Shapley Value-Guided Adaptive Ensemble Learning for Explainable Financial Fraud Detection', tailleTitre: 13, hTitre: 0.7,
      texte: "Aucun caractère commun avec la question posée.", taille: 11.5,
    });
    encadre(s, {
      x: MARGE + 6.24, y: 4.27, w: 5.85, h: 1.55, sur: 'ce que cela implique', accent: C.semantique,
      texte: "Une recherche par mots-clés ne peut pas trouver ce document. Le score n'est pas faible : il est nul, et aucun réglage n'y changerait rien.",
    });
    pied(s, 'Le problème en un exemple');
  }

  // ---- 03 — lexical vs sémantique ---------------------------------------
  {
    const s = nouvelleDiapo(
      "Deux façons de représenter un texte.\n\n" +
      "À gauche, la recherche lexicale : un document est un sac de mots. On compare des chaînes de caractères, pondérées par leur rareté. C'est rapide, gratuit, et c'est la référence du domaine depuis les années 1990.\n\n" +
      "À droite, la recherche sémantique : un texte devient un point dans un espace à 384 dimensions. Deux textes qui veulent dire la même chose se retrouvent au même endroit — même sans mot commun, même dans deux langues différentes.\n\n" +
      "L'analogie : la latitude et la longitude. Deux villes proches ont des coordonnées proches. Ici, deux sens proches ont des coordonnées proches.");
    enTete(s, 'Contexte', 'Deux manières de représenter un texte');

    carte(s, {
      x: MARGE, y: Y_CONTENU, w: 5.85, h: 2.65, accent: C.lexical,
      sur: 'approche lexicale · BM25', titre: 'Un document est un sac de mots',
      liste: [
        'Rapide, sans modèle, sans entraînement',
        "Explicable par construction : on voit les mots qui ont compté",
        { t: 'Aucun mot commun → score nul. Ni synonyme, ni reformulation, ni traduction', c: C.lexical, g: true },
      ],
    });
    carte(s, {
      x: MARGE + 6.24, y: Y_CONTENU, w: 5.85, h: 2.65, accent: C.semantique,
      sur: 'approche sémantique · Sentence-BERT', titre: "Un document est un point dans l'espace",
      liste: [
        "Trouve sans partager un seul mot",
        "Espace commun à une centaine de langues",
        { t: "Opaque : rien n'indique pourquoi un document remonte — d'où le travail d'explication", c: C.semantique, g: true },
      ],
    });
    encadre(s, {
      x: MARGE, y: 4.86, w: LARG, h: 1.5, sur: "l'image mentale", accent: C.cyan,
      texte: "Chaque ville a une latitude et une longitude : deux nombres qui encodent sa position, et deux villes proches ont des coordonnées proches. Ce projet fait la même chose avec le sens. Chercher devient alors une opération géométrique.",
      taille: 13,
    });
    pied(s, 'Lexical contre sémantique');
  }

  // ---- 04 — objectifs ----------------------------------------------------
  {
    const s = nouvelleDiapo(
      "Le cahier des charges fixait sept conditions minimales de validation. Les voici, toutes remplies.\n\n" +
      "Je souligne la dernière, parce que c'est celle qui décide si le projet a un sens : montrer au moins un cas où la recherche sémantique retrouve un document pertinent sans correspondance lexicale évidente.\n\n" +
      "Dans ce projet, ce cas n'est pas une anecdote choisie à la main : il se produit sur les vingt requêtes arabes du jeu d'évaluation, et l'interface le détecte automatiquement.");
    enTete(s, 'Objectifs', 'Sept conditions de validation');

    tableau(s, {
      x: MARGE, y: Y_CONTENU, w: 7.4, colonnes: [6.0, 1.4], hauteurLigne: 0.42,
      entetes: ['Condition minimale du cahier des charges', 'État'],
      rangees: [
        ['Baseline TF-IDF ou BM25 réellement implémentée', { t: 'fait', c: C.hybride, a: 'right', m: true }],
        ["Modèle d'embeddings pour la recherche sémantique", { t: 'fait', c: C.hybride, a: 'right', m: true }],
        ['Index vectoriel et mécanisme Top-K fonctionnels', { t: 'fait', c: C.hybride, a: 'right', m: true }],
        ['Interface permettant de tester le moteur', { t: 'fait', c: C.hybride, a: 'right', m: true }],
        ['Comparaison expérimentale baseline / sémantique', { t: 'fait', c: C.hybride, a: 'right', m: true }],
        ['Precision@K et Recall@K sur un jeu de test', { t: 'fait', c: C.hybride, a: 'right', m: true }],
        [{ t: 'Un cas trouvé sans correspondance lexicale', c: C.texte, g: true }, { t: '20/20', c: C.semantique, a: 'right', m: true, g: true }],
      ],
    });

    encadre(s, {
      x: MARGE + 7.8, y: Y_CONTENU, w: 4.29, h: 1.75, sur: 'au-delà du minimum', accent: C.hybride,
      texte: "Trois extensions facultatives sont implémentées et mesurées : recherche hybride par fusion de rangs, filtres sur métadonnées, et mise en évidence du passage le plus proche.",
      taille: 12,
    });
    chiffre(s, { x: MARGE + 7.8, y: 4.0, w: 2.02, h: 1.15, valeur: '47', legende: 'tests automatiques, tous verts', accent: C.semantique });
    chiffre(s, { x: MARGE + 10.07, y: 4.0, w: 2.02, h: 1.15, valeur: '3', legende: 'moteurs sur le même index', accent: C.cyan });
    pied(s, 'Objectifs et périmètre');
  }

  // ---- 05 — architecture -------------------------------------------------
  {
    const s = nouvelleDiapo(
      "Le système a deux phases, et il est essentiel de ne pas les confondre.\n\n" +
      "L'indexation est hors ligne : lente, exécutée une seule fois. Douze minutes de calcul sur un processeur sans carte graphique.\n\n" +
      "La recherche est en ligne : quelques dizaines de millisecondes, à chaque question.\n\n" +
      "Le mot le plus important de ces deux schémas est « même ». Si j'indexe avec un modèle et que je cherche avec un autre, les deux ensembles de vecteurs vivent dans des espaces différents et les résultats deviennent du pur hasard — sans qu'aucune erreur ne s'affiche. C'est le piège numéro un du domaine, et c'est pour ça que le code n'a qu'un seul module qui connaît le modèle.");
    enTete(s, 'Architecture', 'Deux phases, un seul espace vectoriel');

    s.addText("Chaîne d'indexation  —  hors ligne, une seule fois", {
      x: MARGE, y: 1.85, w: LARG, h: 0.28, isTextBox: true, margin: 0,
      fontSize: 13, bold: true, color: C.texte, fontFace: POLICE, valign: 'middle',
    });
    chaine(s, 2.2, 1.15, [
      { num: '01', nom: 'Corpus arXiv', det: '8 569 résumés, API publique', accent: C.semantique },
      { num: '02', nom: 'Prétraitement', det: 'LaTeX simplifié, découpage en passages', accent: C.semantique },
      { num: '03', nom: 'Embeddings', det: 'préfixe passage:, 384 dimensions', accent: C.semantique },
      { num: '04', nom: 'Index FAISS', det: 'vecteurs normalisés, écrits sur disque', accent: C.semantique },
    ]);

    s.addText('Chaîne de recherche  —  en ligne, à chaque question', {
      x: MARGE, y: 3.6, w: LARG, h: 0.28, isTextBox: true, margin: 0,
      fontSize: 13, bold: true, color: C.texte, fontFace: POLICE, valign: 'middle',
    });
    chaine(s, 3.95, 1.15, [
      { num: '01', nom: 'Question', det: 'français, arabe ou anglais', accent: C.cyan },
      { num: '02', nom: 'Le même encodeur', det: 'préfixe query: cette fois', accent: C.cyan },
      { num: '03', nom: 'Plus proches voisins', det: 'FAISS, ordre de la milliseconde', accent: C.cyan },
      { num: '04', nom: 'Regroupement', det: 'un article, une seule ligne', accent: C.cyan },
    ]);

    encadre(s, {
      x: MARGE, y: 5.35, w: LARG, h: 1.35, sur: 'le piège numéro un du domaine', accent: C.alerte,
      texte: "Indexer avec un modèle et chercher avec un autre place les vecteurs dans deux espaces différents : les résultats deviennent aléatoires, sans aucun message d'erreur. Un seul module du projet connaît le modèle — c'est ce qui rend l'erreur impossible.",
      taille: 12.5,
    });
    pied(s, 'Architecture — les deux phases');
  }

  // ---- 06 — corpus -------------------------------------------------------
  {
    const s = nouvelleDiapo(
      "Le corpus vient de l'API publique d'arXiv : 8 569 articles uniques répartis sur huit catégories d'informatique et de statistiques.\n\n" +
      "Trois raisons de ce choix. D'abord c'est un corpus réel, pas un jeu de données jouet. Ensuite il est entièrement en anglais, ce qui est exactement la condition qui rend la démonstration multilingue significative. Enfin il est reconstructible : un script le retélécharge à l'identique, en respectant le délai de trois secondes qu'impose l'API.");
    enTete(s, 'Étape 1', 'Un corpus réel, reconstructible');

    const stats = [
      { v: '8 569', l: 'articles uniques', c: C.semantique },
      { v: '10 897', l: 'passages indexés', c: C.semantique },
      { v: '8', l: 'catégories arXiv', c: C.cyan },
      { v: '100 %', l: 'anglophone', c: C.cyan },
    ];
    stats.forEach((st, i) => {
      chiffre(s, { x: MARGE + i * 1.85, y: Y_CONTENU, w: 1.68, h: 1.15, valeur: st.v, legende: st.l, accent: st.c, taille: 22 });
    });

    carte(s, {
      x: MARGE, y: 3.32, w: 7.1, h: 2.05, sur: 'les huit catégories interrogées',
      liste: [
        'cs.LG apprentissage · cs.CL langage · cs.CV vision · cs.AI',
        "cs.CR sécurité · cs.IR recherche d'information · cs.NE · stat.ML",
        'Chaque document porte identifiant, titre, résumé, auteurs, date et catégories',
      ],
      taille: 12,
    });

    carte(s, {
      x: MARGE + 7.5, y: Y_CONTENU, w: 4.59, h: 3.17, sur: 'pourquoi arXiv', accent: C.semantique,
      titre: 'Trois raisons', tailleTitre: 14,
      texte: "Réel et riche. Des résumés scientifiques denses, avec du vocabulaire technique rare — le terrain le plus favorable à BM25, donc une comparaison honnête.\n\n" +
             "Entièrement anglophone. C'est ce qui rend la démonstration multilingue significative : aucun mot français ou arabe n'existe dans le corpus.\n\n" +
             "Reconstructible. Un script le retélécharge à l'identique.",
      taille: 12,
    });
    pied(s, 'Le corpus');
  }

  // ---- 07 — prétraitement ------------------------------------------------
  {
    const s = nouvelleDiapo(
      "Le prétraitement est volontairement léger : je ne supprime pas les mots vides et je ne lemmatise pas avant l'encodage, parce qu'un modèle de type BERT a été entraîné sur du texte naturel — le mutiler dégraderait sa représentation. La lemmatisation resterait pertinente pour un pipeline TF-IDF classique, pas ici.\n\n" +
      "Maintenant la décision la plus importante de tout le projet.\n\n" +
      "L'évaluation automatique utilise le titre d'un article comme requête. Si le titre était aussi présent dans le texte indexé, BM25 le retrouverait par simple correspondance exacte, et la comparaison entre les deux moteurs n'aurait plus aucun sens. C'est ce qu'on appelle une fuite de données.\n\n" +
      "J'indexe donc le résumé seul. Le titre reste une métadonnée d'affichage. C'est un paramètre explicite du fichier de configuration.");
    enTete(s, 'Étape 2', 'Prétraitement léger — et une décision qui change tout');

    carte(s, {
      x: MARGE, y: Y_CONTENU, w: 5.85, h: 2.15, sur: 'ce que fait le pipeline',
      liste: [
        'Simplification LaTeX — les formules deviennent un espace',
        "Normalisation des espaces — un texte d'un seul tenant",
        'Découpage en passages — 220 mots, chevauchement de 40',
        "Regroupement par article — une seule ligne, au meilleur score",
      ],
      taille: 11.5,
    });
    carte(s, {
      x: MARGE, y: 4.3, w: 5.85, h: 1.9, sur: 'ce que le pipeline ne fait pas, et pourquoi',
      texte: "Ni suppression des mots vides, ni lemmatisation avant l'encodage : Sentence-BERT a été entraîné sur du texte naturel. Le mutiler dégraderait sa représentation. Ces opérations restent pertinentes pour un pipeline TF-IDF — elles ne le sont pas ici.",
      taille: 12,
    });

    encadre(s, {
      x: MARGE + 6.24, y: Y_CONTENU, w: 5.85, h: 4.28, accent: C.alerte,
      sur: 'la décision méthodologique du projet',
      texte: "Le titre n'est pas indexé.\n\n" +
             "L'évaluation utilise le titre d'un article comme requête. Si ce titre figurait aussi dans le texte indexé, BM25 le retrouverait par correspondance exacte et la comparaison n'aurait plus aucune valeur.\n\n" +
             "C'est une fuite de données classique. L'éviter fait partie du travail — et coûte au moteur sémantique autant qu'à BM25.\n\n" +
             "INCLURE_TITRE_DANS_INDEX = False",
      taille: 13,
    });
    pied(s, 'Prétraitement et fuite de données');
  }

  // ---- 08 — embeddings ---------------------------------------------------
  {
    const s = nouvelleDiapo(
      "Le modèle est multilingual-e5-small. Trois raisons.\n\n" +
      "Un : le multilingue est structurel, pas décoratif. Le modèle a été entraîné sur des paires de phrases traduites, donc « fraud detection », « détection de fraude » et l'équivalent arabe se retrouvent au même endroit de l'espace. Ce n'est pas de la traduction, c'est un espace partagé.\n\n" +
      "Deux : il tient sur un processeur ordinaire. 118 millions de paramètres, 384 dimensions, et j'ai mesuré : 10 897 passages encodés en douze minutes sur un portable sans carte graphique.\n\n" +
      "Trois : il est entraîné spécifiquement pour la recherche, sur des paires question-document.\n\n" +
      "Un piège à connaître : la famille E5 exige les préfixes query et passage. Les oublier dégrade nettement la qualité sans provoquer la moindre erreur visible.");
    enTete(s, 'Étape 3', 'Le modèle : multilingual-e5-small');

    const raisons = [
      { sur: 'raison 1', titre: 'Le multilingue est structurel',
        texte: "Entraîné sur des paires de phrases traduites : « fraud detection », « détection de fraude » et son équivalent arabe tombent au même endroit de l'espace.\n\nCe n'est pas de la traduction — c'est un espace partagé." },
      { sur: 'raison 2', titre: 'Il tient sur un CPU',
        texte: "118 M de paramètres, 384 dimensions. Mesure réelle sur un portable sans carte graphique : 10 897 passages en 12 minutes, pour un index de 16 Mo.\n\nL'étape la plus lente du projet — faite une seule fois." },
      { sur: 'raison 3', titre: 'Il est entraîné pour la recherche',
        texte: "Beaucoup de modèles comparent deux phrases de même nature. E5 est entraîné sur des paires question / document — exactement notre usage." },
    ];
    raisons.forEach((r, i) => {
      carte(s, { x: MARGE + i * 4.13, y: Y_CONTENU, w: 3.83, h: 2.95, accent: C.semantique, ...r, taille: 11.5 });
    });

    encadre(s, {
      x: MARGE, y: 5.12, w: LARG, h: 1.4, sur: 'contrepartie à connaître', accent: C.alerte,
      texte: "La famille E5 exige les préfixes query: et passage:. Les oublier dégrade nettement la qualité sans provoquer la moindre erreur visible. Une requête et un document ne reçoivent volontairement pas le même préfixe.",
      taille: 12.5,
    });
    pied(s, "Le modèle d'embeddings");
  }

  // ---- 09 — index FAISS --------------------------------------------------
  {
    const s = nouvelleDiapo(
      "FAISS répond à une seule question, mais très vite : parmi ces dix mille vecteurs, lesquels ressemblent le plus à celui-ci ?\n\n" +
      "Le choix par défaut est l'index exact. Comparaison exhaustive, donc résultat exact. Sur dix mille vecteurs, une recherche prend une milliseconde : l'approximation n'apporterait rien.\n\n" +
      "Un détail qui compte : je normalise tous les vecteurs à une longueur de un. Le produit scalaire devient alors exactement la similarité cosinus. Autrement dit, je mesure un angle — donc le sens — et pas une longueur, qui refléterait la taille du texte.\n\n" +
      "L'index approximatif IVF est aussi implémenté, et je le mesure. À cette échelle, il ne se justifie pas. Le mesurer vaut mieux que le citer.");
    enTete(s, 'Étape 4', 'FAISS — trouver les plus proches voisins');

    carte(s, {
      x: MARGE, y: Y_CONTENU, w: 5.85, h: 1.75, accent: C.semantique,
      sur: 'par défaut · IndexFlatIP', titre: 'Comparaison exhaustive, résultat exact',
      texte: "Sur 10 897 vecteurs, une recherche prend environ une milliseconde. À cette échelle, l'approximation n'apporterait rien.",
      taille: 12,
    });
    carte(s, {
      x: MARGE, y: 3.9, w: 5.85, h: 1.9, accent: C.lexical,
      sur: 'également implémenté · IndexIVFFlat', titre: 'Les vecteurs sont regroupés en quartiers',
      texte: "Seuls les quartiers les plus prometteurs sont fouillés. Plus rapide, mais approximatif : un bon voisin situé dans un quartier non visité est manqué.",
      taille: 12,
    });

    encadre(s, {
      x: MARGE + 6.24, y: Y_CONTENU, w: 5.85, h: 3.58, accent: C.cyan,
      sur: 'le détail qui rend la mesure juste',
      texte: "Tous les vecteurs sont normalisés à une longueur de 1. Le produit scalaire vaut alors exactement la similarité cosinus.\n\n" +
             "On mesure donc un angle — le sens — et non une longueur, qui ne refléterait que la taille du texte.\n\n" +
             "cos(q, d) = q · d      si  ‖q‖ = ‖d‖ = 1\n\n" +
             "Le compromis vitesse / exhaustivité est mesuré, pas cité.",
      taille: 13,
    });
    pied(s, "L'index vectoriel");
  }

  // ---- 10 — les trois moteurs -------------------------------------------
  {
    const s = nouvelleDiapo(
      "Trois moteurs, et c'est important : ils partagent le même index et les mêmes passages. Ce qui les sépare est uniquement la façon de classer, jamais ce qui a été indexé. C'est la condition pour que la comparaison veuille dire quelque chose.\n\n" +
      "Le sémantique compare des vecteurs de sens. Le lexical compare des mots. L'hybride fait voter les deux.\n\n" +
      "Le troisième mérite qu'on s'y arrête, parce que la façon de fusionner n'est pas évidente.");
    enTete(s, 'Les moteurs', 'Trois moteurs, un seul index');
    s.addText("Ce qui les sépare est uniquement la façon de classer — jamais ce qui a été indexé. C'est la condition pour que la comparaison ait un sens.", {
      x: MARGE, y: 1.76, w: 10.5, h: 0.3, isTextBox: true, margin: 0,
      fontSize: 13, color: C.texteDoux, fontFace: POLICE, valign: 'middle',
    });

    const moteurs = [
      { sur: 'sémantique', titre: 'Sentence-BERT + FAISS', accent: C.semantique,
        texte: "Encode question et documents dans un même espace de 384 dimensions, puis mesure des angles.\n\nTrouve sans partager un seul mot, y compris dans une autre langue." },
      { sur: 'lexical', titre: 'BM25 Okapi', accent: C.lexical,
        texte: "Pondère les mots partagés : un terme rare compte plus, un document long est pénalisé.\n\nRapide, gratuit, sans modèle. Liste vide si aucun mot ne correspond." },
      { sur: 'hybride', titre: 'Fusion RRF', accent: C.hybride,
        texte: "Fusionne les deux classements en n'utilisant que les rangs.\n\nUn document bien classé par les deux passe devant un document premier chez un seul." },
    ];
    moteurs.forEach((m, i) => {
      carte(s, { x: MARGE + i * 4.13, y: 2.25, w: 3.83, h: 2.75, ...m, taille: 11.5 });
    });

    encadre(s, {
      x: MARGE, y: 5.2, w: LARG, h: 1.32, sur: 'conséquence de conception', accent: C.hybride,
      texte: "Les trois exposent exactement la même interface : chercher(requête, k). L'API, l'interface et le script d'évaluation les utilisent sans une seule ligne de code spécifique à l'un d'eux.",
      taille: 12.5,
    });
    pied(s, 'Les trois moteurs');
  }

  // ---- 11 — RRF ----------------------------------------------------------
  {
    const s = nouvelleDiapo(
      "Voici le problème. Un score BM25 vaut typiquement entre zéro et quarante, sans borne supérieure, et il dépend du corpus. Un cosinus vaut entre moins un et un. Les additionner n'a aucun sens : l'échelle de BM25 écraserait l'autre.\n\n" +
      "On pourrait normaliser les scores. Mais la normalisation dépendrait alors du lot de résultats renvoyé, donc de la requête, et deux requêtes ne seraient plus comparables entre elles.\n\n" +
      "La Reciprocal Rank Fusion contourne le problème en n'utilisant que les rangs, qui sont dans la même unité par construction.\n\n" +
      "La constante soixante amortit le sommet du classement : sans elle, la première place vaudrait deux fois la deuxième, ce qui donnerait à un seul moteur un droit de veto sur la fusion.\n\n" +
      "Et le cas limite est déjà traité : quand BM25 ne renvoie rien, la somme se réduit à un seul terme, et la fusion rend le classement sémantique inchangé.");
    enTeteRiche(s, 'Extension · recherche hybride',
      [{ t: 'Fusionner des ' }, { t: 'rangs', c: C.hybride }, { t: ', pas des scores' }], C.hybride);

    carte(s, {
      x: MARGE, y: Y_CONTENU, w: 5.85, h: 2.15, accent: C.lexical, sur: 'le problème',
      texte: "Un score BM25 vaut entre 0 et 40, sans borne supérieure, et dépend du corpus. Un cosinus vaut entre −1 et 1. Les additionner reviendrait à laisser BM25 décider seul.\n\n" +
             "Normaliser ne marche pas non plus : la normalisation dépendrait du lot renvoyé, donc de la requête.",
      taille: 12,
    });
    encadre(s, {
      x: MARGE + 6.24, y: Y_CONTENU, w: 5.85, h: 2.15, accent: C.hybride, sur: 'reciprocal rank fusion',
      texte: "score(d)  =  Σ  1 / (60 + rang)\n\n" +
             "Seuls les rangs interviennent — ils sont dans la même unité par construction. La constante 60 amortit le sommet : sans elle, la 1re place vaudrait deux fois la 2e, donnant à un seul moteur un droit de veto.",
      taille: 12.5,
    });
    carte(s, {
      x: MARGE, y: 4.35, w: 5.85, h: 1.75, accent: C.hybride, sur: 'le comportement voulu',
      texte: "Un document 2e chez les deux moteurs passe devant un document 1er chez un seul. L'accord entre deux méthodes indépendantes est un signal de pertinence.",
      taille: 12,
    });
    carte(s, {
      x: MARGE + 6.24, y: 4.35, w: 5.85, h: 1.75, accent: C.hybride, sur: 'le cas limite, déjà traité',
      texte: "Quand BM25 ne renvoie rien — toutes les requêtes arabes — la somme se réduit à un seul terme et la fusion rend le classement sémantique inchangé. Aucun traitement particulier.",
      taille: 12,
    });
    pied(s, 'Pourquoi fusionner les rangs');
  }

  // ---- 12 — l'application ------------------------------------------------
  {
    const s = nouvelleDiapo(
      "L'architecture logicielle sépare strictement le moteur de l'affichage.\n\n" +
      "Le moteur est une bibliothèque Python. FastAPI le transforme en service web. L'index et le modèle sont chargés une seule fois au démarrage : chaque requête ne paie plus que le coût de la recherche. Sans ce préchauffage, le tout premier utilisateur attendrait quinze secondes — je l'ai mesuré, puis corrigé.\n\n" +
      "L'interface Streamlit ne sait rien de Sentence-BERT ni de FAISS : elle appelle l'API. On peut changer entièrement le moteur sans toucher une ligne d'affichage.\n\n" +
      "Et l'API génère sa propre documentation interactive, sur laquelle je peux vous montrer le moteur sans passer par l'interface.");
    enTete(s, 'Étape 5', 'Une API, une interface, aucun couplage');

    chaine(s, Y_CONTENU, 1.1, [
      { num: 'moteur', nom: 'Bibliothèque Python', det: 'src/ — indexer et chercher', accent: C.semantique },
      { num: 'service', nom: 'FastAPI', det: 'index chargé une seule fois', accent: C.cyan },
      { num: 'client', nom: 'Streamlit', det: "n'appelle que des routes HTTP", accent: C.hybride },
    ]);

    tableau(s, {
      x: MARGE, y: 3.3, w: 6.6, colonnes: [2.0, 4.6], hauteurLigne: 0.4,
      entetes: ['Route', 'Ce qu\'elle apporte'],
      rangees: [
        [{ t: '/recherche', m: true, c: C.semantique }, 'un moteur, k résultats, filtres, explications'],
        [{ t: '/comparer', m: true, c: C.semantique }, { t: "plusieurs moteurs + l'analyse de leurs écarts", c: C.texte, g: true }],
        [{ t: '/facettes', m: true, c: C.semantique }, 'catégories et années réellement présentes'],
        [{ t: '/metriques', m: true, c: C.semantique }, "les résultats de l'évaluation, servis tels quels"],
      ],
    });

    encadre(s, {
      x: MARGE + 7.0, y: 3.3, w: 5.09, h: 2.9, sur: 'trois bénéfices concrets', accent: C.cyan,
      texte: "1. L'index et le modèle sont chargés une fois au démarrage. Un préchauffage explicite évite que le premier utilisateur paie les 15 secondes de chargement.\n\n" +
             "2. L'interface ignore tout du fonctionnement interne : changer de modèle ne touche pas une ligne d'affichage.\n\n" +
             "3. FastAPI génère une documentation interactive — pratique pour montrer le moteur sans l'interface.",
      taille: 11.5,
    });
    pied(s, "L'application");
  }

  // ---- 13 — l'interface --------------------------------------------------
  {
    const s = nouvelleDiapo(
      "L'interface est organisée en cinq vues, qui suivent exactement l'ordre d'une soutenance.\n\n" +
      "Recherche, pour l'usage normal. Duel, pour comparer. Démonstration, pour le scénario multilingue. Évaluation, pour les mesures. Architecture, pour le fonctionnement.\n\n" +
      "Un détail d'ergonomie : la barre de recherche est au-dessus des onglets. On tape la question une fois, et on change de point de vue sans la retaper.\n\n" +
      "Et chaque moteur garde la même couleur partout — violet, ambre, émeraude — des cartes de résultats jusqu'aux histogrammes d'évaluation.");
    enTete(s, "L'application", "Cinq vues, dans l'ordre d'une soutenance");

    const vues = [
      { n: '01', nom: 'Recherche', d: 'poser une question, choisir le moteur, filtrer, lire les résultats justifiés', c: C.semantique },
      { n: '02', nom: 'Duel', d: "la même question aux deux moteurs, et ce que chacun est seul à trouver", c: C.lexical },
      { n: '03', nom: 'Démonstration', d: 'le scénario multilingue en français, arabe et anglais', c: C.hybride },
      { n: '04', nom: 'Évaluation', d: 'les mesures du protocole expérimental, en graphiques', c: C.cyan },
      { n: '05', nom: 'Architecture', d: 'les deux chaînes et ce qui tourne derrière', c: C.semantique },
    ];
    const wv = (LARG - 4 * 0.26) / 5;
    vues.forEach((v, i) => {
      carte(s, {
        x: MARGE + i * (wv + 0.26), y: Y_CONTENU, w: wv, h: 2.3,
        sur: v.n, titre: v.nom, tailleTitre: 13.5, accent: v.c, texte: v.d, taille: 10.5,
      });
    });

    encadre(s, {
      x: MARGE, y: 4.5, w: 5.85, h: 1.6, sur: 'une question tapée une seule fois', accent: C.cyan,
      texte: "La barre de recherche est au-dessus des onglets, pas dans chacun. On pose la question, puis on change de point de vue sans la retaper.",
      taille: 12,
    });
    encadre(s, {
      x: MARGE + 6.24, y: 4.5, w: 5.85, h: 1.6, sur: 'un code couleur qui porte du sens', accent: C.semantique,
      texte: "Chaque moteur garde la même couleur partout : violet le sémantique, ambre le lexical, émeraude l'hybride — des cartes de résultats jusqu'aux histogrammes.",
      taille: 12,
    });
    pied(s, "L'interface — cinq vues");
  }

  // ---- 14 — expliquer un résultat ---------------------------------------
  {
    const s = nouvelleDiapo(
      "Un score de 0,84 affiché seul demande qu'on lui fasse confiance. J'ai donc ajouté deux justifications, de coûts très différents.\n\n" +
      "La première, gratuite : les mots partagés entre la question et le document, surlignés.\n\n" +
      "La seconde, coûteuse : le passage est redécoupé en phrases, chacune est encodée séparément, et je mets en évidence celle dont le vecteur est le plus proche de la question. Le modèle désigne lui-même ce qui a déclenché le rapprochement.\n\n" +
      "C'est la seule qui fonctionne quand il n'y a aucun mot en commun — c'est-à-dire précisément dans le cas qui justifie le projet.\n\n" +
      "Et le coût, je l'assume plutôt que de le masquer : sur un CPU, l'explication coûte environ neuf fois la recherche. C'est pour ça que la phrase clé n'est calculée que pour les cinq premiers résultats. Les mots partagés, eux, restent calculés pour tous, parce que c'est eux qui portent le signal « aucun mot en commun ».");
    enTete(s, 'Explicabilité', 'Pourquoi ce résultat, et pas un autre ?');

    tableau(s, {
      x: MARGE, y: Y_CONTENU, w: 5.85, colonnes: [1.7, 2.75, 1.4], hauteurLigne: 0.42,
      entetes: ['Justification', 'Comment', 'Coût'],
      rangees: [
        [{ t: 'Mots partagés', c: C.lexical, g: true }, 'intersection des mots significatifs', { t: 'nul', c: C.hybride, a: 'right' }],
        [{ t: 'Phrase clé', c: C.semantique, g: true }, 'chaque phrase encodée, on garde la plus proche', { t: '1 appel', c: C.lexical, a: 'right' }],
      ],
    });

    encadre(s, {
      x: MARGE, y: 3.5, w: 5.85, h: 2.55, sur: 'le cas qui vaut la démonstration', accent: C.semantique,
      texte: "Quand la question et le document ne partagent aucun mot, l'interface l'affiche d'elle-même : « aucun mot en commun — le rapprochement est purement sémantique ».\n\n" +
             "C'est la condition de validation n° 7, détectée automatiquement au lieu d'être cherchée à la main pendant la soutenance.",
      taille: 12,
    });

    carte(s, { x: MARGE + 6.24, y: Y_CONTENU, w: 5.85, h: 0.44, sur: 'le coût, mesuré et assumé' });
    chiffre(s, { x: MARGE + 6.24, y: 2.5, w: 2.8, h: 1.15, valeur: '98 ms', legende: 'la recherche', accent: C.hybride, taille: 24 });
    chiffre(s, { x: MARGE + 9.29, y: 2.5, w: 2.8, h: 1.15, valeur: '869 ms', legende: "l'explication (5 premiers)", accent: C.lexical, taille: 24 });
    carte(s, {
      x: MARGE + 6.24, y: 3.9, w: 5.85, h: 2.15,
      texte: "L'explicabilité coûte neuf fois la recherche sur un processeur sans carte graphique. D'où le plafond : la phrase clé n'est calculée que pour les résultats réellement lus.\n\n" +
             "Les mots partagés, gratuits, restent calculés pour tous — ce sont eux qui portent le signal « aucun mot en commun ».",
      taille: 12,
    });
    pied(s, 'Expliquer un résultat');
  }

  // ---- 15 — protocole d'évaluation --------------------------------------
  {
    const s = nouvelleDiapo(
      "Une démonstration réussie peut toujours être une coïncidence. J'ai donc construit trois protocoles complémentaires, sur des centaines de requêtes.\n\n" +
      "Le premier produit une vérité terrain sans aucune annotation manuelle : je prends le titre d'un article au hasard et je m'en sers comme requête. Le bon résultat est connu d'avance, c'est l'article lui-même. Cinq cents requêtes annotées gratuitement.\n\n" +
      "Le deuxième attaque directement l'argument central du projet : la même question posée en trois langues doit renvoyer approximativement les mêmes articles.\n\n" +
      "Le troisième mesure le coût : latence, taille d'index, et le compromis entre index exact et approximatif.");
    enTete(s, 'Évaluation', 'Trois protocoles, aucune annotation manuelle');
    s.addText("Une démonstration réussie peut toujours être une coïncidence. Ces protocoles mesurent ce que les moteurs retrouvent réellement, sur des centaines de requêtes.", {
      x: MARGE, y: 1.76, w: 11, h: 0.3, isTextBox: true, margin: 0,
      fontSize: 13, color: C.texteDoux, fontFace: POLICE, valign: 'middle',
    });

    const protocoles = [
      { sur: 'protocole 1 · 500 requêtes', titre: 'Titre vers résumé',
        texte: "Le titre d'un article tiré au sort sert de requête ; le bon résultat est connu d'avance — c'est l'article lui-même.\n\n500 requêtes annotées sans le moindre travail manuel.\n\nRecall@1, @5, @10 · MRR@10 · nDCG@10" },
      { sur: 'protocole 2 · 20 triplets', titre: 'Cohérence multilingue',
        texte: "La même question en français, en arabe et en anglais. Si l'espace vectoriel est indépendant de la langue, les trois doivent renvoyer les mêmes articles.\n\nAttaque directement l'argument central du projet." },
      { sur: 'protocole 3', titre: 'Coût',
        texte: "Latence médiane et 95e centile, durée de construction, taille de l'index, index exact contre index approximatif.\n\nUn moteur inutilisable en production n'est pas un bon moteur." },
    ];
    protocoles.forEach((p, i) => {
      carte(s, { x: MARGE + i * 4.13, y: 2.25, w: 3.83, h: 2.8, accent: C.semantique, ...p, taille: 11.5 });
    });

    encadre(s, {
      x: MARGE, y: 5.25, w: LARG, h: 1.3, sur: 'reproductibilité', accent: C.hybride,
      texte: "Tous les chiffres qui suivent sont régénérables par une commande. Les graines aléatoires sont fixées ; l'interface lit le fichier produit et ne recalcule jamais rien.",
      taille: 12.5,
    });
    pied(s, "Protocole d'évaluation");
  }

  // ---- 16 — résultat 1 ---------------------------------------------------
  {
    const s = nouvelleDiapo(
      "Premier résultat, et je commence par celui qui ne m'arrange pas.\n\n" +
      "Sur ce protocole, BM25 devance le moteur sémantique sur les cinq métriques. Recall@1 : 93 % contre 89,6 %. MRR : 0,953 contre 0,922.\n\n" +
      "Ce n'est pas un défaut d'implémentation, c'est le terrain de jeu naturel de BM25. Un titre partage avec son résumé des termes techniques rares — un nom de méthode, un acronyme — et faire correspondre des termes rares est exactement ce que BM25 fait le mieux.\n\n" +
      "Je pourrais présenter ces chiffres autrement. Je préfère les présenter tels quels et expliquer pourquoi, parce que la diapositive suivante montre que ce protocole ne mesure pas ce qu'on croit.");
    enTeteRiche(s, 'Résultat 1 · protocole titre → résumé',
      [{ t: 'Sur son terrain, ' }, { t: 'BM25 gagne', c: C.lexical }], C.lexical);

    histogramme(s, {
      x: MARGE, y: Y_CONTENU, w: 7.3, h: 4.3,
      couleurs: [C.semantique, C.lexical],
      series: [
        { name: 'Sémantique', labels: ['Recall@1', 'Recall@5', 'Recall@10', 'MRR@10', 'nDCG@10'], values: [0.896, 0.956, 0.964, 0.9218, 0.9323] },
        { name: 'BM25', labels: ['Recall@1', 'Recall@5', 'Recall@10', 'MRR@10', 'nDCG@10'], values: [0.930, 0.984, 0.990, 0.9531, 0.9622] },
      ],
    });

    tableau(s, {
      x: MARGE + 7.7, y: Y_CONTENU, w: 4.39, colonnes: [1.85, 0.85, 0.85, 0.84], hauteurLigne: 0.42,
      entetes: ['Moteur', 'R@1', 'R@10', 'MRR'],
      rangees: [
        [{ t: 'Sémantique', c: C.semantique }, { t: '0,896', a: 'right', m: true }, { t: '0,964', a: 'right', m: true }, { t: '0,922', a: 'right', m: true }],
        [{ t: 'BM25', c: C.lexical, g: true }, { t: '0,930', a: 'right', m: true, g: true, c: C.texte }, { t: '0,990', a: 'right', m: true, g: true, c: C.texte }, { t: '0,953', a: 'right', m: true, g: true, c: C.texte }],
      ],
    });
    encadre(s, {
      x: MARGE + 7.7, y: 3.55, w: 4.39, h: 2.7, sur: "pourquoi c'est normal", accent: C.lexical,
      texte: "Un titre partage avec son résumé des termes techniques rares — un nom de méthode, un acronyme. Faire correspondre des termes rares est précisément ce que BM25 fait le mieux.\n\n" +
             "Ce n'est pas un défaut d'implémentation : c'est son terrain de jeu naturel.",
      taille: 12,
    });
    pied(s, 'Résultat 1 — BM25 gagne');
  }

  // ---- 17 — résultat 2 : stratification ---------------------------------
  {
    const s = nouvelleDiapo(
      "Voici la diapositive la plus importante de mon analyse, et c'est une critique de mon propre protocole.\n\n" +
      "J'ai réparti les cinq cents mêmes requêtes en trois groupes, selon la part des mots de la requête effectivement présents dans le bon document. C'est la quantité dont BM25 dépend entièrement.\n\n" +
      "Regardez le groupe le plus difficile : il partage encore soixante-trois pour cent de son vocabulaire avec le bon document. Le tiers le plus dur de mon protocole est encore largement lexical.\n\n" +
      "Autrement dit : ce protocole ne descend jamais dans le régime où la correspondance de mots cesse de fonctionner. Il mesure du lexical, pas du sens.\n\n" +
      "Le reconnaître vaut mieux que de présenter les chiffres précédents comme une validation du moteur sémantique. Et cela justifie les deux protocoles suivants.");
    enTete(s, 'Résultat 2 · critique du protocole', 'Ce protocole ne mesure pas le sens', C.alerte);

    histogramme(s, {
      x: MARGE, y: Y_CONTENU, w: 7.3, h: 4.3,
      couleurs: [C.semantique, C.lexical],
      series: [
        { name: 'Sémantique', labels: ['63 % de mots communs', '83 % de mots communs', '96 % de mots communs'], values: [0.827, 0.960, 0.978] },
        { name: 'BM25', labels: ['63 % de mots communs', '83 % de mots communs', '96 % de mots communs'], values: [0.877, 0.988, 0.994] },
      ],
    });

    encadre(s, {
      x: MARGE + 7.7, y: Y_CONTENU, w: 4.39, h: 2.5, sur: "l'observation qui compte", accent: C.alerte,
      texte: "Même le tiers le plus difficile partage encore 63 % de son vocabulaire avec le bon document.\n\n" +
             "Ce protocole ne descend jamais dans le régime où la correspondance de mots cesse de fonctionner.",
      taille: 13,
    });
    carte(s, {
      x: MARGE + 7.7, y: 4.6, w: 4.39, h: 1.65,
      texte: "Le reconnaître vaut mieux que de présenter les chiffres précédents comme une validation du moteur sémantique — et cela justifie les deux protocoles suivants.",
      taille: 12,
    });
    pied(s, 'Résultat 2 — ce que le protocole ne mesure pas');
  }

  // ---- 18 — résultat 3 : appauvries -------------------------------------
  {
    const s = nouvelleDiapo(
      "Pour atteindre ce régime, j'ai retiré les trois mots les plus rares de chaque titre.\n\n" +
      "Mon hypothèse était que BM25, privé de sa signature lexicale, chuterait davantage. C'est l'inverse qui se produit : le moteur sémantique perd 0,357 de MRR, BM25 seulement 0,308.\n\n" +
      "L'exemple explique le résultat. Les mots rares n'étaient pas seulement discriminants, ils portaient le sujet. Leur retrait dégrade le sens autant que le lexique.\n\n" +
      "Et un modèle dense y est plus sensible, parce qu'il compresse la requête entière — mots vides compris — dans un vecteur unique. BM25, lui, ignore simplement les termes qui ne correspondent à rien.\n\n" +
      "Je présente ce résultat parce qu'il est contraire à mon hypothèse de départ. C'est exactement le genre de chose qu'une évaluation sert à découvrir.");
    enTeteRiche(s, 'Résultat 3 · requêtes appauvries',
      [{ t: 'Un résultat ' }, { t: "contraire à l'hypothèse", c: C.lexical }], C.lexical);

    histogramme(s, {
      x: MARGE, y: Y_CONTENU, w: 6.5, h: 4.3,
      couleurs: [C.semantique, C.lexical],
      series: [
        { name: 'Sémantique', labels: ['Requêtes complètes', 'Requêtes appauvries'], values: [0.9218, 0.5644] },
        { name: 'BM25', labels: ['Requêtes complètes', 'Requêtes appauvries'], values: [0.9531, 0.6453] },
      ],
    });

    tableau(s, {
      x: MARGE + 6.9, y: Y_CONTENU, w: 5.19, colonnes: [1.75, 1.05, 1.15, 1.24], hauteurLigne: 0.42,
      entetes: ['Moteur', 'normal', 'appauvri', 'variation'],
      rangees: [
        [{ t: 'Sémantique', c: C.semantique }, { t: '0,922', a: 'right', m: true }, { t: '0,564', a: 'right', m: true }, { t: '−0,357', a: 'right', m: true, c: C.alerte, g: true }],
        [{ t: 'BM25', c: C.lexical }, { t: '0,953', a: 'right', m: true }, { t: '0,645', a: 'right', m: true }, { t: '−0,308', a: 'right', m: true }],
      ],
    });
    carte(s, {
      x: MARGE + 6.9, y: 3.45, w: 5.19, h: 1.25, sur: 'la transformation appliquée',
      texte: "« Discovering Conceptual Metaphors Across Topics and Media Types »\n→ « conceptual across and media types »",
      taille: 11,
    });
    encadre(s, {
      x: MARGE + 6.9, y: 4.85, w: 5.19, h: 1.4, sur: "l'explication", accent: C.semantique,
      texte: "Les mots rares ne portaient pas seulement la signature lexicale : ils portaient le sujet. Un modèle dense compresse la requête entière dans un vecteur unique — il y est donc plus sensible.",
      taille: 11.5,
    });
    pied(s, 'Résultat 3 — contraire à l\'hypothèse');
  }

  // ---- 19 — résultat 4 : multilingue ------------------------------------
  {
    const s = nouvelleDiapo(
      "Voici l'apport réel du projet.\n\n" +
      "Vingt questions posées en français, en arabe et en anglais, sur un corpus entièrement anglophone. Je mesure la part d'articles communs entre les résultats de deux langues.\n\n" +
      "Le moteur sémantique obtient 0,445 entre français et anglais, 0,130 entre arabe et anglais. BM25 obtient 0,035 et zéro.\n\n" +
      "Mais le chiffre à retenir est celui de droite : BM25 ne renvoie strictement rien sur les vingt requêtes arabes. Zéro résultat, vingt fois sur vingt. Ce n'est pas un mauvais réglage : aucun mot arabe n'existe dans un corpus anglophone, donc aucun score n'est calculable.\n\n" +
      "Sur ce terrain, les deux approches ne se comparent pas. Une seule fonctionne.\n\n" +
      "Deux nuances honnêtes. Le recouvrement de 0,445 en français doit se lire avec prudence : sur un corpus aussi dense, deux formulations peuvent renvoyer des articles différents et tous deux pertinents. Et le score arabe est nettement plus faible que le français : la qualité multilingue de ce modèle n'est pas uniforme entre les langues.");
    enTete(s, 'Résultat 4 · cohérence multilingue', 'Le résultat qui justifie le projet');

    histogramme(s, {
      x: MARGE, y: Y_CONTENU, w: 6.5, h: 4.3,
      couleurs: [C.semantique, C.lexical],
      format: '0%', formatAxe: '0%',
      series: [
        { name: 'Sémantique', labels: ['français ↔ anglais', 'arabe ↔ anglais', 'français ↔ arabe'], values: [0.445, 0.130, 0.205] },
        { name: 'BM25', labels: ['français ↔ anglais', 'arabe ↔ anglais', 'français ↔ arabe'], values: [0.035, 0.000, 0.000] },
      ],
      max: 0.6,
    });

    chiffre(s, { x: MARGE + 6.9, y: Y_CONTENU, w: 2.5, h: 1.3, valeur: '20 / 20', legende: 'requêtes arabes sans résultat BM25', accent: C.alerte, taille: 24 });
    chiffre(s, { x: MARGE + 9.65, y: Y_CONTENU, w: 2.44, h: 1.3, valeur: '0 / 20', legende: 'pour le moteur sémantique', accent: C.semantique, taille: 24 });

    encadre(s, {
      x: MARGE + 6.9, y: 3.42, w: 5.19, h: 1.5, sur: 'ce que cela veut dire', accent: C.semantique,
      texte: "Aucun mot arabe n'existe dans un corpus anglophone, donc aucun score n'est calculable. Sur ce terrain, les deux approches ne se comparent pas. Une seule fonctionne.",
      taille: 12.5,
    });
    carte(s, {
      x: MARGE + 6.9, y: 5.06, w: 5.19, h: 1.16, sur: 'deux nuances honnêtes',
      texte: "0,445 en français se lit avec prudence : deux formulations peuvent renvoyer des articles différents et tous deux pertinents. Et 0,130 en arabe : la qualité n'est pas uniforme entre langues.",
      taille: 10.5,
    });
    pied(s, 'Résultat 4 — le résultat central');
  }

  // ---- 20 — résultat 5 : hybride ----------------------------------------
  {
    const s = nouvelleDiapo(
      "Dernier résultat : la fusion hybride, mesurée sur les mêmes protocoles.\n\n" +
      "Elle est meilleure que chacun des deux moteurs pris séparément — sur le protocole titre vers résumé, sur les requêtes appauvries, et sur le groupe à faible recouvrement lexical. Et elle conserve la couverture multilingue : zéro requête arabe sans résultat.\n\n" +
      "Ces chiffres viennent d'une exécution de contrôle sur un corpus réduit ; l'ordre entre les moteurs est net et reproductible, mais les valeurs absolues sont à régénérer sur le corpus complet.\n\n" +
      "Le prix à payer est la latence : la fusion interroge les deux moteurs, donc elle paie la somme de leurs temps.");
    enTeteRiche(s, 'Résultat 5 · fusion hybride',
      [{ t: 'La fusion ' }, { t: 'domine les deux', c: C.hybride }], C.hybride);

    histogramme(s, {
      x: MARGE, y: Y_CONTENU, w: 7.3, h: 4.0,
      couleurs: [C.semantique, C.lexical, C.hybride],
      series: [
        { name: 'Sémantique', labels: ['titre → résumé', 'requêtes appauvries', 'faible recouvrement'], values: [0.929, 0.712, 0.846] },
        { name: 'BM25', labels: ['titre → résumé', 'requêtes appauvries', 'faible recouvrement'], values: [0.975, 0.751, 0.923] },
        { name: 'Hybride', labels: ['titre → résumé', 'requêtes appauvries', 'faible recouvrement'], values: [0.978, 0.774, 0.933] },
      ],
    });
    s.addText("MRR@10 — exécution de contrôle sur corpus réduit. L'ordre entre moteurs est reproductible ; les valeurs absolues sont à régénérer sur le corpus complet.", {
      x: MARGE, y: 6.05, w: 7.3, h: 0.5, isTextBox: true, margin: 0,
      fontSize: 9.5, color: C.texteFaible, fontFace: POLICE, lineSpacingMultiple: 1.1, valign: 'top',
    });

    carte(s, {
      x: MARGE + 7.7, y: Y_CONTENU, w: 4.39, h: 2.4, accent: C.hybride, sur: 'ce que la fusion apporte',
      liste: [
        'Meilleure que chacun sur les trois protocoles de qualité',
        'Écart le plus net là où les deux se contredisent',
        { t: 'Conserve la couverture multilingue : 0 requête arabe sans résultat', c: C.hybride, g: true },
      ],
      taille: 11.5,
    });
    encadre(s, {
      x: MARGE + 7.7, y: 4.5, w: 4.39, h: 1.75, sur: 'le prix à payer', accent: C.alerte,
      texte: "La fusion interroge les deux moteurs : sa latence est par construction la somme des leurs. C'est le seul coût réel de l'opération.",
      taille: 12,
    });
    pied(s, 'Résultat 5 — la fusion hybride');
  }

  // ---- 21 — coût ---------------------------------------------------------
  {
    const s = nouvelleDiapo(
      "Le coût, mesuré.\n\n" +
      "À gauche, les latences. Le temps du moteur sémantique est presque entièrement consacré à l'encodage de la requête ; la recherche FAISS elle-même ne coûte qu'une milliseconde.\n\n" +
      "À droite, le compromis de l'index approximatif. Et voici une conclusion qui va contre l'intuition : à onze mille vecteurs, l'index approximatif fait perdre quatorze pour cent de rappel pour économiser moins d'une milliseconde sur une requête qui en prend quatre-vingt-trois.\n\n" +
      "L'approximation ne se justifie pas à cette échelle. Je la garde implémentée pour le jour où le corpus atteindra le million de documents. Mesurer un compromis vaut mieux que le citer — et ici, la mesure dit de ne pas l'utiliser.");
    enTete(s, 'Résultat 6 · coût', "Ce que ça coûte, et ce que l'approximation ne vaut pas");

    s.addText('Latence par requête', {
      x: MARGE, y: 1.85, w: 5.85, h: 0.28, isTextBox: true, margin: 0,
      fontSize: 13, bold: true, color: C.texte, fontFace: POLICE, valign: 'middle',
    });
    tableau(s, {
      x: MARGE, y: 2.2, w: 5.85, colonnes: [2.45, 1.7, 1.7], hauteurLigne: 0.42,
      entetes: ['Moteur', 'médiane', 'p95'],
      rangees: [
        [{ t: 'Sémantique', c: C.semantique }, { t: '83,4 ms', a: 'right', m: true }, { t: '107,2 ms', a: 'right', m: true }],
        [{ t: 'BM25', c: C.lexical }, { t: '116,7 ms', a: 'right', m: true }, { t: '236,0 ms', a: 'right', m: true }],
      ],
    });
    carte(s, {
      x: MARGE, y: 3.6, w: 5.85, h: 1.55, sur: 'où passe le temps',
      texte: "Le temps du moteur sémantique est presque entièrement consacré à l'encodage de la requête. La recherche FAISS elle-même ne coûte qu'une milliseconde sur 10 897 vecteurs.",
      taille: 12,
    });

    s.addText('Index exact contre index approximatif', {
      x: MARGE + 6.24, y: 1.85, w: 5.85, h: 0.28, isTextBox: true, margin: 0,
      fontSize: 13, bold: true, color: C.texte, fontFace: POLICE, valign: 'middle',
    });
    tableau(s, {
      x: MARGE + 6.24, y: 2.2, w: 5.85, colonnes: [1.85, 1.1, 1.45, 1.45], hauteurLigne: 0.38,
      entetes: ['Index', 'nprobe', 'ms/req.', 'rappel'],
      rangees: [
        [{ t: 'flat (exact)', c: C.texte, g: true }, { t: '—', a: 'right', m: true }, { t: '1,311', a: 'right', m: true }, { t: '1,000', a: 'right', m: true, c: C.hybride, g: true }],
        ['ivf', { t: '1', a: 'right', m: true }, { t: '0,126', a: 'right', m: true }, { t: '0,325', a: 'right', m: true, c: C.alerte }],
        ['ivf', { t: '10', a: 'right', m: true }, { t: '0,124', a: 'right', m: true }, { t: '0,761', a: 'right', m: true }],
        ['ivf', { t: '20', a: 'right', m: true }, { t: '0,449', a: 'right', m: true }, { t: '0,862', a: 'right', m: true }],
      ],
    });
    encadre(s, {
      x: MARGE + 6.24, y: 4.35, w: 5.85, h: 1.8, sur: 'conclusion contre-intuitive', accent: C.alerte,
      texte: "L'approximation fait perdre 14 % de rappel pour économiser moins d'une milliseconde sur une requête qui en prend 83.\n\n" +
             "Elle ne se justifie pas à cette échelle. Elle reste implémentée pour le jour où le corpus atteindra le million de documents.",
      taille: 12,
    });
    pied(s, 'Coût — latence et index');
  }

  // ---- 22 — conclusion ---------------------------------------------------
  {
    const s = nouvelleDiapo(
      "Je conclus sur ce que les mesures autorisent à dire.\n\n" +
      "La thèse de ce projet n'est pas « le sémantique bat le lexical ». Les mesures disent autre chose, de plus solide.\n\n" +
      "Là où les mots se recouvrent, BM25 reste légèrement meilleur, gratuit et instantané. Là où ils ne se recouvrent pas — autre langue, autre vocabulaire — le moteur sémantique est le seul à fonctionner, tandis que BM25 ne renvoie rien.\n\n" +
      "Et c'est exactement pour cette raison que la recherche hybride est devenue le standard en production. Elle n'est pas un bonus du projet : elle en est la conclusion logique. C'est pour ça que je l'ai implémentée et mesurée, et pas seulement citée en perspective.");
    enTete(s, 'Conclusion', 'Ce que les mesures autorisent à dire');

    encadre(s, {
      x: MARGE, y: Y_CONTENU, w: LARG, h: 1.9, sur: 'la thèse défendable', accent: C.semantique,
      texte: "Là où les mots se recouvrent, BM25 reste légèrement meilleur, gratuit et instantané.\n\n" +
             "Là où ils ne se recouvrent pas — autre langue, autre vocabulaire — le moteur sémantique est le seul à fonctionner, tandis que BM25 ne renvoie rien.",
      taille: 16,
    });

    const conclusions = [
      { sur: 'ce que je ne dirai pas', accent: C.lexical,
        texte: "« Le sémantique bat le lexical. » Mes propres mesures le contredisent sur deux protocoles sur trois." },
      { sur: 'ce que je dirai', accent: C.semantique,
        texte: "Les deux approches échouent à des endroits différents. C'est cela, le résultat — et il est plus utile qu'un classement." },
      { sur: 'ce qui en découle', accent: C.hybride,
        texte: "La recherche hybride n'est pas un bonus du projet : elle en est la conclusion logique. D'où son implémentation, et sa mesure." },
    ];
    conclusions.forEach((c, i) => {
      carte(s, { x: MARGE + i * 4.13, y: 4.25, w: 3.83, h: 1.95, ...c, taille: 12 });
    });
    pied(s, 'Conclusion — la thèse défendable');
  }

  // ---- 23 — limites et perspectives -------------------------------------
  {
    const s = nouvelleDiapo(
      "Les limites, que je préfère énoncer moi-même.\n\n" +
      "La qualité multilingue n'est pas uniforme. Le protocole titre vers résumé ne descend jamais dans le régime purement sémantique. Le corpus est mono-domaine. Et l'explicabilité coûte neuf fois la recherche.\n\n" +
      "Les perspectives, par ordre de rapport qualité-effort. Le reranking par cross-encoder est ce qui reste de plus rentable : on repasse les cinquante premiers résultats dans un modèle qui lit la question et le document ensemble, au lieu de comparer deux vecteurs calculés séparément.\n\n" +
      "Ensuite : faire varier les poids de la fusion, tester e5-base pour réduire l'écart entre langues, ajouter une couche de génération, et passer à l'échelle.");
    enTete(s, 'Limites & perspectives', "Ce qui ne marche pas encore, et ce qui suit");

    carte(s, {
      x: MARGE, y: Y_CONTENU, w: 5.85, h: 3.15, accent: C.alerte, sur: 'limites assumées',
      liste: [
        'Qualité multilingue non uniforme — 0,130 en arabe contre 0,445 en français',
        'Le protocole 1 ne mesure pas le sens — son tiers le plus dur reste à 63 % lexical',
        'Corpus mono-domaine — uniquement des résumés scientifiques, en anglais',
        "L'explicabilité coûte cher — 9× la recherche sur CPU",
        'Filtrage par sur-échantillon — un filtre très sélectif peut manquer de survivants',
      ],
      taille: 11.5,
    });
    carte(s, {
      x: MARGE + 6.24, y: Y_CONTENU, w: 5.85, h: 3.15, accent: C.hybride, sur: 'perspectives, par rapport qualité / effort',
      liste: [
        { t: 'Reranking par cross-encoder — un modèle qui lit question et document ensemble. Le plus rentable de ce qui reste', c: C.texte, g: true },
        "Régler les poids de la fusion — l'infrastructure est là, il reste à mesurer",
        'Comparer e5-base à e5-small — en particulier sur l\'arabe',
        'Réponse générée (RAG) — après validation du moteur, pas avant',
        "Passage à l'échelle — 500 000 articles, pour trouver où l'index exact cède",
      ],
      taille: 11.5,
    });
    encadre(s, {
      x: MARGE, y: 5.3, w: LARG, h: 1.2, sur: 'ce que ces limites ne remettent pas en cause', accent: C.semantique,
      texte: "Aucune n'atteint le résultat central : sur un corpus anglophone, la baseline lexicale ne renvoie rien dès que la question change de langue. Ces limites disent où porter l'effort suivant, pas si le projet tient.",
      taille: 12.5,
    });
    pied(s, 'Limites et perspectives');
  }

  // ---- 24 — démonstration ------------------------------------------------
  {
    const s = nouvelleDiapo(
      "Je passe à la démonstration en direct. Le scénario est en trois temps.\n\n" +
      "Un : une question en anglais, dont les mots existent dans le corpus. Les deux moteurs fonctionnent, et ils s'accordent largement. C'est le cas normal.\n\n" +
      "Deux : la même question en français. BM25 s'effondre. Le moteur sémantique continue de répondre.\n\n" +
      "Trois : la même question en arabe. BM25 ne renvoie plus rien du tout. Le moteur sémantique répond toujours, et l'interface signale d'elle-même qu'il n'y a aucun mot en commun.\n\n" +
      "L'onglet Démonstration de l'application déroule ce scénario automatiquement, et affiche à la fin un tableau récapitulatif des trois langues.");
    enTete(s, 'Démonstration en direct', 'Trois questions, une seule idée', C.hybride);

    const temps = [
      { sur: 'temps 1 · anglais', accent: C.hybride, titre: 'machine learning for banking fraud detection', tailleTitre: 12.5,
        texte: "Les mots existent dans le corpus. Les deux moteurs fonctionnent et s'accordent largement. C'est le cas normal." },
      { sur: 'temps 2 · français', accent: C.lexical, titre: 'détection de la fraude bancaire par apprentissage automatique', tailleTitre: 12.5,
        texte: "Même question, autre langue. BM25 s'effondre. Le moteur sémantique continue de répondre." },
      { sur: 'temps 3 · arabe', accent: C.semantique, titre: 'كشف الاحتيال المصرفي باستخدام التعلم الآلي', tailleTitre: 12.5,
        texte: "Autre alphabet. BM25 ne renvoie plus rien. Le sémantique répond, et l'interface signale « aucun mot en commun »." },
    ];
    temps.forEach((t, i) => {
      carte(s, { x: MARGE + i * 4.13, y: Y_CONTENU, w: 3.83, h: 2.75, ...t, taille: 11.5 });
    });

    encadre(s, {
      x: MARGE, y: 5.0, w: LARG, h: 1.5, sur: "ce qui est montré à l'écran", accent: C.hybride,
      texte: "L'onglet Démonstration déroule ce scénario automatiquement dans les trois langues, affiche le verdict de chaque comparaison, et termine par un tableau récapitulatif. Rien n'est préparé à l'avance : les questions viennent du jeu d'évaluation, écrit avant les mesures.",
      taille: 12.5,
    });
    pied(s, 'Démonstration');
  }

  // ---- 25 — merci --------------------------------------------------------
  {
    const s = nouvelleDiapo(
      "Merci de votre attention. Je suis à votre disposition pour vos questions.\n\n" +
      "La diapositive suivante contient les réponses aux questions que j'anticipe — je peux y aller directement si l'une d'elles est posée.");
    pastille(s, MARGE, 1.85, C.semantique, 0.15);
    s.addText('MERCI DE VOTRE ATTENTION', {
      x: MARGE + 0.26, y: 1.78, w: LARG, h: 0.3, isTextBox: true, margin: 0,
      fontSize: 11, bold: true, color: C.semantique, fontFace: POLICE, charSpacing: 1.6, valign: 'middle',
    });
    s.addText('Questions', {
      x: MARGE, y: 2.25, w: LARG, h: 1.1, isTextBox: true, margin: 0,
      fontSize: 52, bold: true, color: C.texte, fontFace: POLICE, valign: 'top',
    });
    s.addText("Le code, la documentation, le protocole d'évaluation et l'interface sont disponibles et reproductibles en cinq commandes.", {
      x: MARGE, y: 3.5, w: 8.4, h: 0.6, isTextBox: true, margin: 0,
      fontSize: 14.5, color: C.texteDoux, fontFace: POLICE, lineSpacingMultiple: 1.25, valign: 'top',
    });

    const finaux = [
      { v: '8 569', l: 'articles indexés', c: C.semantique },
      { v: '3', l: 'moteurs comparés', c: C.cyan },
      { v: '47', l: 'tests automatiques', c: C.hybride },
      { v: '20/20', l: 'requêtes arabes où BM25 échoue', c: C.lexical },
    ];
    finaux.forEach((f, i) => {
      chiffre(s, { x: MARGE + i * 2.55, y: 4.5, w: 2.35, h: 1.3, valeur: f.v, legende: f.l, accent: f.c, taille: 24 });
    });
    pied(s, 'Merci — questions');
  }

  // ---- 26 — annexe -------------------------------------------------------
  {
    const s = nouvelleDiapo("Diapositive d'appui, à n'afficher que si la question est posée.");
    enTete(s, 'Annexe', 'Questions probables, et réponses courtes');

    const qr = [
      { q: '« Pourquoi pas TF-IDF ? »',
        r: "BM25 est une amélioration directe de TF-IDF : saturation de la fréquence des termes et normalisation par la longueur. C'est la référence en production. Choisir TF-IDF aurait affaibli volontairement la baseline." },
      { q: '« Pourquoi 384 dimensions ? »',
        r: "C'est la dimension de sortie de e5-small. Elle n'est pas choisie : elle est imposée par le modèle. e5-base en produirait 768, pour environ trois fois plus de calcul." },
      { q: "« Comment savez-vous que ce n'est pas de la chance ? »",
        r: "500 requêtes annotées automatiquement, graine aléatoire fixée, trois protocoles indépendants, et un fichier de résultats régénérable par une commande." },
      { q: '« BM25 gagne : votre projet ne sert à rien ? »',
        r: "Il gagne sur le protocole qui lui est le plus favorable, et j'explique pourquoi. Sur les requêtes multilingues, il ne renvoie rien, 20 fois sur 20." },
      { q: '« Pourquoi ne pas traduire la requête ? »',
        r: "Ce serait une seconde brique à installer, maintenir et évaluer, avec ses propres erreurs. L'espace vectoriel partagé rend la traduction inutile." },
      { q: '« Et un LLM / un chatbot ? »',
        r: "Un LLM ne remplace ni l'indexation, ni le classement, ni l'évaluation. Il se branche après, sur des résultats déjà pertinents." },
    ];

    qr.forEach((item, i) => {
      const col = i % 2, ligne = Math.floor(i / 2);
      carte(s, {
        x: MARGE + col * 6.24, y: Y_CONTENU + ligne * 1.53, w: 5.85, h: 1.4,
        sur: item.q, texte: item.r, taille: 10.5,
      });
    });
    pied(s, 'Annexe — questions probables');
  }

  await pres.writeFile({ fileName: SORTIE });
  console.log(`${SORTIE} écrit — ${numero} diapositives`);
}

construire().catch(e => { console.error(e); process.exit(1); });
