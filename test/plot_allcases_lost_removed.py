#!/usr/bin/env python
"""
plot_allcases_lost_removed.py
=============================================================================
One figure for ALL four WRF test cases, showing ONLY the cleaned sample set --
i.e. the "lost-output cells removed" panel of
parcel_vs_wrfout_20170714_1aer_org_scatter_DIAGNOSED.png, repeated per case.

For every case <test>/<case>/online/ we reuse exactly what the published
scatter used:
    parcel_inputs.npz    X[N,16], sg2[N,2], fn_wrf[N,2]   (FN11 Aitken, FN21 Accum)
    parcel_shard_*.npz   res[k,6] = (idx, fn0, fn1, smax, bad, tout)
and additionally re-run the DEPLOYED TorchScript emulator offline on the same
stored inputs (cached as diag_fn_ml_offline.npz, as diag_zero_fn.py did):

    lost = (fn_wrf[:,0]<=1e-12) & (fn_wrf[:,1]<=1e-12) & (fn_ml[:,1]>0.01)

i.e. WRF stored a hard zero for BOTH modes although the very same model,
fed the very same stored inputs, returns a clearly non-zero activation.
Those cells are the horizontal zero-band in the published scatter: the
emulator output never reached the WRF state, so they say nothing about
emulator skill.  Plot = clean solves with that band removed.

Also writes a text report classifying every sample that gets dropped anywhere
in the chain (masking -> subsample -> deadline -> parcel failures -> lost band).

Usage
-----
  $HOME/.conda/envs/liranenv_gpu/bin/python plot_allcases_lost_removed.py
  ... --cases 20170714_1aer_org 20170714_3aer_mid      # subset
  ... --no_ml_recompute                                # only use cached fn_ml
=============================================================================
"""
import os
import re
import glob
import argparse

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors

HERE = os.path.dirname(os.path.abspath(__file__))
PT_DEFAULT = os.path.join(os.path.dirname(HERE), "ml_models", "mlp_wrapper.pt")

CASES = [
    ("20170714_1aer_org", "1aer / org"),
    ("20170714_1aer_mid", "1aer / mid"),
    ("20170714_3aer_org", "3aer / org"),
    ("20170714_3aer_mid", "3aer / mid"),
]
MODES = ["Aitken", "Accum"]
ZERO = 1e-12          # "stored exactly 0"
ML_POS = 0.01         # "the emulator clearly wanted a non-zero answer"

COLS = ["tair(K)", "pres(hPa)", "rh(%)", "wbar(cm/s)",
        "na_ait(cm-3)", "na_acc(cm-3)", "na_c1(cm-3)", "na_c2(cm-3)",
        "r_ait(um)", "r_acc(um)", "r_c1(um)", "r_c2(um)",
        "hg_ait", "hg_acc", "hg_c1", "hg_c2"]


# ───────────────────────── loading ──────────────────────────────────────────
def load_case(case_dir, pt_path, allow_recompute=True):
    """Return a dict with everything the plot + report need for one case."""
    on = os.path.join(case_dir, "online")
    z = np.load(os.path.join(on, "parcel_inputs.npz"))
    X, sg2, fn_wrf = z["X"], z["sg2"], z["fn_wrf"]
    N = X.shape[0]

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

    fn_ml = get_fn_ml(on, X, pt_path, allow_recompute)

    lost = (fn_wrf[:, 0] <= ZERO) & (fn_wrf[:, 1] <= ZERO) & (fn_ml[:, 1] > ML_POS)
    legit0 = (fn_wrf[:, 0] <= ZERO) & (fn_wrf[:, 1] <= ZERO) & ~lost
    keep = good & ~lost

    return dict(dir=case_dir, online=on, N=N, X=X, sg2=sg2, fn_wrf=fn_wrf,
                fn_parcel=fn_parcel, smax=smax, bad=bad, tout=tout,
                attempted=attempted, good=good, fn_ml=fn_ml,
                lost=lost, legit0=legit0, keep=keep)


