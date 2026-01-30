
# Ensemble_CGLRRM

**Ensemble simulations and probabilistic evaluation framework for the Coordinated Great Lakes Regulation and Routing Model (CGLRRM)**

This repository provides scripts and workflows to:
- Generate **climatology-based forecasts** using historical Net Basin Supply (NBS)
- Run **ensemble CGLRRM simulations**
- Evaluate lake-level forecasts using **probabilistic metrics** (CRPS, rank histogram)

The framework is designed around **Coordinated historical datasets** and supports reproducible, batch-style ensemble experiments.

---

## Repository Structure

```text
Ensemble_CGLRRM/
│
├── bin/
│   └── cglrrm.exe                  # CGLRRM executable (not tracked by git)
│
├── CC_data/
│   ├── BeginningOfMonth/           # BOM lake levels (initial conditions)
│   ├── MonthlyMean/                # Monthly mean lake levels
│   ├── MonthlyNetBasinSupply/      # Historical RNBS (climatology source)
│   └── README.md                   # Data description
│
├── utils/
│   └── Templates/
│       └── CGLRRM_params.template  # Base parameter template
│
├── scripts/
│   ├── 01_make_ensemble_input.py   # Build ensemble inputs
│   ├── 02_run_ensemble.py          # Run CGLRRM for all members
│   └── 03_eval_ensemble.py         # CRPS + rank histogram evaluation
│
├── experiments/
│   └── ens_climo_2019/             # Auto-generated ensemble experiment
│       ├── members/
│       │   └── YYYYY/
│       │       ├── input/
│       │       ├── output/
│       │       └── params/
│       └── metrics/
│
└── README.md
