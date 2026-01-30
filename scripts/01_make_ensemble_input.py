#!/usr/bin/env python3
from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Tuple, List

import numpy as np

# -------------------------
# CONFIG (edit if needed)
# -------------------------
REPO_ROOT = Path(__file__).resolve().parents[1]

IJC_DIR = REPO_ROOT / "IJC data"                      # note the space
NBS_DIR = IJC_DIR / "MonthlyNetBasinSupply"
BOM_DIR = IJC_DIR / "BeginningofMonth"

TEMPLATE_DIR = REPO_ROOT / "utils" / "Templates"
PARAMS_TEMPLATE = TEMPLATE_DIR / "CGLRRM_params.template"   # <- set this to your actual template file name

EXPERIMENT_DIR = REPO_ROOT / "experiments" / "ens_climo_2019"
TARGET_YEAR = 2019
HIST_YEAR_MIN = 1901
HIST_YEAR_MAX = 2018

# Lakes used by CGLRRM params keys in your older template (Sup/MHu/Eri/Stc).
# Map "logical lake code" -> how it's referenced in params + which NBS file to use.
LAKES = {
    "sp": {"param_key": "Sup NBS Data:"},
    "mh": {"param_key": "MHu NBS data:"},
    "er": {"param_key": "Eri NBS data:"},
    "sc": {"param_key": "Stc NBS data:"},
}

# How to find the historical NBS files under NBS_DIR:
# If your files are like "MNBS_YYYY_sp.txt" etc, keep this.
NBS_GLOB = "*{lake}*.txt"   # e.g., "*sp*.txt" within MonthlyNetBasinSupply

# How to find BOM level files under BOM_DIR (used to set initial levels in params or member init file)
BOM_GLOB = "*{lake}*.txt"   # e.g., "*sp*.txt"

# Simulation window
START_DATE = (2019, 1, 1)
END_DATE = (2019, 12, 31)

#%%
# -------------------------
# helpers
# -------------------------
YEAR_ROW = re.compile(r"^\s*(\d{4})\s+(-?\d+(\.\d+)?\s+){11}(-?\d+(\.\d+)?)\s*$")


def parse_year12_file(path: Path) -> Tuple[List[str], Dict[int, np.ndarray]]:
    header: List[str] = []
    data: Dict[int, np.ndarray] = {}
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
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
        for h in header:
            f.write(h + "\n")
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


def patch_params(
    template_path: Path,
    out_path: Path,
    nbs_paths: Dict[str, Path],
    member_output_dir: Path,
    start_date: Tuple[int, int, int],
    end_date: Tuple[int, int, int],
    out_ext: str,
    init_levels: Dict[str, float] | None = None,
) -> None:
    """
    Patch minimal keys in params:
      - NBS file paths (Sup/MHu/Eri/Stc)
      - Output Directory
      - Start/End Date
      - Output Extension
    Optionally patch BOM init lake levels if your template has keys like:
      "Sup Init Level:" etc (you can add below if needed).
    """
    lines = template_path.read_text(encoding="utf-8", errors="ignore").splitlines()

    def set_prefix(prefix: str, value: str):
        for i, line in enumerate(lines):
            if line.strip().startswith(prefix):
                lines[i] = f"{prefix} {value}"
                return
        # If not found, silently skip (some templates differ)
        return

    # NBS files
    for lk, meta in LAKES.items():
        set_prefix(meta["param_key"], str(nbs_paths[lk]))

    # Standard run controls (these exist in your older style params file)
    set_prefix("Output Directory:", str(member_output_dir))
    set_prefix("Start Date:", f"{start_date[0]},{start_date[1]},{start_date[2]}")
    set_prefix("End Date:", f"{end_date[0]},{end_date[1]},{end_date[2]}")
    set_prefix("Output Extension:", out_ext)

    # Optional: patch init levels if your params template has matching keys
    # Adjust these prefixes to match your real template file.
    if init_levels:
        set_prefix("Sup Init Level:", f"{init_levels.get('sp', '')}")
        set_prefix("MHu Init Level:", f"{init_levels.get('mh', '')}")
        set_prefix("Eri Init Level:", f"{init_levels.get('er', '')}")
        set_prefix("Stc Init Level:", f"{init_levels.get('sc', '')}")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def read_bom_level_for_year(bom_file: Path, year: int) -> float:
    """
    Expect a simple file with year rows or date rows.
    We try two common cases:
      1) YEAR <value>
      2) YYYY-MM-DD <value>
    Returns the first BOM value for Jan of the year if date-based,
    else the year-based value.
    """
    txt = bom_file.read_text(encoding="utf-8", errors="ignore").splitlines()
    # Case 1: year value
    for line in txt:
        parts = line.split()
        if len(parts) >= 2 and parts[0].isdigit() and len(parts[0]) == 4:
            if int(parts[0]) == year:
                return float(parts[1])

    # Case 2: date value (pick earliest in that year)
    best = None
    for line in txt:
        parts = line.split()
        if len(parts) >= 2 and re.match(r"^\d{4}-\d{2}-\d{2}$", parts[0]):
            y = int(parts[0][:4])
            if y == year:
                best = float(parts[1])
                break
    if best is None:
        raise ValueError(f"Could not find BOM init level for {year} in {bom_file}")
    return best


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
        template_nbs[lk] = find_single_file(NBS_DIR, NBS_GLOB.format(lake=lk))
        bom_files[lk] = find_single_file(BOM_DIR, BOM_GLOB.format(lake=lk))

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

        # BOM init levels for TARGET_YEAR (2019 Jan BOM)
        init_levels = {lk: read_bom_level_for_year(bom_files[lk], TARGET_YEAR) for lk in LAKES.keys()}

        # Params
        out_params = par / f"CGLRRM_params.{member}"
        patch_params(
            template_path=PARAMS_TEMPLATE,
            out_path=out_params,
            nbs_paths=out_nbs,
            member_output_dir=out,
            start_date=START_DATE,
            end_date=END_DATE,
            out_ext=f".{member}",
            init_levels=init_levels,
        )

    print("Done. Members at:", EXPERIMENT_DIR / "members")
    print("NOTE: If PARAMS_TEMPLATE filename differs, update PARAMS_TEMPLATE at top of script.")


if __name__ == "__main__":
    main()
