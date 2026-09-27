#!/usr/bin/env python
"""
plot_allcases_arg.py
=============================================================================
ONE pooled figure over ALL four WRF test cases, on exactly the sample set the
published cleaned scatter used (good parcel solve, lost-output cells removed),
comparing three activation fractions per mode:

    fn_parcel   Fortran box model on the stored WRF state   -- ground truth
    fn_wrf      FN11 / FN21, the ML emulator answer WRF applied
    fn_arg      FN13 / FN23, the Abdul-Razzak & Ghan answer WRF computed for
                the SAME cell and step (module_mixactivate.F copies
                fn_ARG(m,n)=fn(m,n) after the ARG solve, before the emulator
                overwrites fn(1,1)/fn(2,1)), now stored in parcel_inputs.npz

Layout (rows = Aitken, Accum):

    col 1   parcel (x) vs emulator (y)   -- emulator skill      [published panel]
    col 2   parcel (x) vs ARG      (y)   -- ARG skill
    col 3   ARG    (x) vs emulator (y)   -- scheme vs scheme

All three panels in a row use the IDENTICAL samples, so the MSE / R numbers are
directly comparable.

Usage
-----
  $HOME/.conda/envs/liranenv_gpu/bin/python plot_allcases_arg.py
  ... --cases 20170714_1aer_org 20170714_3aer_mid     # subset
=============================================================================
"""
import os
import glob
import argparse

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors

HERE = os.path.dirname(os.path.abspath(__file__))

CASES = [
    ("20170714_1aer_org", "1aer / org"),
    ("20170714_1aer_mid", "1aer / mid"),
    ("20170714_3aer_org", "3aer / org"),
    ("20170714_3aer_mid", "3aer / mid"),
]
MODES = ["Aitken", "Accum"]
ZERO = 1e-12          # "stored exactly 0"
ML_POS = 0.01         # "the emulator clearly wanted a non-zero answer"


# ───────────────────────── loading ──────────────────────────────────────────
def load_case(case_dir):
    """Same cleaning chain as plot_allcases_lost_removed.py, plus fn_arg."""
    on = os.path.join(case_dir, "online")
    z = np.load(os.path.join(on, "parcel_inputs.npz"))
    if "fn_arg" not in z.files:
        raise KeyError(f"{on}/parcel_inputs.npz has no fn_arg -- run add_fn_arg.py first")
    fn_wrf, fn_arg = z["fn_wrf"], z["fn_arg"]
    N = fn_wrf.shape[0]

    shards = sorted(glob.glob(os.path.join(on, "parcel_shard_*.npz")))
    if not shards:
        raise FileNotFoundError(f"no parcel_shard_*.npz in {on}")
    res = np.concatenate([np.load(p)["res"] for p in shards], 0)

    fn_parcel = np.full((N, 2), np.nan)
    smax = np.full(N, np.nan)
    bad = np.ones(N, np.int32)
    tout = np.zeros(N, np.int32)
    attempted = np.zeros(N, bool)
    i = res[:, 0].astype(np.int64)
    attempted[i] = True
    fn_parcel[i, 0] = np.clip(res[:, 1], 0, 1)
    fn_parcel[i, 1] = np.clip(res[:, 2], 0, 1)
    smax[i] = res[:, 3]
    bad[i] = res[:, 4].astype(np.int32)
    tout[i] = res[:, 5].astype(np.int32)
    good = attempted & (bad == 0) & (tout == 0) & (smax > 0)

    fn_ml = np.load(os.path.join(on, "diag_fn_ml_offline.npz"))["fn_ml"]
    lost = (fn_wrf[:, 0] <= ZERO) & (fn_wrf[:, 1] <= ZERO) & (fn_ml[:, 1] > ML_POS)

    # FN13/FN23 are PERSISTENT state arrays that only the OLD_CLOUD call site
    # (module_mixactivate.F:1079) writes for the emulated modes; the
    # GROW_SHRINK call site (:789) writes fn13/fn23 only under its n==3 branch.
    # A cell whose last activate_ml call came from GROW_SHRINK therefore keeps
    # whatever fn13/fn23 held before -- an uninitialised value on the first
    # visit (out of [0,1], ~0.5% of rows) or a stale value from an earlier step
    # (indistinguishable in value, but ~50-76% of rows by the bit-identical
    # -across-a-step test).  Only the out-of-range rows can be flagged per row.
    arg_ok = ((fn_arg >= 0.0) & (fn_arg <= 1.0)).all(1)
    keep = good & ~lost & arg_ok

    return dict(N=N, fn_wrf=fn_wrf, fn_arg=fn_arg, fn_parcel=fn_parcel,
                good=good, lost=lost, arg_ok=arg_ok, keep=keep)


