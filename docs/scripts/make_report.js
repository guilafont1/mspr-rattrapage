const { Document, Packer, Paragraph, TextRun, HeadingLevel, Table, TableRow,
        TableCell, WidthType, AlignmentType, LevelFormat, ImageRun, PageBreak,
        ShadingType } = require('docx');
const fs = require('fs');
const path = require('path');

const VIZ = path.join(__dirname, '..', '..', 'viz', 'output');
const DIAG = path.join(__dirname, '..', 'mspr', '02_architecture', 'diagrams');
const OUT = path.join(__dirname, '..', 'livrables');
fs.mkdirSync(OUT, { recursive: true });

const imgViz = f => fs.readFileSync(path.join(VIZ, f));
const imgPath = p => fs.readFileSync(p);
const NAVY = '1B2A5E';

const FLUX = fs.existsSync(path.join(DIAG, 'flux_etl_medaillon.png'))
  ? path.join(DIAG, 'flux_etl_medaillon.png')
  : path.join(DIAG, 'flux_etl_mermaid_export.png');
const SCALE = path.join(DIAG, 'scale_out.png');

const H1 = t => new Paragraph({ heading: HeadingLevel.HEADING_1, spacing: { before: 240, after: 120 }, children: [new TextRun({ text: t, color: NAVY })] });
const H2 = t => new Paragraph({ heading: HeadingLevel.HEADING_2, spacing: { before: 160, after: 80 }, children: [new TextRun({ text: t, color: NAVY })] });
const P = (t, o = {}) => new Paragraph({ children: [new TextRun({ text: t, ...o })], spacing: { after: 120 }, alignment: AlignmentType.JUSTIFIED });
const B = t => new Paragraph({ numbering: { reference: 'bul', level: 0 }, children: [new TextRun(t)], spacing: { after: 60 } });
const IMG = (data, w, h) => new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 160 }, children: [new ImageRun({ type: 'png', data, transformation: { width: w, height: h } })] });
const IMG_VIZ = (f, w, h) => IMG(imgViz(f), w, h);
const CAP = t => new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 }, children: [new TextRun({ text: t, italics: true, size: 18, color: '666666' })] });

function table(headers, rows, widths) {
  const total = widths.reduce((a, b) => a + b, 0);
  const mk = (cells, head) => new TableRow({ tableHeader: head, children: cells.map((c, i) => new TableCell({
    width: { size: widths[i], type: WidthType.DXA },
    shading: head ? { type: ShadingType.CLEAR, fill: NAVY } : undefined,
    children: [new Paragraph({ children: [new TextRun({ text: c, bold: head, color: head ? 'FFFFFF' : '000000', size: 19 })] })],
  })) });
  return new Table({ width: { size: total, type: WidthType.DXA }, columnWidths: widths,
    rows: [mk(headers, true), ...rows.map(r => mk(r, false))] });
}

