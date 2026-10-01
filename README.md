# Replication code — *Have We Been Too Strict? Friction-Corrected Performance Attribution for Active U.S. Equity Mutual Funds*

Master's thesis, Eberhard Karls Universität Tübingen, Chair of Financial Institutions (Prof. Dr. Monika Gehde-Trapp).

Eight Jupyter notebooks reproduce every table, figure and reported number of the empirical part. Each result is
checked automatically against the value printed in the thesis; a notebook stops if a number differs.

---

## Quick start (macOS / Linux)

```bash
# 1. Download the code and go into its folder
git clone https://github.com/isafridi-dxb/6948379-thesis-replication.git
cd 6948379-thesis-replication

# 2. Create an environment and install the packages (Python 3.10 or newer)
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. Check that the packages and all data files are found
python run_all.py --data "/path/to/Data" --check

# 4. Run all eight notebooks in order
python run_all.py --data "/path/to/Data"
```

`/path/to/Data` is the data folder described in section 1. The run ends with `All done`. Every notebook reports
how many thesis checks passed; executed copies with all printed output are saved to `executed/`, the figures to
`figures/`. The source notebooks are left unchanged.

Windows: use `python` instead of `python3` and `.venv\Scripts\activate` instead of `source .venv/bin/activate`.

---

## 1. Data (not included)

The data are licensed (WRDS) or were provided privately, so they are not part of this folder. Arrange them like
this — the folder and file names must match exactly:

```
Data/                                       <- this folder is passed as --data
├── CRSP_Data/
│   └── q_mutualfunds/
│       ├── monthly_tna_ret_nav.sas7bdat    WRDS CRSP Survivor-Bias-Free Mutual Fund Database
│       └── fund_summary2.sas7bdat          (same database)
├── MFLINKS/
│   └── MFLINKS_1.txt                       WRDS MFLINKS (crsp_fundno -> wficn)
└── Factor_Data/
    ├── F-F_Research_Data_5_Factors_2x3.csv Kenneth French Data Library, 202604 CRSP vintage
    ├── F-F_Momentum_Factor.csv             Kenneth French Data Library, 202604 CRSP vintage
    ├── liq_data_1962_2025.txt              Ľuboš Pástor's website (traded liquidity factor = column 4)
    └── Zero_beta_returns.csv               daily zero-beta returns, provided by Prof. Gehde-Trapp
```

- **Use the factor files shipped with the thesis**, not a fresh download: the French and Pástor files are revised
  over time, which changes the values and the header length the code expects.
- **Instead of the two large `.sas7bdat` files** you can copy the folder `CRSP_Data/q_mutualfunds/_cache/`
  (Parquet copies created by NB01 on the first run). The code then uses the cache and skips the slow SAS parsing.
- The folder must be **writable**: all intermediate files (`.parquet`) are written to `Data/CRSP_Data/`.
- The `--check` step lists every required file with ✓ or ✗.

Instead of passing `--data` each time, you can set `DATA_ROOT` once in `thesis_config.py` (line 21).

## 2. Pipeline

Run in this order (`run_all.py` does it automatically). Each notebook starts with a table of its inputs, outputs
and the thesis sections it reproduces.

| NB | Notebook | Reads | Writes |
|---|---|---|---|
| 01 | `01r_sample_construction` | CRSP SAS files, MFLINKS | `analysis_panel.parquet` |
| 02 | `02r_factor_data` | factor files | `factors.parquet`, `rz_monthly.parquet` |
| 03 | `03r_factor_merge` | NB01, NB02 | `panel_with_factors.parquet` |
| 04 | `04r_stage1a_decomposition` | NB03 | `stage1a_results.parquet`, `stage1a_residuals.parquet` (diagnostic only) |
| 05 | `05r_stage1b_cash_correction` | CRSP (cache from NB01), NB03 | `rpassive_D.parquet`, `stage1b_corrected_returns.parquet` |
| 06 | `06r_stage2_alpha_estimation` | NB05 | `stage2a_common_*.parquet`, `stage2b_*.parquet`, `delta_alpha.parquet` |
| 07 | `07r_mechanism_and_robustness` | NB05, NB06 | — |
| 08 | `08r_stage3_pca` | NB01, NB03, NB06 | — |

