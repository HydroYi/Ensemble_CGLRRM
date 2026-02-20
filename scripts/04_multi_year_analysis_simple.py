#!/usr/bin/env python3
"""
Simplified multi-year analysis: Read existing results and generate comparison figures
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

REPO_ROOT = Path(__file__).resolve().parents[1]

# Long-term mean water levels (m)
LONG_TERM_MEANS = {
    'sp': 183.41,  # Lake Superior
    'mh': 176.45,  # Michigan-Huron
    'er': 174.18,  # Lake Erie
}

LAKES = ['sp', 'mh', 'er']

def extract_crps_and_anomaly(year: int, cc_data_dir: Path) -> Dict[str, Dict[str, float]]:
    """Extract annual CRPS and water level anomaly for a year"""
    results = {}

    metrics_dir = REPO_ROOT / "experiments" / f"ens_climo_{year}" / "metrics"

    # Read CRPS summary
    crps_file = metrics_dir / "crps_summary.csv"
    if not crps_file.exists():
        print(f"  → CRPS file not found for {year}")
        return results

    try:
        crps_df = pd.read_csv(crps_file)
    except Exception as e:
        print(f"  → Error reading CRPS for {year}: {e}")
        return results

    # Read monthly mean water levels
    for lake_code in LAKES:
        lake_mapping = {
            'sp': 'Superior',
            'mh': 'MichiganHuron',
            'er': 'Erie',
        }
        lake_name = lake_mapping[lake_code]

        # Find observed data file
        pattern = f"Lake{lake_name}_MonthlyMeanWaterLevels*.csv"
        files = list(cc_data_dir.glob(pattern))
        if not files:
            continue

        # Read observed levels for target year
        filepath = files[0]
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        except:
            continue

        monthly_levels = []
        for line in lines:
            if line.strip().startswith('#') or 'Year' in line:
                continue
            parts = [p.strip() for p in line.split(',')]
            if len(parts) < 2:
                continue
            try:
                y = int(parts[0])
                if y != year:
                    continue
                # Get 12 monthly values
                for month_idx in range(12):
                    if len(parts) > month_idx + 1:
                        try:
                            level = float(parts[month_idx + 1])
                            if level != -9999:
                                monthly_levels.append(level)
                        except ValueError:
                            continue
            except ValueError:
                continue

        if monthly_levels:
            mean_level = np.mean(monthly_levels)
            anomaly = mean_level - LONG_TERM_MEANS[lake_code]

            # Get CRPS from summary
            crps_row = crps_df[crps_df['lake'] == lake_code]
            if not crps_row.empty:
                crps_val = crps_row['crps_mean'].values[0]

                results[lake_code] = {
                    'crps': crps_val,
                    'anomaly': anomaly,
                    'mean_level': mean_level,
                }

    return results

def main():
    # Years to process (from existing experiments)
    experiments_dir = REPO_ROOT / "experiments"

    # Get list of all ens_climo_YYYY directories that exist
    existing_years = []
    for exp_dir in sorted(experiments_dir.glob("ens_climo_*")):
        try:
            year = int(exp_dir.name.split('_')[-1])
            if 2000 <= year <= 2025:
                existing_years.append(year)
        except:
            pass

    existing_years = sorted(set(existing_years))
    print(f"\nFound existing experiments for years: {existing_years}")
    print(f"Processing {len(existing_years)} years...")

    # Collect results
    all_results = {lake: [] for lake in LAKES}
    results_data = []

    cc_data_dir = REPO_ROOT / "CC_data"

    for year in existing_years:
        print(f"\nExtracting results from {year}...", end=" ")
        year_results = extract_crps_and_anomaly(year, cc_data_dir)

        if year_results:
            print("[OK]")
            for lake_code in LAKES:
                if lake_code in year_results:
                    result = year_results[lake_code]
                    all_results[lake_code].append({
                        'year': year,
                        'crps': result['crps'],
                        'anomaly': result['anomaly'],
                    })
                    results_data.append({
                        'year': year,
                        'lake': lake_code,
                        'crps': result['crps'],
                        'anomaly': result['anomaly'],
                        'mean_level': result['mean_level'],
                    })
        else:
            print("[SKIP] (no data)")

    if not results_data:
        print("\n ERROR: No results extracted. Check that experiments exist.")
        return

    # Save comprehensive results
    results_csv = REPO_ROOT / "experiments" / "multi_year_analysis_results.csv"
    pd.DataFrame(results_data).to_csv(results_csv, index=False)
    print(f"\n[OK] Saved results to: {results_csv}")

    # Create comparison figures
    create_comparison_figures(all_results, REPO_ROOT)

def create_comparison_figures(all_results: Dict[str, List[Dict]], repo_root: Path):
    """Create CRPS vs Anomaly comparison figures"""

    lake_names = {
        'sp': 'Lake Superior',
        'mh': 'Michigan-Huron',
        'er': 'Lake Erie',
    }

    output_dir = repo_root / "experiments" / "analysis"
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\nGenerating analysis figures...")

    # Individual lake analysis
    for lake_code in LAKES:
        if not all_results[lake_code]:
            print(f"  → Skipping {lake_code} (no data)")
            continue

        results_df = pd.DataFrame(all_results[lake_code]).sort_values('year')

        # Plot 1 & 2: Evolution of CRPS and Anomaly
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))

        ax1.plot(results_df['year'], results_df['crps'], 'o-', linewidth=2.5, markersize=8, color='steelblue')
        ax1.set_xlabel('Year', fontsize=12, fontweight='bold')
        ax1.set_ylabel('Annual Mean CRPS (m)', fontsize=12, fontweight='bold')
        ax1.set_title(f'{lake_names[lake_code]}: Forecast Skill (CRPS) Evolution', fontsize=14, fontweight='bold')
        ax1.grid(True, alpha=0.3)

        ax2.plot(results_df['year'], results_df['anomaly'], 'o-', linewidth=2.5, markersize=8, color='darkgreen')
        ax2.axhline(y=0, color='red', linestyle='--', linewidth=1.5, label='Long-term mean')
        ax2.set_xlabel('Year', fontsize=12, fontweight='bold')
        ax2.set_ylabel('Water Level Anomaly (m)', fontsize=12, fontweight='bold')
        ax2.set_title(f'{lake_names[lake_code]}: Water Level Anomaly Evolution', fontsize=14, fontweight='bold')
        ax2.grid(True, alpha=0.3)
        ax2.legend(fontsize=11)

        plt.tight_layout()
        plt.savefig(output_dir / f"evolution_{lake_code}.png", dpi=200, bbox_inches='tight')
        plt.close()
        print(f"  [OK] evolution_{lake_code}.png")

        # Plot 3: CRPS vs Anomaly scatter (simplified)
        fig, ax = plt.subplots(figsize=(11, 9))
        ax.scatter(results_df['anomaly'], results_df['crps'],
                   s=200, alpha=0.7, edgecolors='black', linewidth=1.5, color='steelblue')

        ax.set_xlabel('Water Level Anomaly (m)', fontsize=12, fontweight='bold')
        ax.set_ylabel('Annual Mean CRPS (m)', fontsize=12, fontweight='bold')
        ax.set_title(f'{lake_names[lake_code]}: CRPS vs Water Level Anomaly\n(CRPS=0 represents perfect forecast)',
                     fontsize=14, fontweight='bold')
        ax.grid(True, alpha=0.3)
        ax.axhline(y=0, color='green', linestyle=':', linewidth=1.5, alpha=0.7)

        plt.tight_layout()
        plt.savefig(output_dir / f"crps_vs_anomaly_{lake_code}.png", dpi=200, bbox_inches='tight')
        plt.close()
        print(f"  [OK] crps_vs_anomaly_{lake_code}.png")

    # Combined comparison figure
    fig, axes = plt.subplots(2, 3, figsize=(18, 12))

    colors = {'sp': 'steelblue', 'mh': 'orange', 'er': 'green'}

    for idx, lake_code in enumerate(LAKES):
        if not all_results[lake_code]:
            continue

        results_df = pd.DataFrame(all_results[lake_code]).sort_values('year')

        # CRPS evolution
        axes[0, idx].plot(results_df['year'], results_df['crps'], 'o-',
                         linewidth=2.5, markersize=8, color=colors[lake_code])
        axes[0, idx].set_ylabel('CRPS (m)', fontsize=11, fontweight='bold')
        axes[0, idx].set_title(f'{lake_names[lake_code]}: CRPS', fontsize=12, fontweight='bold')
        axes[0, idx].grid(True, alpha=0.3)

        # Anomaly evolution
        axes[1, idx].plot(results_df['year'], results_df['anomaly'], 'o-',
                         linewidth=2.5, markersize=8, color=colors[lake_code])
        axes[1, idx].axhline(y=0, color='red', linestyle='--', linewidth=1.5)
        axes[1, idx].set_xlabel('Year', fontsize=11, fontweight='bold')
        axes[1, idx].set_ylabel('Anomaly (m)', fontsize=11, fontweight='bold')
        axes[1, idx].set_title(f'{lake_names[lake_code]}: Anomaly', fontsize=12, fontweight='bold')
        axes[1, idx].grid(True, alpha=0.3)

    plt.suptitle('Multi-Year Ensemble Analysis (2000-2025)', fontsize=16, fontweight='bold', y=1.00)
    plt.tight_layout()
    plt.savefig(output_dir / "combined_analysis.png", dpi=200, bbox_inches='tight')
    plt.close()
    print(f"  [OK] combined_analysis.png")

    print(f"\n[OK] Analysis complete: {output_dir}")

if __name__ == "__main__":
    main()
