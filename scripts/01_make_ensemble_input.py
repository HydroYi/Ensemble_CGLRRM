#!/usr/bin/env python3
from __future__ import annotations

import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Tuple, List

import numpy as np

# -------------------------
# CONFIG (edit if needed)
# -------------------------
REPO_ROOT = Path(__file__).resolve().parents[1]

CC_DIR = REPO_ROOT / "CC_data"                      # note the space
NBS_DIR = CC_DIR  # NBS CSV files are directly in CC_data
BOM_DIR = CC_DIR  # BOM CSV files are directly in CC_data

TEMPLATE_DIR = REPO_ROOT / "utils" / "Templates"
PARAMS_TEMPLATE = TEMPLATE_DIR / "CGLRRM_params.2008"   # <- set this to your actual template file name

# Get year from command line argument, default to 2000
TARGET_YEAR = int(sys.argv[1]) if len(sys.argv) > 1 else 2000
EXPERIMENT_DIR = REPO_ROOT / "experiments" / f"ens_climo_{TARGET_YEAR}"
HIST_YEAR_MIN = 1901
HIST_YEAR_MAX = TARGET_YEAR - 1

# Lakes used by CGLRRM params keys in your older template (Sup/MHu/Eri/Stc).
# Map "logical lake code" -> how it's referenced in params + which NBS file to use.
LAKES = {
    "sp": {"param_key": "Sup NBS Data:", "name": "Superior"},
    "mh": {"param_key": "MHu NBS data:", "name": "MichiganHuron"},
    "er": {"param_key": "Eri NBS data:", "name": "Erie"},
    "sc": {"param_key": "Stc NBS data:", "name": "StClair"},
}

# How to find the historical NBS files under NBS_DIR:
# Files are like "LakeSuperior_MonthlyNetBasinSupply_1900to2026.csv"
NBS_GLOB = "Lake*_MonthlyNetBasinSupply*.csv"

# How to find BOM level files under BOM_DIR (used to set initial levels in params or member init file)
BOM_GLOB = "Lake*_BeginningOfMonthWaterLevels*.csv"

# Simulation window
START_DATE = (TARGET_YEAR, 1, 1)
END_DATE = (TARGET_YEAR, 12, 31)

#%%
# -------------------------
# helpers
# -------------------------
YEAR_ROW = re.compile(r"^\s*(\d{4})\s+(-?\d+(\.\d+)?\s+){11}(-?\d+(\.\d+)?)\s*$")


def parse_year12_file(path: Path) -> Tuple[List[str], Dict[int, np.ndarray]]:
    header: List[str] = []
    data: Dict[int, np.ndarray] = {}
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        # Try CSV format first (with commas)
        if ',' in line:
            parts = [p.strip() for p in line.split(',')]
            if len(parts) >= 13 and parts[0].isdigit() and len(parts[0]) == 4:
                try:
                    y = int(parts[0])
                    vals = np.array([float(x) for x in parts[1:13]], dtype=float)
                    data[y] = vals
                    continue
                except (ValueError, IndexError):
                    pass
        # Try old fixed-width format
        if YEAR_ROW.match(line):
            parts = line.split()
            y = int(parts[0])
            vals = np.array([float(x) for x in parts[1:13]], dtype=float)
            data[y] = vals
        else:
            header.append(line)
    if not data:
        raise ValueError(f"Could not parse any year rows from {path}")
    return header, data


def format_year12_line(year: int, vals12: np.ndarray) -> str:
    # approximate FORTRAN I4 12F8.0
    return f"{year:4d}" + "".join([f"{v:8.0f}" for v in vals12]) + "\n"


def write_year12_with_replaced_year(template_file: Path, out_file: Path, target_year: int, vals12: np.ndarray) -> None:
    header, data = parse_year12_file(template_file)
    data[target_year] = vals12.copy()
    years = sorted(data.keys())
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with out_file.open("w", encoding="utf-8") as f:
        # Write only comment lines (starting with #), skip CSV headers like "Year, Jan, Feb..."
        for h in header:
            if h.strip().startswith("#") or h.strip() == "":
                f.write(h + "\n")
        # Add units and interval lines (must come before data, without # prefix for CGLRRM to recognize them)
        # Check if units are already specified in any form
        units_line = None
        for h in header:
            if "units" in h.lower():
                if "m3s" in h.lower() or "m3/s" in h.lower():
                    units_line = "Units: m3s"
                    break
        if not units_line:
            units_line = "Units: m3s"
        f.write(units_line + "\n")
        f.write("Interval: monthly\n")
        for y in years:
            f.write(format_year12_line(y, data[y]))


