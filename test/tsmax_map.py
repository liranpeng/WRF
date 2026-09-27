#!/usr/bin/env python
"""
tsmax_map.py
=============================================================================
Map the SIMULATED TIME the Fortran parcel model needs to reach S_max, over the
(log10 wbar, log10 na_accum) plane, with every other input drawn from the WRF
run distributions.

Motivation
----------
The relative-error map (arg_relerr_map_filtered.png) shows its deepest
under-activation at high wbar / low na_accum.  One hypothesis was that the
parcel reference there is not a converged S_max but an artifact of the
50,000 s integration cap.  The cleaning chain already excludes any sample that
reaches the cap (activate.f flags is_bad_sample; plot_allcases_arg.py keeps
only bad==0 & tout==0 & smax>0), and across all four cases ZERO samples were
flagged -- but the 60 s per-sample WALL-CLOCK limit removed 19,526 of 111,208
attempted integrations, preferentially the slow/stiff ones.  This script
measures the underlying quantity directly: how long, in simulated seconds, the
solve actually takes to reach S_max as a function of wbar and na_accum.

How the time is obtained
------------------------
parcel_lib_tsmax/ is a patched copy of the parcel library.  A small module
(parcel_diag.f90) records, inside explact(), the step index at which the
running supersaturation maximum was last raised and the step at which the
solve terminated; the ctypes wrapper returns both.  explact integrates with
dt = 1.0 s, so those step counts ARE simulated seconds.  No numerics were
changed -- only two counters and two extra output arguments.

Sampling
--------
For each (wbar, na_accum) grid node we draw N_PER_BIN real WRF rows at random
and overwrite only wbar and the accumulation-mode number concentration with
the node values.  Everything else -- T, p, RH, Aitken number, both mode
widths, both hygroscopicities, both mean radii -- keeps the joint values of
the drawn row, so the co-variation WRF actually produced is preserved.  Note
this holds the accumulation-mode mean radius fixed while varying its number,
i.e. it is a number-concentration sweep at fixed modal size, the usual
convention for this kind of sensitivity map.

Wall-clock limit
----------------
--tlimit defaults to 600 s, an order of magnitude above the 60 s used to build
the training set, precisely because a 60 s limit would censor the cells this
figure exists to measure.  Cells that still time out are reported separately
and drawn in hatch rather than silently dropped.

Usage
-----
  python tsmax_map.py --nbins 24 --nper 8 --workers 48 --tlimit 600
=============================================================================
"""
import argparse, ctypes, os, sys, time
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))
LIB_DEFAULT = ("/scratch/07088/tg863871/Perlm_Backup/retrain_wrfdist_stam3/"
               "parcel_lib_tsmax/libactivate.so")
CASES = ["20170714_1aer_org", "20170714_1aer_mid",
         "20170714_3aer_org", "20170714_3aer_mid"]

# X column layout (from compare_parcel_vs_wrfout.py:203-207)
C_T, C_P, C_RH, C_W = 0, 1, 2, 3
C_NA = slice(4, 6)        # NA11 (Aitken), NA21 (Accum)   #/cm3
C_RA = slice(8, 10)       # mean radius Aitken, Accum     um
C_HG = slice(12, 14)      # hygroscopicity Aitken, Accum
I_NA_ACC = 5

_lib = None


def _init(lib_path):
    global _lib
    fd = os.open(os.devnull, os.O_WRONLY)
    os.dup2(fd, 1); os.dup2(fd, 2); os.close(fd)   # silence Fortran prints
    _lib = ctypes.CDLL(lib_path)
    f = _lib.fortranactivate_
    f.restype = None
    Pi = ctypes.POINTER(ctypes.c_int); Pf = ctypes.POINTER(ctypes.c_float)
    #                                                     ... smax, t_smax, t_end
    f.argtypes = [Pi, Pf, Pf, Pf, Pf, Pf, Pf, Pf, Pf, Pi, Pi, Pi, Pf, Pf, Pi, Pi]


