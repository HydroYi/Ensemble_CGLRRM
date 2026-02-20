#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
from typing import Dict, List
import sys

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from properscoring import crps_ensemble

REPO_ROOT = Path(__file__).resolve().parents[1]

# Get year from command line argument, default to 2000
TARGET_YEAR = int(sys.argv[1]) if len(sys.argv) > 1 else 2000
EXP_DIR = REPO_ROOT / "experiments" / f"ens_climo_{TARGET_YEAR}"
MEMBERS_DIR = EXP_DIR / "members"
METRICS_DIR = EXP_DIR / "metrics"
CC_DATA_DIR = REPO_ROOT / "CC_data"

# Lakes you want to evaluate
LAKES = ["sp", "mh", "er", "sc"]

def read_obs(target_year: int) -> pd.DataFrame:
    """
    Read observed water levels from CC_data folder.
    Expects files like Lake***_MonthlyMeanWaterLevels_1918to2026.csv
    Returns DataFrame with monthly mean levels for the target year.
    """
    lake_mapping = {
        'sp': 'Superior',
        'mh': 'MichiganHuron',
        'er': 'Erie',
        'sc': 'StClair',
    }

    records = []

    for lake_code, lake_name in lake_mapping.items():
        # Find the file matching this lake
        pattern = f"Lake{lake_name}_MonthlyMeanWaterLevels*.csv"
        matches = list(CC_DATA_DIR.glob(pattern))

        if not matches:
            print(f"WARNING: No observed data file found for {lake_name}")
            continue

        filepath = matches[0]

        # Parse the CSV file
        with open(filepath, 'r') as f:
            lines = f.readlines()

        for line in lines:
            # Skip header and comments
            if not line.strip() or line.strip().startswith('#'):
                continue
            if 'Year' in line:  # Skip column header line
                continue

            # Parse data line: Year, Jan, Feb, ...
            parts = [p.strip() for p in line.split(',')]
            if len(parts) < 2:
                continue

            try:
                year = int(parts[0])
                if year != target_year:
                    continue

                # Extract monthly values
                for month_idx in range(12):
                    if len(parts) > month_idx + 1:
                        try:
                            level = float(parts[month_idx + 1])
                            if level != -9999:  # -9999 means no data
                                # Create date as end of month
                                if month_idx < 11:
                                    date = pd.Timestamp(f"{year}-{month_idx+2:02d}-01") - pd.Timedelta(days=1)
                                else:
                                    date = pd.Timestamp(f"{year}-12-31")

                                records.append({
                                    'date': date,
                                    'lake': lake_code,
                                    'level': level
                                })
                        except ValueError:
                            continue
            except ValueError:
                continue

    if not records:
        raise ValueError(f"Could not read any observed data for year {target_year}")

    df = pd.DataFrame(records)
    df = df.pivot_table(index='date', columns='lake', values='level', aggfunc='first')
    df = df.sort_index()

    return df

def read_member_levels(member_dir: Path) -> pd.DataFrame:
    """
    Read CGLRRM model outputs from a member directory.
    Reads the monthly mean level files: spmmlv.*, mhmmlv.*, ermmlv.*, scmmlv.*

    Each file contains one line with: Year Month1 Month2 ... Month12

    Return DataFrame:
      index = monthly dates (2019-01-31, 2019-02-28, etc)
      columns include LAKES
    """
    lake_files = {
        'sp': 'spmmlv',
        'mh': 'mhmmlv',
        'er': 'ermmlv',
        'sc': 'scmmlv',
    }

    records = []

    for lake_code, filename_prefix in lake_files.items():
        # Find the file with this prefix
        pattern = f"{filename_prefix}.{member_dir.name}"
        filepath = member_dir / "output" / pattern

        if not filepath.exists():
            continue

        # Parse the file - contains Year and 12 monthly values
        with open(filepath, 'r') as f:
            lines = f.readlines()

        for line in lines:
            # Skip header and empty lines
            if not line.strip() or line.strip().startswith('#'):
                continue
            if 'Units' in line or 'Interval' in line:
                continue

            # Parse data line: Year Month1 Month2 ... Month12
            parts = line.split()
            if len(parts) < 13:
                continue

            try:
                year = int(parts[0])

                # Extract 12 monthly values
                for month_idx in range(12):
                    try:
                        level = float(parts[month_idx + 1])

                        # Create date as end of month
                        if month_idx < 11:
                            date = pd.Timestamp(f"{year}-{month_idx+2:02d}-01") - pd.Timedelta(days=1)
                        else:
                            date = pd.Timestamp(f"{year}-12-31")

                        records.append({
                            'date': date,
                            'lake': lake_code,
                            'level': level
                        })
                    except ValueError:
                        continue
            except ValueError:
                continue

    if not records:
        raise FileNotFoundError(f"Could not parse any water levels from {member_dir}")

    df = pd.DataFrame(records)
    df = df.pivot_table(index='date', columns='lake', values='level', aggfunc='first')
    df = df.sort_index()

    # Keep only the requested lakes
    cols = [c for c in LAKES if c in df.columns]
    return df[cols]