def find_single_file(folder: Path, pattern: str) -> Path:
    hits = sorted(folder.glob(pattern))
    if len(hits) == 0:
        raise FileNotFoundError(f"No files match pattern '{pattern}' in {folder}")
    if len(hits) > 1:
        # pick the largest file (often the full record), but warn in message
        hits = sorted(hits, key=lambda p: p.stat().st_size, reverse=True)
    return hits[0]


def find_file_by_lake(folder: Path, pattern: str, lake_name: str) -> Path:
    """Find a file matching pattern and containing lake name."""
    all_hits = sorted(folder.glob(pattern))
    if len(all_hits) == 0:
        raise FileNotFoundError(f"No files match pattern '{pattern}' in {folder}")

    # Filter to files containing the lake name (case-insensitive)
    matching = [f for f in all_hits if lake_name.lower() in f.name.lower()]
    if not matching:
        raise FileNotFoundError(f"No files matching '{pattern}' and containing '{lake_name}' in {folder}")

    return matching[0]


def patch_params(
    template_path: Path,
    out_path: Path,
    nbs_paths: Dict[str, Path],
    member_output_dir: Path,
    start_date: Tuple[int, int, int],
    end_date: Tuple[int, int, int],
    out_ext: str,
    messbase_path: Path | None = None,
    init_levels: Dict[str, float] | None = None,
) -> None:
    """
    Patch keys in params:
      - NBS file paths (Sup/MHu/Eri/Stc)
      - Output Directory
      - Start/End Date + lake levels
      - Output Extension
      - Message Database path
      - Start Levels (lake initial levels for simulation)
    """
    lines = template_path.read_text(encoding="utf-8", errors="ignore").splitlines()

    def set_line_with_key(key_pattern: str, value: str):
        """Find and replace a line that contains key_pattern (case-insensitive)"""
        for i, line in enumerate(lines):
            if key_pattern.lower() in line.lower():
                # Replace everything after the colon with the new value
                if ':' in line:
                    prefix = line[:line.index(':') + 1]
                    lines[i] = f"{prefix} {value}"
                else:
                    lines[i] = f"{key_pattern}: {value}"
                return True
        return False

    # NBS files - match the param_key from LAKES dict
    for lk, meta in LAKES.items():
        set_line_with_key(meta["param_key"], str(nbs_paths[lk]))

    # Output directory and dates
    set_line_with_key("Output Directory", str(member_output_dir) + "/")
    set_line_with_key("Start Date", f"{start_date[0]},{start_date[1]},{start_date[2]}")
    set_line_with_key("End Date", f"{end_date[0]},{end_date[1]},{end_date[2]}")
    set_line_with_key("Output Extension", out_ext)

    # Message Database path
    if messbase_path:
        set_line_with_key("Message DataBase", str(messbase_path))

    # Patch start levels (initial conditions for each lake)
    # The template has keys like "Sup Start Level      : 183.55 m"
    if init_levels:
        set_line_with_key("Sup Start Level", f"{init_levels.get('sp', 0):.2f} m")
        set_line_with_key("MHu Start Level", f"{init_levels.get('mh', 0):.2f} m")
        set_line_with_key("Eri Start Level", f"{init_levels.get('er', 0):.2f} m")
        set_line_with_key("St. C Start Level", f"{init_levels.get('sc', 0):.2f} m")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def read_bom_level_for_year(bom_file: Path, year: int) -> float:
    """
    Expect a simple file with year rows or date rows.
    We try multiple common cases:
      1) CSV: YYYY, <value>, <value>, ...
      2) CSV date: YYYY-MM-DD, <value>
      3) YEAR <value> (fixed-width)
      4) YYYY-MM-DD <value> (fixed-width)
    Returns the first BOM value for Jan of the year if date-based,
    else the year-based value.
    """
    txt = bom_file.read_text(encoding="utf-8", errors="ignore").splitlines()

    # Case 1: CSV format with year
    for line in txt:
        if ',' in line:
            parts = [p.strip() for p in line.split(',')]
            if len(parts) >= 2 and parts[0].isdigit() and len(parts[0]) == 4:
                try:
                    if int(parts[0]) == year:
                        return float(parts[1])
                except (ValueError, IndexError):
                    pass

    # Case 2: Year value (fixed-width)
    for line in txt:
        parts = line.split()
        if len(parts) >= 2 and parts[0].isdigit() and len(parts[0]) == 4:
            if int(parts[0]) == year:
                return float(parts[1])

    # Case 3: CSV date value (pick earliest in that year)
    best = None
    for line in txt:
        if ',' in line:
            parts = [p.strip() for p in line.split(',')]
            if len(parts) >= 2 and re.match(r"^\d{4}-\d{2}-\d{2}$", parts[0]):
                y = int(parts[0][:4])
                if y == year:
                    best = float(parts[1])
                    break
        else:
            parts = line.split()
            if len(parts) >= 2 and re.match(r"^\d{4}-\d{2}-\d{2}$", parts[0]):
                y = int(parts[0][:4])
                if y == year:
                    best = float(parts[1])
                    break

    if best is not None:
        return best

    raise ValueError(f"Could not find BOM init level for {year} in {bom_file}")


