#!/usr/bin/env python
"""
plot_arg_failure_map.py
=============================================================================
Input-space map of where the ARG scheme fails against the Fortran parcel model.

    failure  :=  |fn_ARG - fn_parcel| > 0.1        (absolute activation fraction)

Samples are exactly the pooled, cleaned set used by plot_allcases_arg.py:
all four cases, good parcel solve, lost-output cells removed, and fn_ARG inside
[0,1] for both modes (rows outside that are uninitialised WRF state -- see the
comment in plot_allcases_arg.load_case).

Each panel bins the samples on two emulator inputs and colours the bin by the
failure rate.  "filtered" = bins holding fewer than MIN_CNT samples are left
blank rather than drawn from noise.

Writes (png + eps each):
    arg_failure_map_filtered.{png,eps}   colour = failure rate
    arg_failure_mae_filtered.{png,eps}   colour = mean |fn_ARG - fn_parcel|
    arg_failure_map_filtered_stats.txt

Usage
-----
  $HOME/.conda/envs/liranenv_gpu/bin/python plot_arg_failure_map.py
  ... --tau 0.2 --nbins 20 --min_cnt 50
=============================================================================
"""
import os
import argparse

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from plot_allcases_arg import CASES, MODES, load_case

HERE = os.path.dirname(os.path.abspath(__file__))

# (X column, label, log axis?)  -- only inputs that actually vary in this pool;
# rh, hg_*, and the coarse modes are constant or zero and make useless axes.
AX = {
    "wbar":   (3,  "wbar (cm/s)",       True),
    "na_acc": (5,  "na_accum (cm-3)",   True),
    "na_ait": (4,  "na_Aitken (cm-3)",  True),
    "pres":   (1,  "pressure (hPa)",    False),
    "tair":   (0,  "T (K)",             False),
}
# r_accum is deliberately NOT an axis: it sits at 0.02 um for 9 of 10 deciles in
# this pool, so its panels were >80% empty and its failure rate was flat (0.48).
PAIRS = [("wbar", "na_acc"), ("wbar", "na_ait"), ("na_acc", "na_ait"), ("wbar", "pres")]
LETTERS = "abcdefgh"


def binned(x, y, v, xe, ye, min_cnt):
    """Mean of v per 2D bin, masked where the bin holds < min_cnt samples."""
    cnt, _, _ = np.histogram2d(x, y, bins=[xe, ye])
    tot, _, _ = np.histogram2d(x, y, bins=[xe, ye], weights=v)
    with np.errstate(invalid="ignore", divide="ignore"):
        m = tot / cnt
    return np.ma.masked_where(cnt < min_cnt, m), cnt


