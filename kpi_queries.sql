-- ============================================================
-- Vues KPI — à exécuter après l'ETL (psql -f kpi_queries.sql)
-- Power BI se connecte directement à ces vues.
-- ============================================================

-- 1) KPI mensuels : CA, marge, marge %, panier moyen, croissance mensuelle
CREATE OR REPLACE VIEW v_kpi_mensuel AS
WITH mensuel AS (
    SELECT d.annee_mois,
           SUM(f.ca)                      AS ca,
           SUM(f.marge)                   AS marge,
           COUNT(DISTINCT f.id_commande)  AS nb_commandes
    FROM fait_ventes f
    JOIN dim_date d USING (id_date)
    GROUP BY d.annee_mois
)
SELECT annee_mois,
       ROUND(ca, 2)                                              AS ca,
       ROUND(marge, 2)                                           AS marge,
       ROUND(100 * marge / NULLIF(ca, 0), 2)                     AS marge_pct,
       nb_commandes,
       ROUND(ca / NULLIF(nb_commandes, 0), 2)                    AS panier_moyen,
       ROUND(100 * (ca - LAG(ca) OVER (ORDER BY annee_mois))
             / NULLIF(LAG(ca) OVER (ORDER BY annee_mois), 0), 2) AS croissance_mensuelle_pct
FROM mensuel;

-- 2) Taux de réalisation des objectifs, par région et par mois
CREATE OR REPLACE VIEW v_realisation_objectifs AS
SELECT o.annee_mois,
       r.region,
       ROUND(COALESCE(v.ca, 0), 2)                                  AS ca_realise,
       o.objectif_ca,
       ROUND(100 * COALESCE(v.ca, 0) / NULLIF(o.objectif_ca, 0), 2) AS taux_realisation_pct
FROM fait_objectifs o
JOIN dim_region r USING (id_region)
LEFT JOIN (
    SELECT d.annee_mois, f.id_region, SUM(f.ca) AS ca
    FROM fait_ventes f JOIN dim_date d USING (id_date)
    GROUP BY d.annee_mois, f.id_region
) v ON v.annee_mois = o.annee_mois AND v.id_region = o.id_region;

-- 3) Rentabilité par produit (produits rentables et produits à perte)
CREATE OR REPLACE VIEW v_rentabilite_produit AS
SELECT p.categorie, p.sous_categorie, p.nom_produit,
       ROUND(SUM(f.ca), 2)                                AS ca,
       ROUND(SUM(f.marge), 2)                             AS marge,
       ROUND(100 * SUM(f.marge) / NULLIF(SUM(f.ca), 0), 2) AS marge_pct,
       RANK() OVER (ORDER BY SUM(f.marge) DESC)           AS rang_marge
FROM fait_ventes f
JOIN dim_produit p USING (id_produit)
GROUP BY p.categorie, p.sous_categorie, p.nom_produit;

-- 4) Rentabilité par région
CREATE OR REPLACE VIEW v_rentabilite_region AS
SELECT r.region,
       ROUND(SUM(f.ca), 2)                                 AS ca,
       ROUND(SUM(f.marge), 2)                              AS marge,
       ROUND(100 * SUM(f.marge) / NULLIF(SUM(f.ca), 0), 2) AS marge_pct,
       ROUND(SUM(f.ca) / COUNT(DISTINCT f.id_commande), 2) AS panier_moyen
FROM fait_ventes f
JOIN dim_region r USING (id_region)
GROUP BY r.region;

-- ------------------------------------------------------------
-- Requêtes d'exemple (à lancer pour vérifier / pour le README)
-- ------------------------------------------------------------
-- SELECT * FROM v_kpi_mensuel ORDER BY annee_mois;
-- SELECT * FROM v_rentabilite_produit ORDER BY rang_marge LIMIT 10;      -- Top 10 produits
-- SELECT * FROM v_rentabilite_produit ORDER BY rang_marge DESC LIMIT 10; -- Pires produits
-- SELECT region, AVG(taux_realisation_pct) FROM v_realisation_objectifs GROUP BY region;
