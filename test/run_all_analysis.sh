#!/bin/bash
# =============================================================================
# run_all_analysis.sh -- reproduce, on the cosine_more_fix tree, every parcel-
#                        based analysis figure that currently exists only for
#                        cosine_more.
#
# Prerequisite: each case's online/parcel_inputs.npz and parcel_shard_*.npz
# must exist, i.e. the parcel_cmp jobs submitted from
# <case>/online/submit_parcel_compare_stam3.slurm have completed.  Check with
#     ./run_all_analysis.sh --check
#
# Stages
#   fn_arg   add_fn_arg.py appends the diagnostic ARG fraction (FN13/FN23) to
#            parcel_inputs.npz, row-aligned via the reconstruct log.  MUST run
#            before any of the ARG comparison figures.
#   figures  the six plotting scripts, each writing into this directory
#   tsmax    the time-to-Smax sweep (SEPARATE cost: ~1 h on 48 cores) -- only
#            with --tsmax, since it re-solves the parcel model on a fresh grid
#            rather than reading the harvested shards.
#
# Every script here derives its tree from its own location, so running them
# from this directory analyses the _fix data.  add_fn_arg.py was patched to do
# the same; the cosine_more copy still hardcodes its own tree and is untouched.
#
# USAGE
#   ./run_all_analysis.sh --check      # what is ready, what is missing
#   ./run_all_analysis.sh --fn-arg     # stage 1 only
#   ./run_all_analysis.sh --figures    # stages 1-2
#   ./run_all_analysis.sh --figures --tsmax
# =============================================================================

set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
PY=$HOME/.conda/envs/liranenv_gpu/bin/python
CASES=(20170714_1aer_org 20170714_3aer_org 20170714_1aer_mid 20170714_3aer_mid)

DO_CHECK=0; DO_FNARG=0; DO_FIG=0; DO_TSMAX=0
[ $# -eq 0 ] && DO_CHECK=1
for a in "$@"; do
  case "$a" in
    --check)   DO_CHECK=1 ;;
    --fn-arg)  DO_FNARG=1 ;;
    --figures) DO_FNARG=1; DO_FIG=1 ;;
    --tsmax)   DO_TSMAX=1 ;;
    -h|--help) sed -n '2,33p' "$0"; exit 0 ;;
    *) echo "unknown option: $a" >&2; exit 2 ;;
  esac
done
log() { echo "[$(date +'%H:%M:%S')] $*"; }

# ------------------------------- check -------------------------------------
if [ $DO_CHECK -eq 1 ]; then
    log "=== inputs present? ==="
    printf "  %-20s %-9s %-9s %-8s %s\n" CASE inputs shards fn_arg "cldchem"
    ready=1
    for c in "${CASES[@]}"; do
        d="$HERE/$c/online"
        i=$([ -f "$d/parcel_inputs.npz" ] && echo yes || echo NO)
        s=$(ls "$d"/parcel_shard_*.npz 2>/dev/null | wc -l)
        f=$($PY -c "
import numpy as np,sys
try: print('yes' if 'fn_arg' in np.load('$d/parcel_inputs.npz').files else 'no')
except Exception: print('-')" 2>/dev/null)
        ch=$(grep -E '^ *cldchem_onoff' "$HERE/$c/namelist.input" 2>/dev/null | grep -oE '[01],' | head -1)
        printf "  %-20s %-9s %-9s %-8s %s\n" "$c" "$i" "$s" "$f" "${ch:-?}"
        [ "$i" = "NO" ] && ready=0
    done
    [ $ready -eq 1 ] && log "all cases have inputs" || log "some cases missing inputs -- parcel_cmp jobs not finished"
    exit 0
fi

# ------------------------------ fn_arg -------------------------------------
if [ $DO_FNARG -eq 1 ]; then
    log "=== stage 1: append diagnostic ARG fraction ==="
    ( cd "$HERE" && $PY add_fn_arg.py ) 2>&1 | tail -20
fi

# ------------------------------ figures ------------------------------------
if [ $DO_FIG -eq 1 ]; then
    log "=== stage 2: analysis figures ==="
    for s in plot_allcases_lost_removed.py \
             plot_allcases_arg.py \
             plot_arg_density_map.py \
             plot_arg_failure_map.py \
             plot_arg_failure_map_bwr.py \
             plot_arg_relerr_map.py; do
        [ -f "$HERE/$s" ] || { log "  $s missing, skipping"; continue; }
        log "  running $s"
        ( cd "$HERE" && $PY "$s" ) > "$HERE/${s%.py}.log" 2>&1
        if [ $? -eq 0 ]; then
            log "    ok -> $(ls -t "$HERE"/*.png 2>/dev/null | head -1 | xargs -r basename)"
        else
            log "    FAILED -- see ${s%.py}.log"; tail -4 "$HERE/${s%.py}.log" | sed 's/^/        /'
        fi
    done
fi

# ------------------------------- tsmax -------------------------------------
if [ $DO_TSMAX -eq 1 ]; then
    log "=== stage 3: time-to-Smax sweep (expensive; submit rather than run here) ==="
    if [ -f "$HERE/submit_tsmax_map.sh" ]; then
        ( cd "$HERE" && sbatch submit_tsmax_map.sh )
    else
        log "  no submit_tsmax_map.sh here; copy it from the cosine_more tree and"
        log "  edit its cd path, or run:  cd $HERE && $PY tsmax_map.py --nbins 24 --nper 6 --workers 46"
    fi
fi

log "done"
