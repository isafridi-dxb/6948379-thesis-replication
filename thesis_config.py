"""Shared paths, constants and helpers for the thesis replication notebooks (NB01–NB08).

A replicator edits ONE line: DATA_ROOT below (or sets the environment variable
THESIS_DATA_ROOT). Every notebook imports its paths from here.

Expected layout under DATA_ROOT:
    CRSP_Data/q_mutualfunds/*.sas7bdat   WRDS CRSP MFDB extract (monthly_tna_ret_nav, fund_summary2)
    MFLINKS/MFLINKS_1.txt                WRDS MFLINKS table
    Factor_Data/                         French FF5 + MOM csv, Pastor liq_data_1962_2025.txt, Zero_beta_returns.csv
    CRSP_Data/                           all intermediate .parquet files are written here
"""
import os
import shutil
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

# ── Paths ────────────────────────────────────────────────────────────────────
DATA_ROOT  = Path(os.environ.get("THESIS_DATA_ROOT", "/Volumes/SSK SSD/Thesis SoSe 26/Data"))  # <- edit

CRSP_DIR   = DATA_ROOT / "CRSP_Data" / "q_mutualfunds"
CACHE_DIR  = CRSP_DIR / "_cache"                   # Parquet copies of the SAS files (built by NB01)
MFLINKS_1  = DATA_ROOT / "MFLINKS" / "MFLINKS_1.txt"
FACTOR_DIR = DATA_ROOT / "Factor_Data"
DATA_DIR   = DATA_ROOT / "CRSP_Data"               # every notebook reads/writes its .parquet files here
FIG_DIR    = Path(__file__).resolve().parent / "figures"   # thesis figures (png + pdf)

ARCHIVE_EXISTING = True    # copy an existing output aside (…_archive_<timestamp>.parquet) before overwriting

# ── Model constants (identical in every stage) ───────────────────────────────
FACTORS  = ["mkt_rf", "smb", "hml", "rmw", "cma", "mom", "liq_traded"]   # FF5 + MOM + PS traded liquidity
MIN_OBS  = 60      # minimum monthly observations per fund regression
HAC_LAGS = 12      # Newey-West lags


def check_paths(*paths):
    for p in paths:
        assert Path(p).exists(), f"Path not found: {p}  -> edit DATA_ROOT in thesis_config.py"


def assert_matches(label, got, expected, decimals):
    """Check computed values against the numbers printed in the thesis.

    `decimals` is the precision the thesis reports; the tolerance is 0.6 units of the last printed
    digit (rounding plus occasional double rounding). Integers (decimals=0) must match exactly.
    Set the environment variable THESIS_CHECKS=warn to print mismatches instead of stopping,
    e.g. when running on a different CRSP vintage.
    """
    got = np.asarray(got, dtype=float).ravel()
    exp = np.asarray(expected, dtype=float).ravel()
    tol = 0.6 * 10.0 ** (-decimals) if decimals > 0 else 0.0
    if got.shape == exp.shape and np.all(np.abs(got - exp) <= tol + 1e-9):
        print(f"✓ {label}: matches the thesis")
        return
    msg = f"✗ {label}: computed {np.round(got, decimals + 2).tolist()} vs thesis {exp.tolist()}"
    if os.environ.get("THESIS_CHECKS", "strict") == "warn":
        print(msg)
    else:
        raise AssertionError(msg)


# ── I/O helpers ──────────────────────────────────────────────────────────────
def save_parquet(df, path, index=None):
    """Write df to path, first archiving an existing file if ARCHIVE_EXISTING."""
    path = Path(path)
    if ARCHIVE_EXISTING and path.exists():
        archive = path.with_name(f"{path.stem}_archive_{datetime.now():%Y%m%d_%H%M%S}.parquet")
        shutil.copy2(path, archive)
        print(f"Archived existing file -> {archive.name}")
    df.to_parquet(path, index=index)
    print(f"Saved {path.name}  {df.shape}")


def save_fig(fig, name):
    """Save a thesis figure as PNG (150 dpi) and PDF into FIG_DIR."""
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG_DIR / f"{name}.png", dpi=150, bbox_inches="tight")
    fig.savefig(FIG_DIR / f"{name}.pdf", bbox_inches="tight")
    print(f"Saved figures/{name}.png / .pdf")


