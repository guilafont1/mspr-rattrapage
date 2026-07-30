const pptxgen = require('pptxgenjs');
const fs = require('fs');
const path = require('path');
const VIZ = path.join(__dirname, '..', '..', 'viz', 'output');
const OUT = path.join(__dirname, '..', 'livrables');
fs.mkdirSync(OUT, { recursive: true });

const NAVY = '1B2A5E', BLUE = '0066CC', RED = 'E31B23', GREY = 'F2F3F7', DARK = '222222', GOLD = 'C9A227';
const pres = new pptxgen();
pres.layout = 'LAYOUT_WIDE';
pres.defineSlideMaster({ title: 'M', background: { color: 'FFFFFF' } });

function base(slide, num, title, subtitle) {
  slide.background = { color: 'FFFFFF' };
  slide.addShape('rect', { x: 12.55, y: 0.28, w: 0.5, h: 0.5, fill: { color: NAVY } });
  slide.addText(String(num).padStart(2, '0'), { x: 12.55, y: 0.28, w: 0.5, h: 0.5, color: 'FFFFFF', fontSize: 13, align: 'center', bold: true, margin: 0, valign: 'middle' });
  slide.addText(title, { x: 0.5, y: 0.32, w: 11.7, h: 0.72, fontSize: 29, bold: true, color: NAVY, margin: 0 });
  slide.addShape('rect', { x: 0.5, y: 1.04, w: 0.9, h: 0.06, fill: { color: RED } });
  if (subtitle) slide.addText(subtitle, { x: 0.5, y: 1.13, w: 11, h: 0.4, italic: true, fontSize: 14, color: BLUE, margin: 0 });
  slide.addShape('rect', { x: 0.5, y: 7.18, w: 4.3, h: 0.07, fill: { color: NAVY } });
  slide.addShape('rect', { x: 4.8, y: 7.18, w: 3.7, h: 0.07, fill: { color: 'DDDDDD' } });
  slide.addShape('rect', { x: 8.5, y: 7.18, w: 4.3, h: 0.07, fill: { color: RED } });
}
function card(slide, x, y, w, h, title, lines, accent = NAVY) {
  slide.addShape('roundRect', { x, y, w, h, rectRadius: 0.08, fill: { color: GREY }, line: { color: accent, width: 1.25 } });
  slide.addText(title, { x, y: y + 0.14, w, h: 0.45, align: 'center', bold: true, color: accent, fontSize: 16, margin: 0 });
  slide.addText(lines.map((t, i) => ({ text: t, options: { bullet: true, breakLine: i < lines.length - 1, fontSize: 12.5, color: DARK, paraSpaceAfter: 7 } })),
    { x: x + 0.22, y: y + 0.65, w: w - 0.44, h: h - 0.8, valign: 'top' });
}

// 1 Titre
let s = pres.addSlide();
s.background = { color: NAVY };
s.addShape('rect', { x: 0, y: 0, w: 0.35, h: 7.5, fill: { color: RED } });
s.addText('POC Electio-Analytics', { x: 0.9, y: 2.0, w: 11.6, h: 1.1, fontSize: 46, bold: true, color: 'FFFFFF' });
s.addText('Prévision des tendances électorales par le machine learning', { x: 0.9, y: 3.15, w: 11.6, h: 0.6, fontSize: 21, color: 'D6DCF0' });
s.addShape('rect', { x: 0.95, y: 4.0, w: 2.2, h: 0.06, fill: { color: RED } });
s.addText('96 départements · 5 scrutins · pipeline ETL reproductible', { x: 0.95, y: 4.2, w: 11.5, h: 0.5, fontSize: 15, color: 'AAB4D8' });
s.addText('MSPR TPRE813 — Bloc 3 : Piloter l\u2019informatique décisionnel d\u2019un S.I (Big Data & BI)', { x: 0.95, y: 6.4, w: 11.5, h: 0.5, fontSize: 13, italic: true, color: '8894C0' });

// 2 Plan
s = pres.addSlide(); base(s, 1, 'Plan de présentation');
const plan = ['Contexte & périmètre', 'Sources de données', 'Pipeline ETL (médaillon)', 'Modèle de données', 'Machine Learning', 'Résultats & accuracy', 'Visualisations', 'RGPD & Sécurité', 'Limites & améliorations'];
plan.forEach((t, i) => {
  const col = i < 5 ? 0 : 1, r = i % 5;
  const x = 0.7 + col * 6.3, y = 1.85 + r * 1.02;
  s.addShape('rect', { x, y, w: 0.55, h: 0.72, fill: { color: NAVY } });
  s.addText(String(i + 1), { x, y, w: 0.55, h: 0.72, color: 'FFFFFF', align: 'center', bold: true, margin: 0, valign: 'middle', fontSize: 16 });
  s.addShape('rect', { x: x + 0.55, y, w: 4.7, h: 0.72, fill: { color: GREY }, line: { color: NAVY, width: 1 } });
  s.addText(t, { x: x + 0.7, y, w: 4.5, h: 0.72, bold: true, color: NAVY, fontSize: 15, valign: 'middle', margin: 0 });
});

