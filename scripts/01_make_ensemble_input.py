#!/usr/bin/env python3
from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np


LAKES = ["sp", "mh", "er", "sc"]  # Superior, Michigan-Huron, Erie, St. Clair


@dataclass
class TemplatePaths:
    params_template: Path
    nbs_templates: Dict[str, Path]  # lake -> file


def parse_mnbs_yearly_monthly(path: Path) -> Tuple[List[str], Dict[int, np.ndarray]]:
    """
    Parse MNBS-style file with headers and rows like:
    YYYY  Jan Feb ... Dec  (12 values)
    Returns (header_lines, data_dict[year] = array(12,))
    """
    header_lines: List[str] = []
    data: Dict[int, np.ndarray] = {}

    year_row = re.compile(r"^\s*(\d{4})\s+(-?\d+(\.\d+)?\s+){11}(-?\d+(\.\d+)?)\s*$")

    with path.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if year_row.match(line):
                parts = line.split()
                yr = int(parts[0])
                vals = np.array([float(x) for x in parts[1:13]], dtype=float)
                data[yr] = vals
            else:
                header_lines.append(line.rstrip("\n"))

    if not data:
        raise ValueError(f"No year rows parsed from {path}. Check format.")
    return header_lines, data


def format_mnbs_line(year: int, vals12: np.ndarray) -> str:
    """
    Approximate FORTRAN I4 12F8.0 formatting (integer-ish monthly flows).
    Adjust decimals if your file uses something else.
    """
    return f"{year:4d}" + "".join([f"{v:8.0f}" for v in vals12]) + "\n"


def write_mnbs_with_replaced_year(
    template_path: Path,
    out_path: Path,
    target_year: int,
    replacement_vals12: np.ndarray,
) -> None:
    header, data = parse_mnbs_yearly_monthly(template_path)
    data[target_year] = replacement_vals12.copy()

    years_sorted = sorted(data.keys())
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for h in header:
            f.write(h + "\n")
        for yr in years_sorted:
            f.write(format_mnbs_line(yr, data[yr]))


def patch_params_file(
    params_template: Path,
    out_params: Path,
    member_input_dir: Path,
    member_output_dir: Path,
    nbs_files: Dict[str, Path],
    start_date: Tuple[int, int, int],
    end_date: Tuple[int, int, int],
    out_ext: str,
) -> None:
    """
    Patch the simple key:value lines observed in your params file, e.g.
      Sup NBS Data: ./input/MNBS_2008_sp.txt
      Output Directory: ./output/
      Start Date: 1982,8,1
      End Date: 1983,7,31
      Output Extension: .test

    Those appear near top of your template. (See your uploaded CGLRRM_params.2008)
    """
    text = params_template.read_text(encoding="utf-8", errors="ignore").splitlines()

    def set_line(prefix: str, new_value: str) -> None:
        for i, line in enumerate(text):
            if line.strip().startswith(prefix):
                text[i] = f"{prefix} {new_value}"
                return
        raise ValueError(f"Could not find line starting with '{prefix}' in {params_template}")

    # Match your template naming: sp/mh/er/sc
    set_line("Sup NBS Data:", str(nbs_files["sp"]))
    set_line("MHu NBS data:", str(nbs_files["mh"]))
    set_line("Eri NBS data:", str(nbs_files["er"]))
    set_line("Stc NBS data:", str(nbs_files["sc"]))

    set_line("Output Directory:", str(member_output_dir))
    set_line("Start Date:", f"{start_date[0]},{start_date[1]},{start_date[2]}")
    set_line("End Date:", f"{end_date[0]},{end_date[1]},{end_date[2]}")
    set_line("Output Extension:", out_ext)

    out_params.parent.mkdir(parents=True, exist_ok=True)
    out_params.write_text("\n".join(text) + "\n", encoding="utf-8")


def main():
    """
    Build ensemble members for a 2019 12-month simulation:
      - For each historical year y in [min_year..2018], replace year=2019 NBS with year=y NBS
      - Write member-specific MNBS files + params
    """
    root = Path(__file__).resolve().parents[1]
    exp_root = root / "experiments" / "ens_climo_2019"
    members_root = exp_root / "members"

    templates = TemplatePaths(
        params_template=root / "templates" / "CGLRRM_params.template",
        nbs_templates={
            "er": root / "templates" / "MNBS_template_er.txt",
            "mh": root / "templates" / "MNBS_template_mh.txt",
            "sc": root / "templates" / "MNBS_template_sc.txt",
            "sp": root / "templates" / "MNBS_template_sp.txt",
        },
    )

    target_year = 2019
    last_hist_year = 2018  # "all previous years RNBS records"
    start_date = (2019, 1, 1)
    end_date = (2019, 12, 31)

    # Load historical sequences per lake
    hist_by_lake: Dict[str, Dict[int, np.ndarray]] = {}
    for lk, fp in templates.nbs_templates.items():
        _, data = parse_mnbs_yearly_monthly(fp)
        hist_by_lake[lk] = data

    # Determine common year set across lakes
    common_years = set(hist_by_lake[LAKES[0]].keys())
    for lk in LAKES[1:]:
        common_years &= set(hist_by_lake[lk].keys())

    common_years = {y for y in common_years if y <= last_hist_year}
    if not common_years:
        raise ValueError("No common historical years <= 2018 across all lake MNBS templates.")

    years_sorted = sorted(common_years)
    print(f"Building {len(years_sorted)} members using historical years: {years_sorted[0]}..{years_sorted[-1]}")

    # Fresh build
    if exp_root.exists():
        shutil.rmtree(exp_root)
    (members_root).mkdir(parents=True, exist_ok=True)

    # Create each member
    for y in years_sorted:
        member_name = f"Y{y}"
        member_dir = members_root / member_name
        inp = member_dir / "input"
        out = member_dir / "output"
        inp.mkdir(parents=True, exist_ok=True)
        out.mkdir(parents=True, exist_ok=True)

        # Write member MNBS files where 2019 row is replaced by year y
        out_nbs = {}
        for lk in LAKES:
            out_fp = inp / f"MNBS_{target_year}_as_{y}_{lk}.txt"
            write_mnbs_with_replaced_year(
                template_path=templates.nbs_templates[lk],
                out_path=out_fp,
                target_year=target_year,
                replacement_vals12=hist_by_lake[lk][y],
            )
            out_nbs[lk] = out_fp

        # Patch params
        out_params = member_dir / "CGLRRM_params.member"
        patch_params_file(
            params_template=templates.params_template,
            out_params=out_params,
            member_input_dir=inp,
            member_output_dir=out,
            nbs_files=out_nbs,
            start_date=start_date,
            end_date=end_date,
            out_ext=f".{member_name}",
        )

    print(f"Done. Members created under: {members_root}")


if __name__ == "__main__":
    main()