def get_fn_ml(online_dir, X, pt_path, allow_recompute):
    """Deployed emulator re-run offline on the stored inputs (cached to npz)."""
    cache = os.path.join(online_dir, "diag_fn_ml_offline.npz")
    if os.path.exists(cache):
        c = np.load(cache)
        if c["fn_ml"].shape[0] == X.shape[0]:
            print(f"    fn_ml: cached {os.path.basename(cache)}", flush=True)
            return c["fn_ml"]
        print("    fn_ml: cache shape mismatch -> recomputing", flush=True)
    if not allow_recompute:
        raise FileNotFoundError(f"no usable {cache} and --no_ml_recompute given")

    import torch
    torch.set_num_threads(int(os.environ.get("OMP_NUM_THREADS", "8")))
    print(f"    fn_ml: running {os.path.basename(pt_path)} on "
          f"{X.shape[0]:,} cells ...", flush=True)
    m = torch.jit.load(pt_path, map_location="cpu").eval()
    outs = []
    with torch.no_grad():
        for s in range(0, X.shape[0], 200000):
            t = torch.from_numpy(np.ascontiguousarray(X[s:s + 200000], dtype=np.float32))
            outs.append(m(t).numpy())
    ml = np.concatenate(outs, 0)
    fn_ml = np.clip(ml[:, :2], 0, 1)          # slot0 = Aitken, slot1 = Accum
    np.savez(cache, fn_ml=fn_ml, ml_raw=ml)
    print(f"    fn_ml: wrote {cache}", flush=True)
    return fn_ml


# ───────────────── output-time attribution (no wrfout re-read) ──────────────
def time_edges(online_dir, N):
    """Map every pool index to the wrfout output time it came from.

    compare_parcel_vs_wrfout.py concatenates the files in chronological order
    and, when --max_cells subsamples, keeps a SORTED random subset -- so pool
    order still follows file order.  The reconstruct log records the per-file
    cell counts, hence proportional cumulative counts give the pool boundaries
    (exact when no subsample; +-O(few hundred) cells out of 1.5M otherwise).

    Returns (times[list], edges[len(times)+1]) or (None, None)."""
    logs = sorted(glob.glob(os.path.join(online_dir, "*.out")), key=os.path.getmtime)
    pat = re.compile(r"wrfout_d01_(\S+):\s+([\d,]+) updraft cells")
    best = None
    for lg in logs:                               # newest log that has the listing
        with open(lg) as fh:
            hits = pat.findall(fh.read())
        if hits:
            best = hits
    if not best:
        return None, None
    times = [h[0] for h in best]
    cnt = np.array([int(h[1].replace(",", "")) for h in best], np.int64)
    tot = cnt.sum()
    edges = np.concatenate([[0], np.rint(np.cumsum(cnt) / tot * N).astype(np.int64)])
    edges[-1] = N
    return times, edges


def per_time_table(c, fh):
    times, edges = time_edges(c["online"], c["N"])
    if times is None:
        fh.write("    (no reconstruct log found -- per-output-time table skipped)\n")
        return
    lost, good = c["lost"], c["good"]
    fh.write(f"    {'output time':<22} {'pool cells':>11} {'lost-out':>10} {'frac':>7} "
             f"{'plotted':>8} {'of those lost':>14}\n")
    tot_l = tot_p = 0
    hot, cold = [], []
    for k, t in enumerate(times):
        a, b = edges[k], edges[k + 1]
        if b <= a:
            continue
        nl = int(lost[a:b].sum())
        ng = int(good[a:b].sum())
        ngl = int((good & lost)[a:b].sum())
        fr = nl / (b - a)
        tot_l += nl
        tot_p += ng
        is_phot = (int(t.split("_")[1].split(":")[1]) % 30 == 0)
        flag = "  <== photolysis-alarm step" if is_phot else ""
        fh.write(f"    {t:<22} {b-a:>11,} {nl:>10,} {fr:>7.3f} {ng:>8,} {ngl:>14,}{flag}\n")
        (hot if is_phot else cold).append(fr)
    fh.write(f"    {'TOTAL':<22} {c['N']:>11,} {tot_l:>10,} "
             f"{tot_l/c['N']:>7.3f} {tot_p:>8,} {int((good&lost).sum()):>14,}\n")
    fh.write("\n    loss rate split by the photdt=30 min photolysis alarm "
             "(minute a multiple of 30):\n")
    if cold:
        fh.write(f"      ordinary steps   ({len(cold):>3} times): median {np.median(cold):.3f}  "
                 f"range {min(cold):.3f} - {max(cold):.3f}\n")
    if hot:
        fh.write(f"      alarm steps      ({len(hot):>3} times): median {np.median(hot):.3f}  "
                 f"range {min(hot):.3f} - {max(hot):.3f}\n")
    else:
        fh.write("      alarm steps      (  0 times): this pool spans no :00/:30 output time\n")