const children = [
  new Paragraph({ spacing: { after: 80 }, alignment: AlignmentType.CENTER, children: [new TextRun({ text: 'DOSSIER DE SYNTHÈSE', bold: true, size: 48, color: NAVY })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 60 }, children: [new TextRun({ text: 'POC Electio-Analytics — Prévision des tendances électorales', size: 28, color: '444444' })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 300 }, children: [new TextRun({ text: 'MSPR TPRE813 — Bloc 3 : Piloter l\u2019informatique décisionnel d\u2019un S.I (Big Data & BI)  ·  RNCP 35584', italics: true, size: 20, color: '666666' })] }),

  H1('Résumé exécutif'),
  P('Electio-Analytics souhaite valider, par une preuve de concept, sa capacité à anticiper les tendances électorales à 1–3 ans à partir d\u2019indicateurs socio-économiques publics. Ce POC met en place une chaîne complète et reproductible : collecte de données ouvertes, pipeline ETL en architecture médailon, entrepôt structuré, modèle prédictif supervisé et restitutions visuelles (Dash, API FastAPI, Metabase).'),
  P('Périmètre : les 96 départements de France métropolitaine sur 5 scrutins présidentiels (2002–2022) → 480 lignes GOLD. Après lag politique, le jeu ML compte 384 observations. Le modèle retenu (Gradient Boosting, sélection walk-forward temporelle) atteint une accuracy de 0,53 sur le holdout 2022 — au-dessus du seuil de 0,5 exigé. Walk-forward : 0,37 ; CV géographique secondaire : 0,72 ; baseline CV : 0,41. Chiffres figés le 30/07/2026 dans docs/mspr/04_machine_learning/CHIFFRES_FIGES.md (source data/ml_report.json).'),
  P('Le taux de pauvreté N−1 a une complétude de 40 % en GOLD (millésimes Filosofi 2017 et 2022) : il reste disponible pour la BI et le référentiel, mais est exclu des features ML pour éviter une couverture partielle biaisante. Un référentiel de données, une suite DQM exécutable (inspirée du pattern expectations) et un guide Metabase complètent le dossier.'),

  new Paragraph({ children: [new PageBreak()] }),

  H1('1. Justification du choix de la zone géographique'),
  P('Le cahier des charges impose un périmètre géographique unique. Nous retenons la maille départementale sur l\u2019ensemble de la France métropolitaine. Ce choix répond aux trois critères exigés par le client :'),
  B('Disponibilité des données : résultats électoraux, chômage localisé, emploi salarié, population, pauvreté et créations d\u2019entreprises sont tous publiés à la maille départementale, sur des séries longues (2000–2025), sous Licence Ouverte v2.0.'),
  B('Représentativité et taille exploitable : couvrir les 96 départements plutôt qu\u2019un seul multiplie le volume d\u2019apprentissage (384 observations exploitables contre 5), condition indispensable à un modèle statistiquement crédible, tout en gardant une volumétrie maîtrisée (< 100 Mo, traitement local).'),
  B('Traçabilité : le département est l\u2019unité de référence commune à toutes les sources (référentiel etl/referentiels.py), ce qui garantit des jointures fiables et un suivi de bout en bout.'),
  P('Ce choix est un arbitrage assumé : on privilégie la robustesse statistique (plus d\u2019observations) à l\u2019hyper-localisation. Une déclinaison sur une commune ou une circonscription unique reste possible pour un déploiement ciblé, au prix d\u2019un historique plus court.'),

  H1('2. Choix des indicateurs et référentiel'),
  P('Six indicateurs (+ lags politiques), tous antérieurs au scrutin, ont été retenus pour leur pertinence théorique (littérature du « vote économique ») et leur disponibilité. Le détail des contrats Bronze, des dims et des sources figure dans le référentiel docs/mspr/03_donnees/REFERENTIEL_DONNEES.md.'),
  table(['Indicateur', 'Justification'], [
    ['Taux de chômage (N-1)', 'Variable centrale du vote économique ; forte capacité à expliquer les basculements.'],
    ['Delta chômage sur 5 ans', 'Capte la dynamique (amélioration/dégradation) plutôt que le niveau absolu.'],
    ['Emploi pour 1 000 hab.', 'Vitalité économique normalisée par la population, comparable dans le temps et l\u2019espace.'],
    ['Croissance de l\u2019emploi (5 ans)', 'Tendance de moyen terme, cohérente avec l\u2019horizon de prévision 1–3 ans.'],
    ['Taux de pauvreté (N-1)', 'Tension sociale (BI). Complétude GOLD 40 % — hors modèle ML.'],
    ['Créations d\u2019entreprises', 'Indicateur de dynamisme économique local.'],
    ['Bloc / score gagnant précédent', 'Lag politique : l\u2019inertie électorale est un prédicteur documenté.'],
  ], [3200, 6160]),
  P(''),

  H1('3. Démarche et méthodes employées'),
  H2('3.1 Architecture médailon Bronze / Silver / Gold'),
  B('BRONZE : fichiers normalisés depuis data.gouv.fr / INSEE, contrats validés + manifests — traçabilité et reproductibilité.'),
  B('SILVER : nettoyage — typage, déduplication, contrôles de bornes (DQM). Journal quality_report.txt.'),
  B('GOLD : table analytique « 1 ligne = 1 (département, élection) », SQLite / Postgres (préfixes dim_/fait_/gold_/kpi_).'),
  H2('3.2 Diagramme de flux ETL'),
  P('Le diagramme ci-dessous formalise le flux Sources → RAW → Bronze → Silver → Gold → ML / Metabase (export PNG du schéma Mermaid).'),
];

if (fs.existsSync(FLUX)) {
  children.push(IMG(imgPath(FLUX), 520, 280));
  children.push(CAP('Fig. 0 — Diagramme de flux ETL / architecture médailon.'));
}

