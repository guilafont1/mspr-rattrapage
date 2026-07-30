# Documentation Electio-Analytics

Index des livrables et argumentaires MSPR (Bloc 3 Big Data & BI).

## Arborescence

```
docs/
├── README.md                 ← ce fichier
├── scripts/                  ← génération deck / dossier Word
├── livrables/                ← PPTX + DOCX prêts à remettre
└── mspr/
    ├── 01_sujet_grille/      ← sujet, grilles, règles officielles
    ├── 02_architecture/      ← médailon, diagrammes, scale-out
    ├── 03_donnees/           ← référentiel sources + dataviz
    ├── 04_machine_learning/  ← analyse classes + chiffres figés
    ├── 05_bi_restitution/    ← étoile SQL + Metabase
    ├── 06_rgpd_securite/     ← conformité & secrets
    └── 07_soutenance/        ← argumentaire niveau 3
```

## Par compétence grille

| Compétence | Dossier |
|---|---|
| C1 / C2 / C3 Architecture & Big Data | `mspr/02_architecture/` |
| C5 Data visualisation | `mspr/03_donnees/TECHNIQUES_DATAVIZ.md` |
| C6 Référentiel données | `mspr/03_donnees/REFERENTIEL_DONNEES.md` |
| C4 / C8 ML & qualité | `mspr/04_machine_learning/` + `gx/` |
| C7 BI | `mspr/05_bi_restitution/` |
| C9 RGPD | `mspr/06_rgpd_securite/` |
| Oral / grille niveau 3 | `mspr/07_soutenance/` |

## Régénérer les livrables

```bash
cd docs/scripts
npm install pptxgenjs docx
node make_deck.js      # → ../livrables/*.pptx
node make_report.js    # → ../livrables/*.docx
```

Chiffres à coller : `mspr/04_machine_learning/CHIFFRES_FIGES.md`.