Shared settings — data paths, the seven factors, the 60-month minimum, Newey–West 12 lags and the Stage 2
estimator — are defined once in `thesis_config.py`.

## 3. Where each result comes from

| Thesis | Notebook |
|---|---|
| Section 3.2, Table 1 (attrition), Table 3 (fund summary statistics), cash-weight statistics and coverage figure (Figure A1) | NB01 |
| Sections 3.4–3.5, Table 2 (factor statistics) | NB02 |
| Section 4.1 (passive benchmark alpha), 4.3 (benchmark coverage) | NB05 |
| Section 5.1 (conventional alpha), 5.3 headline Δα̂, Figure 3 | NB06 |
| Section 5.2, Figure 1 (Stage 1a) | NB04 |
| Section 5.3: Table 4 (correction magnitude) | NB05 |
| Section 5.3: Tables 5–6, Figure 2 (mechanism, with a worked example of the units), cash weight in the estimation sample | NB07 |
| Section 5.4.1 (EW vs VW), 5.4.2 (alternative cash instrument) | NB05 |
| Sections 5.4.3–5.4.5, Tables 7–8 | NB07 |
| Sections 4.5, 5.5, 5.6, 6.1 (PCA), Figures 4–6 | NB08 |

## 4. What a successful run looks like

Each check prints one line, e.g. `✓ Table 8: t: matches the thesis`. If a value differs, the notebook stops with
`✗ <label>: computed [...] vs thesis [...]`, and `run_all.py` reports which notebook stopped and how to resume.
To finish the run anyway and list all differences (e.g. on another CRSP vintage), add `--warn`.

Approximate run times on a laptop: NB01 several minutes on the first run (SAS parsing; much faster with the cache),
NB08 a few minutes (200-shuffle permutation test), all others under a minute or two. NB01 needs roughly 8 GB of
free memory when it parses the SAS files.

## 5. Troubleshooting

| Message | Cause and fix |
|---|---|
| `✗ ... NOT FOUND` in the check | A data file is missing or named differently — compare with section 1. |
| `ModuleNotFoundError` | The environment is not active (`source .venv/bin/activate`) or packages are missing (`pip install -r requirements.txt`). |
| `✗ <label>: computed ... vs thesis ...` | A result differs from the thesis — usually a different data vintage. Rerun with `--warn` to see all differences. |
| A notebook stops part-way | Fix the cause, then resume from that notebook: `python run_all.py --from 05`. |
| `Kernel is running over TCP without encryption` | Harmless Jupyter warning; ignore. |
| Running interactively | Open the notebooks in Jupyter or VS Code, select the `.venv` kernel and use *Restart → Run All* in order 01 → 08. Set `DATA_ROOT` in `thesis_config.py` first. |

## 6. Notes for the reader

- **Net returns.** CRSP returns are net of expense ratios and 12b-1 fees (loads are not deducted; CRSP MFDB Guide,
  ch. 2, p. 6). All alphas, including Δα̂, are net-of-fee alphas. The passive benchmark is likewise built from index
  funds' net returns.
- **Units.** Alphas, the return gain (+0.188) and the beta penalty (0.205) are in percentage points per year
  (monthly decimal × 1200). NB07 prints a worked example for the average fund.

- **Table 7, first row (n = 1,949 vs. 1,950).** One fund met the 60-consecutive-month screen in NB01 before step 9
  (removal of pre-July-2003 months of funds later flagged as index funds) shortened its history. It stays in the
  Stage 2 sample, which requires 60 same-month observations in total; NB07 prints its identifier.
- **Zero-beta series.** 213 of the 5,660 in-sample daily values are stored in a corrupted numeric format
  (e.g. `-6,40E+09`) and are excluded before compounding to monthly returns (NB02, section 3).
- **Stage 1a** outputs are a diagnostic (Section 5.2); no later stage uses them.
- Rerunning a notebook copies the previous output file to `..._archive_<timestamp>.parquet` before overwriting it
  (switch off with `ARCHIVE_EXISTING = False` in `thesis_config.py`).
