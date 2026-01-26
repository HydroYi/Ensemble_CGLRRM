#!/usr/bin/env python3
from __future__ import annotations

import subprocess
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    exp_root = root / "experiments" / "ens_climo_2019"
    members_root = exp_root / "members"

    exe = root / "bin" / "cglrrm.exe"  # adjust to your actual executable name
    if not exe.exists():
        raise FileNotFoundError(f"Missing executable at {exe}. Put your model binary there.")

    member_dirs = sorted([p for p in members_root.iterdir() if p.is_dir()])
    if not member_dirs:
        raise RuntimeError("No members found. Run scripts/01_make_ensemble_inputs.py first.")

    for md in member_dirs:
        params = md / "CGLRRM_params.member"
        if not params.exists():
            raise FileNotFoundError(f"Missing params for member {md.name}: {params}")

        print(f"Running member {md.name} ...")
        # If your model expects: cglrrm.exe <params_file>
        # adjust arguments accordingly (some models use cwd-relative paths)
        subprocess.run([str(exe), str(params)], check=True, cwd=str(md))

    print("All members finished.")


if __name__ == "__main__":
    main()
