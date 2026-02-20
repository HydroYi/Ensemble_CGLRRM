#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
EXE = REPO_ROOT / "bin" / "cglrrm.exe"

# Get year from command line argument, default to 2000
TARGET_YEAR = int(sys.argv[1]) if len(sys.argv) > 1 else 2000
EXP_DIR = REPO_ROOT / "experiments" / f"ens_climo_{TARGET_YEAR}"
MEMBERS_DIR = EXP_DIR / "members"
TEMPLATE_DIR = REPO_ROOT / "utils" / "Templates"
MESSBASE = TEMPLATE_DIR / "messbase.txt"
INI_TEMPLATE = TEMPLATE_DIR / "cglrrm.ini"

def main():
    if not EXE.exists():
        raise FileNotFoundError(f"Missing executable: {EXE}")

    # Copy messbase.txt to bin directory if it doesn't exist
    messbase_in_bin = EXE.parent / "messbase.txt"
    if MESSBASE.exists() and not messbase_in_bin.exists():
        import shutil
        shutil.copy(str(MESSBASE), str(messbase_in_bin))
        print(f"Copied messbase.txt to {messbase_in_bin}")

    members = sorted([p for p in MEMBERS_DIR.iterdir() if p.is_dir()])
    if not members:
        raise RuntimeError("No members found. Run scripts/01_make_ensemble_input.py first.")

    for mdir in members:
        params_dir = mdir / "params"
        params_files = sorted(params_dir.glob("CGLRRM_params.Y*"))
        if not params_files:
            raise FileNotFoundError(f"No params found in {params_dir}")
        params = params_files[0]

        # Create cglrrm.ini in the member directory pointing to the params file
        ini_file = mdir / "cglrrm.ini"
        ini_file.write_text(str(params) + "\n")

        print(f"Running {mdir.name} ...")
        # Many Fortran models assume relative paths; run from member folder
        subprocess.run([str(EXE), str(params)], check=True, cwd=str(mdir))

    print("All members finished.")

if __name__ == "__main__":
    main()