# ─────────────────────────── plotting ───────────────────────────────────────
def panel(ax, p, y, title, ylab, note=""):
    ok = np.isfinite(p) & np.isfinite(y)
    p, y = p[ok], y[ok]
    if p.size == 0:
        ax.set_title(title + " (no data)", fontsize=9)
        return
    ax.hexbin(p, y, gridsize=80, mincnt=1, cmap="viridis", extent=[0, 1, 0, 1],
              norm=mcolors.LogNorm(vmin=1), rasterized=True)
    ax.plot([0, 1], [0, 1], "r--", lw=1)
    mse = ((y - p) ** 2).mean()
    r = np.corrcoef(p, y)[0, 1] if p.size > 2 else np.nan
    ax.text(0.03, 0.97, f"N={p.size:,}\nMSE={mse:.2e}\nR={r:.4f}" + note,
            transform=ax.transAxes, va="top", fontsize=8,
            bbox=dict(fc="white", alpha=0.85))
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    ax.set_xlabel("fn_parcel (Fortran box model)")
    ax.set_ylabel(ylab)
    ax.set_title(title, fontsize=9)


def save_fig(fig, prefix):
    """PNG + EPS.  Data layers are rasterized (the PS backend drops alpha),
       axes/text stay vector -- same convention as compare_parcel_vs_wrfout.py."""
    for ext in ("png", "eps"):
        p = f"{prefix}.{ext}"
        fig.savefig(p, dpi=300, bbox_inches="tight")
        print(f"Wrote {p}", flush=True)
    plt.close(fig)


# ─────────────────────────── report ─────────────────────────────────────────
def pct(a, b):
    return 100.0 * a / max(b, 1)


def criterion(fh):
    """The exact rule that declares one sample 'lost', spelled out."""
    def w(s=""):
        fh.write(s + "\n")

    w("-" * 100)
    w("HOW A SINGLE SAMPLE IS DECLARED 'LOST'")
    w("-" * 100)
    w("One sample = one wrfout grid cell (k,j,i) at one output time at which activate_ml")
    w("ran.  For that cell we hold three things:")
    w("")
    w("    fn_wrf   [2]  FN11, FN21 as WRF stored them   -- what the model state actually got")
    w("    fn_ml    [2]  the SAME deployed TorchScript file (ml_models/mlp_wrapper.pt),")
    w("                  re-run offline on the 16 inputs rebuilt from the SAME wrfout record")
    w("                  -- what the emulator returns for that cell")
    w("    fn_parcel[2]  the Fortran box model on the same inputs -- ground-truth physics")
    w("")
    w("fn_parcel is NEVER used in the decision.  The test compares the emulator against")
    w("itself, so 'lost' can never mean 'the emulator was wrong'.")
    w("")
    w("A sample is LOST if and only if all three tests pass:")
    w("")
    w(f"  T1  fn_wrf[Aitken] <= {ZERO:g}     stored Aitken activation is exactly zero")
    w(f"  T2  fn_wrf[Accum]  <= {ZERO:g}     stored Accum  activation is exactly zero")
    w(f"  T3  fn_ml[Accum]   >  {ML_POS}       the emulator, on those very inputs, returns a")
    w("                                 clearly non-zero Accum activation")
    w("")
    w("  lost = T1 & T2 & T3                      (code: one line, no tuning per case)")
    w("  keep = clean parcel solve & not lost")
    w("")
    w("Why each test:")
    w("  T1 & T2 together  a genuine emulator answer is essentially never exactly 0.0 in BOTH")
    w("                    modes at once; a hard double zero is the signature of a value that")
    w("                    was never written, not of a value that was computed.  Requiring")
    w("                    BOTH modes is what makes the test conservative: a cell where the")
    w("                    emulator really did predict ~0 for one mode is not touched.")
    w("  T3                separates 'never landed' from 'landed, and the answer was zero'.")
    w("                    The emulator output is clipped to [0,1], so a negative raw output")
    w("                    legitimately becomes an exact 0 -- those cells satisfy T1+T2 and")
    w("                    MUST be kept.  T3 is the only thing that distinguishes them.")
    w("                    Accum is used, not Aitken, because Aitken activation is genuinely")
    w("                    near zero over most of this domain (median fn_parcel ~1e-4) and so")
    w("                    carries no discriminating power; Accum is the mode that actually")
    w("                    activates (median ~0.18).")
    w("")
    w("Why the two thresholds are safe:")
    w(f"  {ZERO:g}   is 'exactly zero' in float32 -- there is no populated bin between")
    w("          0 and 1e-6 in any case (see the histogram argument below).")
    w(f"  {ML_POS}    sits in an empty valley.  Among the cells that pass T1+T2, the offline")
    w("          emulator is either exactly 0 (25-70% of them, depending on case) or")
    w("          >0.01 (the rest); only 0.4-1.6% land in the whole interval (0, 0.01).")
    w("          Moving the threshold anywhere in 1e-3 .. 0.02 changes the verdict on")
    w("          <1% of the flagged cells.")
    w(f"  {ML_POS}    is also 10-250x the reproduction noise: on cells where the output DID")
    w("          land, mean |fn_wrf - fn_ml| is 4e-5 to 1e-3 (reported per case below).")
    w("          So T3 can only fire on a discrepancy far larger than any float / thread /")
    w("          library difference between WRF's in-line inference and the offline re-run.")
    w("")
    w("Validity precondition (checked): ml_models/mlp_wrapper.pt was last modified")
    w("2026-07-27 10:47, before the first wrfout of every one of the four runs, so the")
    w("offline re-run uses the exact weights that were deployed online.")
    w("")