def main():
    # Fresh rebuild
    if EXPERIMENT_DIR.exists():
        shutil.rmtree(EXPERIMENT_DIR)
    (EXPERIMENT_DIR / "members").mkdir(parents=True, exist_ok=True)
    (EXPERIMENT_DIR / "metrics").mkdir(parents=True, exist_ok=True)

    # Discover template NBS files (full records) to use as “base”; we will overwrite the TARGET_YEAR row.
    template_nbs: Dict[str, Path] = {}
    bom_files: Dict[str, Path] = {}

    for lk in LAKES.keys():
        lake_name = LAKES[lk]["name"]
        template_nbs[lk] = find_file_by_lake(NBS_DIR, NBS_GLOB, lake_name)
        bom_files[lk] = find_file_by_lake(BOM_DIR, BOM_GLOB, lake_name)

    # Parse NBS records once
    nbs_data: Dict[str, Dict[int, np.ndarray]] = {}
    for lk, fp in template_nbs.items():
        _, data = parse_year12_file(fp)
        nbs_data[lk] = data

    # Determine usable years (must exist for all lakes)
    common_years = set(range(HIST_YEAR_MIN, HIST_YEAR_MAX + 1))
    for lk in LAKES.keys():
        common_years &= set(nbs_data[lk].keys())
    years = sorted(common_years)

    if not years:
        raise RuntimeError("No common historical years found across lake NBS files in MonthlyNetBasinSupply.")

    print(f"Building {len(years)} members for {TARGET_YEAR} using climatology years {years[0]}..{years[-1]}")

    for y in years:
        member = f"Y{y}"
        mdir = EXPERIMENT_DIR / "members" / member
        inp = mdir / "input"
        out = mdir / "output"
        par = mdir / "params"
        inp.mkdir(parents=True, exist_ok=True)
        out.mkdir(parents=True, exist_ok=True)
        par.mkdir(parents=True, exist_ok=True)

        # Member NBS: same file structure as template, but replace TARGET_YEAR row with year=y monthly sequence
        out_nbs: Dict[str, Path] = {}
        for lk in LAKES.keys():
            out_fp = inp / f"MonthlyNetBasinSupply_{TARGET_YEAR}_as_{y}_{lk}.txt"
            write_year12_with_replaced_year(
                template_file=template_nbs[lk],
                out_file=out_fp,
                target_year=TARGET_YEAR,
                vals12=nbs_data[lk][y],
            )
            out_nbs[lk] = out_fp

        # BOM init levels for member (use historical year y for consistent initial conditions)
        init_levels = {lk: read_bom_level_for_year(bom_files[lk], y) for lk in LAKES.keys()}

        # Params
        out_params = par / f"CGLRRM_params.{member}"
        messbase_path = REPO_ROOT / "utils" / "Templates" / "messbase.txt"
        patch_params(
            template_path=PARAMS_TEMPLATE,
            out_path=out_params,
            nbs_paths=out_nbs,
            member_output_dir=out,
            start_date=START_DATE,
            end_date=END_DATE,
            out_ext=f".{member}",
            messbase_path=messbase_path,
            init_levels=init_levels,
        )

    print("Done. Members at:", EXPERIMENT_DIR / "members")
    print("NOTE: If PARAMS_TEMPLATE filename differs, update PARAMS_TEMPLATE at top of script.")


if __name__ == "__main__":
    main()
