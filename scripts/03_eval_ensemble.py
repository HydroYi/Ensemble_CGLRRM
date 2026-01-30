#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from properscoring import crps_ensemble

REPO_ROOT = Path(__file__).resolve().parents[1]
EXP_DIR = REPO_ROOT / "experiments" / "ens_climo_2019"
MEMBERS_DIR = EXP_DIR / "members"
METRICS_DIR = EXP_DIR / "metrics"

# Lakes you want to evaluate (match your output columns)
LAKES = ["sp", "mh", "er", "sc"]

# Observed BOM or monthly mean levels for 2019 (you can point to IJC data if you have it there)
OBS_LEVELS_CSV = REPO_ROOT / "data" / "obs_levels_2019.csv"   # create this

def read_obs(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["date"]).set_index("date").sort_index()
    return df

def read_member_levels(member_dir: Path) -> pd.DataFrame:
    """
    EDIT THIS to match your model outputs.

    Return DataFrame:
      index = monthly dates (2019-01-01 .. 2019-12-01)
      columns include LAKES (subset ok)
    """
    # Example placeholder:
    out_csv = member_dir / "output" / "water_levels.csv"
    if not out_csv.exists():
        raise FileNotFoundError(f"Expected {out_csv}. Edit read_member_levels() to match your output file(s).")
    df = pd.read_csv(out_csv, parse_dates=["date"]).set_index("date").sort_index()
    cols = [c for c in LAKES if c in df.columns]
    return df[cols]

def rank_histogram(obs: np.ndarray, ens: np.ndarray, seed: int = 123) -> np.ndarray:
    """
    obs: (T,)
    ens: (T, M)
    returns counts (M+1,)
    """
    rng = np.random.default_rng(seed)
    T, M = ens.shape
    counts = np.zeros(M + 1, dtype=int)
    for t in range(T):
        if np.isnan(obs[t]) or np.any(np.isnan(ens[t, :])):
            continue
        combined = np.concatenate([ens[t, :], [obs[t]]])
        jitter = rng.uniform(-1e-9, 1e-9, size=combined.shape)
        ranks = np.argsort(combined + jitter)
        obs_rank = int(np.where(ranks == M)[0][0])
        counts[obs_rank] += 1
    return counts

def main():
    METRICS_DIR.mkdir(parents=True, exist_ok=True)
    obs = read_obs(OBS_LEVELS_CSV)

    members = sorted([p for p in MEMBERS_DIR.iterdir() if p.is_dir()])
    if not members:
        raise RuntimeError("No members found. Run make_inputs + run first.")

    member_names: List[str] = []
    member_dfs: List[pd.DataFrame] = []
    for mdir in members:
        member_names.append(mdir.name)
        member_dfs.append(read_member_levels(mdir))

    # Align dates and lakes
    common_index = obs.index
    for dfm in member_dfs:
        common_index = common_index.intersection(dfm.index)
    common_lakes = [lk for lk in LAKES if lk in obs.columns]
    for dfm in member_dfs:
        common_lakes = [lk for lk in common_lakes if lk in dfm.columns]

    if len(common_index) == 0 or len(common_lakes) == 0:
        raise RuntimeError("No overlapping dates/lakes between obs and ensemble outputs.")

    obs_al = obs.loc[common_index, common_lakes]

    # Stack ensemble by lake: (T, M)
    ens_by_lake: Dict[str, np.ndarray] = {}
    for lk in common_lakes:
        ens_by_lake[lk] = np.stack([dfm.loc[common_index, lk].to_numpy() for dfm in member_dfs], axis=1)

    # CRPS
    crps_summary = []
    crps_monthly_rows = []
    for lk in common_lakes:
        y = obs_al[lk].to_numpy()
        f = ens_by_lake[lk]          # (T,M)
        crps_t = crps_ensemble(y, f) # (T,)
        crps_summary.append({"lake": lk, "crps_mean": float(np.nanmean(crps_t)), "n": int(np.sum(~np.isnan(crps_t)))})
        for dt, val in zip(common_index, crps_t):
            crps_monthly_rows.append({"date": dt, "lake": lk, "crps": float(val)})

    pd.DataFrame(crps_summary).to_csv(METRICS_DIR / "crps_summary.csv", index=False)
    pd.DataFrame(crps_monthly_rows).to_csv(METRICS_DIR / "crps_by_lake_and_month.csv", index=False)

    # Rank histograms
    rh_counts = {}
    for lk in common_lakes:
        y = obs_al[lk].to_numpy()
        f = ens_by_lake[lk]
        counts = rank_histogram(y, f)
        rh_counts[lk] = counts

        # plot
        plt.figure()
        plt.bar(np.arange(len(counts)), counts)
        plt.title(f"Rank histogram (2019) - {lk}")
        plt.xlabel("Rank bin (0..M)")
        plt.ylabel("Count")
        plt.tight_layout()
        plt.savefig(METRICS_DIR / f"rankhist_{lk}.png", dpi=200)
        plt.close()

    # Save counts
    rh_df = pd.DataFrame({lk: rh_counts[lk] for lk in rh_counts})
    rh_df.index = [f"bin_{i}" for i in rh_df.index]
    rh_df.to_csv(METRICS_DIR / "rankhist_counts.csv")

    print("Wrote metrics to:", METRICS_DIR)

if __name__ == "__main__":
    main()
