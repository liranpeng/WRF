#!/bin/bash
# =============================================================================
# check_jobs.sh -- one-screen status of the four 20170714 WRF cases.
#
#   ./check_jobs.sh          print status once
#   ./check_jobs.sh -w       refresh every 60 s until every case hits the target
#   ./check_jobs.sh -w 120   refresh every 120 s
#
# Columns:
#   JOB       SLURM id + state, or "idle" if nothing is queued for that case
#   RESTART   newest COMPLETE wrfrst (truncated / still-being-written skipped)
#   SIM       simulated minutes completed
#   REMAIN    simulated minutes still to run to reach the 5 h target
# =============================================================================

set -uo pipefail

BASE=/scratch/07088/tg863871/Perlm_Backup/WRF_stam3_ml_mixout_bce_lr1e-4_cosine_more_fix/test
CASES=(20170714_1aer_org 20170714_1aer_mid 20170714_3aer_org 20170714_3aer_mid)
SUBMIT=submit_run_WRF_skx_dev_new_short.sh

SIM_START="2017-07-15 09:02:00"
SIM_HOURS=5
STALE_SECS=180
USER_NAME=$(whoami)

WATCH=0; INTERVAL=60
if [ "${1:-}" = "-w" ]; then WATCH=1; [ -n "${2:-}" ] && INTERVAL="$2"; fi

start_epoch=$(date -u -d "$SIM_START" +%s)
target_epoch=$(( start_epoch + SIM_HOURS*3600 ))

# Identify jobs by WorkDir, never by job name -- names like "14_3aer_mid" are
# reused across WRF_dm / cosine_more / cosine_more_fix and would mis-attribute
# another codebase's job to this campaign.
declare -A JOBMAP
refresh_jobmap() {
    JOBMAP=()
    local jid part st nm wd rp tag
    while read -r jid part st nm; do
        [ -z "$jid" ] && continue
        wd=$(scontrol show job "$jid" 2>/dev/null | tr ' ' '\n' | sed -n 's/^WorkDir=//p' | head -1)
        [ -z "$wd" ] && continue
        rp=$(readlink -f "$wd" 2>/dev/null) || continue
        # R=running P=pending, partition abbreviated, "!" marks a legacy name
        case "$st" in RUNNING) tag=R ;; PENDING) tag=P ;; *) tag=${st:0:1} ;; esac
        [ "${nm#cmf_}" = "$nm" ] && tag="${tag}!"
        JOBMAP["$rp"]="${JOBMAP[$rp]:+${JOBMAP[$rp]} }${jid}/${part#skx}${tag}"
    done < <(squeue -u "$USER_NAME" -h -o "%i %P %T %j" 2>/dev/null)
}

latest_good_rst() {
    local dir="$1" modal now f sz mt
    shopt -s nullglob; local files=("$dir"/wrfrst_d01_*); shopt -u nullglob
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

show() {
    echo "===== WRF campaign status  $(date +'%Y-%m-%d %H:%M:%S') ====="
    printf "target: %s + %d h = %s\n\n" "$SIM_START" "$SIM_HOURS" \
           "$(date -u -d "@$target_epoch" +'%Y-%m-%d %H:%M:%S')"
    printf "%-20s %-26s %-22s %8s %8s\n" CASE JOB RESTART SIM REMAIN
    printf "%-20s %-26s %-22s %8s %8s\n" -------------------- -------------------------- ---------------------- -------- --------

    local ndone=0
    refresh_jobmap
    for c in "${CASES[@]}"; do
        local dir="$BASE/$c" jobstr="idle" rp rst t simmin remain
        rp=$(readlink -f "$dir" 2>/dev/null)
        [ -n "${JOBMAP[$rp]:-}" ] && jobstr="${JOBMAP[$rp]}"

        rst=$(latest_good_rst "$dir")
        if [ -z "$rst" ]; then
            printf "%-20s %-26s %-22s %8s %8s\n" "$c" "$jobstr" "(none complete)" "-" "-"
            continue
        fi
        t=$(basename "$rst" | sed 's/^wrfrst_d01_//')
        local t_epoch; t_epoch=$(date -u -d "$(echo "$t" | tr '_' ' ')" +%s)
        simmin=$(( (t_epoch - start_epoch) / 60 ))
        remain=$(( (target_epoch - t_epoch) / 60 ))
        [ "$remain" -lt 0 ] && remain=0
        [ "$remain" -eq 0 ] && ndone=$(( ndone + 1 ))
        printf "%-20s %-26s %-22s %8s %8s\n" "$c" "$jobstr" "$t" "${simmin}m" "${remain}m"
    done
    echo
    echo "$ndone of ${#CASES[@]} cases have reached the target."
    return $(( ${#CASES[@]} - ndone ))
}

if [ $WATCH -eq 0 ]; then
    show; exit 0
fi

while true; do
    clear 2>/dev/null
    if show; then
        echo "ALL CASES COMPLETE."
        exit 0
    fi
    sleep "$INTERVAL"
done
