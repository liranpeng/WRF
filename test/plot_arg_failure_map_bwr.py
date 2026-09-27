#!/usr/bin/env python
"""
plot_arg_failure_map_bwr.py
=============================================================================
Re-styled version of plot_arg_failure_map.py.

    colour         = the MEAN DIFFERENCE in each input-space bin
    contour lines  = the FAILURE RATE in the same bins

where

    difference := fn_ARG - fn_parcel          (signed, "map" figure)
    failure    := |fn_ARG - fn_parcel| > tau  (tau = 0.1 by default)

Two figures, same axes and same bins as before:

    arg_failure_map_filtered.{png,eps}
        colour = mean signed difference on a blue-white-red diverging scale,
        symmetric about 0.  BLUE = ARG activates LESS than the parcel model,
        RED = ARG activates MORE.  White = unbiased bin.
    arg_failure_mae_filtered.{png,eps}
        colour = mean |fn_ARG - fn_parcel| on the white->red half of the same
        palette (an absolute error has no sign, so only half the ramp is used).

Both carry black failure-rate contours at 0.10 0.25 0.50 0.75 0.90 with inline
labels.  The contour field is lightly smoothed (nan-aware 3x3 box) so the lines
are readable; the colours are the raw bin means.

Samples are exactly the pooled, cleaned set used by plot_allcases_arg.py:
all four cases, good parcel solve, lost-output cells removed, and fn_ARG inside
[0,1] for both modes.  "filtered" = bins holding fewer than MIN_CNT samples are
left blank rather than drawn from noise.

Usage
-----
  $HOME/.conda/envs/liranenv_gpu/bin/python plot_arg_failure_map_bwr.py
  ... --tau 0.2 --nbins 20 --min_cnt 50
=============================================================================
"""
import os
import argparse

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

from plot_allcases_arg import CASES, MODES, load_case

HERE = os.path.dirname(os.path.abspath(__file__))

# (X column, label, log axis?) -- only inputs that actually vary in this pool.
AX = {
    "wbar":   (3,  "wbar (cm/s)",       True),
    "na_acc": (5,  "na_accum (cm-3)",   True),
    "na_ait": (4,  "na_Aitken (cm-3)",  True),
    "pres":   (1,  "pressure (hPa)",    False),
    "tair":   (0,  "T (K)",             False),
}
PAIRS = [("wbar", "na_acc"), ("wbar", "na_ait"), ("na_acc", "na_ait"), ("wbar", "pres")]
LETTERS = "abcdefgh"

LEVELS = [0.10, 0.25, 0.50, 0.75, 0.90]

# blue -> white -> red, and its upper (white -> red) half for the unsigned figure
CMAP_DIV = plt.get_cmap("RdBu_r").copy()
CMAP_ABS = LinearSegmentedColormap.from_list(
    "RdBu_r_upper", plt.get_cmap("RdBu_r")(np.linspace(0.5, 1.0, 256)))
for _c in (CMAP_DIV, CMAP_ABS):
    _c.set_bad(alpha=0.0)          # empty / under-populated bins stay blank


def bin_means(x, y, vals, xe, ye, min_cnt):
    """Per-bin mean of every array in `vals`, masked below min_cnt samples."""
    cnt, _, _ = np.histogram2d(x, y, bins=[xe, ye])
    out = []
    for v in vals:
        tot, _, _ = np.histogram2d(x, y, bins=[xe, ye], weights=v)
        with np.errstate(invalid="ignore", divide="ignore"):
            m = tot / cnt
        out.append(np.ma.masked_where(cnt < min_cnt, m))
    return out, cnt


def smooth_nan(M):
    """3x3 box mean that ignores masked cells, for legible contour lines."""
    A = np.where(M.mask, np.nan, M.filled(np.nan)) if np.ma.isMaskedArray(M) else np.asarray(M)
    acc = np.zeros_like(A, float)
    num = np.zeros_like(A, float)
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            S = np.roll(np.roll(A, dx, 0), dy, 1)
            if dx == 1:
                S[0, :] = np.nan
            elif dx == -1:
                S[-1, :] = np.nan
            if dy == 1:
                S[:, 0] = np.nan
            elif dy == -1:
                S[:, -1] = np.nan
            ok = np.isfinite(S)
            acc[ok] += S[ok]
            num[ok] += 1.0
    with np.errstate(invalid="ignore", divide="ignore"):
        out = acc / num
    # never invent a contour where there is no data at all
    return np.ma.masked_invalid(np.where(np.isfinite(A), out, np.nan))


def prepare(X, S, A, F, nbins, min_cnt):
    """Bin every panel once; returns per (mode, pair) dict of edges + fields."""
    panels = {}
    for r in range(len(MODES)):
        for c, (kx, ky) in enumerate(PAIRS):
            jx, _, logx = AX[kx]
            jy, _, logy = AX[ky]
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
            (Ms, Ma, Mf), _ = bin_means(xx, yy, [S[ok, r], A[ok, r], F[ok, r]],
                                        xe, ye, min_cnt)
            panels[(r, c)] = dict(xe=xe, ye=ye, signed=Ms, absol=Ma, rate=Mf,
                                  n=int(ok.sum()),
                                  overall_bias=float(S[ok, r].mean()),
                                  overall_mae=float(A[ok, r].mean()),
                                  overall_rate=float(F[ok, r].mean()))
    return panels