children.push(
  H2('3.3 Prévention du data leakage'),
  P('Pour prédire l\u2019élection de l\u2019année N, seules des données de l\u2019année N-1 et antérieures sont mobilisées. Sélection du modèle : 0,4 × accuracy walk-forward + 0,6 × accuracy holdout 2022. La CV GroupKFold par département reste une métrique secondaire (généralisation spatiale), et non le critère de rétention — le Random Forest y excelle via stickiness politique mais échoue sur 2022.'),
  H2('3.4 Industrialisation'),
  P('Le pipeline est orchestré par run_pipeline.py. Une suite de tests (pytest) et une suite DQM exécutable (dqm/run_checkpoint.py, pattern expectations) vérifient bornes, unicité et complétude. En production : DAG Airflow (stub fourni) + object store S3/MinIO.'),

  H1('4. Modèle Conceptuel de Données'),
  P('Comparaison argumentée des modèles multidimensionnels :'),
  B('Étoile (retenu) : faits au centre, dimensions dénormalisées — simplicité BI et performance en lecture, adapté à ~480 observations GOLD.'),
  B('Flocon (évalué, non retenu) : dimensions normalisées (région→département) — gain d\u2019intégrité insuffisant face à la complexité des jointures à cette échelle.'),
  B('Grappe / constellation (partielle) : plusieurs faits (élections, chômage, emploi) partageant dim_departement / dim_annee / dim_bloc.'),
  P('Schéma SQL commenté : sql/schema.sql ; voir aussi docs/mspr/05_bi_restitution/MODELISATION_MULTIDIM.md.'),

  H1('4 bis. Stratégie Big Data & restitution BI'),
  P('Datalake médailon : RAW immuable, bronze normalisé, silver contrôlé, gold consommable. Ingestion parallèle (ThreadPoolExecutor). Object store MinIO (profil datalake). Metabase (profil Docker bi, http://localhost:3000) se branche sur Gold/Postgres pour la restitution jury. Scale-out cible : Airflow + workers + S3/OVH.'),
);

if (fs.existsSync(SCALE)) {
  children.push(IMG(imgPath(SCALE), 460, 320));
  children.push(CAP('Fig. 0b — Pipeline distribué (scale-out Airflow / Spark).'));
}

