#!/usr/bin/env python
"""
plot_arg_relerr_map.py
=============================================================================
Companion to plot_arg_failure_map_bwr.py, in the metric the activation
literature uses.

    colour         = MEDIAN RELATIVE error in the activated fraction
                     (and hence in activated number, since N_a cancels)

                         delta_rel = (fn_ARG - fn_parcel) / fn_parcel

    contour lines  = the same FAILURE RATE as the companion figure,
                     |fn_ARG - fn_parcel| > tau,  tau = 0.1

Why a separate figure.  The companion figure colours the ABSOLUTE difference
fn_ARG - fn_parcel, whose magnitude is capped by fn_parcel itself: where the
parcel model activates almost nothing, even a total misprediction is a small
absolute number.  Phinney et al. (2003), Ghan et al. (2011) and Rothenberg &
Wang (2016) all report RELATIVE error in Smax / Nd, so the absolute map cannot
be compared with them directly.  This figure closes that gap.

Conventions
-----------
* delta_rel is undefined where the parcel model does not activate, so bins are
  built only from samples with fn_parcel > FN_MIN (default 0.01).  Panels
  report how many samples survive that cut -- for the Aitken mode it is a small
  minority, which is itself the explanation for that row's low absolute
  failure rate.
* The per-bin statistic is the MEDIAN, not the mean: delta_rel is bounded below
  by -1 but unbounded above, so its mean is dragged upward by a thin tail of
  large over-activations and is not a good measure of the typical cell.  The
  stats file reports both.
* Colour scale is fixed at +/-1 (blue = ARG activates less; -1 = ARG activates
  nothing the parcel model activates; red = ARG activates more) so the two
  modes and all four panel pairs are directly comparable.  Bins above +1 are
  shown at the top colour and the bar is drawn with an arrow.

Writes
    arg_relerr_map_filtered.{png,eps}
    arg_relerr_map_filtered_stats.txt

Usage
-----
  $HOME/.conda/envs/liranenv_gpu/bin/python plot_arg_relerr_map.py
  ... --tau 0.1 --nbins 24 --min_cnt 20 --fn_min 0.01
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

CMAP = plt.get_cmap("RdBu_r").copy()
CMAP.set_bad(alpha=0.0)


def binned_median(x, y, v, xe, ye, min_cnt):
    """Per-bin median of v, masked where the bin holds < min_cnt samples.

    Done by hand rather than with scipy so the script has no extra dependency:
    digitize into a flat bin id, sort by it, and take the median of each run."""
    nx, ny = len(xe) - 1, len(ye) - 1
    ix = np.clip(np.digitize(x, xe) - 1, 0, nx - 1)
    iy = np.clip(np.digitize(y, ye) - 1, 0, ny - 1)
    inside = (x >= xe[0]) & (x <= xe[-1]) & (y >= ye[0]) & (y <= ye[-1])
    ix, iy, v = ix[inside], iy[inside], v[inside]

    flat = ix * ny + iy
    order = np.argsort(flat, kind="stable")
    flat, vs = flat[order], v[order]
    starts = np.searchsorted(flat, np.arange(nx * ny), side="left")
    ends = np.searchsorted(flat, np.arange(nx * ny), side="right")

    M = np.full(nx * ny, np.nan)
    cnt = (ends - starts).astype(float)
    for b in np.where(cnt >= min_cnt)[0]:
        M[b] = np.median(vs[starts[b]:ends[b]])
    return (np.ma.masked_invalid(M.reshape(nx, ny)), cnt.reshape(nx, ny))


def binned_mean(x, y, v, xe, ye, min_cnt):
    cnt, _, _ = np.histogram2d(x, y, bins=[xe, ye])
    tot, _, _ = np.histogram2d(x, y, bins=[xe, ye], weights=v)
    with np.errstate(invalid="ignore", divide="ignore"):
        m = tot / cnt
    return np.ma.masked_where(cnt < min_cnt, m)


def smooth_nan(M):
    """3x3 box mean ignoring masked cells, for legible contour lines."""
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


def draw(X, R, F, USE, tau, nbins, min_cnt, fn_min, npool, out_prefix, title_extra):
    fig, axes = plt.subplots(2, 4, figsize=(23, 11.5), constrained_layout=True)
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

            # bin edges from ALL samples so the axes match the companion figure
            xe = np.linspace(np.percentile(xx, 0.5), np.percentile(xx, 99.5), nbins + 1)
            ye = np.linspace(np.percentile(yy, 0.5), np.percentile(yy, 99.5), nbins + 1)

            # colour: median relative error, only over samples where it is defined
            u = USE[fin, r]
            M, _ = binned_median(xx[u], yy[u], R[fin, r][u], xe, ye, min_cnt)
            # contours: failure rate over ALL samples, as in the companion figure
            Rate = binned_mean(xx, yy, F[fin, r], xe, ye, min_cnt)

            ax.set_facecolor("0.86")
            pc = ax.pcolormesh(xe, ye, M.T, cmap=CMAP, vmin=-1.0, vmax=1.0,
                               shading="flat", rasterized=True)

            xc = 0.5 * (xe[:-1] + xe[1:])
            yc = 0.5 * (ye[:-1] + ye[1:])
            S = smooth_nan(Rate)
            lv = [l for l in LEVELS if np.nanmin(S) < l < np.nanmax(S)] if S.count() else []
            if lv:
                cs = ax.contour(xc, yc, S.T, levels=lv, colors="k",
                                linewidths=[1.0 + 0.5 * (l == 0.5) for l in lv],
                                linestyles="-", zorder=4)
                ax.clabel(cs, inline=True, inline_spacing=2, fontsize=9, fmt="%.2f")

            ax.text(-0.16, 1.10, f"({LETTERS[li]})", transform=ax.transAxes,
                    fontsize=20, fontweight="bold", va="top", ha="left")
            li += 1
            med = float(np.median(R[fin, r][u])) if u.any() else np.nan
            # Accum row fills the upper left, so drop the box to the bottom left there
            ty, tva = (0.03, "bottom") if mode == "Accum" else (0.97, "top")
            ax.text(0.03, ty,
                    f"N usable={int(u.sum()):,} / {int(fin.sum()):,}\n"
                    f"bins shown={int(M.count())}/{nbins*nbins}\n"
                    f"median rel err={med:+.3f}\n"
                    f"frac ARG<parcel={np.mean(R[fin, r][u] < 0) if u.any() else np.nan:.3f}",
                    transform=ax.transAxes, va=tva, fontsize=11, zorder=6,
                    bbox=dict(fc="white", alpha=0.92, ec="0.7"))
            ax.set_xlabel(("log10 " if logx else "") + lx, fontsize=14)
            ax.set_ylabel(("log10 " if logy else "") + ly, fontsize=14)
            ax.tick_params(axis="both", labelsize=12)
            ax.set_title(f"{mode}: {ky} vs {kx}", fontsize=15)

        cb = fig.colorbar(pc, ax=list(axes[r, :]), fraction=0.022, pad=0.010,
                          aspect=28, extend="max")
        cb.ax.tick_params(labelsize=11)
        cb.set_label(f"{mode}: median (fn_ARG - fn_parcel)/fn_parcel", fontsize=12, labelpad=8)

    fig.suptitle(
        "ARG median RELATIVE error against the Fortran parcel model\n"
        "colour = median (fn_ARG - fn_parcel)/fn_parcel   (blue = ARG activates LESS, "
        "-1 = ARG activates nothing; red = MORE)   |   black contours = failure rate "
        f"|fn_ARG - fn_parcel| > {tau:g} at {', '.join(f'{l:g}' for l in LEVELS)}\n"
        f"all four cases pooled, cleaned sample set (N={npool:,}); relative error taken "
        f"only where fn_parcel > {fn_min:g}; grey = fewer than {min_cnt} such samples in "
        f"the bin{title_extra}", fontsize=13.5)
    for ext in ("png", "eps"):
        p = f"{out_prefix}.{ext}"
        fig.savefig(p, dpi=300, bbox_inches="tight")
        print(f"Wrote {p}", flush=True)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cases", nargs="*", default=None)
    ap.add_argument("--tau", type=float, default=0.1, help="failure threshold (contours)")
    ap.add_argument("--nbins", type=int, default=24)
    ap.add_argument("--min_cnt", type=int, default=20)
    ap.add_argument("--fn_min", type=float, default=0.01,
                    help="relative error is only defined where fn_parcel exceeds this")
    ap.add_argument("--out_prefix", default=os.path.join(HERE, "arg_relerr"))
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

    Xs, Ps, As, per_case = [], [], [], []
    for cdir, label in cases:
        print(f"loading {cdir} ...", flush=True)
        c = load_case(os.path.join(HERE, cdir))
        k = c["keep"]
        z = np.load(os.path.join(HERE, cdir, "online", "parcel_inputs.npz"))
        X = z["X"][k]
        P = c["fn_parcel"][k]; A = c["fn_arg"][k]
        if want is not None:
            if "callsite" not in z.files:
                raise KeyError(f"{cdir}: no 'callsite' in parcel_inputs.npz -- "
                               "run arg_offline/add_callsite.py first")
            sel = z["callsite"][k] == want
            X, P, A = X[sel], P[sel], A[sel]
            print(f"    callsite={args.callsite}: kept {int(sel.sum()):,}"
                  f" / {int(sel.size):,}", flush=True)
        Xs.append(X); Ps.append(P); As.append(A)
        per_case.append((label, int(X.shape[0])))
        print(f"    kept={X.shape[0]:,}", flush=True)
    X = np.concatenate(Xs, 0); P = np.concatenate(Ps, 0); A = np.concatenate(As, 0)
    print(f"pooled: {X.shape[0]:,}", flush=True)

    USE = P > args.fn_min                       # relative error defined here
    with np.errstate(invalid="ignore", divide="ignore"):
        R = np.where(USE, (A - P) / np.where(P > 0, P, np.nan), np.nan)
    F = (np.abs(A - P) > args.tau).astype(float)

    extra = ("\nCAVEAT: fn_ARG (FN13/FN23) is a persistent WRF array; on cells last served "
             "by the GROW_SHRINK call site it is stale, so part of this error is "
             "time-mismatch, not scheme error.")
    draw(X, R, F, USE, args.tau, args.nbins, args.min_cnt, args.fn_min,
         X.shape[0], args.out_prefix + "_map_filtered", extra)

    # ── stats, including the regimes the activation literature quotes ──
    W_cms, NAIT, NACC = X[:, 3], X[:, 4], X[:, 5]
    W_ms = W_cms / 100.0
    rep = args.out_prefix + "_map_filtered_stats.txt"
    with open(rep, "w") as fh:
        fh.write("=" * 104 + "\nARG RELATIVE ERROR vs THE FORTRAN PARCEL MODEL\n" + "=" * 104 + "\n\n")
        fh.write("relative error := (fn_ARG - fn_parcel) / fn_parcel, "
                 f"taken only where fn_parcel > {args.fn_min:g}\n")
        fh.write(f"failure (contours) := |fn_ARG - fn_parcel| > {args.tau:g}\n")
        fh.write(f"bins: {args.nbins} x {args.nbins}, blank below {args.min_cnt} usable samples\n\n")
        fh.write(f"{'case':<14} {'kept':>9}\n")
        for label, n in per_case:
            fh.write(f"{label:<14} {n:>9,}\n")
        fh.write(f"{'POOLED':<14} {X.shape[0]:>9,}\n\n")

        for m, mode in enumerate(MODES):
            u = USE[:, m]
            r = R[u, m]
            fh.write(f"{mode}: usable={int(u.sum()):,} ({u.mean():.3f} of pool)  "
                     f"median rel={np.median(r):+.4f}  mean rel={r.mean():+.4f}  "
                     f"frac(ARG<parcel)={np.mean(A[u, m] < P[u, m]):.4f}\n")
            fh.write(f"    fn_parcel mean={P[:, m].mean():.4f}  frac<0.01={np.mean(P[:, m] < 0.01):.4f}"
                     f"   fn_ARG mean={A[:, m].mean():.4f}  frac<0.01={np.mean(A[:, m] < 0.01):.4f}"
                     f"  frac exactly 0={np.mean(A[:, m] == 0.0):.4f}\n")

        m = 1
        u = USE[:, m]
        fh.write("\n" + "=" * 104 + "\n")
        fh.write("ACCUM, in the coordinate the literature uses: N_accum / w  (cm-3 per m s-1)\n")
        fh.write("Phinney et al. (2003): ARG fails for V < 50 cm/s and Na > 500 cm-3.\n")
        fh.write("Ghosh et al. (2025, GMD 18, 4899): the kinetically limited regime is N/w > 1e4.\n")
        fh.write("=" * 104 + "\n")
        ratio = NACC / np.maximum(W_ms, 1e-12)
        fh.write(f"{'N/w bin':>26} {'n':>8} {'fn_parcel':>10} {'fn_ARG':>9} {'abs bias':>10} "
                 f"{'median rel':>11} {'mean rel':>10} {'ARG<parcel':>11}\n")
        edges = [0, 1e3, 3e3, 1e4, 3e4, 1e5, 3e5, 1e6, np.inf]
        for b in range(len(edges) - 1):
            s = (ratio >= edges[b]) & (ratio < edges[b + 1])
            su = s & u
            if s.sum() < 50 or su.sum() < 10:
                continue
            fh.write(f"[{edges[b]:>10.3g},{edges[b+1]:>10.3g}) {int(s.sum()):>8,} "
                     f"{P[s, m].mean():>10.4f} {A[s, m].mean():>9.4f} "
                     f"{(A[s, m]-P[s, m]).mean():>+10.4f} {np.median(R[su, m]):>+11.4f} "
                     f"{R[su, m].mean():>+10.4f} {np.mean(A[su, m] < P[su, m]):>11.4f}\n")

        fh.write("\n" + "=" * 104 + "\n")
        fh.write("ACCUM, the named regimes\n" + "=" * 104 + "\n")
        for name, s in (("all cells", np.ones(X.shape[0], bool)),
                        ("Phinney regime: V<50 cm/s & Na_acc>500 cm-3",
                         (W_cms < 50) & (NACC > 500)),
                        ("Phinney 'good' regime: V>50 & Na_acc<500",
                         (W_cms >= 50) & (NACC <= 500))):
            su = s & u
            if su.sum() < 10:
                continue
            nd = (A[su, m] * NACC[su]).mean() / (P[su, m] * NACC[su]).mean()
            fh.write(f"  {name:<44} n={int(su.sum()):>7,}  median rel={np.median(R[su, m]):+.4f}  "
                     f"mean rel={R[su, m].mean():+.4f}  frac(ARG<parcel)={np.mean(A[su, m] < P[su, m]):.4f}  "
                     f"mean Nact ARG/parcel={nd:.4f}\n")

        fh.write("\n" + "=" * 104 + "\n")
        fh.write("ACCUM: does ARG show the unphysical 'Nact falls as Na rises'? (w < 50 cm/s)\n")
        fh.write("=" * 104 + "\n")
        lo = W_cms < 50.0
        ed = np.percentile(NACC[lo], np.linspace(0, 100, 11))
        fh.write(f"{'Na_accum bin (cm-3)':>26} {'n':>8} {'Nact_parcel':>13} {'Nact_ARG':>11} {'ARG/parcel':>11}\n")
        for b in range(10):
            s = lo & (NACC >= ed[b]) & (NACC <= ed[b+1] if b == 9 else NACC < ed[b+1])
            if s.sum() < 50:
                continue
            ndp = (P[s, m] * NACC[s]).mean(); nda = (A[s, m] * NACC[s]).mean()
            fh.write(f"[{ed[b]:>10.4g},{ed[b+1]:>10.4g}) {int(s.sum()):>8,} {ndp:>13.2f} "
                     f"{nda:>11.2f} {nda/max(ndp,1e-9):>11.4f}\n")
    print(f"Wrote {rep}", flush=True)


if __name__ == "__main__":
    main()
