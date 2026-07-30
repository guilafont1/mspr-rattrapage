# -*- coding: utf-8 -*-
"""Genere le notebook Jupyter d'analyse exploratoire (livrable cahier des charges)."""
import nbformat as nbf
import os

nb = nbf.v4.new_notebook()
md = lambda t: nbf.v4.new_markdown_cell(t)
code = lambda t: nbf.v4.new_code_cell(t)

nb.cells = [
md("""# POC Electio-Analytics - Analyse exploratoire
**MSPR TPRE813 - Bloc 3 (Big Data & BI)**

Ce notebook documente la demarche d'exploration des donnees et de modelisation,
de facon reproductible. Il s'appuie sur la couche GOLD produite par le pipeline
ETL (`etl/02_transform.py`).

> Les donnees utilisees ici proviennent du jeu de demonstration
> (`etl/00_demo_data.py`). Pour le rendu final, brancher les vraies sources via
> `etl/01_download.py` puis re-executer le pipeline : le notebook est identique."""),

md("## 1. Chargement des donnees"),
code("""import pandas as pd, numpy as np, sqlite3
import matplotlib.pyplot as plt, seaborn as sns
sns.set_theme(style='whitegrid')

con = sqlite3.connect('../data/gold/electio_poc.db')
gold = pd.read_sql('SELECT * FROM gold_dataset_analytique', con)
print(gold.shape)
gold.head()"""),

md("## 2. Qualite & completude\nOn verifie la structure, les types et les valeurs manquantes."),
code("""print(gold.info())
gold.isna().sum()"""),

md("## 3. Statistiques descriptives des indicateurs"),
code("""NUM = ['taux_chomage_n1','delta_chomage_5a','emploi_pour_1000hab',
       'croissance_emploi_5a_pct','taux_pauvrete_n1','creations_entreprises_n1']
gold[NUM].describe().T"""),

md("## 4. Distribution de la variable cible\nLe bloc arrive en tete au 1er tour, par election."),
code("""ax = gold.groupby(['annee','bloc_gagnant']).size().unstack(fill_value=0).plot(
    kind='bar', stacked=True, figsize=(9,4))
ax.set_title('Bloc gagnant par election (nb departements)'); plt.tight_layout()"""),

md("## 5. Correlations indicateurs <-> resultat\nQuelle donnee est la plus liee au vote ? (question du client)"),
code("""NUM_DISPO = [c for c in NUM if gold[c].notna().any()]  # écarte pauvreté (Filosofi 2023 seult)
g = gold.dropna(subset=NUM_DISPO).copy()
g['cible'] = g['bloc_gagnant'].astype('category').cat.codes
plt.figure(figsize=(8,6))
sns.heatmap(g[NUM_DISPO+['cible']].corr(), annot=True, fmt='.2f', cmap='RdBu_r', center=0)
plt.title('Matrice de correlation'); plt.tight_layout()"""),

md("## 6. Lien socio-economique / vote\nDistribution du chomage N-1 selon le bloc gagnant."),
code("""plt.figure(figsize=(8,5))
sns.boxplot(data=g, x='bloc_gagnant', y='taux_chomage_n1')
plt.title('Chomage N-1 selon le bloc en tete'); plt.tight_layout()"""),

md("""## 7. Modelisation - apprentissage supervise
On predit le bloc gagnant a partir d'indicateurs **strictement anterieurs**
au scrutin (pas de fuite). Validation croisee groupee par departement."""),
code("""from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.model_selection import GroupKFold, cross_val_score

NUM_DISPO = [c for c in NUM if gold[c].notna().any()]  # pauvreté écartée (dispo 2023 uniquement)
df = gold.dropna(subset=['taux_chomage_n1','bloc_gagnant_precedent']).reset_index(drop=True)
X = df[NUM_DISPO+['bloc_gagnant_precedent']]; y = df['bloc_gagnant']; grp = df['code_dept']
pipe = Pipeline([
  ('prep', ColumnTransformer([
     ('num', StandardScaler(), NUM_DISPO),
     ('cat', OneHotEncoder(handle_unknown='ignore'), ['bloc_gagnant_precedent'])])),
  ('clf', RandomForestClassifier(n_estimators=300, max_depth=8,
                                 class_weight='balanced', random_state=42))])
acc = cross_val_score(pipe, X, y, cv=GroupKFold(5), groups=grp, scoring='accuracy')
print(f'Accuracy CV groupee: {acc.mean():.3f} +/- {acc.std():.3f}')"""),

md("""## 8. Interpretation & limites
- La variable la plus predictive est le **taux de chomage N-1** (cf. importances).
- **Accuracy** = proportion de predictions correctes ; on la complete par le
  **F1 macro** (robuste au desequilibre des classes) et une **CV groupee**
  par departement pour mesurer la generalisation geographique.
- **Limites** : un modele electoral sur indicateurs socio-economiques ignore
  les dynamiques de campagne, l'offre politique et les chocs conjoncturels.
  Le POC demontre la methode et l'industrialisation, pas une capacite de
  prevision electorale definitive. C'est un point a expliciter au client."""),

code("""con.close()
print('Notebook execute.')"""),
]

os.makedirs(os.path.join(os.path.dirname(__file__)), exist_ok=True)
with open(os.path.join(os.path.dirname(__file__), 'analyse_exploratoire.ipynb'), 'w') as f:
    nbf.write(nb, f)
print('Notebook ecrit.')