def _run(task):
    """task = (k, row[16], sg[2], tlimit) -> (k, smax, t_smax, t_end, bad, tout, wall)"""
    k, row, sg, tlimit = task
    num = np.ascontiguousarray(row[C_NA], np.float32)
    sig = np.ascontiguousarray(sg,        np.float32)
    kap = np.ascontiguousarray(row[C_HG], np.float32)
    ra  = np.ascontiguousarray(row[C_RA], np.float32)
    fo  = np.zeros(2, np.float32)
    Pf = ctypes.POINTER(ctypes.c_float)
    nm = ctypes.c_int(2)
    t  = ctypes.c_float(float(row[C_T]));  p  = ctypes.c_float(float(row[C_P]))
    rh = ctypes.c_float(float(row[C_RH])); w  = ctypes.c_float(float(row[C_W]))
    tl = ctypes.c_int(int(tlimit)); bad = ctypes.c_int(0); to = ctypes.c_int(0)
    sm = ctypes.c_float(0.0); ns = ctypes.c_int(-1); ne = ctypes.c_int(-1)
    t0 = time.time()
    _lib.fortranactivate_(
        ctypes.byref(nm), ctypes.byref(t), ctypes.byref(p), ctypes.byref(rh),
        num.ctypes.data_as(Pf), ctypes.byref(w), sig.ctypes.data_as(Pf),
        kap.ctypes.data_as(Pf), ra.ctypes.data_as(Pf), ctypes.byref(tl),
        ctypes.byref(bad), ctypes.byref(to), fo.ctypes.data_as(Pf),
        ctypes.byref(sm), ctypes.byref(ns), ctypes.byref(ne))
    return (k, float(sm.value), int(ns.value), int(ne.value),
            int(bad.value), int(to.value), time.time() - t0)


