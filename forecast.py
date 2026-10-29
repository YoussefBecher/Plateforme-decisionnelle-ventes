"""
Prévision des ventes — Plateforme décisionnelle
1) Charge le CA mensuel (depuis PostgreSQL ou depuis le CSV)
2) Compare plusieurs modèles sur les derniers mois (backtest : MAE, RMSE, MAPE)
3) Réentraîne le meilleur modèle sur tout l'historique et prévoit les N prochains mois
4) Exporte : prevision_ventes.csv, graphique PNG, et table prevision_ventes dans PostgreSQL

Usage :
    pip install pandas numpy scikit-learn matplotlib sqlalchemy psycopg2-binary
    python forecast.py                               # lit la base (vue v_kpi_mensuel)
    python forecast.py --csv data/superstore.csv     # lit directement le CSV
    python forecast.py --horizon 6 --test 6
Optionnel : pip install statsmodels  -> ajoute le modèle Holt-Winters à la comparaison.
"""
import argparse
import os
import warnings

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.linear_model import LinearRegression

warnings.filterwarnings("ignore")

DB_URL = os.getenv("DB_URL", "postgresql+psycopg2://postgres:postgres@localhost:5432/ventes_bi")


# ------------------------------------------------------------ chargement
def load_monthly(csv_path=None) -> pd.Series:
    """Retourne le CA mensuel sous forme de série indexée par le 1er jour du mois."""
    if csv_path:
        df = pd.read_csv(csv_path, encoding="latin-1", usecols=["Order Date", "Sales"])
        df["Order Date"] = pd.to_datetime(df["Order Date"])
        s = df.groupby(df["Order Date"].dt.to_period("M").dt.to_timestamp())["Sales"].sum()
    else:
        from sqlalchemy import create_engine
        df = pd.read_sql("SELECT annee_mois, ca FROM v_kpi_mensuel ORDER BY annee_mois",
                         create_engine(DB_URL), parse_dates=["annee_mois"])
        s = df.set_index("annee_mois")["ca"].astype(float)
    s = s.asfreq("MS")                      # impose une fréquence mensuelle régulière
    return s.interpolate()                  # comble un éventuel mois manquant


# ---------------------------------------------------------------- modèles
# Chaque modèle : fonction (train: Series, horizon: int) -> np.ndarray de prévisions
def modele_naif_saisonnier(train: pd.Series, h: int) -> np.ndarray:
    """Prévoit la valeur du même mois l'an dernier (référence minimale)."""
    last_year = train.iloc[-12:].to_numpy()
    return np.array([last_year[i % 12] for i in range(h)])


def _features(index: pd.DatetimeIndex, t0: int) -> pd.DataFrame:
    X = pd.DataFrame({"t": np.arange(t0, t0 + len(index))}, index=index)
    mois = pd.get_dummies(index.month, prefix="m").astype(float)
    mois.index = index
    for m in range(1, 13):                  # garantit les 12 colonnes même sur un petit échantillon
        mois[f"m_{m}"] = mois.get(f"m_{m}", 0.0)
    return pd.concat([X, mois[[f"m_{m}" for m in range(1, 13)]]], axis=1)


def modele_regression(train: pd.Series, h: int) -> np.ndarray:
    """Tendance linéaire + saisonnalité mensuelle (variables indicatrices)."""
    X = _features(train.index, 0)
    reg = LinearRegression().fit(X, train.to_numpy())
    futur = pd.date_range(train.index[-1] + pd.offsets.MonthBegin(1), periods=h, freq="MS")
    return np.maximum(reg.predict(_features(futur, len(train))), 0)


def modele_holt_winters(train: pd.Series, h: int) -> np.ndarray:
    """Lissage exponentiel triple (nécessite statsmodels et >= 24 mois)."""
    from statsmodels.tsa.holtwinters import ExponentialSmoothing
    fit = ExponentialSmoothing(train, trend="add", seasonal="add", seasonal_periods=12).fit()
    return np.maximum(fit.forecast(h).to_numpy(), 0)


def modeles_disponibles(n_mois: int) -> dict:
    modeles = {"Naïf saisonnier": modele_naif_saisonnier, "Régression tendance+saison": modele_regression}
    if n_mois >= 24:
        try:
            import statsmodels  # noqa: F401
            modeles["Holt-Winters"] = modele_holt_winters
        except ImportError:
            pass
    return modeles