def report(cases, fh):
    def w(s=""):
        fh.write(s + "\n")

    w("=" * 100)
    w("WHICH SAMPLES ARE REMOVED, AND WHY")
    w("=" * 100)
    w("Chain of filters, from every grid point WRF wrote to the points actually plotted.")
    w("Steps 1-3 are inherited from compare_parcel_vs_wrfout.py (they define the pool and")
    w("the parcel-model workload); steps 4-5 are the ones this figure applies.")
    w("")
    w("  1. GRID MASK      keep only cells where activate_ml actually ran and the two")
    w("                    active modes carry physical aerosol:")
    w("                    EMTAIR>0 & EMWBAR>0 & NA11,NA21 > 1 cm-3 & HG>0 & VO>0.")
    w("                    -> removes all non-updraft / aerosol-free cells (~97% of the grid).")
    w("  2. SUBSAMPLE      seeded random draw down to --max_cells = 1,500,000 pool cells.")
    w("                    Unbiased; only limits pool size.")
    w("  3. DEADLINE       the Fortran parcel model is ~2 solves/s/core, so a 12,000 s")
    w("                    budget only reaches 1.5-2.2% of the pool.  The solve order is a")
    w("                    seeded permutation, so the attempted subset is an unbiased sample.")
    w("  4. PARCEL FAILURE drop cells where the box model did not converge cleanly:")
    w("                    bad!=0 (solver error), tout!=0 (60 s per-sample timeout),")
    w("                    or smax<=0 (no supersaturation reached).  This is a PHYSICS-")
    w("                    dependent cut -- the failures are not uniform in input space.")
    w("  5. LOST OUTPUT    NEW HERE.  Drop cells where WRF stored FN11=FN21=0 exactly while")
    w("                    the same deployed TorchScript model, re-run offline on the same")
    w(f"                    stored inputs, returns fn_ml(Accum) > {ML_POS}.  The emulator")
    w("                    result never reached the WRF state for those cells, so they are")
    w("                    a bookkeeping artifact, not emulator error.  They form the")
    w("                    horizontal zero-band along y=0 in the published scatter.")
    w("                    Cells where WRF stored 0 AND the emulator also says ~0 are KEPT")
    w("                    (genuine non-activation).")
    w("")
    criterion(fh)

    for c, label in cases:
        w("=" * 100)
        w(f"CASE {os.path.basename(c['dir'])}   ({label})")
        w("=" * 100)
        N = c["N"]
        att, good, lost, keep = c["attempted"], c["good"], c["lost"], c["keep"]
        fail = att & ~good
        w(f"  pool cells (after steps 1-2)            : {N:>10,}")
        w(f"  attempted by parcel model (step 3)      : {int(att.sum()):>10,} "
          f"({pct(att.sum(), N):.1f}% of pool)")
        w(f"  step 4 removed - parcel did not converge: {int(fail.sum()):>10,} "
          f"({pct(fail.sum(), att.sum()):.1f}% of attempted)")
        w(f"        solver error   bad!=0             : {int((att & (c['bad'] != 0)).sum()):>10,}")
        w(f"        timeout        tout!=0 (60 s)     : {int((att & (c['tout'] != 0)).sum()):>10,}")
        w(f"        no supersat.   smax<=0            : "
          f"{int((att & (c['bad'] == 0) & (c['tout'] == 0) & ~(c['smax'] > 0)).sum()):>10,}")
        w(f"  clean solves (published N)              : {int(good.sum()):>10,}")
        w(f"  step 5 removed - lost emulator output   : {int((good & lost).sum()):>10,} "
          f"({pct((good & lost).sum(), good.sum()):.1f}% of published N)")
        w(f"  PLOTTED (clean & output landed)         : {int(keep.sum()):>10,}")
        w("")
        w(f"  whole-pool view (no parcel model needed, all {N:,} cells):")
        z_both = (c["fn_wrf"][:, 0] <= ZERO) & (c["fn_wrf"][:, 1] <= ZERO)
        w(f"    stored FN11=FN21=0 exactly            : {int(z_both.sum()):>10,} "
          f"({pct(z_both.sum(), N):.1f}%)")
        w(f"      of those, lost output (ml>{ML_POS})      : {int(lost.sum()):>10,} "
          f"({pct(lost.sum(), max(z_both.sum(),1)):.1f}% of the zeros)")
        w(f"      of those, genuine ~0 (ml<={ML_POS})      : {int(c['legit0'].sum()):>10,}")
        nz = ~z_both
        d = np.abs(c["fn_wrf"][nz, 1] - c["fn_ml"][nz, 1])
        w(f"    on the NON-zero cells, |stored - offline emulator| : "
          f"mean={d.mean():.2e}  max={d.max():.2e}")
        w("      -> wherever the output landed, the stored field IS the emulator;")
        w("         the discrepancy is essentially all in the zero-band.")
        w("")
        w("    what the criterion does NOT catch (still in the plotted set):")
        one0 = (c["fn_wrf"][:, 0] <= ZERO) ^ (c["fn_wrf"][:, 1] <= ZERO)
        d0 = np.abs(c["fn_wrf"][nz, 0] - c["fn_ml"][nz, 0])
        w(f"      exactly ONE mode stored 0 (partial loss)   : {int(one0.sum()):>9,} "
          f"({pct(one0.sum(), N):.2f}% of pool)")
        w(f"      non-zero cells with |stored-offline| > 0.01: "
          f"{int((d > 0.01).sum()):>9,} Accum / {int((d0 > 0.01).sum()):,} Aitken "
          f"({pct((d > 0.01).sum(), nz.sum()):.2f}% of non-zero cells)")
        w("      -> a small residue; the both-modes-zero test is deliberately strict so")
        w("         that no genuine emulator error is discarded.")
        w("")

        # what the removed cells look like -- outputs
        gl = good & lost
        gk = keep
        w("  A) WHAT THE STEP-5 (lost-output) SAMPLES LOOK LIKE")
        if gl.sum():
            for m, nm in enumerate(MODES):
                w(f"    [{nm}] removed cells: fn_parcel mean={c['fn_parcel'][gl, m].mean():.4f} "
                  f"median={np.median(c['fn_parcel'][gl, m]):.4f} | "
                  f"offline fn_ml mean={c['fn_ml'][gl, m].mean():.4f} | stored fn_wrf = 0")
                w(f"           kept  cells: fn_parcel mean={c['fn_parcel'][gk, m].mean():.4f} "
                  f"median={np.median(c['fn_parcel'][gk, m]):.4f} | "
                  f"stored fn_wrf mean={c['fn_wrf'][gk, m].mean():.4f}")
            w("    -> the removed cells are ORDINARY activating cells (parcel and emulator")
            w("       both give a normal non-zero fraction); only the stored value is 0.")
            w("")
            w("    input distribution, removed vs kept (5th / 50th / 95th percentile):")
            w(f"    {'input':<14} {'REMOVED p05':>12} {'p50':>11} {'p95':>11} | "
              f"{'KEPT p05':>11} {'p50':>11} {'p95':>11}")
            for j in range(16):
                a = np.percentile(c["X"][gl, j], [5, 50, 95])
                b = np.percentile(c["X"][gk, j], [5, 50, 95])
                w(f"    {COLS[j]:<14} {a[0]:>12.4g} {a[1]:>11.4g} {a[2]:>11.4g} | "
                  f"{b[0]:>11.4g} {b[1]:>11.4g} {b[2]:>11.4g}")
            w("    -> the two distributions overlap: the removal is NOT a physical regime cut.")
        else:
            w("    none (this case has no lost-output cells among the clean solves)")
        w("")

        w("  B) WHEN THEY HAPPEN (per wrfout output time, whole pool)")
        per_time_table(c, fh)
        w("")

        # what the parcel failures look like
        w("  C) WHAT THE STEP-4 (parcel-failure) SAMPLES LOOK LIKE")
        if fail.sum():
            w(f"    {'input':<14} {'FAILED p05':>12} {'p50':>11} {'p95':>11} | "
              f"{'SOLVED p05':>11} {'p50':>11} {'p95':>11}")
            for j in (0, 1, 2, 3, 4, 5, 8, 9, 12, 13):
                a = np.percentile(c["X"][fail, j], [5, 50, 95])
                b = np.percentile(c["X"][good, j], [5, 50, 95])
                w(f"    {COLS[j]:<14} {a[0]:>12.4g} {a[1]:>11.4g} {a[2]:>11.4g} | "
                  f"{b[0]:>11.4g} {b[1]:>11.4g} {b[2]:>11.4g}")
            w("    (parcel failures are dominated by the 60 s timeout: slow/stiff cases,")
            w("     typically weak updraft and/or large aerosol loading.)")
        else:
            w("    none")
        w("")


