import numpy as np
import pandas as pd
from scipy.spatial import ConvexHull
from scipy.spatial.distance import pdist
from itertools import combinations

# ── Constants ────────────────────────────────────────────────────────────────
TERRITORIES = ["ACAL", "ACAR", "MCAL", "MCAR", "PCAL", "PCAR", "VBL", "VBR"]

ANTERIOR     = {"ACAL", "ACAR", "MCAL", "MCAR"}
POSTERIOR    = {"PCAL", "PCAR", "VBL", "VBR"}
LEFT         = {"ACAL", "MCAL", "PCAL", "VBL"}
RIGHT        = {"ACAR", "MCAR", "PCAR", "VBR"}


def _shannon_entropy(counts):
    """Shannon entropy from a dict or array of counts (zeros ignored)."""
    counts = np.array(list(counts), dtype=float)
    counts = counts[counts > 0]
    if len(counts) == 0:
        return 0.0
    probs = counts / counts.sum()
    return -np.sum(probs * np.log2(probs))


# ── Main function ─────────────────────────────────────────────────────────────
def aggregate_lesion_features(
    df: pd.DataFrame,
    mean_columns: list[str],
    mean_sd_columns: list[str],
    patient_col: str = "Patient ID",
) -> pd.DataFrame:
    """
    Aggregate per-lesion rows into one row per patient with a rich feature set.

    Parameters
    ----------
    df : pd.DataFrame
        Input table with one row per lesion.
    mean_columns : list[str]
        Columns for which only the per-patient mean is computed.
    mean_sd_columns : list[str]
        Columns for which both mean and SD are computed (saved as
        <col>_mean and <col>_sd).
    patient_col : str
        Column containing patient identifiers.

    Returns
    -------
    pd.DataFrame
        One row per patient.
    """

    records = []

    for patient_id, grp in df.groupby(patient_col):
        row = {patient_col: patient_id}
        n   = len(grp)

        # ── Basic flag ────────────────────────────────────────────────────────
        row["is_single_lesion"] = int(n == 1)
        row["n_lesions"]        = n

        # ── User-specified aggregations ───────────────────────────────────────
        for col in mean_columns:
            row[f"{col}"] = grp[col].mean()

        for col in mean_sd_columns:
            row[f"{col}_mean"] = grp[col].mean()
            row[f"{col}_sd"]   = grp[col].std(ddof=0)

        # ── Volumes ───────────────────────────────────────────────────────────
        vols = grp["Individual lesion volume"].values.astype(float)
        row["max_lesion_volume"]    = vols.max()
        row["volume_asymmetry"]     = vols.std(ddof=0) / (vols.mean() + 1e-9)
        row["volume_ratio"] = vols.max() / vols.sum()

        # ── Centroids ─────────────────────────────────────────────────────────
        centroids = grp[["centroid_x", "centroid_y", "centroid_z"]].values

        # Volume-weighted centre of mass
        w = vols / (vols.sum() + 1e-9)
        com = (centroids * w[:, None]).sum(axis=0)
        row["com_x"], row["com_y"], row["com_z"] = com
        centroids = centroids[~np.isnan(centroids).any(axis=1)]

        # ── Spatial spread metrics ────────────────────────────────────────────
        if len(centroids) >= 2:
            pairwise = pdist(centroids)                     # all pairwise distances
            row["centroid_mean_dist"]   = pairwise.mean()
            row["centroid_max_dist"]    = pairwise.max()
            row["centroid_spread_x"]    = centroids[:, 0].std(ddof=0)
            row["centroid_spread_y"]    = centroids[:, 1].std(ddof=0)
            row["centroid_spread_z"]    = centroids[:, 2].std(ddof=0)
        else:
            for k in ["centroid_mean_dist", "centroid_max_dist",
                      "centroid_spread_x", "centroid_spread_y", "centroid_spread_z"]:
                row[k] = 0.0

        # ── Vascular territory features ───────────────────────────────────────
        terr_col  = "region"
        territories_present = set(grp[terr_col].dropna().unique())

        # One-hot per territory (count of lesions)
        terr_counts = grp[terr_col].value_counts()
        for t in TERRITORIES:
            row[f"n_lesions_{t}"] = int(terr_counts.get(t, 0))

        row["n_territories"]           = len(territories_present)
        row["territory_entropy"]       = _shannon_entropy(
            [terr_counts.get(t, 0) for t in TERRITORIES]
        )

        # Volume entropy across territories
        terr_vols = grp.groupby(terr_col)["Individual lesion volume"].sum()
        row["territory_volume_entropy"] = _shannon_entropy(
            [terr_vols.get(t, 0) for t in TERRITORIES]
        )

        # Gini coefficient helper (count- and volume-based)
        def _gini(arr):
            arr = np.array(arr, dtype=float)
            if arr.sum() == 0:
                return np.nan
            arr_s = np.sort(arr)
            n_t   = len(arr_s)
            return (2 * np.sum((np.arange(1, n_t + 1)) * arr_s)
                    / (n_t * arr_s.sum()) - (n_t + 1) / n_t)


        # Hemisphere & circulation flags
        row["bilateral"]                  = int(bool(territories_present & LEFT)
                                                and bool(territories_present & RIGHT))
        row["anterior_and_posterior"]     = int(bool(territories_present & ANTERIOR)
                                                and bool(territories_present & POSTERIOR))

        records.append(row)

    result = pd.DataFrame(records).set_index(patient_col)
    return result