# ─────────────────────────── plotting ───────────────────────────────────────
def panel(ax, x, y, title, xlab, ylab, letter=""):
    if letter:
        ax.text(-0.17, 1.13, f"({letter})", transform=ax.transAxes,
                fontsize=20, fontweight="bold", va="top", ha="left")
    ok = np.isfinite(x) & np.isfinite(y)
    x, y = x[ok], y[ok]
    if x.size == 0:
        ax.set_title(title + " (no data)", fontsize=14)
        return
    ax.hexbin(x, y, gridsize=80, mincnt=1, cmap="viridis", extent=[0, 1, 0, 1],
              norm=mcolors.LogNorm(vmin=1), rasterized=True)
    ax.plot([0, 1], [0, 1], "r--", lw=1.4)
    mse = ((y - x) ** 2).mean()
    bias = (y - x).mean()
    r = np.corrcoef(x, y)[0, 1] if x.size > 2 else np.nan
    ax.text(0.03, 0.97,
            f"N={x.size:,}\nMSE={mse:.2e}\nRMSE={np.sqrt(mse):.3f}\n"
            f"bias={bias:+.3f}\nR={r:.4f}",
            transform=ax.transAxes, va="top", fontsize=12,
            bbox=dict(fc="white", alpha=0.85))
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    ax.tick_params(axis="both", labelsize=13)
    ax.set_xlabel(xlab, fontsize=14); ax.set_ylabel(ylab, fontsize=14)
    ax.set_title(title, fontsize=15)


def save_fig(fig, prefix):
    """PNG + EPS; data layers rasterized (PS backend drops alpha), axes vector."""
    for ext in ("png", "eps"):
        p = f"{prefix}.{ext}"
        fig.savefig(p, dpi=300, bbox_inches="tight")
        print(f"Wrote {p}", flush=True)
    plt.close(fig)