// 3 Contexte
s = pres.addSlide(); base(s, 1, 'Contexte & périmètre', 'Besoin client et cadrage du POC');
card(s, 0.55, 1.75, 3.95, 4.9, 'Besoin client', ['Anticiper les tendances électorales à 1–3 ans', 'À partir d\u2019indicateurs socio-économiques publics', 'Preuve de concept avant investissement'], BLUE);
card(s, 4.7, 1.75, 3.95, 4.9, 'Périmètre retenu', ['96 départements métropolitains', '5 scrutins présidentiels (2002–2022)', '384 observations exploitables : volume nécessaire au ML', 'Maille unique = jointures fiables, traçabilité'], NAVY);
card(s, 8.85, 1.75, 3.95, 4.9, 'Critères de succès', ['Accuracy > 0,5 sur le jeu de test', 'Pipeline automatisé et reproductible', 'Livrables SQL / CSV / notebook / visualisations', 'Conformité RGPD'], GOLD);

// 4 Sources
s = pres.addSlide(); base(s, 2, 'Sources de données retenues', 'Collecte — couche BRONZE (Licence Ouverte v2.0)');
const hd = t => ({ text: t, options: { bold: true, color: 'FFFFFF', fill: { color: NAVY }, fontSize: 13 } });
const rows = [
  [hd('Source'), hd('Contenu'), hd('Granularité'), hd('Utilisée pour')],
  ['data.gouv.fr — Présidentielles T1', 'Résultats → 5 blocs politiques', 'Département', 'Variable cible + lag'],
  ['INSEE — Chômage localisé', 'Taux trimestriel', 'Dépt. (trim.)', 'Chômage N-1, delta 5 ans'],
  ['INSEE — Emploi salarié', 'Emploi total trimestriel', 'Dépt. (trim.)', 'Emploi/1000 hab, croissance'],
  ['INSEE — Population', 'Population annuelle', 'Dépt. (annuel)', 'Normalisation'],
  ['INSEE — Pauvreté (Filosofi)', 'Taux de pauvreté', 'Dépt. (annuel)', 'Tension sociale'],
  ['INSEE — Créations d\u2019entreprises', 'Créations pour 10k hab.', 'Dépt. (annuel)', 'Dynamisme économique'],
];
s.addTable(rows, { x: 0.55, y: 1.75, w: 12.25, colW: [3.5, 3.55, 2.2, 3.0], fontSize: 12.5, border: { color: 'CCCCCC', pt: 0.5 }, rowH: 0.5, valign: 'middle' });
s.addText('✓ Toutes les sources sous Licence Ouverte v2.0 · Aucune donnée personnelle · Agrégation départementale', { x: 0.55, y: 6.35, w: 12.25, h: 0.4, italic: true, fontSize: 12.5, color: NAVY, align: 'center' });

// 5 Pipeline ETL
s = pres.addSlide(); base(s, 3, 'Pipeline ETL', 'Architecture médaillon Bronze → Silver → Gold');
const steps = [['BRONZE', 'B87333', ['CSV bruts data.gouv / INSEE', 'Jamais modifiés', 'Traçabilité totale']], ['SILVER', '8A8D93', ['Typage + déduplication', 'Contrôles de bornes', 'Journal qualité']], ['GOLD', GOLD, ['1 ligne = 1 (dépt, élection)', 'Features anti-leakage', 'SQLite + CSV indexés']]];
steps.forEach(([t, c, lines], i) => {
  const x = 0.75 + i * 4.35;
  s.addShape('roundRect', { x, y: 2.0, w: 3.65, h: 3.5, rectRadius: 0.1, fill: { color: GREY }, line: { color: c, width: 2.5 } });
  s.addShape('rect', { x, y: 2.0, w: 3.65, h: 0.6, fill: { color: c } });
  s.addText(t, { x, y: 2.0, w: 3.65, h: 0.6, align: 'center', bold: true, color: 'FFFFFF', fontSize: 18, margin: 0, valign: 'middle' });
  s.addText(lines.map((l, j) => ({ text: l, options: { bullet: true, breakLine: j < lines.length - 1, fontSize: 13, paraSpaceAfter: 9, color: DARK } })), { x: x + 0.25, y: 2.8, w: 3.15, h: 2.5, valign: 'top' });
  if (i < 2) s.addText('→', { x: x + 3.65, y: 3.35, w: 0.7, h: 0.8, fontSize: 34, bold: true, color: NAVY, align: 'center', margin: 0 });
});
s.addText('Orchestration : run_pipeline.py enchaîne les étapes · tests automatisés (pytest) · anti data-leakage garanti', { x: 0.75, y: 6.0, w: 12.0, h: 0.5, italic: true, fontSize: 13, color: NAVY, align: 'center' });

