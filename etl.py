"""
ETL — Plateforme décisionnelle d'analyse des ventes
Extract : lecture du CSV (format Superstore)
Transform : nettoyage, calcul CA / coût / marge, construction des dimensions
Load : chargement dans PostgreSQL (schéma en étoile défini dans schema.sql)

Usage :
    pip install pandas sqlalchemy psycopg2-binary numpy
    python generate_data.py                 # (optionnel) crée data/superstore.csv
    python etl.py data/superstore.csv
Variable d'environnement : DB_URL (défaut ci-dessous)
"""
import os
import sys
import logging

import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("etl")

DB_URL = os.getenv("DB_URL", "postgresql+psycopg2://postgres:postgres@localhost:5432/ventes_bi")
CSV_PATH = sys.argv[1] if len(sys.argv) > 1 else "data/superstore.csv"

COLONNES = {
    "Order ID": "id_commande", "Order Date": "date_commande",
    "Customer ID": "id_client", "Customer Name": "nom_client", "Segment": "segment",
    "Region": "region", "Product ID": "id_produit", "Category": "categorie",
    "Sub-Category": "sous_categorie", "Product Name": "nom_produit",
    "Sales": "ca", "Quantity": "quantite", "Discount": "remise", "Profit": "marge",
}


# ---------------------------------------------------------------- EXTRACT
def extract(path: str) -> pd.DataFrame:
    log.info("Extraction de %s", path)
    df = pd.read_csv(path, encoding="latin-1")
    log.info("%d lignes lues", len(df))
    return df


# -------------------------------------------------------------- TRANSFORM
def transform(raw: pd.DataFrame):
    manquantes = set(COLONNES) - set(raw.columns)
    if manquantes:
        raise ValueError(f"Colonnes manquantes dans le CSV : {manquantes}")

    df = raw[list(COLONNES)].rename(columns=COLONNES).copy()

    # Nettoyage
    avant = len(df)
    df = df.drop_duplicates()
    df = df.dropna(subset=["id_commande", "date_commande", "id_client", "id_produit", "region", "ca"])
    df["date_commande"] = pd.to_datetime(df["date_commande"], errors="coerce")
    df = df.dropna(subset=["date_commande"])
    df["remise"] = df["remise"].fillna(0)
    df["quantite"] = df["quantite"].fillna(1).astype(int)
    log.info("Nettoyage : %d lignes supprimées", avant - len(df))

    # Mesures calculées
    df["cout"] = (df["ca"] - df["marge"]).round(2)
    df["ca"] = df["ca"].round(2)
    df["marge"] = df["marge"].round(2)

    # Dimension date (calendrier complet)
    jours = pd.date_range(df["date_commande"].min(), df["date_commande"].max(), freq="D")
    dim_date = pd.DataFrame({"date": jours})
    dim_date["id_date"] = dim_date["date"].dt.strftime("%Y%m%d").astype(int)
    dim_date["annee"] = dim_date["date"].dt.year
    dim_date["trimestre"] = dim_date["date"].dt.quarter
    dim_date["mois"] = dim_date["date"].dt.month
    dim_date["nom_mois"] = dim_date["date"].dt.strftime("%B")
    dim_date["annee_mois"] = dim_date["date"].dt.to_period("M").dt.to_timestamp()

    # Autres dimensions
    regions = sorted(df["region"].unique())
    dim_region = pd.DataFrame({"id_region": range(1, len(regions) + 1), "region": regions})
    dim_client = df[["id_client", "nom_client", "segment"]].drop_duplicates("id_client")
    dim_produit = df[["id_produit", "nom_produit", "categorie", "sous_categorie"]].drop_duplicates("id_produit")

    # Table de faits
    df = df.merge(dim_region, on="region")
    df["id_date"] = df["date_commande"].dt.strftime("%Y%m%d").astype(int)
    fait_ventes = df[["id_commande", "id_date", "id_client", "id_produit", "id_region",
                      "quantite", "remise", "ca", "cout", "marge"]]

    # Objectifs mensuels par région (SIMULÉS : réel × facteur aléatoire reproductible)
    # À remplacer par un vrai fichier d'objectifs si vous en avez un.
    rng = np.random.default_rng(42)
    obj = (df.assign(annee_mois=df["date_commande"].dt.to_period("M").dt.to_timestamp())
             .groupby(["id_region", "annee_mois"], as_index=False)["ca"].sum())
    obj["objectif_ca"] = (obj["ca"] * rng.uniform(0.90, 1.15, len(obj))).round(2)
    fait_objectifs = obj[["id_region", "annee_mois", "objectif_ca"]]

    return {
        "dim_date": dim_date, "dim_region": dim_region, "dim_client": dim_client,
        "dim_produit": dim_produit, "fait_ventes": fait_ventes, "fait_objectifs": fait_objectifs,
    }


# ------------------------------------------------------------------- LOAD
def load(tables: dict) -> None:
    engine = create_engine(DB_URL)
    with engine.begin() as conn:
        log.info("Création du schéma (schema.sql)")
        conn.execute(text(open("schema.sql", encoding="utf-8").read()))
    # Ordre important : dimensions avant faits (clés étrangères)
    ordre = ["dim_date", "dim_region", "dim_client", "dim_produit", "fait_ventes", "fait_objectifs"]
    for nom in ordre:
        tables[nom].to_sql(nom, engine, if_exists="append", index=False, chunksize=5000)
        log.info("Table %-15s chargée : %d lignes", nom, len(tables[nom]))


def main() -> None:
    raw = extract(CSV_PATH)
    tables = transform(raw)
    load(tables)
    log.info("ETL terminé. Exécutez maintenant : psql -d ventes_bi -f kpi_queries.sql")


if __name__ == "__main__":
    main()
