#!/usr/bin/env python3
"""
Multi-year ensemble analysis: Run simulations for 2000-2025 (except 2019, 2025)
Calculate annual CRPS and water level anomalies
Generate comparison figures
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List
import subprocess
import sys

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

def run_year_simulation(year: int) -> bool:
    """Run ensemble simulation for a given year"""
    print(f"\n{'='*60}")
    print(f"Running ensemble simulation for {year}")
    print(f"{'='*60}")

    # Run script 1 (make ensemble input)
    script1 = REPO_ROOT / "scripts" / "01_make_ensemble_input.py"
    try:
        result = subprocess.run([sys.executable, str(script1), str(year)],
                              capture_output=True, timeout=120)
        if result.returncode != 0:
            print(f"ERROR running make_ensemble_input for {year}")
            print(result.stderr.decode())
            return False
        print(result.stdout.decode())
    except subprocess.TimeoutExpired:
        print(f"TIMEOUT running make_ensemble_input for {year}")
        return False

    # Run script 2 (ensemble execution)
    script2 = REPO_ROOT / "scripts" / "02_run_ensemble.py"
    try:
        result = subprocess.run([sys.executable, str(script2), str(year)],
                              capture_output=True, timeout=600)
        if result.returncode != 0:
            print(f"ERROR running ensemble for {year}")
            print(result.stderr.decode())
            return False
        print(result.stdout.decode())
    except subprocess.TimeoutExpired:
        print(f"TIMEOUT running ensemble for {year}")
        return False

    # Run script 3 (evaluation)
    script3 = REPO_ROOT / "scripts" / "03_eval_ensemble.py"
    try:
        result = subprocess.run([sys.executable, str(script3), str(year)],
                              capture_output=True, timeout=600)
        if result.returncode != 0:
            print(f"ERROR running eval_ensemble for {year}")
            print(result.stderr.decode())
            return False
        print(result.stdout.decode())
    except subprocess.TimeoutExpired:
        print(f"TIMEOUT running eval_ensemble for {year}")
        return False

    return True

def extract_crps_and_anomaly(year: int) -> Dict[str, Dict[str, float]]:
    """Extract annual CRPS and water level anomaly for a year"""
    results = {}

    metrics_dir = REPO_ROOT / "experiments" / f"ens_climo_{year}" / "metrics"

    # Read CRPS summary
    crps_file = metrics_dir / "crps_summary.csv"
    if not crps_file.exists():
        print(f"WARNING: No CRPS file for {year}")
        return results

    crps_df = pd.read_csv(crps_file)

    # Read monthly mean water levels
    cc_data_dir = REPO_ROOT / "CC_data"

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
        with open(filepath, 'r') as f:
            lines = f.readlines()

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
    # Years to run (excluding 2000, 2019, and 2025)
    years_to_run = [y for y in range(2000, 2026) if y not in [2000, 2019, 2025]]

    print(f"\nRunning ensemble simulations for years: {years_to_run}")
    print(f"Total simulations: {len(years_to_run)}")

    # Collect results
    all_results = {lake: [] for lake in LAKES}
    results_data = []

    for year in years_to_run:
        # Run simulation
        success = run_year_simulation(year)

        if success:
            # Extract metrics
            year_results = extract_crps_and_anomaly(year)

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

    # Save comprehensive results
    results_csv = REPO_ROOT / "experiments" / "multi_year_analysis_results.csv"
    pd.DataFrame(results_data).to_csv(results_csv, index=False)
    print(f"\nSaved results to: {results_csv}")

    # Create comparison figures
    create_comparison_figures(all_results, REPO_ROOT)

def create_comparison_figures(all_results: Dict[str, List[Dict]], repo_root: Path):
    """Create CRPS vs Anomaly comparison figures and lead time performance"""

    lake_names = {
        'sp': 'Lake Superior',
        'mh': 'Michigan-Huron',
        'er': 'Lake Erie',
    }

    output_dir = repo_root / "experiments" / "analysis"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Individual lake analysis
    for lake_code in LAKES:
        if not all_results[lake_code]:
            continue

        results_df = pd.DataFrame(all_results[lake_code])

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))

        # Plot 1: CRPS over time
        ax1.plot(results_df['year'], results_df['crps'], 'o-', linewidth=2, markersize=8, color='steelblue')
        ax1.set_xlabel('Year', fontsize=12, fontweight='bold')
        ax1.set_ylabel('Annual Mean CRPS (m)', fontsize=12, fontweight='bold')
        ax1.set_title(f'{lake_names[lake_code]}: Forecast Skill (CRPS) Evolution', fontsize=14, fontweight='bold')
        ax1.grid(True, alpha=0.3)

        # Plot 2: Water Level Anomaly over time
        ax2.plot(results_df['year'], results_df['anomaly'], 'o-', linewidth=2, markersize=8, color='darkgreen')
        ax2.axhline(y=0, color='red', linestyle='--', linewidth=1.5, label='Long-term mean')
        ax2.set_xlabel('Year', fontsize=12, fontweight='bold')
        ax2.set_ylabel('Water Level Anomaly (m)', fontsize=12, fontweight='bold')
        ax2.set_title(f'{lake_names[lake_code]}: Water Level Anomaly Evolution', fontsize=14, fontweight='bold')
        ax2.grid(True, alpha=0.3)
        ax2.legend(fontsize=11)

        plt.tight_layout()
        plt.savefig(output_dir / f"evolution_{lake_code}.png", dpi=200, bbox_inches='tight')
        plt.close()

        # Plot 3: CRPS vs Anomaly scatter (simplified)
        fig, ax = plt.subplots(figsize=(10, 8))
        ax.scatter(results_df['anomaly'], results_df['crps'],
                   s=150, alpha=0.7, edgecolors='black', color='steelblue')

        ax.set_xlabel('Water Level Anomaly (m)', fontsize=12, fontweight='bold')
        ax.set_ylabel('Annual Mean CRPS (m)', fontsize=12, fontweight='bold')
        ax.set_title(f'{lake_names[lake_code]}: CRPS vs Water Level Anomaly\n(CRPS=0 represents perfect forecast)',
                     fontsize=14, fontweight='bold')
        ax.grid(True, alpha=0.3)
        ax.axhline(y=0, color='green', linestyle=':', linewidth=1.5, alpha=0.7)

        plt.tight_layout()
        plt.savefig(output_dir / f"crps_vs_anomaly_{lake_code}.png", dpi=200, bbox_inches='tight')
        plt.close()

        # Plot 4: Lead time performance (1-12 months)
        lead_time_crps = extract_lead_time_performance(lake_code, repo_root)
        if lead_time_crps:
            fig, ax = plt.subplots(figsize=(12, 6))
            months = list(range(1, 13))
            crps_values = [lead_time_crps.get(m, np.nan) for m in months]
            ax.plot(months, crps_values, 'o-', linewidth=2.5, markersize=10, color='darkred')
            ax.set_xlabel('Lead Time (months)', fontsize=12, fontweight='bold')
            ax.set_ylabel('Mean CRPS (m)', fontsize=12, fontweight='bold')
            ax.set_title(f'{lake_names[lake_code]}: Forecast Performance by Lead Time', fontsize=14, fontweight='bold')
            ax.set_xticks(months)
            ax.grid(True, alpha=0.3)
            ax.axhline(y=0, color='green', linestyle=':', linewidth=1.5, alpha=0.7, label='Perfect forecast')
            ax.legend(fontsize=11)
            plt.tight_layout()
            plt.savefig(output_dir / f"lead_time_performance_{lake_code}.png", dpi=200, bbox_inches='tight')
            plt.close()

    # Combined comparison figure
    fig, axes = plt.subplots(2, 3, figsize=(18, 12))

    colors = {'sp': 'steelblue', 'mh': 'orange', 'er': 'green'}

    for idx, lake_code in enumerate(LAKES):
        if not all_results[lake_code]:
            continue

        results_df = pd.DataFrame(all_results[lake_code])

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

    print(f"\nGenerated analysis figures in: {output_dir}")

def extract_lead_time_performance(lake_code: str, repo_root: Path) -> Dict[int, float]:
    """Extract monthly CRPS performance for lead times 1-12 months"""
    lead_time_crps = {}

    experiments_dir = repo_root / "experiments"
    years_to_process = []

    # Get list of processed years
    for exp_dir in sorted(experiments_dir.glob("ens_climo_*")):
        try:
            year = int(exp_dir.name.split('_')[-1])
            if 2001 <= year <= 2025 and year not in [2019, 2025]:
                years_to_process.append(year)
        except:
            pass

    # Collect monthly CRPS data
    monthly_data = {i: [] for i in range(1, 13)}

    for year in years_to_process:
        metrics_file = experiments_dir / f"ens_climo_{year}" / "metrics" / "crps_by_lake_and_month.csv"

        if not metrics_file.exists():
            continue

        try:
            crps_df = pd.read_csv(metrics_file)
            lake_data = crps_df[crps_df['lake'] == lake_code]

            if not lake_data.empty:
                lake_data = lake_data.sort_values('date')
                for month_idx, (_, row) in enumerate(lake_data.iterrows(), 1):
                    if month_idx <= 12:
                        crps_val = row['crps']
                        if not np.isnan(crps_val):
                            monthly_data[month_idx].append(crps_val)
        except Exception as e:
            continue

    # Calculate mean CRPS for each lead time
    for month, values in monthly_data.items():
        if values:
            lead_time_crps[month] = float(np.mean(values))

    return lead_time_crps

if __name__ == "__main__":
    main()
