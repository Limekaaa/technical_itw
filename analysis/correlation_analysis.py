"""Correlation / redundancy analysis of the training dataset.

Goal: understand how numeric variables link to each other so redundant,
derived or noisy columns can be dropped for a more robust estimator.

What it computes (all pairwise-complete, NaNs never filled except where
explicitly noted):
  1. Pearson r matrix + two-sided p-values  (linear association)
  2. Spearman rho matrix                    (monotonic, rank-based, robust)
  3. Pairwise-N matrix                       (coverage per pair -- varies a
     lot here because missingness is structural, e.g. macros exist only
     on food-days, HR is absent for p03)
  4. Hierarchical clustering on 1-|rho| distance -> redundancy groups
  5. VIF on high-coverage complete-case subsets (multicollinearity score)
  6. Label relevance: Pearson/Spearman/MI of every feature vs
     readiness_next_day on the 290 labeled rows
     (MI uses median imputation -- documented approximation)
  7. Pooled vs within-participant correlations (participant-confound check:
     with 3 participants, pooled r can be driven by between-person level
     shifts -- Simpson-type effects)

Outputs (in analysis/): correlation_matrix_pearson.csv,
correlation_matrix_spearman.csv, correlation_pair_n.csv,
correlation_pvalues.csv, within_participant_pearson.csv,
strong_pairs.csv, vif_core.csv, label_relevance.csv,
redundancy_groups.csv + a printed text summary.

Usage: .venv/bin/python analysis/correlation_analysis.py
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats
from scipy.cluster import hierarchy
from sklearn.feature_selection import mutual_info_regression
from sklearn.linear_model import LinearRegression

BASE_DIR = Path(__file__).resolve().parents[1]
OUT_DIR = BASE_DIR / "analysis"
DATASET = BASE_DIR / "output_dataset" / "training_dataset.csv"
LABEL = "readiness_next_day"

sys.path.insert(0, str(BASE_DIR))
from src.pre_processing.pre_processor import get_feature_columns  # noqa: E402


# --------------------------------------------------------------------------
# Data prep
# --------------------------------------------------------------------------
def load_numeric_matrix():
    """Feature matrix: get_feature_columns() restricted to numeric cols.

    Drops object columns (gender/chronotype -- both constant in practice,
    see recon) and zero-variance columns (Pearson undefined for them).
    Returns (df_numeric, dropped_report).
    """
    df = pd.read_csv(DATASET)
    feats = get_feature_columns(df)
    num = df[feats].select_dtypes(include=[np.number]).copy()
    dropped = {"non_numeric": [c for c in feats if c not in num.columns]}
    zero_var = [c for c in num.columns if num[c].nunique(dropna=True) <= 1]
    num = num.drop(columns=zero_var)
    dropped["zero_variance"] = zero_var
    return df, num, dropped


# --------------------------------------------------------------------------
# Pairwise matrices
# --------------------------------------------------------------------------
def pairwise_pearson(num):
    """Pearson r + two-sided p + N for every pair (pairwise-complete)."""
    cols = list(num.columns)
    n = len(cols)
    r = pd.DataFrame(np.nan, index=cols, columns=cols)
    p = pd.DataFrame(np.nan, index=cols, columns=cols)
    cnt = pd.DataFrame(0, index=cols, columns=cols)
    for i in range(n):
        x = num[cols[i]].to_numpy()
        r.iloc[i, i] = 1.0
        p.iloc[i, i] = 0.0
        cnt.iloc[i, i] = int(np.isfinite(x).sum())
        for j in range(i + 1, n):
            y = num[cols[j]].to_numpy()
            mask = np.isfinite(x) & np.isfinite(y)
            nij = int(mask.sum())
            cnt.iloc[i, j] = cnt.iloc[j, i] = nij
            if nij < 3:
                continue
            try:
                rij, pij = stats.pearsonr(x[mask], y[mask])
            except (ValueError, TypeError):
                continue
            r.iloc[i, j] = r.iloc[j, i] = rij
            p.iloc[i, j] = p.iloc[j, i] = pij
    return r, p, cnt


def within_participant_pearson(df, cols):
    """Pearson r after subtracting participant means (within-person signal).

    Each column is demeaned per participant_id on available values, then
    correlated pairwise-complete. Contrasting this with the pooled matrix
    exposes correlations driven purely by between-participant level
    shifts (participant confounding).
    """
    wide = df[cols].copy()
    for c in cols:
        means = df.groupby("participant_id")[c].transform("mean")
        wide[c] = wide[c] - means
    return wide.corr(method="pearson", min_periods=3)


# --------------------------------------------------------------------------
# Redundancy grouping + VIF
# --------------------------------------------------------------------------
def redundancy_groups(rho, threshold=0.8):
    """Agglomerative groups with |Spearman| >= threshold.

    Distance = 1 - |rho| (NaN treated as 0 correlation), average linkage,
    flat cut at 1 - threshold. Returns list of sorted multi-member groups.
    """
    d = 1.0 - rho.abs().fillna(0.0).to_numpy()
    np.fill_diagonal(d, 0.0)
    condensed = d[np.triu_indices(len(rho), k=1)]
    if not np.all(np.isfinite(condensed)) or len(condensed) == 0:
        return []
    z = hierarchy.linkage(condensed, method="average")
    labels = hierarchy.fcluster(z, t=1.0 - threshold, criterion="distance")
    groups = {}
    for col, lab in zip(rho.columns, labels):
        groups.setdefault(lab, []).append(col)
    return sorted(
        (sorted(g) for g in groups.values() if len(g) > 1),
        key=lambda g: (-len(g), g),
    )


def vif_table(frame):
    """Variance inflation factors for a complete numeric frame.

    VIF_j = 1/(1-R^2_j): how much var(beta_j) is inflated by collinearity
    with the other columns. Rule of thumb: >10 severe, >5 moderate.
    """
    cols = list(frame.columns)
    out = []
    for j, c in enumerate(cols):
        others = [k for k in cols if k != c]
        model = LinearRegression().fit(frame[others].to_numpy(), frame[c].to_numpy())
        r2 = model.score(frame[others].to_numpy(), frame[c].to_numpy())
        vif = float("inf") if r2 >= 1.0 else 1.0 / (1.0 - r2)
        out.append({"column": c, "vif": round(vif, 2), "r2_vs_rest": round(r2, 4)})
    return pd.DataFrame(out).sort_values("vif", ascending=False).reset_index(drop=True)


# --------------------------------------------------------------------------
# Label relevance
# --------------------------------------------------------------------------
def label_relevance(df, num):
    """Pearson r / Spearman rho / MI of each feature vs the label.

    Correlations are pairwise-complete on the 290 labeled rows. MI
    (mutual_info_regression, kNN-based, captures nonlinear dependence)
    needs complete data: median imputation on labeled rows -- an
    approximation, flagged in the report.
    """
    lab = df[df[LABEL].notna()].reset_index(drop=True)
    y = lab[LABEL].to_numpy()
    rows = []
    for c in num.columns:
        x = lab[c].to_numpy()
        mask = np.isfinite(x)
        nij = int(mask.sum())
        if nij < 3:
            rows.append({"column": c, "pearson_r": np.nan, "pearson_p": np.nan,
                         "spearman_rho": np.nan, "n": nij})
            continue
        try:
            pr, pp = stats.pearsonr(x[mask], y[mask])
        except (ValueError, TypeError):
            pr, pp = np.nan, np.nan
        try:
            sr = stats.spearmanr(x[mask], y[mask]).statistic
        except (ValueError, TypeError):
            sr = np.nan
        rows.append({"column": c, "pearson_r": pr, "pearson_p": pp,
                     "spearman_rho": sr, "n": nij})
    rel = pd.DataFrame(rows)
    imp = lab[num.columns].median()
    x_imp = lab[num.columns].fillna(imp).to_numpy()
    with np.errstate(all="ignore"):
        mi = mutual_info_regression(x_imp, y, random_state=0)
    rel["mi"] = mi
    rel["abs_spearman"] = rel["spearman_rho"].abs()
    return rel.sort_values("abs_spearman", ascending=False).reset_index(drop=True)


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------
def main():
    df, num, dropped = load_numeric_matrix()
    print(f"rows={len(df)} labeled={int(df[LABEL].notna().sum())} "
          f"numeric_features={num.shape[1]}")
    print(f"dropped non-numeric: {dropped['non_numeric']}")
    print(f"dropped zero-variance: {dropped['zero_variance']}")

    print("pairwise Pearson ...")
    r_pearson, pvals, pair_n = pairwise_pearson(num)
    print("spearman ...")
    r_spearman = num.corr(method="spearman", min_periods=3)

    r_pearson.to_csv(OUT_DIR / "correlation_matrix_pearson.csv")
    r_spearman.to_csv(OUT_DIR / "correlation_matrix_spearman.csv")
    pair_n.to_csv(OUT_DIR / "correlation_pair_n.csv")
    pvals.to_csv(OUT_DIR / "correlation_pvalues.csv")

    # Strong pairs (|pearson| >= 0.6), ranked.
    recs = []
    cols = list(num.columns)
    for i in range(len(cols)):
        for j in range(i + 1, len(cols)):
            rij = r_pearson.iloc[i, j]
            if np.isfinite(rij) and abs(rij) >= 0.6:
                recs.append({"var_a": cols[i], "var_b": cols[j],
                             "pearson_r": round(float(rij), 3),
                             "spearman_rho": (round(float(r_spearman.iloc[i, j]), 3)
                                              if np.isfinite(r_spearman.iloc[i, j]) else np.nan),
                             "n": int(pair_n.iloc[i, j]),
                             "p": float(pvals.iloc[i, j]) if np.isfinite(pvals.iloc[i, j]) else np.nan})
    strong = pd.DataFrame(recs).sort_values("pearson_r", key=np.abs, ascending=False)
    strong.to_csv(OUT_DIR / "strong_pairs.csv", index=False)
    print(f"strong pairs (|r|>=0.6): {len(strong)}")

    # Redundancy groups at |rho| >= 0.8 and >= 0.9.
    groups08 = redundancy_groups(r_spearman, 0.8)
    groups09 = redundancy_groups(r_spearman, 0.9)
    with open(OUT_DIR / "redundancy_groups.csv", "w") as fh:
        fh.write("threshold,members\n")
        for g in groups09:
            fh.write(f"0.9,\"{';'.join(g)}\"\n")
        for g in groups08:
            fh.write(f"0.8,\"{';'.join(g)}\"\n")
    print(f"redundancy groups: {len(groups09)} @0.9, {len(groups08)} @0.8")

    # Within-participant matrix (confound check).
    print("within-participant Pearson ...")
    r_within = within_participant_pearson(df, cols)
    r_within.to_csv(OUT_DIR / "within_participant_pearson.csv")

    # VIF on complete-case, high-coverage subsets.
    for min_cov in (1.0, 0.95):
        cov = num.notna().mean()
        core = [c for c in num.columns if cov[c] >= min_cov]
        cc = num[core].dropna()
        print(f"VIF subset coverage>={min_cov}: {len(core)} cols, {len(cc)} complete rows")
        if len(cc) >= 100 and len(core) >= 2:
            vif = vif_table(cc[core])
            vif.to_csv(OUT_DIR / f"vif_core_cov{int(min_cov * 100)}.csv", index=False)
            print(vif.head(12).to_string(index=False))

    # Label relevance.
    print("label relevance ...")
    rel = label_relevance(df, num)
    rel.to_csv(OUT_DIR / "label_relevance.csv", index=False)
    print(rel.head(20).to_string(index=False))

    print(f"\nwrote outputs to {OUT_DIR}")


if __name__ == "__main__":
    main()