def read_sas_cached(fname, columns=None):
    """Read CRSP_DIR/<fname> through a Parquet cache in CACHE_DIR.

    The cache is rebuilt automatically when the SAS file is newer than the cached copy. If only the
    cache is present (SAS file not copied), the cache is used. Delete CACHE_DIR to force a full re-parse.
    """
    import pyreadstat
    CACHE_DIR.mkdir(exist_ok=True)
    src = CRSP_DIR / fname
    pq  = CACHE_DIR / fname.replace(".sas7bdat", ".parquet")
    cache_ok = pq.exists() and (not src.exists() or pq.stat().st_mtime >= src.stat().st_mtime)
    if not cache_ok:                       # (with only the cache copied, the SAS file is not needed)
        df, _ = pyreadstat.read_sas7bdat(str(src), encoding="latin1")
        df.to_parquet(pq)
        print(f"[cache] parsed and cached {fname}")
        return df[columns] if columns else df
    return pd.read_parquet(pq, columns=columns)


def describe_cash(s):
    """Descriptive statistics of a cash-weight series in percent (per_cash_clean), missing values dropped."""
    s = pd.Series(s).dropna()
    q = s.quantile([.01, .05, .10, .25, .50, .75, .90, .95, .99])
    return pd.Series({"N": s.size, "mean": s.mean(), "sd": s.std(), "min": s.min(),
                      **{f"p{round(k * 100)}": v for k, v in q.items()}, "max": s.max(),
                      "% < 0": (s < 0).mean() * 100, "% = 0": (s == 0).mean() * 100,
                      "% > 5": (s > 5).mean() * 100, "% > 10": (s > 10).mean() * 100})


# ── Estimation helpers ───────────────────────────────────────────────────────
def max_consecutive_run(dates):
    """Length of the longest run of consecutive calendar months in `dates`."""
    dates = sorted(dates)
    max_run = run = 1
    for i in range(1, len(dates)):
        diff = (dates[i].year - dates[i-1].year) * 12 + (dates[i].month - dates[i-1].month)
        run = run + 1 if diff == 1 else 1
        max_run = max(max_run, run)
    return max_run


def estimate_alpha(frame, fund_list, ycol, label, winsorize=False, factors=FACTORS):
    """Fund-by-fund factor OLS with Newey-West(HAC_LAGS) standard errors (Stages 2a/2b).

    Same-months rule: a row is used only if ALL factors and BOTH the raw (excess_ret) and the
    corrected (excess_r_corrected) excess return are present, so conventional and corrected
    alphas are estimated on identical rows. Rows are sorted by date within fund because HAC
    lags are defined by row order. Optional winsorisation clips ycol at its pooled 1st/99th
    percentile over the estimation rows.
    """
    from statsmodels.regression.linear_model import OLS
    from statsmodels.tools import add_constant

    need = list(dict.fromkeys(list(factors) + ["excess_ret", "excess_r_corrected", ycol]))
    keep = list(dict.fromkeys(["wficn", "caldt"] + need))
    sub = (frame[keep]
           .dropna(subset=need)
           .sort_values(["wficn", "caldt"], kind="mergesort"))
    sub = sub[sub["wficn"].isin(set(fund_list))].copy()
    if winsorize:
        lo, hi = sub[ycol].quantile(0.01), sub[ycol].quantile(0.99)
        sub[ycol] = sub[ycol].clip(lo, hi)
        print(f"  [{label}] winsorised {ycol} to [{lo*100:.2f}%, {hi*100:.2f}%]")

    results, residuals = [], []
    for fund, f in sub.groupby("wficn", sort=False):
        if len(f) < MIN_OBS:
            continue
        m = OLS(f[ycol].values, add_constant(f[list(factors)].values)).fit(
            cov_type="HAC", cov_kwds={"maxlags": HAC_LAGS})
        row = {"wficn": fund, "alpha": m.params[0], "alpha_se": m.bse[0],
               "alpha_tstat": m.tvalues[0], "alpha_pval": m.pvalues[0]}
        row.update({f"beta_{c.split('_')[0]}": m.params[k + 1] for k, c in enumerate(factors)})
        row.update({"r_squared": m.rsquared, "n_obs": len(f)})
        results.append(row)
        res = f[["wficn", "caldt"]].copy()
        res["residual"] = m.resid
        residuals.append(res)
    print(f"  [{label}] estimated {len(results)} funds")
    return pd.DataFrame(results), pd.concat(residuals, ignore_index=True)
