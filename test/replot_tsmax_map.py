#!/usr/bin/env python3
"""
Redraw tsmax_map restricted to log10(wbar) >= 0, with a colorbar matched to
that sub-range and larger fonts.

Why restrict.  The full map spans log10 wbar = -1.12 to 2.04, and the weak-
updraft third of it dominates the colour scale (median 644 s at w < 0.32 cm/s
against 37 s at w > 16 cm/s) while contributing the sparse, poorly sampled bins
at the edge of the WRF distribution.  Cutting to w >= 1 cm/s covers the regime
the ARG comparison actually concerns and lets the colour scale resolve the
9-565 s range that remains, instead of compressing it against a 2600 s tail.

Reads tsmax_map.npz written by tsmax_map.py; writes png + eps + pdf.

  python replot_tsmax_map.py [--wmin 0.0]
"""
import argparse
import os

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--npz", default="tsmax_map.npz")
    ap.add_argument("--out", default="tsmax_map_wgt1")
    ap.add_argument("--wmin", type=float, default=0.0,
                    help="keep bins with log10(wbar) >= this (default 0)")
    a = ap.parse_args()

    z = np.load(a.npz)
    T, CEN = z["T"], z["CEN"]
    we, ne = z["wedges"], z["nedges"]
    wm = 0.5 * (we[1:] + we[:-1])

    keep = wm >= a.wmin
    i0 = int(np.argmax(keep))                 # first retained column
    T, CEN = T[keep, :], CEN[keep, :]
    we = we[i0:i0 + keep.sum() + 1]
    wmk = wm[keep]

    finite = T[np.isfinite(T)]
    vmin = max(1.0, np.floor(finite.min()))
    vmax = np.ceil(np.percentile(finite, 99))
    print(f"  {T.shape[0]}x{T.shape[1]} bins, w = {10**wmk.min():.2f}-{10**wmk.max():.1f} cm/s")
    print(f"  t_Smax {finite.min():.1f}-{finite.max():.1f} s; colorbar {vmin:.0f}-{vmax:.0f} s")

    fig, ax = plt.subplots(figsize=(11.5, 8.4))
    pcm = ax.pcolormesh(we, ne, np.ma.masked_invalid(T).T, cmap="viridis",
                        norm=mcolors.LogNorm(vmin=vmin, vmax=vmax),
                        shading="flat")
    cb = fig.colorbar(pcm, ax=ax, extend="max", pad=0.02)
    cb.set_label(r"median simulated time to reach $S_{max}$   (s)", fontsize=19)
    cb.ax.tick_params(labelsize=16)
    cb.set_ticks([10, 20, 50, 100, 200, 500])
    cb.ax.set_yticklabels(["10", "20", "50", "100", "200", "500"])

    CS = ax.contour(wmk, 0.5 * (ne[1:] + ne[:-1]), np.ma.masked_invalid(T).T,
                    levels=[20, 50, 100, 200], colors="k", linewidths=1.6)
    ax.clabel(CS, fmt="%.0f s", fontsize=15)

    # Bins where a large share of solves exceeded the wall-clock limit.  This is
    # a COMPUTE-time limit (solver stiffness), not the 50,000 s simulated-time
    # integration cap, and it is not confined to weak updraft -- hence marking
    # it explicitly rather than describing it as an edge effect.
    ax.contourf(wmk, 0.5 * (ne[1:] + ne[:-1]), CEN.T, levels=[0.25, 1.0],
                colors="none", hatches=["///"])

    ax.set_xlabel(r"$\log_{10}\ \bar{w}$   (cm s$^{-1}$)", fontsize=21)
    ax.set_ylabel(r"$\log_{10}\ n_{\mathrm{acc}}$   (cm$^{-3}$)", fontsize=21)
    ax.tick_params(labelsize=17)
    ax.set_title("Simulated time for the Fortran parcel model to reach "
                 "$S_{max}$\n"
                 r"$\bar{w} \geq 1$ cm s$^{-1}$; other inputs drawn from the "
                 "WRF run distributions",
                 fontsize=20)
    ax.text(0.015, 0.025,
            f"max anywhere here: {finite.max():.0f} s\n"
            "integration cap: 50,000 s of simulated time\n"
            "hatch: >25% of solves exceeded the 300 s wall-clock limit",
            transform=ax.transAxes, fontsize=14, va="bottom",
            bbox=dict(fc="white", alpha=0.88, ec="0.6"))

    fig.tight_layout()
    for ext in ("png", "eps", "pdf"):
        out = f"{a.out}.{ext}"
        fig.savefig(out, dpi=200, bbox_inches="tight")
        print(f"  wrote {os.path.abspath(out)}")
    plt.close(fig)


if __name__ == "__main__":
    main()
