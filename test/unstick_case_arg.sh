#!/bin/bash
# =============================================================================
# unstick_case.sh -- push a wedged case past the step it cannot get through,
#                    using the FEWEST possible restart intervals with cloud
#                    chemistry switched off.
#
# STRATEGY (escalating, minimal)
#   Rather than guessing how many steps to run with cldchem off, advance ONE
#   restart interval at a time and immediately test whether cldchem can go back
#   on.  The moment the model runs with chemistry on again, stop escalating and
#   hand the case back to the driver:
#
#     T = newest complete wrfrst
#     repeat, k = 1, 2, 3, ... MAX_OFF_STEPS:
#         cldchem_onoff = 0,0 ; start = T ; run until ONE new wrfrst ; stop
#         T = that new wrfrst                       <- k intervals now off
#         cldchem_onoff = 1,1 ; start = T ; submit and watch
#             -> produced a new wrfrst : SUCCESS, leave it running, stop here
#             -> stalled again         : cancel, loop (one more interval off)
#
#   So a stall that clears after 2 simulated minutes costs exactly one interval
#   with chemistry off; one that needs 8 minutes costs four.  Chemistry is
#   never off for longer than the stall actually requires.
#
#   The successful cldchem-on job is submitted under the driver's own job name
#   (cmf_<case>) and is deliberately NOT cancelled -- it keeps integrating and
#   the driver adopts it on the next pass.
#
# COORDINATION
#   A .campaign_pause file in the case directory makes wrf_campaign.sh skip the
#   case entirely (no namelist rewrite, no submit, no cancel) for the duration.
#   The other three cases keep running untouched.  Every namelist edit is backed
#   up first, and cldchem_onoff is restored to 1 on every exit path, including
#   failure, timeout and Ctrl-C.
#
# USAGE
#   ./unstick_case.sh 20170714_1aer_mid            # refuses unless stalled
#   ./unstick_case.sh 20170714_1aer_mid --force
#   ./unstick_case.sh 20170714_1aer_mid --dry-run
#   ./unstick_case.sh 20170714_1aer_mid --max-off 6
#
#   Run under nohup -- each interval is ~10 min of wall clock plus queue time:
#     nohup ./unstick_case.sh 20170714_1aer_mid > unstick_1aer_mid.log 2>&1 &
# =============================================================================

set -uo pipefail

BASE=/scratch/07088/tg863871/WRF_dm/test
SUBMIT=submit_run_WRF_skx_dev_new_short.sh
SHORT_PART=skx-dev; SHORT_TIME=02:00:00
STALE_SECS=180        # a wrfrst must be untouched this long to count as complete
STALL_SECS=2700       # running this long with no new output => stalled
POLL=60
MAX_WAIT=$((8*3600))  # per-phase ceiling, covers queue wait + integration
MAX_OFF_STEPS=8       # give up after this many intervals with chemistry off
USER_NAME=$(whoami)

CASE="${1:-}"; shift || true
DRY=0; FORCE=0
while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run) DRY=1 ;;
    --force)   FORCE=1 ;;
    --max-off) shift; MAX_OFF_STEPS="${1:-8}" ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
  shift
done
[ -z "$CASE" ] && { sed -n '2,45p' "$0"; exit 2; }
DIR="$BASE/$CASE"
[ -d "$DIR" ] || { echo "no such case dir: $DIR" >&2; exit 2; }
NL="$DIR/namelist.input"
PAUSE="$DIR/.campaign_pause"
CMF="arg_$(s=${CASE#20170714_}; echo ${s%_ARG})"

log() { echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*"; }
run() { if [ $DRY -eq 1 ]; then log "  [dry-run] $*"; else "$@"; fi; }

latest_good_rst() {
    local d="$1" modal now f sz mt
    shopt -s nullglob; local files=("$d"/wrfrst_d01_*); shopt -u nullglob
    [ ${#files[@]} -eq 0 ] && return 1
    modal=$(stat -c '%s' "${files[@]}" 2>/dev/null | sort | uniq -c | sort -rn | head -1 | awk '{print $2}')
    [ -z "$modal" ] && return 1
    now=$(date +%s)
    for f in $(printf '%s\n' "${files[@]}" | sort -r); do
        sz=$(stat -c '%s' "$f" 2>/dev/null) || continue
        mt=$(stat -c '%Y' "$f" 2>/dev/null) || continue
        [ "$sz" -lt "$modal" ] && continue
        [ $(( now - mt )) -lt "$STALE_SECS" ] && continue
        echo "$f"; return 0
    done
    return 1
}
rst_time() { basename "$1" | sed 's/^wrfrst_d01_//'; }

newest_output_age() {
    local d="$1" n
    n=$(find "$d" -maxdepth 1 \( -name 'wrfrst_d01_*' -o -name 'wrfout_d01_*' \
          -o -name 'rsl.error.0000' -o -name 'wrf.runtime.*.log' \) \
          -printf '%T@\n' 2>/dev/null | sort -rn | head -1)
    [ -z "$n" ] && { echo 999999; return; }
    echo $(( $(date +%s) - ${n%.*} ))
}

case_jobs() {
    local rp; rp=$(readlink -f "$DIR")
    local jid wd
    for jid in $(squeue -u "$USER_NAME" -h -o "%i" 2>/dev/null); do
        wd=$(scontrol show job "$jid" 2>/dev/null | tr ' ' '\n' | sed -n 's/^WorkDir=//p' | head -1)
        [ -z "$wd" ] && continue
        [ "$(readlink -f "$wd" 2>/dev/null)" = "$rp" ] || continue
        echo "${jid}:$(squeue -j "$jid" -h -o '%T' 2>/dev/null)"
    done
}
cancel_all() {
    local e
    for e in $(case_jobs); do
        log "  cancelling ${e%%:*} (${e#*:})"
        run scancel "${e%%:*}"
    done
}

set_cldchem() {
    local v="$1"
    [ $DRY -eq 1 ] && { log "  [dry-run] cldchem_onoff = $v, $v"; return; }
    cp -p "$NL" "$NL.bak.unstick.$(date +%Y%m%d_%H%M%S)"
    sed -i "s/^\( *cldchem_onoff *=\).*/\1 ${v},      ${v},/" "$NL"
    log "  $(grep -E '^ *cldchem_onoff' "$NL" | tr -s ' ')"
}
set_start() {
    local t="$1" Y=${1:0:4} M=${1:5:2} D=${1:8:2} h=${1:11:2} m=${1:14:2}
    [ $DRY -eq 1 ] && { log "  [dry-run] start -> $t"; return; }
    sed -i -e "s/^\( *start_year *=\).*/\1 ${Y},/" \
           -e "s/^\( *start_month *=\).*/\1 ${M},/" \
           -e "s/^\( *start_day *=\).*/\1 ${D},/" \
           -e "s/^\( *start_hour *=\).*/\1 ${h},/" \
           -e "s/^\( *start_minute *=\).*/\1 ${m},/" \
           -e "s/^\( *restart *=\).*/\1 .true.,/" "$NL"
    log "  start -> $t"
}

submit_job() {   # $1 = job name ; echoes job id
    local jname="$1" out jid
    if [ $DRY -eq 1 ]; then echo "DRYRUN"; return 0; fi
    out=$(cd "$DIR" && sbatch -J "$jname" -p "$SHORT_PART" -t "$SHORT_TIME" "$SUBMIT" 2>&1)
    jid=$(echo "$out" | grep -oE 'Submitted batch job [0-9]+' | grep -oE '[0-9]+' | tail -1)
    [ -z "$jid" ] && { log "  SUBMIT FAILED: $(echo "$out" | tail -3 | tr '\n' ' ')" >&2; return 1; }
    echo "$jid"
}

# watch <jobid> <T_before>
#   echoes the new restart time and returns 0  -- progressed
#   returns 1 -- stalled (RUNNING, no output for STALL_SECS)
#   returns 2 -- job left the queue with no new restart, or MAX_WAIT elapsed
watch() {
    local jid="$1" tbefore="$2" waited=0 r tt st age
    if [ $DRY -eq 1 ]; then echo "$tbefore"; return 0; fi
    while [ $waited -lt $MAX_WAIT ]; do
        r=$(latest_good_rst "$DIR")
        if [ -n "$r" ]; then
            tt=$(rst_time "$r")
            [ "$tt" != "$tbefore" ] && { echo "$tt"; return 0; }
        fi
        st=$(squeue -j "$jid" -h -o "%T" 2>/dev/null)
        if [ -z "$st" ]; then
            r=$(latest_good_rst "$DIR"); tt=$(rst_time "${r:-}")
            [ -n "${tt:-}" ] && [ "$tt" != "$tbefore" ] && { echo "$tt"; return 0; }
            return 2
        fi
        if [ "$st" = "RUNNING" ]; then
            age=$(newest_output_age "$DIR")
            [ "$age" -gt "$STALL_SECS" ] && return 1
        fi
        sleep $POLL; waited=$((waited + POLL))
    done
    return 2
}

# ============================== verify ======================================
log "=== unstick $CASE (escalating, max $MAX_OFF_STEPS intervals off) ==="
rst0=$(latest_good_rst "$DIR") || { log "no complete wrfrst -- refusing"; exit 1; }
T=$(rst_time "$rst0")
T_START="$T"
log "newest complete restart: $T"

jobs=$(case_jobs)
running=$(echo "$jobs" | grep -c ":RUNNING" || true)
age=$(newest_output_age "$DIR")
log "jobs: $(echo ${jobs:-none} | tr '\n' ' ') | newest output age: ${age}s"
if [ $FORCE -eq 0 ] && [ "$running" -gt 0 ] && [ "$age" -lt "$STALL_SECS" ]; then
    log "REFUSING: a job is RUNNING and wrote output ${age}s ago (< ${STALL_SECS}s)."
    log "This case is progressing normally. Re-run with --force to override."
    exit 3
fi

# ---- from here on, always restore chemistry and lift the pause -------------
cleanup() {
    local rc=$?
    if [ $DRY -eq 0 ]; then
        if ! grep -qE '^ *cldchem_onoff *= *1,' "$NL" 2>/dev/null; then
            log "cleanup: restoring cldchem_onoff = 1, 1"
            sed -i "s/^\( *cldchem_onoff *=\).*/\1 1,      1,/" "$NL"
        fi
        rm -f "$PAUSE"
    fi
    log "cleanup done (exit $rc)"
}
trap cleanup EXIT

log "pausing campaign driver for this case"
[ $DRY -eq 1 ] || : > "$PAUSE"
cancel_all
sleep 5

# ========================== escalating loop =================================
ok=0
for (( k=1; k<=MAX_OFF_STEPS; k++ )); do
    log "--- attempt $k: one more interval with cldchem OFF (total $k) ---"
    set_cldchem 0
    set_start "$T"
    jid=$(submit_job "unstick_${CASE#20170714_}") || exit 1
    log "  submitted $jid (cldchem off) from $T"
    Tnew=$(watch "$jid" "$T"); rc=$?
    case $rc in
      0) log "  advanced $T -> $Tnew with chemistry off"; T="$Tnew" ;;
      1) log "  *** STALLED even with cldchem off at $T -- the switch does not"
         log "  *** clear this one. Giving up; nothing more to try here."
         cancel_all; exit 5 ;;
      2) log "  job ended with no new restart -- giving up"; cancel_all; exit 4 ;;
    esac
    log "  stopping the cldchem-off job"
    cancel_all
    sleep 10

    log "--- testing cldchem ON from $T ---"
    set_cldchem 1
    set_start "$T"
    jid=$(submit_job "$CMF") || exit 1
    log "  submitted $jid (cldchem on) from $T"
    Ton=$(watch "$jid" "$T"); rc=$?
    case $rc in
      0) log "  SUCCESS: chemistry back on and integrating ($T -> $Ton)"
         T="$Ton"; ok=1 ;;
      1) log "  still stalls with chemistry on -- extending by one more interval"
         cancel_all; sleep 10 ;;
      2) log "  cldchem-on job ended with no new restart -- extending"
         cancel_all; sleep 10 ;;
    esac
    [ $ok -eq 1 ] && break
done

if [ $ok -ne 1 ]; then
    log "EXHAUSTED $MAX_OFF_STEPS intervals with chemistry off without clearing the stall"
    log "restoring cldchem_onoff = 1 and start = $T; driver will retry"
    set_cldchem 1; set_start "$T"
    exit 6
fi

# ============================== success =====================================
log "cldchem_onoff is back to 1,1 and job $jid is running -- leaving it alone"
log "lifting pause; wrf_campaign.sh adopts $CMF on its next pass"
[ $DRY -eq 1 ] || rm -f "$PAUSE"
log "=== done: $CASE cleared $T_START -> $T using $k interval(s) with cldchem off ==="