// 6 Modèle de données
s = pres.addSlide(); base(s, 4, 'Modèle de données', 'Schéma en étoile — nommage explicite');
card(s, 0.55, 1.8, 3.95, 4.4, 'Dimensions', ['dim_departement', 'dim_annee', '(clés de référence)'], BLUE);
card(s, 4.7, 1.8, 3.95, 4.4, 'Faits', ['fait_resultat_election', 'fait_chomage_trimestriel', 'fait_emploi_trimestriel'], NAVY);
card(s, 8.85, 1.8, 3.95, 4.4, 'Gold (analytique)', ['gold_dataset_analytique', 'Dénormalisée pour ML & BI', 'SQLite indexé : electio_poc.db'], GOLD);
s.addText('384 observations · 96 départements × élections · 6 indicateurs + lag politique', { x: 0.55, y: 6.4, w: 12.25, h: 0.4, italic: true, fontSize: 13, color: NAVY, align: 'center' });

// 7 ML
s = pres.addSlide(); base(s, 5, 'Machine Learning', 'Classification supervisée du bloc en tête');
card(s, 0.55, 1.8, 5.95, 4.6, 'Protocole rigoureux', ['Split temporel : test = scrutin le plus récent', 'Validation croisée GroupKFold par département', 'Un dépt jamais en train ET en test (anti-leakage)', 'Métriques : accuracy + F1 macro (classes déséquilibrées)'], NAVY);
card(s, 6.7, 1.8, 6.1, 4.6, '5 modèles comparés', ['Baseline (classe majoritaire) — référence', 'Régression logistique', 'Arbre de décision', 'Random Forest (fort en CV géo)', 'Gradient Boosting — retenu (walk-forward)'], BLUE);


// 8 Résultats
s = pres.addSlide(); base(s, 6, 'Résultats & accuracy', 'Gradient Boosting — holdout 2022 = 0,53 (données réelles)');
s.addImage({ path: path.join(VIZ, '6_model_compare.png'), x: 0.55, y: 1.8, w: 6.4, h: 3.6 });
s.addImage({ path: path.join(VIZ, '5_confusion.png'), x: 1.6, y: 5.5, w: 4.3, h: 1.5, sizing: { type: 'contain', w: 4.3, h: 1.5 } });
card(s, 7.2, 1.8, 5.6, 5.2, 'Métriques clés (données réelles)', ['Holdout 2022 : 0,53 (> 0,5)', 'Walk-forward : 0,37', 'CV géo secondaire : 0,72', 'Baseline CV : 0,41', 'Sélection temporelle (pas stickiness RF)', 'Top feature : pct gagnant précédent', 'Pauvreté : 40 % GOLD, hors modèle ML'], GOLD);

// 9 Visualisations
s = pres.addSlide(); base(s, 7, 'Visualisations', 'Exploration & restitution');
s.addImage({ path: path.join(VIZ, '1_evolution_blocs.png'), x: 0.55, y: 1.75, w: 6.0, h: 3.33 });
s.addImage({ path: path.join(VIZ, '3_correlations.png'), x: 6.9, y: 1.75, w: 5.0, h: 4.06 });
s.addImage({ path: path.join(VIZ, '4_chomage_par_bloc.png'), x: 0.55, y: 5.2, w: 5.0, h: 1.9 });

// 10 RGPD
s = pres.addSlide(); base(s, 8, 'RGPD & Sécurité');
card(s, 0.55, 1.8, 5.95, 4.6, 'Conformité', ['Données publiques agrégées : aucune donnée personnelle', 'Aucun risque de ré-identification (maille dépt.)', 'Licence Ouverte v2.0 — sources mentionnées'], BLUE);
card(s, 6.7, 1.8, 6.1, 4.6, 'Traçabilité & bonnes pratiques', ['Couche BRONZE immuable + journal qualité', 'Tests automatisés + code versionné', 'Extension opinion/réseaux sociaux → AIPD préalable'], NAVY);

// 11 Limites & améliorations
s = pres.addSlide(); base(s, 9, 'Limites & axes d\u2019amélioration');
card(s, 0.55, 1.8, 5.95, 4.6, 'Limites assumées', ['Modèle socio-éco : ignore campagne & offre politique', 'Capte des tendances de fond, pas l\u2019issue exacte', 'POC = méthode + industrialisation démontrées'], RED);
card(s, 6.7, 1.8, 6.1, 4.6, 'Améliorations', ['Enrichir : sécurité, démographie, infra-départemental', 'Modèles séquentiels + intervalles de confiance', 'Orchestration Airflow, dashboard PowerBI'], BLUE);

// 12 Merci
s = pres.addSlide();
s.background = { color: NAVY };
s.addShape('rect', { x: 0, y: 0, w: 0.35, h: 7.5, fill: { color: RED } });
s.addText('Merci — Questions ?', { x: 0.9, y: 3.0, w: 11.6, h: 1.0, fontSize: 42, bold: true, color: 'FFFFFF' });
s.addShape('rect', { x: 0.95, y: 4.1, w: 2.2, h: 0.06, fill: { color: RED } });
s.addText('POC Electio-Analytics · MSPR TPRE813', { x: 0.95, y: 4.35, w: 11.5, h: 0.5, fontSize: 15, color: 'AAB4D8' });

pres.writeFile({ fileName: path.join(OUT, 'Support_soutenance_POC_ElectioAnalytics.pptx') }).then(() => console.log('pptx OK'));
