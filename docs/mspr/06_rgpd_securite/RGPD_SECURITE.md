# RGPD & sécurité — méthodologie de collecte

## Nature des données
| Critère | Statut POC |
|---|---|
| Source | data.gouv.fr / INSEE — **Licence Ouverte v2.0 (Etalab)** |
| Granularité | Département (agrégat) |
| Données personnelles | **Aucune** |
| Ré-identification | Non pertinente (pas d’individus) |

## Licence Ouverte v2.0 — obligations & droits
- **Paternité** : mentionner la source (INSEE, Ministère de l’Intérieur / data.gouv) dans tout livrable et dashboard.
- **Le client peut** : réutiliser, adapter, commercialiser les **traitements** et modèles dérivés, sous réserve de la mention de paternité des données sources.
- **Le client ne peut pas** : laisser croire que le producteur public cautionne le produit ; supprimer les mentions légales des jeux d’origine.
- **PI du POC** : code, mapping blocs, features et modèles = actifs projet / prestataire selon contrat ; les données brutes restent sous LO v2.0.

## Clauses contractuelles types (client / fournisseur)
1. Périmètre données : uniquement sources publiques agrégées listées au référentiel.
2. Responsabilité : le fournisseur garantit la traçabilité médailon et l’absence volontaire de données personnelles.
3. Si le client ajoute opinion / réseaux sociaux → **AIPD** + avenant base légale avant ingestion.
4. Réversibilité : export Gold (CSV/SQL) + manifests ; secrets hors dépôt.

## Principes respectés
1. **Minimisation** — uniquement indicateurs nécessaires au modèle.
2. **Finalité** — POC de prévision électorale / aide à la décision.
3. **Exactitude** — contrôles DQM + tests + SANITY anti-demo + checkpoint GX.
4. **Limitation de conservation** — jeux versionnés dans `data/` ; bruts archivés en RAW/MinIO.
5. **Intégrité / confidentialité** — secrets hors dépôt (`.env`), pas de credentials en dur.

## Sécurité opérationnelle (POC)
- Séparation des services Docker (db / api / ui / minio / metabase).
- Variables d’environnement pour Postgres / MinIO / Aiven SSL.
- **Rotation du secret Aiven** : le mot de passe / certificat est lu depuis `.env` (non versionné) ; rotation = régénérer sur la console Aiven, mettre à jour `.env`, redémarrer `backend` — aucune clé dans le dépôt Git (preuve : `.gitignore` + `.env.example` sans secret).
- Bronze immuable = piste d’audit.
- Journal qualité = preuve de traçabilité des traitements.

## Options d’hébergement (deck)
- **Cloud** (ex. Suisse / UE) : conformité RGPD, moindre exposition Cloud Act US.
- **On-premise** : souveraineté, VLAN isolé, cible ISO 27001 / RSSI.

## Si le périmètre évolue (données d’opinion, réseaux sociaux)
- AIPD (analyse d’impact)
- Base légale documentée
- Anonymisation / agrégation
- Clauses contractuelles client-fournisseur

## Phrase orale type niveau 3
« Méthodologie conforme par conception : données publiques LO v2.0 avec paternité, minimisation, secrets externalisés et rotatifs (Aiven), auditabilité médailon. Nous savons basculer en AIPD si le client ajoute de la donnée personnelle. »

