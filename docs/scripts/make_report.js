const { Document, Packer, Paragraph, TextRun, HeadingLevel, Table, TableRow,
        TableCell, WidthType, AlignmentType, LevelFormat, ImageRun, PageBreak,
        ShadingType, BorderStyle } = require('docx');
const fs = require('fs');
const path = require('path');

const VIZ = path.join(__dirname, '..', '..', 'viz', 'output');
const OUT = path.join(__dirname, '..', 'livrables');
fs.mkdirSync(OUT, { recursive: true });
const img = f => fs.readFileSync(path.join(VIZ, f));
const NAVY = '1B2A5E';

const H1 = t => new Paragraph({ heading: HeadingLevel.HEADING_1, spacing: { before: 240, after: 120 }, children: [new TextRun({ text: t, color: NAVY })] });
const H2 = t => new Paragraph({ heading: HeadingLevel.HEADING_2, spacing: { before: 160, after: 80 }, children: [new TextRun({ text: t, color: NAVY })] });
const P = (t, o = {}) => new Paragraph({ children: [new TextRun({ text: t, ...o })], spacing: { after: 120 }, alignment: AlignmentType.JUSTIFIED });
const B = t => new Paragraph({ numbering: { reference: 'bul', level: 0 }, children: [new TextRun(t)], spacing: { after: 60 } });
const IMG = (f, w, h) => new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 160 }, children: [new ImageRun({ type: 'png', data: img(f), transformation: { width: w, height: h } })] });
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

