#!/usr/bin/env python
"""Add fn_arg[N,2] = (FN13, FN23) -- the ARG activation fraction WRF computed for
the SAME cell/step, before the emulator overwrote fn(1,1)/fn(2,1) -- to each
case's parcel_inputs.npz, row-aligned with X / sg2 / fn_wrf.

Row alignment is reproduced, not assumed:
  * same file list  (taken from the reconstruct log that produced the npz)
  * same mask       (EMTAIR>0 & EMWBAR>0 & NA{11,21}>1cm-3 & HG{11,21}>0 & VO{11,21}>0)
  * same subsample  (np.random.default_rng(42).choice(N, 1_500_000, replace=False), sorted)
and then VERIFIED: the reconstructed FN11/FN21 must equal the stored fn_wrf
exactly, element for element.  Nothing is written unless that check passes.
"""
import os, re, sys, glob
import glob
import re
import numpy as np
import netCDF4
from multiprocessing import Pool

# Tree is derived from this file's own location, as in every other analysis
# script here (plot_allcases_arg.py, plot_arg_relerr_map.py, ...).  It was
# previously hardcoded to the cosine_more tree, so a copy placed in
# cosine_more_fix would silently rewrite cosine_more's parcel_inputs.npz.
TEST = os.path.dirname(os.path.abspath(__file__))
# The reconstruct log records the exact ORDERED list of wrfout files that went
# into parcel_inputs.npz.  fn_arg must be built from that same list in that same
# order or the rows will not align with X/sg2/fn_wrf, so we discover the log
# rather than globbing wrfout (which would silently reorder or add files).
# Previously this was a hardcoded map of cosine_more slurm job-id filenames.
CASES = ["20170714_1aer_org", "20170714_1aer_mid",
         "20170714_3aer_org", "20170714_3aer_mid"]


def find_log(case):
    """Newest file in <case>/online/ that carries the per-file reconstruct
    counts.  Raises if none: better to stop than to mis-align rows."""
    d = os.path.join(TEST, case, "online")
    cand = sorted(glob.glob(os.path.join(d, "*.out"))
                  + glob.glob(os.path.join(d, "*.log")),
                  key=lambda f: os.path.getmtime(f), reverse=True)
    for f in cand:
        try:
            if re.search(r"wrfout_d01_\S+:\s+[\d,]+ updraft cells", open(f).read()):
                return f
        except OSError:
            continue
    raise FileNotFoundError(
        f"{case}: no reconstruct log with per-file counts in {d}.\n"
        f"        Run the reconstruct phase first (setup_online_dirs.sh --reconstruct).")
MAX_CELLS = 1_500_000
NEED = ["EMTAIR", "EMWBAR", "NA11", "NA21", "VO11", "VO21", "HG11", "HG21",
        "FN11", "FN21", "FN13", "FN23"]


def one_file(path):
    nc = netCDF4.Dataset(path, "r"); nc.set_auto_mask(False)
    g = lambda v: nc.variables[v][0].astype(np.float64).ravel()   # as read_wrfout does
    d = {v: g(v) for v in NEED}
    nc.close()
    mask = (d["EMTAIR"] > 0.0) & (d["EMWBAR"] > 0.0)
    for tag in ("11", "21"):
        mask &= (d[f"NA{tag}"] * 1e-6 > 1.0) & (d[f"HG{tag}"] > 0.0) & (d[f"VO{tag}"] > 0.0)
    idx = np.where(mask)[0]
    return (np.stack([d["FN11"][idx], d["FN21"][idx]], 1),
            np.stack([d["FN13"][idx], d["FN23"][idx]], 1))


def files_from_log(case):
    log = find_log(case)
    hits = re.findall(r"(wrfout_d01_\S+):\s+[\d,]+ updraft cells", open(log).read())
    return [os.path.join(TEST, case, h) for h in hits]


def main():
    for case in CASES:
        files = files_from_log(case)
        print(f"=== {case}: {len(files)} wrfout files from {os.path.basename(find_log(case))}", flush=True)
        with Pool(8) as p:
            parts = p.map(one_file, files)
        fn_wrf_re = np.concatenate([a for a, _ in parts], 0)
        fn_arg = np.concatenate([b for _, b in parts], 0)
        N = fn_wrf_re.shape[0]
        print(f"    pool before subsample: {N:,}", flush=True)
        if MAX_CELLS and N > MAX_CELLS:
            sel = np.random.default_rng(42).choice(N, size=MAX_CELLS, replace=False)
            sel.sort()
            fn_wrf_re, fn_arg = fn_wrf_re[sel], fn_arg[sel]

        npz_path = os.path.join(TEST, case, "online", "parcel_inputs.npz")
        z = np.load(npz_path)
        stored = z["fn_wrf"]
        if stored.shape != fn_wrf_re.shape or not np.array_equal(stored, fn_wrf_re):
            nbad = (stored.shape != fn_wrf_re.shape) or int((stored != fn_wrf_re).sum())
            print(f"    !! ROW ALIGNMENT FAILED (shape {stored.shape} vs {fn_wrf_re.shape}, "
                  f"mismatches {nbad}) -- npz NOT touched", flush=True)
            continue
        print(f"    row alignment verified: FN11/FN21 identical to stored fn_wrf "
              f"({stored.shape[0]:,} rows)", flush=True)

        tmp = npz_path + ".tmp.npz"
        np.savez(tmp, X=z["X"], sg2=z["sg2"], fn_wrf=z["fn_wrf"], fn_arg=fn_arg)
        z.close()
        os.replace(tmp, npz_path)
        print(f"    wrote {npz_path}  (+fn_arg[{fn_arg.shape[0]:,},2], "
              f"mean ARG Aitken={fn_arg[:,0].mean():.4f} Accum={fn_arg[:,1].mean():.4f})",
              flush=True)


if __name__ == "__main__":
    main()
