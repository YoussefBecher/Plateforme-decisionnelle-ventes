-- ============================================================
-- Plateforme décisionnelle ventes — schéma en étoile (PostgreSQL)
-- ============================================================
DROP VIEW  IF EXISTS v_kpi_mensuel, v_realisation_objectifs, v_rentabilite_produit, v_rentabilite_region CASCADE;
DROP TABLE IF EXISTS fait_objectifs, fait_ventes, dim_date, dim_produit, dim_client, dim_region CASCADE;

CREATE TABLE dim_date (
    id_date     INT PRIMARY KEY,          -- format AAAAMMJJ
    date        DATE NOT NULL,
    annee       INT  NOT NULL,
    trimestre   INT  NOT NULL,
    mois        INT  NOT NULL,
    nom_mois    VARCHAR(12) NOT NULL,
    annee_mois  DATE NOT NULL             -- 1er jour du mois
);

CREATE TABLE dim_region  (id_region  INT PRIMARY KEY, region VARCHAR(50) NOT NULL);
CREATE TABLE dim_client  (id_client  VARCHAR(20) PRIMARY KEY, nom_client VARCHAR(100), segment VARCHAR(50));
CREATE TABLE dim_produit (id_produit VARCHAR(30) PRIMARY KEY, nom_produit VARCHAR(200), categorie VARCHAR(50), sous_categorie VARCHAR(50));

CREATE TABLE fait_ventes (
    id_vente    SERIAL PRIMARY KEY,
    id_commande VARCHAR(30) NOT NULL,
    id_date     INT         NOT NULL REFERENCES dim_date(id_date),
    id_client   VARCHAR(20) NOT NULL REFERENCES dim_client(id_client),
    id_produit  VARCHAR(30) NOT NULL REFERENCES dim_produit(id_produit),
    id_region   INT         NOT NULL REFERENCES dim_region(id_region),
    quantite    INT,
    remise      NUMERIC(5,2),
    ca          NUMERIC(12,2) NOT NULL,   -- chiffre d'affaires
    cout        NUMERIC(12,2) NOT NULL,
    marge       NUMERIC(12,2) NOT NULL    -- ca - cout
);

CREATE TABLE fait_objectifs (
    id_region    INT  NOT NULL REFERENCES dim_region(id_region),
    annee_mois   DATE NOT NULL,
    objectif_ca  NUMERIC(12,2) NOT NULL,
    PRIMARY KEY (id_region, annee_mois)
);

CREATE INDEX idx_fv_date    ON fait_ventes(id_date);
CREATE INDEX idx_fv_produit ON fait_ventes(id_produit);
CREATE INDEX idx_fv_region  ON fait_ventes(id_region);