def draw(panels, stat, tau, nbins, min_cnt, npool, out_prefix, title_extra):
    """stat='signed' -> diverging bias figure; 'absol' -> mean |d| figure."""
    fig, axes = plt.subplots(2, 4, figsize=(23, 11.5), constrained_layout=True)
    li = 0
    for r, mode in enumerate(MODES):
        # one colour scale per row so the four panels of a mode are comparable
        row = [panels[(r, c)][stat] for c in range(len(PAIRS))]
        if stat == "signed":
            v = max([float(np.nanpercentile(np.abs(m.compressed()), 99))
                     for m in row if m.count()] or [0.1])
            v = max(round(v + 0.049, 1), 0.1)
            kw = dict(cmap=CMAP_DIV, vmin=-v, vmax=v)
            cb_lab = f"{mode}: mean (fn_ARG - fn_parcel)"
        else:
            v = max([float(np.nanpercentile(m.compressed(), 99))
                     for m in row if m.count()] or [0.1])
            v = max(round(v + 0.049, 1), 0.1)
            kw = dict(cmap=CMAP_ABS, vmin=0.0, vmax=v)
            cb_lab = f"{mode}: mean |fn_ARG - fn_parcel|"

        for c, (kx, ky) in enumerate(PAIRS):
            P = panels[(r, c)]
            ax = axes[r, c]
            _, lx, logx = AX[kx]
            _, ly, logy = AX[ky]
            xe, ye = P["xe"], P["ye"]

            # grey canvas so an EMPTY bin never reads as a white (= zero) bin
            ax.set_facecolor("0.86")
            pc = ax.pcolormesh(xe, ye, P[stat].T, shading="flat",
                               rasterized=True, **kw)

            # failure-rate contours on bin centres
            xc = 0.5 * (xe[:-1] + xe[1:])
            yc = 0.5 * (ye[:-1] + ye[1:])
            R = smooth_nan(P["rate"])
            lv = [l for l in LEVELS if np.nanmin(R) < l < np.nanmax(R)] if R.count() else []
            if lv:
                cs = ax.contour(xc, yc, R.T, levels=lv, colors="k",
                                linewidths=[1.0 + 0.5 * (l == 0.5) for l in lv],
                                linestyles="-", zorder=4)
                ax.clabel(cs, inline=True, inline_spacing=2, fontsize=9, fmt="%.2f")

            ax.text(-0.16, 1.10, f"({LETTERS[li]})", transform=ax.transAxes,
                    fontsize=20, fontweight="bold", va="top", ha="left")
            li += 1
            ax.text(0.03, 0.97,
                    f"N={P['n']:,}\nbins shown={int(P[stat].count())}/{nbins*nbins}\n"
                    + (f"overall bias={P['overall_bias']:+.3f}" if stat == "signed"
                       else f"overall MAE={P['overall_mae']:.3f}")
                    + f"\noverall fail rate={P['overall_rate']:.3f}",
                    transform=ax.transAxes, va="top", fontsize=11, zorder=6,
                    bbox=dict(fc="white", alpha=0.92, ec="0.7"))
            ax.set_xlabel(("log10 " if logx else "") + lx, fontsize=14)
            ax.set_ylabel(("log10 " if logy else "") + ly, fontsize=14)
            ax.tick_params(axis="both", labelsize=12)
            ax.set_title(f"{mode}: {ky} vs {kx}", fontsize=15)

        cb = fig.colorbar(pc, ax=list(axes[r, :]), fraction=0.022, pad=0.010,
                          aspect=28)
        cb.ax.tick_params(labelsize=11)
        cb.set_label(cb_lab, fontsize=12, labelpad=8)

    head = ("ARG mean signed difference" if stat == "signed"
            else "ARG mean absolute difference") + " against the Fortran parcel model"
    sign_note = ("   (blue = ARG activates LESS than the parcel model, red = MORE)"
                 if stat == "signed" else "")
    fig.suptitle(
        f"{head}\n"
        f"colour = mean {'(fn_ARG - fn_parcel)' if stat == 'signed' else '|fn_ARG - fn_parcel|'}"
        f"{sign_note}   |   black contours = failure rate |fn_ARG - fn_parcel| > {tau:g} "
        f"at {', '.join(f'{l:g}' for l in LEVELS)} (3x3-smoothed for legibility)\n"
        f"all four cases pooled, cleaned sample set (N={npool:,}); "
        f"grey = bins with < {min_cnt} samples, left blank ('filtered'){title_extra}",
        fontsize=13.5)
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
    ap.add_argument("--callsite", choices=["all", "old_cloud", "grow_shrink"],
                    default="all",
                    help="restrict to rows produced by one activate_ml call site. "
                         "old_cloud = the site that actually wrote FN13/FN23, so the "
                         "stored ARG is synchronous there; grow_shrink = the site that "
                         "did not, so the stored ARG is stale. Requires 'callsite' in "
                         "the npz (see arg_offline/add_callsite.py).")
    args = ap.parse_args()

    cases = [c for c in CASES if args.cases is None or c[0] in args.cases]
    want = {"old_cloud": 2, "grow_shrink": 1}.get(args.callsite)

    Xs, Ss, per_case = [], [], []
    for cdir, label in cases:
        print(f"loading {cdir} ...", flush=True)
        c = load_case(os.path.join(HERE, cdir))
        k = c["keep"]
        z = np.load(os.path.join(HERE, cdir, "online", "parcel_inputs.npz"))
        X = z["X"][k]
        s = c["fn_arg"][k] - c["fn_parcel"][k]           # SIGNED difference
        if want is not None:
            if "callsite" not in z.files:
                raise KeyError(f"{cdir}: no 'callsite' in parcel_inputs.npz -- "
                               "run arg_offline/add_callsite.py first")
            sel = z["callsite"][k] == want
            X, s = X[sel], s[sel]
            print(f"    callsite={args.callsite}: kept {int(sel.sum()):,}"
                  f" / {int(sel.size):,}", flush=True)
        Xs.append(X); Ss.append(s)
        per_case.append((label, int(X.shape[0]),
                         float(np.nanmean(np.abs(s[:, 0]) > args.tau)),
                         float(np.nanmean(np.abs(s[:, 1]) > args.tau)),
                         float(np.nanmean(s[:, 0])), float(np.nanmean(s[:, 1]))))
        print(f"    kept={X.shape[0]:,}", flush=True)
    X = np.concatenate(Xs, 0)
    S = np.concatenate(Ss, 0)
    A = np.abs(S)
    F = (A > args.tau).astype(float)
    print(f"pooled: {X.shape[0]:,}", flush=True)

    panels = prepare(X, S, A, F, args.nbins, args.min_cnt)

    extra = ("\nCAVEAT: fn_ARG (FN13/FN23) is a persistent WRF array; on cells last served "
             "by the GROW_SHRINK call site it is stale, so part of this error is "
             "time-mismatch, not scheme error.")
    draw(panels, "signed", args.tau, args.nbins, args.min_cnt, X.shape[0],
         args.out_prefix + "_map_filtered", extra)
    draw(panels, "absol", args.tau, args.nbins, args.min_cnt, X.shape[0],
         args.out_prefix + "_mae_filtered", extra)

    rep = args.out_prefix + "_map_filtered_stats.txt"
    with open(rep, "w") as fh:
        fh.write("=" * 96 + "\nARG vs THE FORTRAN PARCEL MODEL"
                 "  (colour = mean difference, contours = failure rate)\n" + "=" * 96 + "\n\n")
        fh.write(f"difference := fn_ARG - fn_parcel   (signed)\n")
        fh.write(f"failure    := |fn_ARG - fn_parcel| > {args.tau:g}\n")
        fh.write(f"bins       : {args.nbins} x {args.nbins}, blank below {args.min_cnt} samples\n")
        fh.write(f"contours   : {', '.join(f'{l:g}' for l in LEVELS)}\n\n")
        fh.write(f"{'case':<14} {'kept':>9} {'Ait fail':>10} {'Acc fail':>10} "
                 f"{'Ait bias':>10} {'Acc bias':>10}\n")
        for label, n, fa, fc, ba, bc in per_case:
            fh.write(f"{label:<14} {n:>9,} {fa:>10.4f} {fc:>10.4f} {ba:>+10.4f} {bc:>+10.4f}\n")
        fh.write(f"{'POOLED':<14} {X.shape[0]:>9,} {F[:,0].mean():>10.4f} {F[:,1].mean():>10.4f} "
                 f"{S[:,0].mean():>+10.4f} {S[:,1].mean():>+10.4f}\n\n")
        for r, mode in enumerate(MODES):
            s, a = S[:, r], A[:, r]
            fh.write(f"{mode}: bias={s.mean():+.4f}  frac(ARG>parcel)={np.mean(s>0):.4f}  "
                     f"mean|d|={a.mean():.4f}  median|d|={np.median(a):.4f}  "
                     f"p90={np.percentile(a,90):.4f}  p99={np.percentile(a,99):.4f}  "
                     f"n_fail={int((a>args.tau).sum()):,}\n")
        fh.write("\nby input decile (pooled, Accum):  bias = mean(fn_ARG - fn_parcel)\n")
        for key, (j, lab, _) in AX.items():
            v = X[:, j]
            ed = np.percentile(v, np.linspace(0, 100, 11))
            fh.write(f"  {lab}\n")
            for b in range(10):
                sel = (v >= ed[b]) & (v <= ed[b + 1] if b == 9 else v < ed[b + 1])
                if sel.sum():
                    fh.write(f"    [{ed[b]:>10.4g},{ed[b+1]:>10.4g})  n={int(sel.sum()):>7,}  "
                             f"fail={F[sel,1].mean():.4f}  "
                             f"bias={S[sel,1].mean():+.4f}  mean|d|={A[sel,1].mean():.4f}\n")
    print(f"Wrote {rep}", flush=True)


if __name__ == "__main__":
    main()