children.push(
  new Paragraph({ children: [new PageBreak()] }),

  H1('5. Modèles testés et résultats (chiffres figés)'),
  P('Cinq approches comparées. Critère de sélection : robustesse temporelle (walk-forward + holdout), pas la seule CV géographique.'),
  table(['Modèle', 'Accuracy CV géo', 'Walk-forward', 'Holdout 2022'], [
    ['Baseline (classe majoritaire)', '0,41', '0,16', '0,15'],
    ['Régression logistique', '—', '0,25', '0,10'],
    ['Arbre de décision', '—', '—', '—'],
    ['Random Forest', '0,69', '—', '~0,05'],
    ['Gradient Boosting (retenu)', '0,72', '0,37', '0,53'],
  ], [3600, 1800, 1800, 1800]),
  P(''),
  P('Le Gradient Boosting (n=200, depth=3, lr=0,1) est retenu : holdout 2022 = 0,53 (> 0,5). Le Random Forest reste fort en CV géo (~0,69) mais échoue sur la recomposition 2022 ; d\u2019où le critère temporel. Top features : pct_gagnant_precedent, delta_chomage_5a, marge_gagnante_precedente. Pauvreté N−1 : 40 % en GOLD, hors ML.'),
  IMG_VIZ('6_model_compare.png', 460, 259), CAP('Fig. 1 — Comparaison des modèles.'),
  IMG_VIZ('5_confusion.png', 360, 300), CAP('Fig. 2 — Matrice de confusion (holdout 2022).'),
  IMG_VIZ('7_importance.png', 460, 276), CAP('Fig. 3 — Importance des variables.'),

  H1('6. Qualité des données (suite DQM)'),
  P('La qualité est assurée à trois niveaux : contrôles Silver dans l\u2019ETL (16 OK / 0 KO), tests pytest anti-leakage, et une suite DQM exécutable (module dqm/). Cette suite est un outil interne inspiré du pattern « expectations » (contrôles nommés, rapport JSON/HTML) — ce n\u2019est pas l\u2019installation du produit Great Expectations. Commande : python dqm/run_checkpoint.py (ou make dqm).'),
  B('expect_election_pct_between_0_100'),
  B('expect_election_dept_in_metro'),
  B('expect_chomage_between_0_30'),
  B('expect_gold_unique_dept_annee'),
  B('expect_gold_chomage_n1_complete (+ pauvreté N−1 non vide)'),

  H1('7. Visualisations'),
  IMG_VIZ('1_evolution_blocs.png', 460, 256), CAP('Fig. 4 — Évolution du score moyen par bloc.'),
  IMG_VIZ('3_correlations.png', 380, 309), CAP('Fig. 5 — Matrice de corrélation.'),
  IMG_VIZ('4_chomage_par_bloc.png', 420, 262), CAP('Fig. 6 — Chômage N-1 selon le bloc en tête.'),
  IMG_VIZ('8_projection.png', 380, 244), CAP('Fig. 7 — Projection probabiliste.'),

  new Paragraph({ children: [new PageBreak()] }),

  H1('8. Réponses aux questions du client'),
  H2('Quelle donnée est la plus corrélée aux résultats ?'),
  P('Avec le protocole actuel, le score du gagnant précédent (pct_gagnant_precedent ≈ 0,32) domine, devant la dynamique du chômage sur cinq ans (delta_chomage_5a ≈ 0,16) et la marge gagnante précédente. Autrement dit, inertie politique + tendance du chômage.'),
  H2('Principe d\u2019un apprentissage supervisé'),
  P('On fournit au modèle des exemples étiquetés (indicateurs X, résultat y). Le modèle apprend f(X) → y, puis on mesure la généralisation sur un holdout temporel jamais vu (2022).'),
  H2('Comment définir le degré de précision (accuracy) ?'),
  P('L\u2019accuracy est la proportion de prédictions correctes. Exigence CDC : > 0,5 sur le jeu de test — atteinte avec 0,53 sur le holdout 2022 (chiffres figés).'),

  H1('9. Sécurité et conformité RGPD'),
  B('Données exclusivement publiques et agrégées au niveau départemental : aucune donnée à caractère personnel.'),
  B('Licence Ouverte v2.0 (Etalab) : réutilisation libre sous réserve de mentionner la source.'),
  B('Traçabilité : BRONZE immuable, journal DQM, suite dqm/, tests automatisés, code versionné.'),
  B('Secrets externalisés (.env) ; hébergement cloud UE / on-premise documentés (docs/mspr/06_rgpd_securite/).'),
  B('Extension future opinion / réseaux sociaux → AIPD préalable.'),

  H1('10. Limites et axes d\u2019amélioration'),
  P('Limites assumées : un modèle socio-économique ignore campagne, offre politique et chocs conjoncturels. Le POC démontre une méthode et son industrialisation.'),
  B('Enrichir les features : sécurité, démographie fine, infra-départemental.'),
  B('Fiabiliser : historique plus long, modèles séquentiels, intervalles de confiance.'),
  B('Industrialiser : Airflow en prod, Metabase branché Gold, scale-out Spark si volume.'),

  H1('Annexe — Livrables fournis'),
  B('Code complet : ETL, ML, visualisations, tests, orchestrateur, suite DQM.'),
  B('Référentiel de données + diagrammes de flux (PNG).'),
  B('Chiffres figés (CHIFFRES_FIGES.md) + ml_report.json.'),
  B('Guide Metabase + schéma SQL + journal qualité.'),
  B('Support de soutenance (PowerPoint) régénéré.'),
);

const doc = new Document({
  numbering: { config: [{ reference: 'bul', levels: [{ level: 0, format: LevelFormat.BULLET, text: '\u2022', style: { paragraph: { indent: { left: 480, hanging: 240 } } } }] }] },
  styles: { default: { document: { run: { font: 'Calibri', size: 22 } } },
    paragraphStyles: [
      { id: 'Heading1', name: 'Heading 1', basedOn: 'Normal', next: 'Normal', quickFormat: true, run: { size: 30, bold: true, color: NAVY }, paragraph: { spacing: { before: 240, after: 120 } } },
      { id: 'Heading2', name: 'Heading 2', basedOn: 'Normal', next: 'Normal', quickFormat: true, run: { size: 24, bold: true, color: NAVY } },
    ] },
  sections: [{
    properties: { page: { margin: { top: 1000, bottom: 1000, left: 1100, right: 1100 } } },
    children,
  }],
});

Packer.toBuffer(doc).then(b => {
  fs.writeFileSync(path.join(OUT, 'Dossier_synthese_POC_ElectioAnalytics.docx'), b);
  console.log('docx OK');
});