def make_fig(X, D, tau, stat, nbins, min_cnt, out_prefix, title_extra):
    """stat='rate' -> fraction failing; stat='mae' -> mean |fn_ARG - fn_parcel|."""
    fig, axes = plt.subplots(2, 4, figsize=(22, 11))
    li = 0
    for r, mode in enumerate(MODES):
        d = D[:, r]
        v = (d > tau).astype(float) if stat == "rate" else d
        vmax = 1.0 if stat == "rate" else float(np.percentile(d, 99))
        for c, (kx, ky) in enumerate(PAIRS):
            ax = axes[r, c]
            jx, lx, logx = AX[kx]
            jy, ly, logy = AX[ky]
            x, y = X[:, jx], X[:, jy]
            ok = np.isfinite(x) & np.isfinite(y)
            if logx:
                ok &= x > 0
            if logy:
                ok &= y > 0
            xx = np.log10(x[ok]) if logx else x[ok]
            yy = np.log10(y[ok]) if logy else y[ok]
            xe = np.linspace(np.percentile(xx, 0.5), np.percentile(xx, 99.5), nbins + 1)
            ye = np.linspace(np.percentile(yy, 0.5), np.percentile(yy, 99.5), nbins + 1)
            M, cnt = binned(xx, yy, v[ok], xe, ye, min_cnt)

            pc = ax.pcolormesh(xe, ye, M.T, cmap="RdYlBu_r", vmin=0, vmax=vmax,
                               shading="flat", rasterized=True)
            cb = fig.colorbar(pc, ax=ax, fraction=0.046, pad=0.03)
            cb.ax.tick_params(labelsize=11)
            cb.set_label("failure rate" if stat == "rate" else "mean |fn_ARG - fn_parcel|",
                         fontsize=12)

            ax.text(-0.19, 1.10, f"({LETTERS[li]})", transform=ax.transAxes,
                    fontsize=20, fontweight="bold", va="top", ha="left")
            li += 1
            overall = float(np.mean(v[ok])) if ok.any() else np.nan
            ax.text(0.03, 0.97,
                    f"N={int(ok.sum()):,}\nbins shown={int((~M.mask).sum())}/{nbins*nbins}\n"
                    + (f"overall rate={overall:.3f}" if stat == "rate"
                       else f"overall MAE={overall:.3f}"),
                    transform=ax.transAxes, va="top", fontsize=11,
                    bbox=dict(fc="white", alpha=0.85))
            ax.set_xlabel(("log10 " if logx else "") + lx, fontsize=14)
            ax.set_ylabel(("log10 " if logy else "") + ly, fontsize=14)
            ax.tick_params(axis="both", labelsize=12)
            ax.set_title(f"{mode}: {ky} vs {kx}", fontsize=15)

    head = ("ARG failure rate" if stat == "rate" else
            "ARG mean absolute error") + " against the Fortran parcel model"
    defn = (f"failure = |fn_ARG - fn_parcel| > {tau:g}" if stat == "rate"
            else "colour = mean |fn_ARG - fn_parcel|, no threshold applied")
    fig.suptitle(f"{head}   --   {defn}, "
                 f"all four cases pooled, cleaned sample set (N={X.shape[0]:,})\n"
                 f"bins with < {min_cnt} samples left blank ('filtered'){title_extra}",
                 fontsize=15)
    fig.tight_layout(rect=[0, 0, 1, 0.93])
    for ext in ("png", "eps"):
        p = f"{out_prefix}.{ext}"
        fig.savefig(p, dpi=300, bbox_inches="tight")
        print(f"Wrote {p}", flush=True)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cases", nargs="*", default=None)
    ap.add_argument("--tau", type=float, default=0.1, help="failure threshold")
    ap.add_argument("--nbins", type=int, default=24)
    ap.add_argument("--min_cnt", type=int, default=20,
                    help="bins with fewer samples than this are left blank")
    ap.add_argument("--out_prefix", default=os.path.join(HERE, "arg_failure"))
    args = ap.parse_args()

    cases = [c for c in CASES if args.cases is None or c[0] in args.cases]

    Xs, Ds, per_case = [], [], []
    for cdir, label in cases:
        print(f"loading {cdir} ...", flush=True)
        c = load_case(os.path.join(HERE, cdir))
        k = c["keep"]
        X = np.load(os.path.join(HERE, cdir, "online", "parcel_inputs.npz"))["X"][k]
        d = np.abs(c["fn_arg"][k] - c["fn_parcel"][k])
        Xs.append(X); Ds.append(d)
        per_case.append((label, int(k.sum()),
                         float(np.nanmean(d[:, 0] > args.tau)),
                         float(np.nanmean(d[:, 1] > args.tau))))
        print(f"    kept={k.sum():,}", flush=True)
    X = np.concatenate(Xs, 0); D = np.concatenate(Ds, 0)
    print(f"pooled: {X.shape[0]:,}", flush=True)

    extra = ("\nCAVEAT: fn_ARG (FN13/FN23) is a persistent WRF array; on cells last served "
             "by the GROW_SHRINK call site it is stale, so part of this error is "
             "time-mismatch, not scheme error.")
    make_fig(X, D, args.tau, "rate", args.nbins, args.min_cnt,
             args.out_prefix + "_map_filtered", extra)
    make_fig(X, D, args.tau, "mae", args.nbins, args.min_cnt,
             args.out_prefix + "_mae_filtered", extra)

    rep = args.out_prefix + "_map_filtered_stats.txt"
    with open(rep, "w") as fh:
        fh.write("=" * 90 + "\nARG FAILURE vs THE FORTRAN PARCEL MODEL\n" + "=" * 90 + "\n\n")
        fh.write(f"failure := |fn_ARG - fn_parcel| > {args.tau:g}\n")
        fh.write(f"bins    : {args.nbins} x {args.nbins}, blank below {args.min_cnt} samples\n\n")
        fh.write(f"{'case':<14} {'kept':>9} {'Aitken fail':>13} {'Accum fail':>12}\n")
        for label, n, fa, fc in per_case:
            fh.write(f"{label:<14} {n:>9,} {fa:>13.4f} {fc:>12.4f}\n")
        fh.write(f"{'POOLED':<14} {X.shape[0]:>9,} "
                 f"{np.mean(D[:,0] > args.tau):>13.4f} {np.mean(D[:,1] > args.tau):>12.4f}\n\n")
        for r, mode in enumerate(MODES):
            d = D[:, r]
            fh.write(f"{mode}: mean|d|={d.mean():.4f}  median|d|={np.median(d):.4f}  "
                     f"p90={np.percentile(d,90):.4f}  p99={np.percentile(d,99):.4f}  "
                     f"n_fail={int((d>args.tau).sum()):,}\n")
        fh.write("\nfailure rate by input decile (pooled, Accum):\n")
        for key, (j, lab, _) in AX.items():
            v = X[:, j]
            ed = np.percentile(v, np.linspace(0, 100, 11))
            fh.write(f"  {lab}\n")
            for b in range(10):
                s = (v >= ed[b]) & (v <= ed[b + 1] if b == 9 else v < ed[b + 1])
                if s.sum():
                    fh.write(f"    [{ed[b]:>10.4g},{ed[b+1]:>10.4g})  n={int(s.sum()):>7,}  "
                             f"fail={np.mean(D[s,1] > args.tau):.4f}  "
                             f"mean|d|={D[s,1].mean():.4f}\n")
    print(f"Wrote {rep}", flush=True)


if __name__ == "__main__":
    main()
