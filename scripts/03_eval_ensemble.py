#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

# pip install properscoring
from properscoring import crps_ensemble  # CRPS for ensemble forecasts :contentReference[oaicite:3]{index=3}


LAKE_COLS = ["sp", "mh", "er", "sc"]


def read_obs(obs_csv: Path) -> pd.DataFrame:
    df = pd.read_csv(obs_csv, parse_dates=["date"])
    df = df.set_index("date").sort_index()
    return df


def read_member_levels(member_dir: Path) -> pd.DataFrame:
    """
    TODO: customize this to your model outputs.

    Return a DataFrame with:
      index: monthly dates (e.g., 2019-01-01 ... 2019-12-01)
      columns: LAKE_COLS (subset allowed)

    Example if each member writes: output/water_levels.csv with 'date,sp,mh,er,sc'
    """
    out_csv = member_dir / "output" / "water_levels.csv"
    if not out_csv.exists():
        raise FileNotFoundError(
            f"Expected output not found: {out_csv}\n"
            "Edit read_member_levels() to match your model output filenames."
        )

    df = pd.read_csv(out_csv, parse_dates=["date"]).set_index("date").sort_index()
    # Keep only expected lake cols if present
    cols = [c for c in LAKE_COLS if c in df.columns]
    return df[cols]


def rank_histogram(obs: np.ndarray, ens: np.ndarray) -> np.ndarray:
    """
    obs: (T,) observations
    ens: (T, M) ensemble members
    Returns histogram counts of size M+1 (verification rank bins).
    """
    T, M = ens.shape
    counts = np.zeros(M + 1, dtype=int)

    for t in range(T):
        if np.isnan(obs[t]) or np.any(np.isnan(ens[t, :])):
            continue
        # Rank of obs among ensemble (with random tie-breaking)
        combined = np.concatenate([ens[t, :], [obs[t]]])
        # Use stable ranking with random jitter for ties:
        jitter = np.random.uniform(-1e-9, 1e-9, size=combined.shape)
        ranks = np.argsort(combined + jitter)
        obs_rank = int(np.where(ranks == M)[0][0])  # obs is last element
        counts[obs_rank] += 1

    return counts


def main():
    root = Path(__file__).resolve().parents[1]
    exp_root = root / "experiments" / "ens_climo_2019"
    members_root = exp_root / "members"
    metrics_dir = exp_root / "metrics"
    metrics_dir.mkdir(parents=True, exist_ok=True)

    obs = read_obs(root / "data" / "obs_levels_2019.csv")

    member_dirs = sorted([p for p in members_root.iterdir() if p.is_dir()])
    if not member_dirs:
        raise RuntimeError("No members found. Run scripts/01_make_ensemble_inputs.py and 02_run_ensemble.py first.")

    # Read all members -> align on common dates/cols
    member_dfs: List[pd.DataFrame] = []
    member_names: List[str] = []

    for md in member_dirs:
        dfm = read_member_levels(md)
        member_dfs.append(dfm)
        member_names.append(md.name)

    # Align all members to intersection
    common_index = obs.index
    for dfm in member_dfs:
        common_index = common_index.intersection(dfm.index)

    if len(common_index) == 0:
        raise RuntimeError("No overlapping dates between obs and member outputs.")

    cols = [c for c in LAKE_COLS if c in obs.columns]
    for dfm in member_dfs:
        cols = [c for c in cols if c in dfm.columns]

    if not cols:
        raise RuntimeError("No common lake columns between obs and member outputs.")

    obs_al = obs.loc[common_index, cols].copy()

    # Stack ensemble: (T, M) per lake
    # Build a dict lake -> ens_matrix
    ens_by_lake: Dict[str, np.ndarray] = {}
    for lk in cols:
        mats = []
        for dfm in member_dfs:
            mats.append(dfm.loc[common_index, lk].to_numpy())
        ens_by_lake[lk] = np.stack(mats, axis=1)  # (T, M)

    # Compute CRPS per lake (mean over time) + per-month table
    crps_rows = []
    rh_rows = []

    for lk in cols:
        y = obs_al[lk].to_numpy()          # (T,)
        f = ens_by_lake[lk]                # (T, M)
        # properscoring expects forecasts shape (..., M)
        crps_t = crps_ensemble(y, f)       # (T,) :contentReference[oaicite:4]{index=4}

        crps_rows.append({
            "lake": lk,
            "crps_mean": float(np.nanmean(crps_t)),
            "n": int(np.sum(~np.isnan(crps_t))),
        })

        # Rank histogram
        rh = rank_histogram(y, f)          # (M+1,)
        rh_rows.append(pd.Series(rh, name=lk))

        # Save per-time CRPS
        out_crps_ts = pd.DataFrame({"date": common_index, "crps": crps_t}).set_index("date")
        out_crps_ts.to_csv(metrics_dir / f"crps_timeseries_{lk}.csv")

    pd.DataFrame(crps_rows).to_csv(metrics_dir / "crps_summary.csv", index=False)

    rh_df = pd.DataFrame(rh_rows).T
    rh_df.index = [f"rankbin_{i}" for i in range(rh_df.shape[0])]
    rh_df.to_csv(metrics_dir / "rank_histograms.csv")

    print("Wrote:")
    print(" -", metrics_dir / "crps_summary.csv")
    print(" -", metrics_dir / "rank_histograms.csv")
    print(" -", metrics_dir / "crps_timeseries_<lake>.csv")


if __name__ == "__main__":
    main()
