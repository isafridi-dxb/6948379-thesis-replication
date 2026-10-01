"""Run the full replication: pre-flight check, then NB01 → NB08 in order.

Usage (from this folder):
    python run_all.py --data "/path/to/Data"        # check, then run all eight notebooks
    python run_all.py --data "/path/to/Data" --check   # only check Python packages and data files
    python run_all.py --data "/path/to/Data" --from 05 # resume at NB05 (earlier outputs must exist)
    python run_all.py --data "/path/to/Data" --warn    # report thesis mismatches instead of stopping

--data can be omitted if DATA_ROOT in thesis_config.py is already correct.
Executed copies of the notebooks, with all printed output and figures, are saved to ./executed/.
The source notebooks are not modified.
"""
import argparse
import importlib
import os
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
NOTEBOOKS = sorted(HERE.glob("0[1-8]*.ipynb"))
PACKAGES = ["pandas", "numpy", "scipy", "statsmodels", "matplotlib", "pyarrow", "pyreadstat", "nbclient", "ipykernel"]


def preflight():
    ok = True
    print(f"Python {sys.version.split()[0]} ({sys.executable})")
    if sys.version_info < (3, 10):
        print("  ✗ Python 3.10 or newer is required"); ok = False
    for pkg in PACKAGES:
        try:
            m = importlib.import_module(pkg)
            print(f"  ✓ {pkg:<12} {getattr(m, '__version__', '')}")
        except ImportError:
            print(f"  ✗ {pkg:<12} missing  ->  pip install -r requirements.txt"); ok = False

    sys.path.insert(0, str(HERE))
    import thesis_config as cfg
    print(f"\nDATA_ROOT = {cfg.DATA_ROOT}")
    need = [
        cfg.CRSP_DIR / "monthly_tna_ret_nav.sas7bdat",
        cfg.CRSP_DIR / "fund_summary2.sas7bdat",
        cfg.MFLINKS_1,
        cfg.FACTOR_DIR / "F-F_Research_Data_5_Factors_2x3.csv",
        cfg.FACTOR_DIR / "F-F_Momentum_Factor.csv",
        cfg.FACTOR_DIR / "liq_data_1962_2025.txt",
        cfg.FACTOR_DIR / "Zero_beta_returns.csv",
    ]
    for p in need:
        cached = p.suffix == ".sas7bdat" and (cfg.CACHE_DIR / p.name.replace(".sas7bdat", ".parquet")).exists()
        if p.exists() or cached:
            print(f"  ✓ {p.relative_to(cfg.DATA_ROOT)}" + ("  (Parquet cache present)" if cached and not p.exists() else ""))
        else:
            print(f"  ✗ {p.relative_to(cfg.DATA_ROOT)}  NOT FOUND"); ok = False
    if cfg.DATA_ROOT.exists() and not os.access(cfg.DATA_DIR if cfg.DATA_DIR.exists() else cfg.DATA_ROOT, os.W_OK):
        print(f"  ✗ {cfg.DATA_DIR} is not writable (outputs are saved there)"); ok = False
    print("\nPre-flight " + ("passed." if ok else "FAILED — fix the ✗ items above (see README, section 1)."))
    return ok


def run(start):
    import nbformat
    from nbclient import NotebookClient
    from nbclient.exceptions import CellExecutionError

    out_dir = HERE / "executed"
    out_dir.mkdir(exist_ok=True)
    todo = [nb for nb in NOTEBOOKS if nb.name[:2] >= start]
    t_all = time.time()
    for path in todo:
        print(f"\n▶ {path.name} ...", flush=True)
        nb = nbformat.read(path, as_version=4)
        client = NotebookClient(nb, timeout=None, kernel_name="python3",
                                resources={"metadata": {"path": str(HERE)}})
        t0 = time.time()
        try:
            client.execute()
        except CellExecutionError as e:
            nbformat.write(nb, out_dir / path.name)
            lines = [l for l in re.sub(r"\x1b\[[0-9;]*m", "", str(e)).splitlines() if l.strip()]
            print("\n".join(lines[-8:]))
            print(f"\n✗ {path.name} stopped after {time.time() - t0:.0f}s. Error: {lines[-1] if lines else '?'}")
            print(f"  Open executed/{path.name} to see the output up to the failing cell.")
            print(f"  After fixing the cause, resume with:  python run_all.py --from {path.name[:2]}")
            sys.exit(1)
        nbformat.write(nb, out_dir / path.name)
        text = "".join(o.get("text", "") for c in nb.cells if c.cell_type == "code" for o in c.get("outputs", []))
        n_ok, n_bad = text.count("✓"), text.count("✗")
        print(f"{'✓' if not n_bad else '!'} {path.name} finished in {time.time() - t0:.0f}s — {n_ok} thesis checks passed"
              + (f", {n_bad} MISMATCHES (warn mode)" if n_bad else ""))
    print(f"\nAll done in {(time.time() - t_all) / 60:.1f} min. Executed notebooks: executed/   Figures: figures/")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", help="DATA_ROOT folder (overrides thesis_config.py)")
    ap.add_argument("--check", action="store_true", help="only run the pre-flight check")
    ap.add_argument("--from", dest="start", default="01", help="first notebook to run, e.g. 05")
    ap.add_argument("--warn", action="store_true", help="print thesis mismatches instead of stopping")
    args = ap.parse_args()
    if args.data:
        os.environ["THESIS_DATA_ROOT"] = str(Path(args.data).expanduser().resolve())   # inherited by the kernels
    if args.warn:
        os.environ["THESIS_CHECKS"] = "warn"
    os.chdir(HERE)
    if not preflight():
        sys.exit(1)
    if not args.check:
        run(args.start.zfill(2))