def rank_histogram(obs: np.ndarray, ens: np.ndarray, n_bins: int = 10, seed: int = 123) -> np.ndarray:
    """
    obs: (T,)
    ens: (T, M)
    n_bins: number of rank histogram bins (default 10)
    returns counts (n_bins,)
    """
    rng = np.random.default_rng(seed)
    T, M = ens.shape
    counts = np.zeros(n_bins, dtype=int)

    for t in range(T):
        if np.isnan(obs[t]) or np.any(np.isnan(ens[t, :])):
            continue
        combined = np.concatenate([ens[t, :], [obs[t]]])
        jitter = rng.uniform(-1e-9, 1e-9, size=combined.shape)
        ranks = np.argsort(combined + jitter)
        obs_rank = int(np.where(ranks == M)[0][0])

        # Map rank to bin (0 to M ranks -> 0 to n_bins-1 bins)
        bin_idx = min(int(obs_rank * n_bins / (M + 1)), n_bins - 1)
        counts[bin_idx] += 1

    return counts

def plot_ensemble_timeseries(obs: pd.DataFrame, member_dfs: List[pd.DataFrame],
                             crps_monthly: pd.DataFrame, common_index, common_lakes,
                             metrics_dir: Path) -> None:
    """
    Plot ensemble simulated vs observed timeseries with mean CRPS displayed.
    Shows all ensemble members as thin lines with observed as thick line.
    """
    for lk in common_lakes:
        fig, ax = plt.subplots(figsize=(14, 6))

        # Plot ensemble members (light gray lines)
        for member_df in member_dfs:
            if lk in member_df.columns:
                ax.plot(member_df.index, member_df[lk], 'gray', alpha=0.3, linewidth=0.8)

        # Plot observed (bold blue line)
        obs_data = obs.loc[common_index, lk]
        ax.plot(obs_data.index, obs_data.values, 'b-', linewidth=2.5, label='Observed', marker='o', markersize=6)

        # Calculate and display mean CRPS in top right
        crps_subset = crps_monthly[crps_monthly['lake'] == lk]
        mean_crps = crps_subset['crps'].mean()
        ax.text(0.98, 0.97, f'Mean CRPS = {mean_crps:.4f} m',
               transform=ax.transAxes, fontsize=12, fontweight='bold',
               verticalalignment='top', horizontalalignment='right',
               bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.8))

        # Labels and formatting
        ax.set_xlabel('Date', fontsize=12)
        ax.set_ylabel('Water Level (m)', fontsize=12)
        lake_names = {'sp': 'Lake Superior', 'mh': 'Michigan-Huron', 'er': 'Lake Erie', 'sc': 'St. Clair'}
        ax.set_title(f'Ensemble Timeseries vs Observed - {lake_names.get(lk, lk)}', fontsize=14, fontweight='bold')
        ax.legend(loc='best', fontsize=11)
        ax.grid(True, alpha=0.3)
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(metrics_dir / f"timeseries_{lk}.png", dpi=200, bbox_inches='tight')
        plt.close()

def main():
    METRICS_DIR.mkdir(parents=True, exist_ok=True)

    # Read observed data
    try:
        obs = read_obs(TARGET_YEAR)
    except ValueError as e:
        print(f"ERROR: {e}")
        return

    members = sorted([p for p in MEMBERS_DIR.iterdir() if p.is_dir()])
    if not members:
        raise RuntimeError("No members found. Run scripts/01_make_ensemble_input.py first.")

    member_names: List[str] = []
    member_dfs: List[pd.DataFrame] = []
    for mdir in members:
        member_names.append(mdir.name)
        try:
            member_dfs.append(read_member_levels(mdir))
        except FileNotFoundError as e:
            print(f"WARNING: {e}")
            continue

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
    crps_monthly_df = pd.DataFrame(crps_monthly_rows)
    crps_monthly_df.to_csv(METRICS_DIR / "crps_by_lake_and_month.csv", index=False)

    # Plot ensemble timeseries with CRPS values
    plot_ensemble_timeseries(obs_al, member_dfs, crps_monthly_df, common_index, common_lakes, METRICS_DIR)

    # Rank histograms with 10 bins
    rh_counts = {}
    for lk in common_lakes:
        y = obs_al[lk].to_numpy()
        f = ens_by_lake[lk]
        counts = rank_histogram(y, f, n_bins=10)
        rh_counts[lk] = counts

        # plot
        plt.figure(figsize=(10, 6))
        plt.bar(np.arange(len(counts)), counts, width=0.7, edgecolor='black')
        plt.title(f"Rank Histogram (2019) - {lk} (10 bins)", fontsize=14, fontweight='bold')
        plt.xlabel("Rank Bin", fontsize=12)
        plt.ylabel("Count", fontsize=12)
        plt.xticks(np.arange(len(counts)), [f"Bin {i}" for i in range(len(counts))], rotation=45)
        plt.grid(True, alpha=0.3, axis='y')
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
