#!/usr/bin/env python
"""
plot_arg_density_map.py
=============================================================================
Sample-density companion to plot_arg_failure_map_bwr.py / plot_arg_relerr_map.py.

    colour         = empirical joint PDF of the pooled sample set
    contour lines  = the same failure rate, |fn_ARG - fn_parcel| > tau

Same cases, same cleaning, same bins, same panels and same contour levels as
the other two figures, so the three overlay one-for-one.  The point is to say
whether the structure in those figures sits on well-sampled ground or on a few
cells in a corner.

Because every bin is the same size in the plotted coordinate (log10 x for the
log axes, linear otherwise), the per-bin count is proportional to the joint
PDF in those coordinates; the colour bar is labelled as a density,
    pdf = count / (N_total * dx * dy),
so it integrates to one over each panel, and is drawn on a log scale because
the sampling spans several decades.

Bins holding at least one sample but fewer than MIN_CNT -- the ones the other
two figures grey out -- are outlined in green so it is obvious which structure
was suppressed for being under-sampled rather than absent.

Writes
    arg_density_map_filtered.{png,eps}
    arg_density_map_filtered_stats.txt

Usage
-----
  $HOME/.conda/envs/liranenv_gpu/bin/python plot_arg_density_map.py
=============================================================================
"""
import os
import argparse

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm

from plot_allcases_arg import CASES, MODES, load_case

HERE = os.path.dirname(os.path.abspath(__file__))

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

CMAP = plt.get_cmap("viridis").copy()      # sequential, single ramp: magnitude
CMAP.set_bad(alpha=0.0)