# ─────────────────────────── stats report ───────────────────────────────────
def stats_block(fh, tag, x, y, xlab, ylab):
    ok = np.isfinite(x) & np.isfinite(y)
    x, y = x[ok], y[ok]
    mse = ((y - x) ** 2).mean()
    fh.write(f"    {tag:<34} N={x.size:>9,}  MSE={mse:.4e}  RMSE={np.sqrt(mse):.4f}  "
             f"bias={(y-x).mean():+.4f}  R={np.corrcoef(x,y)[0,1]:+.4f}\n")
    fh.write(f"      {'mean ' + xlab:<28} {x.mean():.4f}   "
             f"{'mean ' + ylab:<24} {y.mean():.4f}\n")
    fh.write(f"      {'frac ' + xlab + ' < 0.01':<28} {np.mean(x < 0.01):.4f}   "
             f"{'frac ' + ylab + ' < 0.01':<24} {np.mean(y < 0.01):.4f}\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cases", nargs="*", default=None)
    ap.add_argument("--out_prefix",
                    default=os.path.join(HERE, "parcel_vs_ARG_vs_ML_ALLCASES"))
    args = ap.parse_args()

    cases = [c for c in CASES if args.cases is None or c[0] in args.cases]

    P, W, A = [], [], []          # parcel, wrf(ML), ARG -- kept rows only
    Pf, Wf, Af = [], [], []       # full pool (no parcel-solve requirement)
    per_case = []
    for cdir, label in cases:
        print(f"loading {cdir} ...", flush=True)
        c = load_case(os.path.join(HERE, cdir))
        k = c["keep"]
        P.append(c["fn_parcel"][k]); W.append(c["fn_wrf"][k]); A.append(c["fn_arg"][k])
        clean = ~c["lost"] & c["arg_ok"]
        Wf.append(c["fn_wrf"][clean]); Af.append(c["fn_arg"][clean])
        per_case.append((label, c["N"], int(c["good"].sum()), int(c["lost"].sum()),
                         int((~c["arg_ok"]).sum()), int(k.sum())))
        print(f"    N={c['N']:,}  good={c['good'].sum():,}  lost={c['lost'].sum():,}"
              f"  ARG out-of-range={(~c['arg_ok']).sum():,}  kept={k.sum():,}", flush=True)

    P = np.concatenate(P, 0); W = np.concatenate(W, 0); A = np.concatenate(A, 0)
    Wf = np.concatenate(Wf, 0); Af = np.concatenate(Af, 0)
    print(f"\npooled kept samples: {P.shape[0]:,}", flush=True)

    # ── figure ──
    fig, axes = plt.subplots(2, 3, figsize=(16.5, 10.5))
    letters = [["a", "b", "c"], ["d", "e", "f"]]
    for r, mode in enumerate(MODES):
        panel(axes[r, 0], P[:, r], W[:, r],
              f"{mode}: ML emulator vs parcel", "fn_parcel (Fortran box model)",
              "fn_wrf  (ML emulator, applied)", letters[r][0])
        panel(axes[r, 1], P[:, r], A[:, r],
              f"{mode}: ARG vs parcel", "fn_parcel (Fortran box model)",
              "fn_ARG  (FN13/FN23, same cell)", letters[r][1])
        panel(axes[r, 2], W[:, r], A[:, r],
              f"{mode}: ARG vs ML emulator", "fn_wrf  (ML emulator, applied)",
              "fn_ARG  (FN13/FN23, same cell)", letters[r][2])
    fig.suptitle("All four cases pooled, cleaned sample set (good parcel solve, "
                 f"lost-output cells removed) -- N={P.shape[0]:,}\n"
                 "columns: emulator skill | ARG skill | ARG vs emulator      "
                 "(red dashed = 1:1, colour = log10 count)\n"
                 "CAVEAT: fn_ARG (FN13/FN23) is a persistent WRF array written only by the "
                 "OLD_CLOUD call site; on cells last served by the\nGROW_SHRINK call site it "
                 "is stale (~50-76% of cells by the bit-identical-across-a-step test), so the "
                 "two ARG columns\nare NOT strictly synchronous with fn_parcel / fn_wrf.",
                 fontsize=13)
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    save_fig(fig, args.out_prefix)

    # ── text report ──
    rep = args.out_prefix + "_stats.txt"
    with open(rep, "w") as fh:
        fh.write("=" * 100 + "\n")
        fh.write("POOLED ARG / EMULATOR / PARCEL COMPARISON\n")
        fh.write("=" * 100 + "\n\n")
        fh.write("fn_parcel  Fortran box model on the stored WRF state (ground truth)\n")
        fh.write("fn_wrf     FN11 / FN21 -- ML emulator fraction WRF applied\n")
        fh.write("fn_ARG     FN13 / FN23 -- ARG fraction WRF computed for the same cell,\n")
        fh.write("           saved before the emulator overwrote fn(1,1)/fn(2,1).\n")
        fh.write("           Rows whose fn_ARG falls outside [0,1] in either mode are\n")
        fh.write("           DROPPED here: fn13/fn23 are persistent state arrays that the\n")
        fh.write("           GROW_SHRINK call site (module_mixactivate.F:789) never writes\n")
        fh.write("           for the emulated modes, so an unvisited cell can expose an\n")
        fh.write("           uninitialised value (seen up to 5.5e5 and -3.4e10).\n\n")
        fh.write(f"{'case':<14} {'pool N':>10} {'good solve':>11} {'lost':>10} "
                 f"{'ARG>1 or <0':>12} {'kept':>10}\n")
        for label, N, ng, nl, nab, nk in per_case:
            fh.write(f"{label:<14} {N:>10,} {ng:>11,} {nl:>10,} {nab:>12,} {nk:>10,}\n")
        fh.write(f"{'POOLED':<14} {'':>10} {'':>11} {'':>10} {'':>12} {P.shape[0]:>10,}\n\n")

        for r, mode in enumerate(MODES):
            fh.write("-" * 100 + f"\n{mode}\n" + "-" * 100 + "\n")
            stats_block(fh, "ML emulator vs parcel", P[:, r], W[:, r], "fn_parcel", "fn_wrf")
            stats_block(fh, "ARG         vs parcel", P[:, r], A[:, r], "fn_parcel", "fn_ARG")
            stats_block(fh, "ARG         vs ML emulator", W[:, r], A[:, r], "fn_wrf", "fn_ARG")
            fh.write("\n    full cleaned pool (no parcel-solve requirement):\n")
            stats_block(fh, "ARG vs ML emulator (all cells)", Wf[:, r], Af[:, r],
                        "fn_wrf", "fn_ARG")
            fh.write("\n")
    print(f"Wrote {rep}", flush=True)


if __name__ == "__main__":
    main()
