"""
Génère un jeu de données de ventes fictif au format Superstore (data/superstore.csv).
Utile pour tester l'ETL tout de suite. Vous pouvez ensuite le remplacer par le vrai
fichier Superstore de Kaggle : les noms de colonnes sont identiques.
"""
import os
import numpy as np
import pandas as pd

rng = np.random.default_rng(7)
N_LIGNES = 8000

regions = ["Tunis", "Sfax", "Sousse", "Nabeul", "Bizerte"]
produits = []
catalogue = {
    "Technologie": {"Téléphones": (300, 900), "Accessoires": (15, 120), "Ordinateurs": (700, 2200)},
    "Mobilier": {"Chaises": (60, 400), "Bureaux": (150, 900), "Étagères": (40, 250)},
    "Fournitures": {"Papeterie": (3, 40), "Classeurs": (5, 60), "Imprimantes": (120, 600)},
}
for cat, sous in catalogue.items():
    for sc, (pmin, pmax) in sous.items():
        for i in range(1, 7):
            produits.append((f"{cat[:3].upper()}-{sc[:3].upper()}-{i:03d}", f"{sc} modèle {i}",
                             cat, sc, rng.uniform(pmin, pmax)))

clients = [(f"CL-{i:04d}", f"Client {i}", rng.choice(["Consommateur", "Entreprise", "Bureau à domicile"]))
           for i in range(1, 501)]

dates = pd.to_datetime("2024-01-01") + pd.to_timedelta(rng.integers(0, 3 * 365, N_LIGNES), unit="D")
rows = []
for i in range(N_LIGNES):
    p = produits[rng.integers(len(produits))]
    c = clients[rng.integers(len(clients))]
    qte = int(rng.integers(1, 8))
    remise = float(rng.choice([0, 0, 0, 0.1, 0.2, 0.3]))
    prix = p[4]
    ca = prix * qte * (1 - remise)
    cout = prix * qte * rng.uniform(0.60, 0.85)
    saison = 1.25 if dates[i].month in (11, 12) else 1.0   # pic de fin d'année
    rows.append({
        "Order ID": f"CMD-{dates[i].year}-{rng.integers(1, N_LIGNES // 2):06d}",
        "Order Date": dates[i].strftime("%Y-%m-%d"),
        "Customer ID": c[0], "Customer Name": c[1], "Segment": c[2],
        "Region": regions[rng.integers(len(regions))],
        "Product ID": p[0], "Category": p[2], "Sub-Category": p[3], "Product Name": p[1],
        "Sales": round(ca * saison, 2), "Quantity": qte, "Discount": remise,
        "Profit": round(ca * saison - cout * saison, 2),
    })

os.makedirs("data", exist_ok=True)
pd.DataFrame(rows).to_csv("data/superstore.csv", index=False, encoding="latin-1")
print(f"data/superstore.csv créé ({N_LIGNES} lignes)")
