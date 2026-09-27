#!/bin/bash
# =============================================================================
# setup_online_dirs.sh -- build the per-case online/ subdirectories for the
#                         cosine_more_fix runs, mirroring cosine_more.
#
# The cosine_more cases each carry an online/ directory holding
#
#     compare_parcel_vs_wrfout.py    the harvest + parcel-solve driver
#     parcel_inputs.npz              X[N,16], sg2[N,2], fn_wrf[N,2], fn_arg[N,2]
#     parcel_shard_*.npz             res[k,6] = (idx, fn0, fn1, smax, bad, tout)
#     diag_fn_ml_offline.npz         offline emulator predictions
#
# cosine_more_fix has none of these, so every analysis that needs harvested
# activation states (the relative-error map, the time-to-Smax sweep, the
# wall-clock timeout statistics) still runs on cosine_more data -- i.e. on the
# tree WITHOUT the fn13/fn23 fix.  This script creates the directories and
# drives the harvest so those analyses can be repeated on the fixed runs.
#
# STAGES
#   1  mkdir online/ per case and copy the driver (+ slurm template if present)
#   2  reconstruct : read every wrfout once, write parcel_inputs.npz
#                    (X, sg2, fn_wrf).  Cheap-ish, I/O bound, one pass.
#   3  parcel      : solve the Fortran parcel model on those states, write
#                    parcel_shard_*.npz.  EXPENSIVE -- submit to the queue.
#   4  fn_arg      : add_fn_arg.py appends the diagnostic ARG fraction
#                    (FN13/FN23) row-aligned to parcel_inputs.npz.
#
# Stage 3 is the costly one: at the measured cost distribution (median 9.7 s,
# mean 13.8 s per converged solve, ~20% exceeding 60 s) a full case is O(100)
# core-hours, so it is submitted rather than run here.
#
# USAGE
#   ./setup_online_dirs.sh              # stage 1 only (safe, no compute)
#   ./setup_online_dirs.sh --reconstruct   # stages 1-2
#   ./setup_online_dirs.sh --submit        # stages 1-2 then submit stage 3
#   ./setup_online_dirs.sh --fn-arg        # stage 4, after stage 3 completes
# =============================================================================

set -uo pipefail

FIX=/scratch/07088/tg863871/Perlm_Backup/WRF_stam3_ml_mixout_bce_lr1e-4_cosine_more_fix/test
SRC=/scratch/07088/tg863871/Perlm_Backup/WRF_stam3_ml_mixout_bce_lr1e-4_cosine_more/test
CASES=(20170714_1aer_org 20170714_3aer_org 20170714_1aer_mid 20170714_3aer_mid)
PY=$HOME/.conda/envs/liranenv_gpu/bin/python
DRIVER=compare_parcel_vs_wrfout.py

DO_RECON=0; DO_SUBMIT=0; DO_FNARG=0
for a in "$@"; do
  case "$a" in
    --reconstruct) DO_RECON=1 ;;
    --submit)      DO_RECON=1; DO_SUBMIT=1 ;;
    --fn-arg)      DO_FNARG=1 ;;
    -h|--help)     sed -n '2,40p' "$0"; exit 0 ;;
    *) echo "unknown option: $a" >&2; exit 2 ;;
  esac
done

log() { echo "[$(date +'%H:%M:%S')] $*"; }

# ---------------- stage 1: directories + driver ----------------------------
log "=== stage 1: create online/ and copy the driver ==="
for c in "${CASES[@]}"; do
    d="$FIX/$c/online"
    mkdir -p "$d"
    # take the driver from the matching cosine_more case so any per-case edits
    # are preserved; fall back to 3aer_org if that case has none.
    src="$SRC/$c/online/$DRIVER"
    [ -f "$src" ] || src="$SRC/20170714_3aer_org/online/$DRIVER"
    cp -p "$src" "$d/$DRIVER"
    for extra in submit_parcel_compare_stam3.slurm; do
        [ -f "$SRC/$c/online/$extra" ] && cp -p "$SRC/$c/online/$extra" "$d/" 2>/dev/null
    done
    n=$(ls "$FIX/$c"/wrfout_d01_* 2>/dev/null | wc -l)
    printf "  %-20s online/ ready, %3d wrfout files\n" "$c" "$n"
done

# ---------------- stage 2: reconstruct -------------------------------------
if [ $DO_RECON -eq 1 ]; then
    log "=== stage 2: reconstruct parcel_inputs.npz (one pass over wrfout) ==="
    for c in "${CASES[@]}"; do
        d="$FIX/$c/online"
        if [ -f "$d/parcel_inputs.npz" ]; then
            log "  $c: parcel_inputs.npz exists, skipping (delete to redo)"
            continue
        fi
        log "  $c: reconstructing ..."
        ( cd "$d" && $PY "$DRIVER" --phase reconstruct --all \
            > reconstruct.log 2>&1 )
        if [ -f "$d/parcel_inputs.npz" ]; then
            sz=$(stat -c %s "$d/parcel_inputs.npz" | numfmt --to=iec)
            n=$($PY -c "import numpy as np;print(np.load('$d/parcel_inputs.npz')['X'].shape[0])" 2>/dev/null)
            log "  $c: wrote parcel_inputs.npz ($sz, N=${n:-?})"
        else
            log "  $c: FAILED -- see $d/reconstruct.log"
            tail -5 "$d/reconstruct.log" 2>/dev/null | sed 's/^/      /'
        fi
    done
fi

# ---------------- stage 3: parcel solve (submitted) ------------------------
if [ $DO_SUBMIT -eq 1 ]; then
    log "=== stage 3: submit the parcel solves ==="
    for c in "${CASES[@]}"; do
        d="$FIX/$c/online"
        [ -f "$d/parcel_inputs.npz" ] || { log "  $c: no parcel_inputs.npz, skipping"; continue; }
        if [ -f "$d/submit_parcel_compare_stam3.slurm" ]; then
            out=$( cd "$d" && sbatch submit_parcel_compare_stam3.slurm 2>&1 )
            jid=$(echo "$out" | grep -oE 'Submitted batch job [0-9]+' | grep -oE '[0-9]+')
            log "  $c: submitted ${jid:-FAILED}"
            [ -z "$jid" ] && echo "$out" | tail -3 | sed 's/^/      /'
        else
            log "  $c: no slurm template in online/ -- run by hand:"
            echo "        cd $d && $PY $DRIVER --phase parcel --all --workers 48"
        fi
    done
fi

# ---------------- stage 4: append fn_arg -----------------------------------
if [ $DO_FNARG -eq 1 ]; then
    log "=== stage 4: append the diagnostic ARG fraction ==="
    if [ -f "$FIX/add_fn_arg.py" ]; then
        ( cd "$FIX" && $PY add_fn_arg.py )
    elif [ -f "$SRC/add_fn_arg.py" ]; then
        cp -p "$SRC/add_fn_arg.py" "$FIX/"
        log "  copied add_fn_arg.py from cosine_more; it hard-codes TEST -- check it points at _more_fix"
        grep -nE "^TEST *=|^CASES *=" "$FIX/add_fn_arg.py" | sed 's/^/      /'
        log "  NOT running it until that is confirmed"
    else
        log "  add_fn_arg.py not found in either tree"
    fi
fi

log "done"
