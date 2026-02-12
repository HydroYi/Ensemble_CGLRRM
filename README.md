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
  historical NBS sequences and preparing input files

- `02_run_ensemble.py`  
  Runs CGLRRM for all ensemble members in batch mode

- `03_eval_ensemble.py`  
  Evaluates ensemble lake-level simulations using probabilistic
  metrics such as **CRPS** and **rank histograms**

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
2. Simulations are **initialized using beginning-of-month lake levels**
3. CGLRRM is run independently for each ensemble member
4. Ensemble lake-level simulations are evaluated against observations
   using probabilistic metrics

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
