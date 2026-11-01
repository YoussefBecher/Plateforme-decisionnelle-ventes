# Plateforme décisionnelle d'analyse et de prévision des ventes

Système complet d'aide à la décision : un pipeline **ETL en Python**, un **entrepôt de données SQL (PostgreSQL)** en schéma en étoile, une **prévision des ventes** à six mois, et un **tableau de bord** (Power BI et page web interactive).

**Technologies** : Python (pandas, scikit-learn, statsmodels), SQL / PostgreSQL, Power BI (DAX), HTML / JavaScript.

**Voir le tableau de bord en ligne** : https://youssefbecher.github.io/Plateforme-decisionnelle-ventes/
![Tableau de bord](images/dashboard.png)

## Indicateurs suivis

| Indicateur | Définition |
|---|---|
| Chiffre d'affaires | Somme des ventes |
| Marge bénéficiaire | Marge ÷ chiffre d'affaires |
| Croissance mensuelle | (CA du mois − CA du mois précédent) ÷ CA du mois précédent |
| Panier moyen | CA ÷ nombre de commandes distinctes |
| Taux de réalisation | CA réalisé ÷ objectif de la période |

Analyses complémentaires : rentabilité par produit et par région, classement des produits les plus et les moins rentables, prévision du CA.

## Architecture

```
CSV de ventes ──► etl.py (extraction, nettoyage, calculs) ──► PostgreSQL (schéma en étoile)
                                                                   │
                                      kpi_queries.sql (vues KPI) ◄─┤
                                      forecast.py (prévision)   ───┘
                                                                   ▼
                                         Power BI (modèle + mesures DAX)  /  index.html
```

**Modèle de données** : une table de faits `fait_ventes` reliée aux dimensions `dim_date`, `dim_produit`, `dim_client` et `dim_region`, plus une table `fait_objectifs` pour les objectifs mensuels par région.

## Contenu du dépôt

| Fichier | Rôle |
|---|---|
| `generate_data.py` | Génère un jeu de données de démonstration au format Superstore (8 000 lignes, 2024-2026) |
| `etl.py` | Extraction, nettoyage, construction des dimensions et chargement dans PostgreSQL |
| `schema.sql` | Création du schéma en étoile |
| `kpi_queries.sql` | Vues SQL des KPI (mensuel, objectifs, rentabilité par produit et région) |
| `forecast.py` | Prévision du CA : comparaison de modèles sur un backtest, puis prévision à 6 mois |
| `ventes_dashboard.pbix` | Rapport Power BI (modèle, mesures DAX, 3 pages) |
| `index.html` | Tableau de bord web interactif, autonome |

## Lancer le projet

Prérequis : Python 3.10 ou plus, PostgreSQL.

```bash
pip install pandas numpy scikit-learn matplotlib sqlalchemy psycopg2-binary
# optionnel : pip install statsmodels   (ajoute le modèle Holt-Winters)

# 1. créer la base
psql -U postgres -c "CREATE DATABASE ventes_bi;"

# 2. indiquer la connexion (adapter l'utilisateur, le mot de passe et le port)
export DB_URL="postgresql+psycopg2://postgres:MOT_DE_PASSE@127.0.0.1:5432/ventes_bi"
# Windows PowerShell : $env:DB_URL="postgresql+psycopg2://postgres:MOT_DE_PASSE@127.0.0.1:5432/ventes_bi"

# 3. pipeline
python generate_data.py                  # crée data/superstore.csv
python etl.py data/superstore.csv        # charge l'entrepôt
psql -U postgres -d ventes_bi -f kpi_queries.sql   # crée les vues KPI
python forecast.py                       # prévision + table prevision_ventes
```

Sans base de données, la prévision se lance directement sur le CSV :
`python forecast.py --csv data/superstore.csv --no-db`

Dans Power BI : *Obtenir les données*, *Base de données PostgreSQL*, puis importer les tables `fait_ventes`, `fait_objectifs`, `dim_*` et `prevision_ventes`.

## Prévision des ventes

`forecast.py` compare trois modèles sur les 6 derniers mois conservés comme jeu de test, puis réentraîne le meilleur sur tout l'historique :

- modèle naïf saisonnier (valeur du même mois l'année précédente), qui sert de référence ;
- régression linéaire avec tendance et saisonnalité mensuelle ;
- lissage exponentiel de Holt-Winters.

Les erreurs sont mesurées par MAE, RMSE et MAPE, et l'intervalle de confiance d'environ 95 % est déduit de l'erreur de test.

## Résultats sur les données de démonstration

- Chiffre d'affaires cumulé : 11,57 M, marge : 2,19 M (18,9 %).
- Panier moyen : 1 994 sur 5 803 commandes.
- Réalisation des objectifs : 98 %.
- Prévision janvier-juin 2027 par Holt-Winters : entre 282 k et 333 k de CA mensuel (MAPE d'environ 9 % sur le backtest).

## Limites

- Les données sont **générées aléatoirement** : elles servent à démontrer le pipeline, pas à tirer des conclusions commerciales. Le script accepte aussi le vrai fichier Superstore de Kaggle, qui a les mêmes colonnes.
- Les objectifs mensuels sont **simulés** (CA réel multiplié par un facteur aléatoire reproductible).
- Avec 36 mois d'historique, la prévision reste indicative.

## Pistes d'amélioration

- Orchestrer l'ETL avec un planificateur (cron, Airflow).
- Ajouter des tests de qualité de données.
- Ajouter un modèle de prévision par région ou par catégorie.