const doc = new Document({
  numbering: { config: [{ reference: 'bul', levels: [{ level: 0, format: LevelFormat.BULLET, text: '\u2022', style: { paragraph: { indent: { left: 480, hanging: 240 } } } }] }] },
  styles: { default: { document: { run: { font: 'Calibri', size: 22 } } },
    paragraphStyles: [
      { id: 'Heading1', name: 'Heading 1', basedOn: 'Normal', next: 'Normal', quickFormat: true, run: { size: 30, bold: true, color: NAVY }, paragraph: { spacing: { before: 240, after: 120 } } },
      { id: 'Heading2', name: 'Heading 2', basedOn: 'Normal', next: 'Normal', quickFormat: true, run: { size: 24, bold: true, color: NAVY } },
    ] },
  sections: [{
    properties: { page: { margin: { top: 1000, bottom: 1000, left: 1100, right: 1100 } } },
    children: [
    new Paragraph({ spacing: { after: 80 }, alignment: AlignmentType.CENTER, children: [new TextRun({ text: 'DOSSIER DE SYNTHÈSE', bold: true, size: 48, color: NAVY })] }),
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 60 }, children: [new TextRun({ text: 'POC Electio-Analytics — Prévision des tendances électorales', size: 28, color: '444444' })] }),
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 300 }, children: [new TextRun({ text: 'MSPR TPRE813 — Bloc 3 : Piloter l\u2019informatique décisionnel d\u2019un S.I (Big Data & BI)  ·  RNCP 35584', italics: true, size: 20, color: '666666' })] }),

    // ---- Résumé exécutif ----
    H1('Résumé exécutif'),
    P('Electio-Analytics souhaite valider, par une preuve de concept, sa capacité à anticiper les tendances électorales à 1–3 ans à partir d\u2019indicateurs socio-économiques publics. Ce POC met en place une chaîne complète et reproductible : collecte de données ouvertes, pipeline ETL en architecture médaillon, entrepôt structuré, modèle prédictif supervisé et restitutions visuelles.'),
    P('Périmètre : les 96 départements de France métropolitaine sur 5 scrutins présidentiels (2002–2022). Après ajout du lag politique, le jeu analytique compte 384 observations. Le modèle retenu (Random Forest) atteint une accuracy de 0,66 et un F1 macro de 0,65 en validation croisée groupée par département — nettement au-dessus du seuil de 0,5 exigé et de la baseline (0,41). Les indicateurs les plus prédictifs sont la dynamique du chômage sur 5 ans et l\u2019emploi rapporté à la population.', { }),
    P('Les résultats de ce dossier sont calculés sur les données publiques réelles (data.gouv.fr pour les résultats électoraux, INSEE pour le chômage, l\u2019emploi, la population, la pauvreté et les créations d\u2019entreprises). Le taux de pauvreté n\u2019étant disponible qu\u2019à partir de 2023 (postérieur à tous les scrutins étudiés), il est automatiquement écarté des variables du modèle pour éviter toute fuite temporelle.', { bold: true, color: '8B0000' }),

    new Paragraph({ children: [new PageBreak()] }),

    // ---- 1 ----
    H1('1. Justification du choix de la zone géographique'),
    P('Le cahier des charges impose un périmètre géographique unique. Nous retenons la maille départementale sur l\u2019ensemble de la France métropolitaine. Ce choix répond aux trois critères exigés par le client :'),
    B('Disponibilité des données : résultats électoraux, chômage localisé, emploi salarié, population, pauvreté et créations d\u2019entreprises sont tous publiés à la maille départementale, sur des séries longues (2000–2025), sous Licence Ouverte v2.0.'),
    B('Représentativité et taille exploitable : couvrir les 96 départements plutôt qu\u2019un seul multiplie le volume d\u2019apprentissage (384 observations exploitables contre 5), condition indispensable à un modèle statistiquement crédible, tout en gardant une volumétrie maîtrisée (< 100 Mo, traitement local).'),
    B('Traçabilité : le département est l\u2019unité de référence commune à toutes les sources, ce qui garantit des jointures fiables et un suivi de bout en bout.'),
    P('Ce choix est un arbitrage assumé : on privilégie la robustesse statistique (plus d\u2019observations) à l\u2019hyper-localisation. Une déclinaison sur une commune ou une circonscription unique reste possible pour un déploiement ciblé, au prix d\u2019un historique plus court.'),

    // ---- 2 ----
    H1('2. Choix des indicateurs et justification'),
    P('Six indicateurs, tous antérieurs au scrutin, ont été retenus pour leur pertinence théorique (littérature du « vote économique ») et leur disponibilité :'),
    table(['Indicateur', 'Justification'], [
      ['Taux de chômage (N-1)', 'Variable centrale du vote économique ; forte capacité à expliquer les basculements.'],
      ['Delta chômage sur 5 ans', 'Capte la dynamique (amélioration/dégradation) plutôt que le niveau absolu.'],
      ['Emploi pour 1 000 hab.', 'Vitalité économique normalisée par la population, comparable dans le temps et l\u2019espace.'],
      ['Croissance de l\u2019emploi (5 ans)', 'Tendance de moyen terme, cohérente avec l\u2019horizon de prévision 1–3 ans.'],
      ['Taux de pauvreté (N-1)', 'Tension sociale, corrélée au vote protestataire.'],
      ['Créations d\u2019entreprises', 'Indicateur de dynamisme économique local.'],
      ['Bloc gagnant précédent', 'Lag politique : l\u2019inertie électorale est un prédicteur documenté.'],
    ], [3200, 6160]),
    P(''),

    // ---- 3 ----
    H1('3. Démarche et méthodes employées'),
    H2('3.1 Architecture médaillon Bronze / Silver / Gold'),
    B('BRONZE : fichiers bruts téléchargés depuis data.gouv.fr / INSEE, jamais modifiés — garantie de traçabilité et de reproductibilité.'),
    B('SILVER : nettoyage — typage explicite, déduplication sur clés naturelles, contrôles de bornes. Chaque contrôle est journalisé dans quality_report.txt.'),
    B('GOLD : table analytique « 1 ligne = 1 (département, élection) », chargée dans une base SQLite au schéma nommé explicitement (préfixes dim_/fait_/gold_).'),
    H2('3.2 Prévention du data leakage'),
    P('Pour prédire l\u2019élection de l\u2019année N, seules des données de l\u2019année N-1 et antérieures sont mobilisées (moyennes, deltas, lags). Deux dispositifs de validation complémentaires sont utilisés : un split temporel (entraînement 2002–2017, test 2022) qui reproduit un usage prospectif réel, et une validation croisée groupée par département (GroupKFold) qui garantit qu\u2019un même département n\u2019apparaît jamais simultanément en entraînement et en test — la mesure de généralisation est donc honnête.'),
    H2('3.3 Industrialisation'),
    P('Le pipeline est orchestré par un script unique (run_pipeline.py) enchaînant collecte, transformation, entraînement et visualisation. Une suite de tests automatisés (pytest) vérifie l\u2019absence de doublons, le respect des bornes, la cohérence de la base et la nature antérieure des features. En production, cet orchestrateur serait remplacé par un DAG Airflow (une tâche par étape).'),

    // ---- 4 ----
    H1('4. Modèle Conceptuel de Données'),
    P('Comparaison argumentée des modèles multidimensionnels :'),
    B('Étoile (retenu) : faits au centre, dimensions dénormalisées — simplicité BI et performance en lecture, adapté à ~480 observations GOLD.'),
    B('Flocon (évalué, non retenu) : dimensions normalisées (région→département) — gain d\u2019intégrité insuffisant face à la complexité des jointures à cette échelle.'),
    B('Grappe / constellation (partielle) : plusieurs faits (élections, chômage, emploi) partageant dim_departement / dim_annee / dim_bloc.'),
    P('La base déployée suit donc une étoile enrichie : dimensions de référence (dim_departement, dim_annee, dim_bloc) et tables de faits par source. Ces faits sont dénormalisés dans gold_dataset_analytique, table unique prête pour le machine learning et la BI. Le schéma SQL commenté est fourni (sql/schema.sql) ; voir aussi docs/mspr/05_bi_restitution/MODELISATION_MULTIDIM.md.'),

    H1('4 bis. Stratégie Big Data'),
    P('Datalake médailon : RAW immuable, bronze normalisé, silver contrôlé, gold consommable. Ingestion parallèle des scrutins (ThreadPoolExecutor). Object store MinIO compatible S3 (docker compose --profile datalake) synchronisé via etl/03_sync_datalake.py. Pattern ELT : charge des bruts puis transformation. Scale-out cible : Airflow + workers + S3/OVH. Détail : docs/mspr/02_architecture/ARCHITECTURE_BIGDATA.md.'),

    new Paragraph({ children: [new PageBreak()] }),

    // ---- 5 ----
    H1('5. Modèles testés et résultats'),
    P('Cinq approches ont été comparées, dont une baseline (prédiction de la classe majoritaire) servant de point de référence. La métrique de sélection est le F1 macro en validation croisée groupée, robuste au déséquilibre entre blocs.'),
    table(['Modèle', 'Accuracy CV', 'F1 macro CV', 'Accuracy test 2022'], [
      ['Baseline (classe majoritaire)', '0,41', '0,15', '0,15'],
      ['Régression logistique', '0,59', '0,59', '0,35'],
      ['Arbre de décision', '0,59', '0,56', '0,05'],
      ['Random Forest (retenu)', '0,66', '0,65', '0,07'],
      ['Gradient Boosting', '0,63', '0,61', '0,27'],
    ], [3600, 1920, 1920, 1920]),
    P(''),
    P('Le Random Forest est retenu : meilleur compromis accuracy/F1 en validation croisée, et il fournit une importance des variables interprétable. L\u2019écart avec la baseline (0,66 vs 0,41) démontre que les indicateurs apportent un pouvoir prédictif réel. On note en revanche une accuracy faible sur le seul scrutin de test 2022 : ce résultat n\u2019est pas une anomalie du modèle mais reflète le caractère atypique de 2022 (forte recomposition politique, montée de l\u2019extrême droite), qu\u2019un modèle entraîné sur 2002–2017 ne pouvait pas anticiper. C\u2019est une illustration concrète des limites d\u2019une prévision électorale fondée sur les seuls indicateurs socio-économiques — la validation croisée groupée, moins dépendante d\u2019un unique scrutin, reste la mesure de référence.'),
    IMG('6_model_compare.png', 460, 259), CAP('Fig. 1 — Comparaison des modèles (validation croisée groupée par département).'),
    IMG('5_confusion.png', 360, 300), CAP('Fig. 2 — Matrice de confusion du modèle retenu sur le scrutin de test.'),
    IMG('7_importance.png', 460, 276), CAP('Fig. 3 — Importance des variables : la dynamique du chômage sur 5 ans domine.'),

    // ---- 6 ----
    H1('6. Visualisations'),
    IMG('1_evolution_blocs.png', 460, 256), CAP('Fig. 4 — Évolution du score moyen par bloc sur les cinq scrutins.'),
    IMG('3_correlations.png', 380, 309), CAP('Fig. 5 — Matrice de corrélation indicateurs / résultat.'),
    IMG('4_chomage_par_bloc.png', 420, 262), CAP('Fig. 6 — Distribution du chômage N-1 selon le bloc arrivé en tête.'),
    IMG('8_projection.png', 380, 244), CAP('Fig. 7 — Projection probabiliste du bloc en tête.'),

    new Paragraph({ children: [new PageBreak()] }),

    // ---- 7 ----
    H1('7. Réponses aux questions du client'),
    H2('Quelle donnée est la plus corrélée aux résultats ?'),
    P('La dynamique du chômage sur cinq ans (delta_chomage_5a) est la variable la plus déterminante du Random Forest (≈ 0,28), devant l\u2019emploi rapporté à la population (≈ 0,20) et la croissance de l\u2019emploi (≈ 0,15). Autrement dit, c\u2019est moins le niveau instantané du chômage que sa tendance qui est liée au vote. Le boxplot (fig. 6) illustre le lien entre chômage et blocs protestataires.'),
    H2('Principe d\u2019un apprentissage supervisé'),
    P('On fournit au modèle des exemples étiquetés — des couples (indicateurs X, résultat connu y). Le modèle apprend une fonction f(X) → y en minimisant l\u2019erreur sur un jeu d\u2019entraînement, puis on mesure sa capacité à généraliser sur un jeu de test qu\u2019il n\u2019a jamais vu. Ici, X = les six indicateurs + le lag politique, y = le bloc arrivé en tête.'),
    H2('Comment définir le degré de précision (accuracy) ?'),
    P('L\u2019accuracy est la proportion de prédictions correctes sur le jeu de test (prédictions justes / total). Nous la complétons par le F1 macro, plus robuste lorsque les classes sont déséquilibrées, et par une validation croisée groupée qui donne une estimation plus fiable qu\u2019un unique découpage. Exigence du cahier des charges : accuracy > 0,5 — atteinte (0,66 en CV groupée).'),

    // ---- 8 ----
    H1('8. Sécurité et conformité RGPD'),
    B('Données exclusivement publiques et agrégées au niveau départemental : aucune donnée à caractère personnel, aucun risque de ré-identification.'),
    B('Licence Ouverte v2.0 (Etalab) : réutilisation libre sous réserve de mentionner la source — mentions incluses dans le README et la couche BRONZE.'),
    B('Traçabilité et auditabilité : couche BRONZE immuable, journal DQM (quality_report.txt), tests automatisés et code versionné assurent la reproductibilité complète du traitement.'),
    B('Secrets externalisés (.env) ; options d\u2019hébergement cloud UE/neutre ou on-premise documentées (voir docs/mspr/06_rgpd_securite/RGPD_SECURITE.md).'),
    B('Extension future : en cas d\u2019ajout de données d\u2019opinion ou de flux de réseaux sociaux (potentiellement personnelles), une analyse d\u2019impact (AIPD) préalable, la minimisation des données et une base légale documentée seraient requises.'),

    // ---- 9 ----
    H1('9. Limites et axes d\u2019amélioration'),
    P('Limites assumées : un modèle électoral fondé sur des indicateurs socio-économiques ignore les dynamiques de campagne, l\u2019offre politique et les chocs conjoncturels ; il capte des tendances de fond, pas l\u2019issue exacte d\u2019un scrutin. Le POC démontre une méthode et son industrialisation, non une capacité de prévision définitive — ce point doit être explicité au client.'),
    B('Enrichir les features : sécurité, vie associative, démographie fine, et données infra-départementales.'),
    B('Fiabiliser le modèle : historique électoral plus long, modèles séquentiels, calibration des probabilités et intervalles de confiance.'),
    B('Industrialiser : orchestration Airflow, tests étendus, restitution PowerBI branchée sur la base pour les utilisateurs non techniques.'),

    H1('Annexe — Livrables fournis'),
    B('Code complet commenté : ETL, ML, visualisations, tests, orchestrateur.'),
    B('Notebook Jupyter d\u2019analyse exploratoire (analyse_exploratoire.ipynb).'),
    B('Jeu de données nettoyé/normalisé : base SQLite electio_poc.db + CSV GOLD.'),
    B('Schéma SQL commenté et journal qualité.'),
    B('Support de soutenance (PowerPoint).'),
  ]}],
});

Packer.toBuffer(doc).then(b => { fs.writeFileSync(path.join(OUT, 'Dossier_synthese_POC_ElectioAnalytics.docx'), b); console.log('docx OK'); });