def load_pool(base):
    Xs, Gs = [], []
    for c in CASES:
        f = os.path.join(base, c, "online", "parcel_inputs.npz")
        if not os.path.exists(f):
            print(f"  skip (missing): {f}"); continue
        z = np.load(f)
        X, sg = z["X"], z["sg2"]
        ok = np.isfinite(X).all(1) & np.isfinite(sg).all(1) \
             & (X[:, C_W] > 0) & (X[:, I_NA_ACC] > 0)
        Xs.append(X[ok]); Gs.append(sg[ok])
        print(f"  {c}: {int(ok.sum()):,}")
    return np.concatenate(Xs, 0), np.concatenate(Gs, 0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=HERE)
    ap.add_argument("--lib", default=LIB_DEFAULT)
    ap.add_argument("--nbins", type=int, default=24)
    ap.add_argument("--nper", type=int, default=8)
    ap.add_argument("--workers", type=int, default=max(1, os.cpu_count() - 2))
    ap.add_argument("--tlimit", type=int, default=600)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", default="tsmax_map")
    a = ap.parse_args()

    print("loading WRF input pool ...", flush=True)
    X, SG = load_pool(a.base)
    print(f"pooled rows: {X.shape[0]:,}", flush=True)

    w_cms = X[:, C_W]; na_acc = X[:, I_NA_ACC]
    wl = np.log10(w_cms); nl = np.log10(na_acc)
    wlo, whi = np.percentile(wl, [0.5, 99.5])
    nlo, nhi = np.percentile(nl, [0.5, 99.5])
    wedges = np.linspace(wlo, whi, a.nbins + 1)
    nedges = np.linspace(nlo, nhi, a.nbins + 1)
    wmid = 0.5 * (wedges[1:] + wedges[:-1])
    nmid = 0.5 * (nedges[1:] + nedges[:-1])
    print(f"grid: log10 w [{wlo:.2f},{whi:.2f}]  log10 na_acc [{nlo:.2f},{nhi:.2f}]")

    rng = np.random.default_rng(a.seed)
    tasks, keys = [], []
    k = 0
    for i, wm in enumerate(wmid):
        for j, nm_ in enumerate(nmid):
            idx = rng.integers(0, X.shape[0], a.nper)
            for s in idx:
                row = X[s].copy()
                row[C_W] = 10.0 ** wm             # cm/s, as stored in X
                row[I_NA_ACC] = 10.0 ** nm_       # #/cm3
                tasks.append((k, row, SG[s], a.tlimit))
                keys.append((i, j)); k += 1
    print(f"{len(tasks):,} parcel solves on {a.workers} workers "
          f"(wall-clock limit {a.tlimit}s each)", flush=True)

    t0 = time.time()
    res = np.full((len(tasks), 5), np.nan)
    done = 0
    with Pool(a.workers, initializer=_init, initargs=(a.lib,)) as pool:
        for (kk, smax, ts, te, bad, to, wall) in pool.imap_unordered(_run, tasks, chunksize=1):
            res[kk] = (smax, ts, te, bad, to)
            done += 1
            if done % max(1, len(tasks) // 40) == 0:
                el = time.time() - t0
                print(f"  {done:,}/{len(tasks):,}  {el/60:.1f} min "
                      f"(eta {el/done*(len(tasks)-done)/60:.1f} min)", flush=True)
    print(f"finished in {(time.time()-t0)/60:.1f} min", flush=True)

    keys = np.array(keys)
    smax, tsm, tend, bad, tout = (res[:, c] for c in range(5))
    good = (bad == 0) & (tout == 0) & (smax > 0) & (tsm > 0)
    print(f"converged: {int(good.sum()):,}/{len(tasks):,}  "
          f"wallclock-timeout: {int((tout != 0).sum()):,}  "
          f"step-cap(bad): {int((bad != 0).sum()):,}  "
          f"no-supersat: {int(((bad==0)&(tout==0)&~(smax>0)).sum()):,}")

    nb = a.nbins
    T   = np.full((nb, nb), np.nan)
    CEN = np.zeros((nb, nb))
    CNT = np.zeros((nb, nb))
    for i in range(nb):
        for j in range(nb):
            m = (keys[:, 0] == i) & (keys[:, 1] == j)
            CNT[i, j] = m.sum()
            g = m & good
            if g.sum():
                T[i, j] = np.median(tsm[g])
            CEN[i, j] = (m & ~good).sum() / max(1, m.sum())

    np.savez(os.path.join(HERE, a.out + ".npz"),
             wedges=wedges, nedges=nedges, T=T, CEN=CEN, CNT=CNT,
             tsm=tsm, tend=tend, smax=smax, bad=bad, tout=tout, keys=keys)

    # ---------------------------------------------------------------- plot
    fig, ax = plt.subplots(figsize=(9.2, 7.2))
    finite = np.isfinite(T)
    vmin = max(1.0, np.nanpercentile(T[finite], 1)) if finite.any() else 1
    vmax = np.nanpercentile(T[finite], 99) if finite.any() else 1e4
    pcm = ax.pcolormesh(wedges, nedges, np.ma.masked_invalid(T).T,
                        cmap="viridis", norm=mcolors.LogNorm(vmin=vmin, vmax=vmax),
                        shading="flat")
    cb = fig.colorbar(pcm, ax=ax, extend="both")
    cb.set_label("median simulated time to reach $S_{max}$  (s)", fontsize=13)

    # hatch bins where a meaningful fraction did not converge in the limit
    Hm = np.ma.masked_where(CEN.T < 0.25, CEN.T)
    ax.pcolormesh(wedges, nedges, Hm, cmap=mcolors.ListedColormap(["none"]),
                  hatch="///", edgecolor="crimson", linewidth=0.0, shading="flat")

    CS = ax.contour(0.5*(wedges[1:]+wedges[:-1]), 0.5*(nedges[1:]+nedges[:-1]),
                    np.ma.masked_invalid(T).T,
                    levels=[10, 100, 1000, 10000], colors="k", linewidths=1.1)
    ax.clabel(CS, fmt="%.0f s", fontsize=10)

    ax.set_xlabel(r"$\log_{10}\ \bar{w}$  (cm s$^{-1}$)", fontsize=14)
    ax.set_ylabel(r"$\log_{10}\ n_{\mathrm{acc}}$  (cm$^{-3}$)", fontsize=14)
    ax.set_title("Simulated time for the Fortran parcel model to reach $S_{max}$\n"
                 f"other inputs drawn from the WRF run distributions; "
                 f"{a.nper} samples/bin, wall-clock limit {a.tlimit}s",
                 fontsize=13)
    ax.text(0.02, 0.02,
            f"red hatch: >25% of samples did not converge within {a.tlimit}s wall clock\n"
            f"integration cap is 50,000 s of simulated time",
            transform=ax.transAxes, fontsize=9, va="bottom",
            bbox=dict(fc="white", alpha=0.85))
    fig.tight_layout()
    for ext in ("png", "eps"):
        fig.savefig(os.path.join(HERE, f"{a.out}.{ext}"), dpi=150)
    print("wrote", os.path.join(HERE, a.out + ".png"))


if __name__ == "__main__":
    main()