def smooth_nan(M):
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
    return np.ma.masked_invalid(np.where(np.isfinite(A), out, np.nan))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cases", nargs="*", default=None)
    ap.add_argument("--tau", type=float, default=0.1)
    ap.add_argument("--nbins", type=int, default=24)
    ap.add_argument("--min_cnt", type=int, default=20)
    ap.add_argument("--out_prefix", default=os.path.join(HERE, "arg_density"))
    args = ap.parse_args()

    cases = [c for c in CASES if args.cases is None or c[0] in args.cases]
    Xs, Ps, As = [], [], []
    for cdir, label in cases:
        print(f"loading {cdir} ...", flush=True)
        c = load_case(os.path.join(HERE, cdir))
        k = c["keep"]
        Xs.append(np.load(os.path.join(HERE, cdir, "online", "parcel_inputs.npz"))["X"][k])
        Ps.append(c["fn_parcel"][k]); As.append(c["fn_arg"][k])
    X = np.concatenate(Xs, 0); P = np.concatenate(Ps, 0); A = np.concatenate(As, 0)
    N = X.shape[0]
    F = (np.abs(A - P) > args.tau).astype(float)
    print(f"pooled: {N:,}", flush=True)

    fig, axes = plt.subplots(2, 4, figsize=(23, 11.5), constrained_layout=True)
    report = []
    li = 0
    for r, mode in enumerate(MODES):
        for c, (kx, ky) in enumerate(PAIRS):
            ax = axes[r, c]
            jx, lx, logx = AX[kx]
            jy, ly, logy = AX[ky]
            x, y = X[:, jx], X[:, jy]
            fin = np.isfinite(x) & np.isfinite(y)
            if logx:
                fin &= x > 0
            if logy:
                fin &= y > 0
            xx = np.log10(x[fin]) if logx else x[fin]
            yy = np.log10(y[fin]) if logy else y[fin]
            xe = np.linspace(np.percentile(xx, 0.5), np.percentile(xx, 99.5), args.nbins + 1)
            ye = np.linspace(np.percentile(yy, 0.5), np.percentile(yy, 99.5), args.nbins + 1)

            cnt, _, _ = np.histogram2d(xx, yy, bins=[xe, ye])
            dx = xe[1] - xe[0]
            dy = ye[1] - ye[0]
            pdf = cnt / (cnt.sum() * dx * dy)
            Mp = np.ma.masked_where(cnt < 1, pdf)

            ax.set_facecolor("0.86")
            pc = ax.pcolormesh(xe, ye, Mp.T, cmap=CMAP, shading="flat", rasterized=True,
                               norm=LogNorm(vmin=max(Mp.min(), 1e-6), vmax=Mp.max()))

            # bins the other two figures grey out: 1 <= count < min_cnt
            thin = (cnt >= 1) & (cnt < args.min_cnt)
            if thin.any():
                ax.contour(0.5 * (xe[:-1] + xe[1:]), 0.5 * (ye[:-1] + ye[1:]),
                           thin.T.astype(float), levels=[0.5], colors="#39ff14",
                           linewidths=1.2, zorder=5)

            # same failure-rate contours as the other two figures
            tot, _, _ = np.histogram2d(xx, yy, bins=[xe, ye], weights=F[fin, r])
            with np.errstate(invalid="ignore", divide="ignore"):
                rate = np.ma.masked_where(cnt < args.min_cnt, tot / cnt)
            S = smooth_nan(rate)
            lv = [l for l in LEVELS if np.nanmin(S) < l < np.nanmax(S)] if S.count() else []
            if lv:
                cs = ax.contour(0.5 * (xe[:-1] + xe[1:]), 0.5 * (ye[:-1] + ye[1:]), S.T,
                                levels=lv, colors="k",
                                linewidths=[1.0 + 0.5 * (l == 0.5) for l in lv], zorder=4)
                ax.clabel(cs, inline=True, inline_spacing=2, fontsize=9, fmt="%.2f")

            n_thin = int(cnt[thin].sum())
            n_shown = int(cnt[cnt >= args.min_cnt].sum())
            report.append((mode, f"{ky} vs {kx}", int(cnt.sum()), int((cnt >= args.min_cnt).sum()),
                           int(thin.sum()), n_shown, n_thin))

            ax.text(-0.16, 1.10, f"({LETTERS[li]})", transform=ax.transAxes,
                    fontsize=20, fontweight="bold", va="top", ha="left")
            li += 1
            ax.text(0.03, 0.97,
                    f"N={int(cnt.sum()):,}\n"
                    f"bins with data={int((cnt>=1).sum())}/{args.nbins**2}\n"
                    f"bins >= {args.min_cnt}={int((cnt>=args.min_cnt).sum())}\n"
                    f"samples in thin bins={n_thin:,} ({100*n_thin/max(cnt.sum(),1):.2f}%)",
                    transform=ax.transAxes, va="top", fontsize=11, zorder=6,
                    bbox=dict(fc="white", alpha=0.92, ec="0.7"))
            ax.set_xlabel(("log10 " if logx else "") + lx, fontsize=14)
            ax.set_ylabel(("log10 " if logy else "") + ly, fontsize=14)
            ax.tick_params(axis="both", labelsize=12)
            ax.set_title(f"{mode}: {ky} vs {kx}", fontsize=15)

        cb = fig.colorbar(pc, ax=list(axes[r, :]), fraction=0.022, pad=0.010, aspect=28)
        cb.ax.tick_params(labelsize=11)
        cb.set_label(f"{mode}: joint PDF of samples (per unit plotted area)",
                     fontsize=12, labelpad=8)

    fig.suptitle(
        "Sample density of the pooled evaluation set, on the bins of "
        "Figures arg_failure_map_filtered / arg_relerr_map_filtered\n"
        "colour = empirical joint PDF (log scale; integrates to 1 per panel)   |   "
        f"black contours = failure rate |fn_ARG - fn_parcel| > {args.tau:g} at "
        f"{', '.join(f'{l:g}' for l in LEVELS)}   |   green outline = bins with 1-"
        f"{args.min_cnt-1} samples, greyed out in the other two figures\n"
        f"all four cases pooled, cleaned sample set (N={N:,}); grey = no samples at all",
        fontsize=13.5)
    for ext in ("png", "eps"):
        p = f"{args.out_prefix}_map_filtered.{ext}"
        fig.savefig(p, dpi=300, bbox_inches="tight")
        print(f"Wrote {p}", flush=True)
    plt.close(fig)

    # ── how much of the sample actually sits in the high-updraft region? ──
    W, NACC = X[:, 3], X[:, 5]
    rep = args.out_prefix + "_map_filtered_stats.txt"
    with open(rep, "w") as fh:
        fh.write("=" * 96 + "\nSAMPLE DENSITY OF THE POOLED EVALUATION SET\n" + "=" * 96 + "\n\n")
        fh.write(f"{'mode':<8} {'panel':<20} {'N':>8} {'bins>=min':>10} {'thin bins':>10} "
                 f"{'N shown':>9} {'N thin':>8}\n")
        for row in report:
            fh.write(f"{row[0]:<8} {row[1]:<20} {row[2]:>8,} {row[3]:>10} {row[4]:>10} "
                     f"{row[5]:>9,} {row[6]:>8,}\n")

        fh.write("\n" + "=" * 96 + "\n")
        fh.write("Population of the regions the other two figures highlight (Accum mode)\n")
        fh.write("=" * 96 + "\n")
        for name, s in (("w > 30 cm/s (high-updraft blue)", W > 30),
                        ("w > 50 cm/s", W > 50),
                        ("w > 100 cm/s", W > 100),
                        ("w > 30 & Na_acc < 100  (deep blue corner)", (W > 30) & (NACC < 100)),
                        ("w < 10 & Na_acc > 500  (red corner)", (W < 10) & (NACC > 500)),
                        ("Phinney regime: w<50 & Na_acc>500", (W < 50) & (NACC > 500))):
            fh.write(f"  {name:<44} n={int(s.sum()):>7,}  ({100*s.mean():>5.2f}% of pool)\n")

        fh.write("\n" + "=" * 96 + "\n")
        fh.write("Marginal sample count by updraft decile (deciles are equal-count by "
                 "construction;\nthe 2-D panels are what reveal the joint sparsity)\n")
        fh.write("=" * 96 + "\n")
        ed = np.percentile(W, np.linspace(0, 100, 11))
        for b in range(10):
            s = (W >= ed[b]) & (W <= ed[b + 1] if b == 9 else W < ed[b + 1])
            fh.write(f"  [{ed[b]:>10.4g},{ed[b+1]:>10.4g})  n={int(s.sum()):>7,}  "
                     f"median Na_acc={np.median(NACC[s]):>8.1f} cm-3\n")
    print(f"Wrote {rep}", flush=True)


if __name__ == "__main__":
    main()
