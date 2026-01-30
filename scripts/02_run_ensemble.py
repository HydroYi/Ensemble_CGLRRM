#!/usr/bin/env python3
from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
EXE = REPO_ROOT / "bin" / "cglrrm.exe"
EXP_DIR = REPO_ROOT / "experiments" / "ens_climo_2019"
MEMBERS_DIR = EXP_DIR / "members"

def main():
    if not EXE.exists():
        raise FileNotFoundError(f"Missing executable: {EXE}")

    members = sorted([p for p in MEMBERS_DIR.iterdir() if p.is_dir()])
    if not members:
        raise RuntimeError("No members found. Run scripts/ens2019_make_inputs.py first.")

    for mdir in members:
        params_dir = mdir / "params"
        params_files = sorted(params_dir.glob("CGLRRM_params.Y*"))
        if not params_files:
            raise FileNotFoundError(f"No params found in {params_dir}")
        params = params_files[0]

        print(f"Running {mdir.name} ...")
        # Many Fortran models assume relative paths; run from member folder
        subprocess.run([str(EXE), str(params)], check=True, cwd=str(mdir))

    print("All members finished.")

if __name__ == "__main__":
    main()