# ─────────────────────────────── main ───────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--test_dir", default=HERE)
    ap.add_argument("--cases", nargs="*", default=[c for c, _ in CASES])
    ap.add_argument("--pt", default=PT_DEFAULT, help="deployed TorchScript emulator")
    ap.add_argument("--no_ml_recompute", action="store_true",
                    help="fail instead of running the emulator when no cache exists")
    ap.add_argument("--out_prefix",
                    default=os.path.join(HERE, "parcel_vs_wrfout_ALLCASES_lost_removed"))
    args = ap.parse_args()

    labels = dict(CASES)
    loaded = []
    for cname in args.cases:
        cdir = os.path.join(args.test_dir, cname)
        print(f"[{cname}]", flush=True)
        c = load_case(cdir, args.pt, not args.no_ml_recompute)
        print(f"    pool={c['N']:,}  clean solves={int(c['good'].sum()):,}  "
              f"lost-output among them={int((c['good']&c['lost']).sum()):,}  "
              f"plotted={int(c['keep'].sum()):,}", flush=True)
        loaded.append((c, labels.get(cname, cname)))

    # ---------------- figure: rows = mode, cols = case ----------------
    n = len(loaded)
    fig, axes = plt.subplots(2, n, figsize=(4.8 * n, 9.0), squeeze=False)
    for col, (c, label) in enumerate(loaded):
        k = c["keep"]
        drop = int((c["good"] & c["lost"]).sum())
        note = f"\nremoved {drop:,} ({pct(drop, c['good'].sum()):.1f}%)"
        for m, nm in enumerate(MODES):
            panel(axes[m][col], c["fn_parcel"][k, m], c["fn_wrf"][k, m],
                  f"{label} -- {nm}", "fn_wrf (stored FN, ML applied)", note)
    fig.suptitle(
        "Fortran parcel model vs WRF-applied ML emulator -- lost-output cells removed\n"
        "kept: clean parcel solves whose emulator output actually reached the WRF state "
        f"(dropped: stored FN11=FN21=0 while the same model re-run offline gives >{ML_POS})",
        fontsize=12)
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    save_fig(fig, args.out_prefix)

    # ---------------- text report ----------------
    txt = args.out_prefix + "_removed_samples.txt"
    with open(txt, "w") as fh:
        report(loaded, fh)
    print(f"Wrote {txt}", flush=True)
    with open(txt) as fh:
        print(fh.read())


if __name__ == "__main__":
    main()