# -------------------------------------------------------------- évaluation
def metriques(reel: np.ndarray, prevu: np.ndarray) -> dict:
    err = reel - prevu
    return {"MAE": np.mean(np.abs(err)),
            "RMSE": np.sqrt(np.mean(err ** 2)),
            "MAPE_%": np.mean(np.abs(err / reel)) * 100}


def backtest(serie: pd.Series, n_test: int, modeles: dict):
    train, test = serie.iloc[:-n_test], serie.iloc[-n_test:]
    lignes, previsions = [], {}
    for nom, fn in modeles.items():
        try:
            p = fn(train, n_test)
        except Exception as e:                      # un modèle qui échoue n'arrête pas le reste
            print(f"  [!] {nom} ignoré : {e}")
            continue
        previsions[nom] = p
        lignes.append({"modele": nom, **metriques(test.to_numpy(), p)})
    return pd.DataFrame(lignes).sort_values("RMSE").reset_index(drop=True), test, previsions


# ------------------------------------------------------------------- sortie
def tracer(serie, futur, test, prev_test, best, out_png):
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.plot(serie.index, serie, color="#1f4e79", lw=2, label="CA réel")
    ax.plot(test.index, prev_test, color="#999999", ls=":", lw=2, label=f"Backtest ({best})")
    ax.plot(futur.index, futur["ca_prevu"], color="#d9822b", lw=2.5, marker="o", label="Prévision")
    ax.fill_between(futur.index, futur["borne_basse"], futur["borne_haute"],
                    color="#d9822b", alpha=0.2, label="Intervalle ~95 %")
    ax.set_title("Chiffre d'affaires mensuel — réel et prévision")
    ax.set_ylabel("CA")
    ax.grid(alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_png, dpi=150)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", help="CSV Superstore (sinon lecture de la base)")
    ap.add_argument("--horizon", type=int, default=6, help="mois à prévoir")
    ap.add_argument("--test", type=int, default=6, help="mois gardés pour le backtest")
    ap.add_argument("--no-db", action="store_true", help="n'écrit pas dans PostgreSQL")
    a = ap.parse_args()

    serie = load_monthly(a.csv)
    print(f"Historique : {len(serie)} mois ({serie.index[0]:%Y-%m} -> {serie.index[-1]:%Y-%m})")
    if len(serie) < a.test + 12:
        raise SystemExit("Pas assez d'historique : il faut au moins 12 mois + le nombre de mois de test.")

    modeles = modeles_disponibles(len(serie) - a.test)
    resultats, test, prev_test = backtest(serie, a.test, modeles)
    print("\nBacktest sur les", a.test, "derniers mois :")
    print(resultats.round(2).to_string(index=False))

    best = resultats.loc[0, "modele"]
    rmse = resultats.loc[0, "RMSE"]
    print(f"\nMeilleur modèle : {best}")

    # Réentraînement sur tout l'historique + prévision
    p = modeles[best](serie, a.horizon)
    dates = pd.date_range(serie.index[-1] + pd.offsets.MonthBegin(1), periods=a.horizon, freq="MS")
    futur = pd.DataFrame({"ca_prevu": p}, index=dates)
    futur["borne_basse"] = np.maximum(futur["ca_prevu"] - 1.96 * rmse, 0)   # intervalle approximatif
    futur["borne_haute"] = futur["ca_prevu"] + 1.96 * rmse

    # Table unique réel + prévision (pratique pour Power BI)
    hist = pd.DataFrame({"ca_reel": serie})
    table = pd.concat([hist, futur]).rename_axis("annee_mois").reset_index()
    table["modele"] = np.where(table["ca_prevu"].notna(), best, None)
    table = table.round(2)

    table.to_csv("prevision_ventes.csv", index=False)
    resultats.round(2).to_csv("comparaison_modeles.csv", index=False)
    tracer(serie, futur, test, prev_test[best], best, "prevision_ventes.png")
    print("\nPrévisions :")
    print(futur.round(0).to_string())
    print("\nFichiers créés : prevision_ventes.csv, comparaison_modeles.csv, prevision_ventes.png")

    if not a.no_db:
        try:
            from sqlalchemy import create_engine
            table.to_sql("prevision_ventes", create_engine(DB_URL), if_exists="replace", index=False)
            print("Table prevision_ventes écrite dans PostgreSQL.")
        except Exception as e:
            print(f"[!] Écriture en base impossible ({e}). Le CSV reste utilisable dans Power BI.")


if __name__ == "__main__":
    main()
