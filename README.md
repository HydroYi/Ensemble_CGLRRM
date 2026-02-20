# Ensemble_CGLRRM

This repository provides a **Python-based ensemble workflow** for running and evaluating the  
**Coordinated Great Lakes Regulation and Routing Model (CGLRRM)**.

The main goal is to support **ensemble and uncertainty analysis of Great Lakes water levels** by:
- Constructing **climatology-based ensemble simulations** using historical Net Basin Supply (NBS)
- Running CGLRRM in batch mode for many ensemble members
- Evaluating probabilistic performance using metrics such as **CRPS** and **rank histograms**

The workflow is built around **historical Coordinated Committee Great Lakes datasets** and is intended for research and model evaluation purposes.
This workflow is also intended to be extended to use the NBS ensembles from the BIL-SA model outputs.

---

## Important Note on CGLRRM Executable

The CGLRRM model executable (`bin/cglrrm.exe`) is **not publicly available** and is therefore  
**not included** in this repository.

Users must obtain the executable through appropriate institutional or agency channels  
and place it manually in the `bin/` directory.

---

## Repository Structure (What Each Folder Is For)



### 📁 `bin/`
Contains the **CGLRRM executable**.

- Expected file: `cglrrm.exe`
- Not tracked by git
- Required to actually run model simulations

---

### 📁 `CC_data/`
Historical **Great Lakes datasets** used by the workflow.

This folder includes:
- **Beginning-of-Month (BOM) lake water levels**  
  Used to initialize CGLRRM simulations
- **Monthly Mean lake water levels**  
  Used for evaluation and verification
- **Monthly Residual Net Basin Supply (RNBS)**  
  Historical NBS records used to construct ensemble forcings

All datasets are derived from **Coordinated Committee Great Lakes data sources** and are organized by lake.

---

### 📁 `utils/Templates/`
Model **template files** required by CGLRRM.

- Contains the **base parameter file**
- Scripts automatically modify this template to create
  member-specific parameter files for ensemble simulations

---

### 📁 `scripts/`
Python scripts that implement the **ensemble workflow**.

- `01_make_ensemble_input.py`
  Builds ensemble members by replacing the target-year NBS with
  historical NBS sequences and preparing input files.
  **Usage**: `python scripts/01_make_ensemble_input.py <year>`
  - Accepts year as command-line argument (default: 2000)
  - Dynamically creates ensemble members using years 1901 to TARGET_YEAR-1
  - Initializes simulations using water levels from the corresponding historical year

- `02_run_ensemble.py`
  Runs CGLRRM for all ensemble members in batch mode.
  **Usage**: `python scripts/02_run_ensemble.py <year>`
  - Accepts year as command-line argument (default: 2000)
  - Processes ensemble members for the specified target year

- `03_eval_ensemble.py`
  Evaluates ensemble lake-level simulations using probabilistic
  metrics such as **CRPS** and **rank histograms**.
  **Usage**: `python scripts/03_eval_ensemble.py <year>`
  - Accepts year as command-line argument (default: 2000)
  - Generates monthly CRPS data for lead time analysis
  - Creates timeseries and rank histogram plots

- `04_multi_year_analysis.py`
  Runs complete multi-year ensemble analysis pipeline (2001-2025, excluding 2019, 2025).
  - Automatically invokes scripts 01, 02, and 03 for each year
  - Generates CRPS vs Water Level Anomaly comparison plots (without trend lines)
  - **New feature**: Generates lead time performance plots (CRPS for 1-12 months ahead)
  - Creates combined multi-lake comparison figures
  - Outputs results CSV with annual metrics

- `04_multi_year_analysis_simple.py`
  Regenerates analysis figures from existing simulation results.
  - Use when simulations are already complete and you only want to update plots
  - Shows CRPS evolution and anomaly patterns over time
  - Includes CRPS vs Anomaly scatter plots with CRPS=0 reference line

---

### 📁 `experiments/`
Automatically generated **experiment outputs**.

This folder is created by the scripts and typically contains:
- One subfolder per ensemble member
- Member-specific input files, parameter files, and model outputs
- Aggregated evaluation metrics and diagnostic figures

Users generally do **not** edit this folder manually.

---

## Scientific Workflow (High-Level)

1. **Historical NBS data** are used to construct a climatological ensemble
   (each historical year becomes one ensemble member)
2. Simulations are **initialized using beginning-of-month lake levels** from the same historical year
3. CGLRRM is run independently for each ensemble member for a target year
4. Ensemble lake-level simulations are evaluated against observations
   using probabilistic metrics (CRPS, rank histograms)
5. **Multi-year analysis** aggregates results across multiple years and generates:
   - Annual CRPS vs Water Level Anomaly scatter plots
   - Forecast skill evolution over time
   - Lead time performance analysis (1-12 months ahead)

### Key Improvements

- **Year-specific ensemble member ranges**: Each target year uses ensemble members from 1901 to (TARGET_YEAR-1),
  ensuring consistent historical context as the observation period extends
- **Consistent initial conditions**: Each ensemble member uses water level initialization from its corresponding
  historical year, maintaining internal consistency
- **Lead time analysis**: Monthly CRPS values are aggregated to show how forecast skill degrades with increasing lead time
- **Simplified visualizations**: CRPS vs Anomaly plots focus on data relationships without trend lines or year labels

---

## Generated Output Figures

The analysis scripts generate the following visualizations in `experiments/analysis/`:

### Evolution Plots
- `evolution_sp.png`, `evolution_mh.png`, `evolution_er.png`
  - Left panels: Annual mean CRPS evolution over target years
  - Right panels: Water level anomaly evolution relative to long-term means

### CRPS vs Anomaly Scatter Plots
- `crps_vs_anomaly_sp.png`, `crps_vs_anomaly_mh.png`, `crps_vs_anomaly_er.png`
  - Shows relationship between forecast skill (CRPS) and water level departure from long-term mean
  - Green dotted line at CRPS=0 indicates perfect forecast skill

### Lead Time Performance Plots (New)
- `lead_time_performance_sp.png`, `lead_time_performance_mh.png`, `lead_time_performance_er.png`
  - Shows mean CRPS for each lead month (1-12 months ahead)
  - Aggregated across all simulation years to show skill degradation with forecast horizon
  - Green dotted line indicates perfect forecast skill

### Combined Multi-Lake Comparison
- `combined_analysis.png`
  - 2×3 grid comparing CRPS and anomaly evolution for all three lakes

---

## Intended Use

This repository is intended for:
- Great Lakes hydrology and regulation research
- Ensemble forecasting and uncertainty analysis
- Model benchmarking and performance evaluation

It is **not** intended as a general-purpose CGLRRM user interface.

---

## Maintainer

**Yi Hong**  
University of Michigan / CIGLR
