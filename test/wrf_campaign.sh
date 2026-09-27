#!/bin/bash
# =============================================================================
# wrf_campaign.sh -- auto-restart driver for the four 20170714 WRF cases
#                    in the cosine_more_fix tree.
#
# STRATEGY
#   For each case, race a long skx job (12 h) against short skx-dev jobs (2 h):
#   skx-dev usually starts quickly but only buys 2 h; skx waits longer in the
#   queue but then runs 12 h uninterrupted.  Both are submitted.  Once the long
#   skx job is RUNNING, this driver cancels that case's pending skx-dev jobs.
#
#   Every pass the driver rewrites namelist.input to the newest COMPLETE
#   wrfrst, so whichever job starts next always resumes from the latest good
#   restart.  Rewriting the namelist under a running job is safe: WRF reads it
#   only at startup.
#
# TWO SAFETY PROPERTIES THAT MATTER
#
#   1. Jobs are matched to cases by SLURM WorkDir, never by job name.
#      Names like "14_3aer_mid" are reused by /scratch/.../WRF_dm and
#      /scratch/.../cosine_more.  Name matching attributes another codebase's
#      job to this campaign and stalls the case forever.
#
#   2. Two WRF instances in one directory would corrupt each other's
#      wrfout/wrfrst.  --dependency=singleton is NOT used for this: singleton
#      is strict FIFO per job name, so the short skx-dev job ends up waiting on
#      the 12 h skx job submitted before it, which is the opposite of the
#      intended race.  Mutual exclusion is instead enforced at runtime by a
#      .wrf_running.lock in each case directory (see the guard added to
#      submit_run_WRF_skx_dev_new_short.sh): whichever job starts second sees a
#      live lock and stands down immediately.
#
#   3. Stall detection: if a RUNNING job has produced no new wrfrst/wrfout/rsl
#      output for STALL_SECS while having been running at least that long, it
#      is cancelled and a WARNING is written to this log.  Restarts normally
#      land every ~10 min, so a long silence means the job is wedged.
#
#   Partition, wall time and job name are passed on the sbatch command line,
#   overriding the #SBATCH directives inside the submit script.
#
# JOB NAMES  cmf_<case>, unique to this tree, so a job here is never confused
#            with the identically named jobs in WRF_dm / cosine_more.
#
# USAGE
#   ./wrf_campaign.sh                 run the loop (checks every 10 min)
#   ./wrf_campaign.sh --once          single pass, then exit
#   ./wrf_campaign.sh --dry-run       show actions, submit/cancel nothing
#   nohup ./wrf_campaign.sh > campaign.log 2>&1 &
# =============================================================================

set -uo pipefail

BASE=/scratch/07088/tg863871/Perlm_Backup/WRF_stam3_ml_mixout_bce_lr1e-4_cosine_more_fix/test
CASES=(20170714_1aer_org 20170714_1aer_mid 20170714_3aer_org 20170714_3aer_mid)
SUBMIT=submit_run_WRF_skx_dev_new_short.sh   # body only; -p/-t/-J overridden below

LONG_PART=skx;      LONG_TIME=12:00:00
SHORT_PART=skx-dev; SHORT_TIME=02:00:00

# ---- Campaign target -------------------------------------------------------
SIM_START="2017-07-15 09:02:00"
SIM_HOURS=5
SIM_START_EPOCH=$(date -u -d "$SIM_START" +%s)
TARGET_EPOCH=$(( SIM_START_EPOCH + SIM_HOURS * 3600 ))
TARGET_END=$(date -u -d "@${TARGET_EPOCH}" +"%Y-%m-%d_%H:%M:%S")

POLL_SECS=600      # check every 10 minutes
STALE_SECS=180     # a restart must be untouched this long to count as complete
STALL_SECS=2700    # 45 min with no new output from a running job => stalled
UNSTICK=1          # 1 = on a stall, run unstick_case.sh (cldchem-off recovery)
                   #     instead of just cancelling the wedged job
USER_NAME=$(whoami)

DRY_RUN=0; ONCE=0
for a in "$@"; do
  case "$a" in
    --dry-run)     DRY_RUN=1 ;;
    --once)        ONCE=1 ;;
    --no-unstick)  UNSTICK=0 ;;
    -h|--help) sed -n '2,45p' "$0"; exit 0 ;;
    *) echo "unknown option: $a" >&2; exit 2 ;;
  esac
done

log() { echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*"; }
run() { if [ $DRY_RUN -eq 1 ]; then log "  [dry-run] $*"; else "$@"; fi; }

# cmf_1aer_org, cmf_3aer_mid, ...  (unique to this tree)
job_name() { echo "cmf_${1#20170714_}"; }

to_epoch() { date -u -d "$(echo "$1" | tr '_' ' ')" +%s; }
rst_time() { basename "$1" | sed 's/^wrfrst_d01_//'; }

# ---- latest_good_rst <casedir> --------------------------------------------
# Newest restart whose size matches the modal (= full) size and which has not
# been written to for STALE_SECS.  This is what rejects a half-written file
# such as the 33 GB wrfrst_d01_2017-07-15_09:14:00 left by a job that died
# mid-write, when the complete ones are all 48,118,443,880 bytes.
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

# ---- job map: realpath(WorkDir) -> "jobid:partition:state:name ..." --------
declare -A JOBMAP
refresh_jobmap() {
    JOBMAP=()
    local jid part st nm el wd rp
    while read -r jid part st nm el; do
        [ -z "$jid" ] && continue
        wd=$(scontrol show job "$jid" 2>/dev/null | tr ' ' '\n' | sed -n 's/^WorkDir=//p' | head -1)
        [ -z "$wd" ] && continue
        rp=$(readlink -f "$wd" 2>/dev/null) || continue
        JOBMAP["$rp"]="${JOBMAP[$rp]:-} ${jid}:${part}:${st}:${nm}:$(elapsed_secs "$el")"
    done < <(squeue -u "$USER_NAME" -h -o "%i %P %T %j %M" 2>/dev/null)
}

# ---- elapsed_secs "1-02:03:04" | "02:03:04" | "03:04" ----------------------
elapsed_secs() {
    local e="${1:-0}" d=0 t
    case "$e" in *-*) d=${e%%-*}; t=${e#*-} ;; *) t="$e" ;; esac
    local IFS=:; set -- $t
    case $# in
        3) echo $(( 10#${d:-0}*86400 + 10#$1*3600 + 10#$2*60 + 10#$3 )) ;;
        2) echo $(( 10#${d:-0}*86400 + 10#$1*60 + 10#$2 )) ;;
        *) echo 0 ;;
    esac
}

# ---- newest_output_age <casedir> : seconds since this case last wrote ------
newest_output_age() {
    local dir="$1" newest
    newest=$(find "$dir" -maxdepth 1 \
                \( -name 'wrfrst_d01_*' -o -name 'wrfout_d01_*' \
                   -o -name 'rsl.error.0000' -o -name 'wrf.runtime.*.log' \) \
                -printf '%T@\n' 2>/dev/null | sort -rn | head -1)
    [ -z "$newest" ] && { echo 999999; return; }
    echo $(( $(date +%s) - ${newest%.*} ))
}
case_jobs() {
    local rp; rp=$(readlink -f "$1" 2>/dev/null) || return 1
    echo "${JOBMAP[$rp]:-}"
}

# ---- set_start <namelist> <YYYY-MM-DD_HH:MM:SS> : only rewrites if changed --
set_start() {
    local nl="$1" t="$2"
    local Y=${t:0:4} M=${t:5:2} D=${t:8:2} h=${t:11:2} m=${t:14:2}
    local cur_h cur_m
    cur_h=$(sed -n 's/^ *start_hour *= *\([0-9]*\).*/\1/p'   "$nl" | head -1)
    cur_m=$(sed -n 's/^ *start_minute *= *\([0-9]*\).*/\1/p' "$nl" | head -1)
    if [ "$((10#${cur_h:-99}))" -eq "$((10#$h))" ] && [ "$((10#${cur_m:-99}))" -eq "$((10#$m))" ]; then
        return 1   # already current
    fi
    if [ $DRY_RUN -eq 1 ]; then log "  [dry-run] would set start=$t in $nl"; return 0; fi
    cp -p "$nl" "$nl.bak.$(date +%Y%m%d_%H%M%S)"
    sed -i \
      -e "s/^\( *start_year *=\).*/\1 ${Y},/" \
      -e "s/^\( *start_month *=\).*/\1 ${M},/" \
      -e "s/^\( *start_day *=\).*/\1 ${D},/" \
      -e "s/^\( *start_hour *=\).*/\1 ${h},/" \
      -e "s/^\( *start_minute *=\).*/\1 ${m},/" \
      -e "s/^\( *restart *=\).*/\1 .true.,/" \
      "$nl"
    return 0
}

# ---- submit <casedir> <name> <partition> <walltime> ------------------------
submit() {
    local dir="$1" name="$2" part="$3" tl="$4" out rc jid
    if [ $DRY_RUN -eq 1 ]; then
        log "  [dry-run] sbatch -J $name -p $part -t $tl $SUBMIT"
        return 0
    fi
    out=$(cd "$dir" && sbatch -J "$name" -p "$part" -t "$tl" "$SUBMIT" 2>&1)
    rc=$?
    # TACC's sbatch prints a banner before "Submitted batch job NNNNNNN".
    jid=$(echo "$out" | grep -oE 'Submitted batch job [0-9]+' | grep -oE '[0-9]+' | tail -1)
    if [ $rc -ne 0 ] || [ -z "$jid" ]; then
        log "  SUBMIT FAILED ($part): $(echo "$out" | tail -3 | tr '\n' ' ')"
        return 1
    fi
    log "  submitted $jid  ($part, $tl)"
    return 0
}

# =============================== main loop ==================================
log "campaign start | target ${TARGET_END} (${SIM_HOURS} h from ${SIM_START}) | poll ${POLL_SECS}s"
[ $DRY_RUN -eq 1 ] && log "DRY RUN -- nothing submitted or cancelled"

while true; do
    all_done=1
    refresh_jobmap

    for c in "${CASES[@]}"; do
        dir="$BASE/$c"
        [ -d "$dir" ] || { log "$c: MISSING directory"; continue; }

        # unstick_case.sh drops .campaign_pause here while it walks a wedged
        # case through the cldchem-off recovery.  Hands off entirely: no
        # namelist rewrite, no submit, no cancel -- it is driving that case.
        if [ -f "$dir/.campaign_pause" ]; then
            log "$c: PAUSED (.campaign_pause present) -- unstick_case.sh has it"
            all_done=0
            continue
        fi

        name=$(job_name "$c")
        jobs=$(case_jobs "$dir")

        rst=$(latest_good_rst "$dir")
        if [ -z "$rst" ]; then
            log "$c: no complete wrfrst yet [jobs:${jobs:- none}]"
            all_done=0; continue
        fi
        t=$(rst_time "$rst"); t_epoch=$(to_epoch "$t")

        # ---- target reached: stop and release any remaining jobs ----
        if [ "$t_epoch" -ge "$TARGET_EPOCH" ]; then
            if [ -n "$jobs" ]; then
                for e in $jobs; do
                    log "$c: DONE at $t -- cancelling ${e%%:*}"
                    run scancel "${e%%:*}"
                done
            else
                log "$c: DONE (restart $t >= $TARGET_END)"
            fi
            continue
        fi
        all_done=0

        # ---- keep the namelist pointed at the newest good restart ----
        if set_start "$dir/namelist.input" "$t"; then
            log "$c: namelist start -> $t"
        fi

        # ---- inspect this case's jobs ----
        # A job in this directory that does NOT carry this campaign's name is a
        # legacy submission (e.g. 3365139 "14_3aer"). --dependency=singleton
        # keys on the job name, so it cannot protect a cmf_* job from running
        # concurrently with one of those -- two WRF instances in one directory
        # would corrupt each other. While any legacy job is present we keep the
        # namelist current but submit nothing, and take over once it drains.
        long_running=0; have_long=0; have_short=0; short_jobs=""; legacy=""
        stalled=""
        for e in $jobs; do
            jid=${e%%:*}; rest=${e#*:}; part=${rest%%:*}
            rest=${rest#*:}; st=${rest%%:*}
            rest=${rest#*:}; nm=${rest%%:*}; el=${rest#*:}

            # ---- stall check: running, but nothing written for a long time --
            if [ "$st" = "RUNNING" ]; then
                age=$(newest_output_age "$dir")
                if [ "$age" -gt "$STALL_SECS" ] && [ "${el:-0}" -gt "$STALL_SECS" ]; then
                    log "$c: *** WARNING STALLED *** job $jid ($nm,$part) running ${el}s but no new"
                    log "$c: *** output for ${age}s (threshold ${STALL_SECS}s) ***"
                    stalled="$stalled $jid"
                    if [ $UNSTICK -eq 1 ] && [ $DRY_RUN -eq 0 ]; then
                        # Hand the case to the cldchem-off recovery: it cancels
                        # the wedged job itself, runs one restart interval with
                        # cloud chemistry off to get past the bad step, restores
                        # cldchem_onoff=1 and the start time, then unpauses.
                        log "$c: launching unstick_case.sh (cldchem-off recovery)"
                        setsid nohup ./unstick_case.sh "$c" --force \
                            > "unstick_${c}.log" 2>&1 < /dev/null &
                    else
                        log "$c: *** cancelling it (unstick disabled) ***"
                        run scancel "$jid"
                    fi
                    continue
                fi
            fi

            if [ "$nm" != "$name" ]; then
                legacy="$legacy ${jid}(${nm},${part},${st})"
                continue
            fi
            case "$part" in
                "$LONG_PART")  have_long=1;  [ "$st" = "RUNNING" ] && long_running=1 ;;
                "$SHORT_PART") have_short=1; short_jobs="$short_jobs ${jid}:${st}" ;;
            esac
        done

        if [ -n "$legacy" ]; then
            log "$c: at $t -- legacy job(s)$legacy still in queue; not submitting until they drain"
            continue
        fi

        # ---- long job is RUNNING: the skx job wins ----
        # Cancel EVERY skx-dev job for this case, running as well as queued.
        # A running one is cancelled because the skx job preempts it via the
        # lock anyway (see the guard in the submit script); cancelling here
        # releases the dev nodes instead of leaving the job to spin.  Killing a
        # dev job mid-restart-write can leave a truncated wrfrst, which
        # latest_good_rst already rejects on size.
        # have_short stays 0 afterwards, so no new skx-dev is submitted for
        # this case for as long as the skx job keeps running.
        if [ $long_running -eq 1 ] && [ -n "$short_jobs" ]; then
            for e in $short_jobs; do
                jid=${e%%:*}; st=${e#*:}
                log "$c: skx job RUNNING -- cancelling skx-dev $jid ($st)"
                run scancel "$jid"
            done
            have_short=0
        fi

        # ---- top up so one of each is in flight ----
        # Short first: skx-dev normally starts within minutes, so it begins
        # making progress while the long skx job is still waiting for nodes.
        if [ $have_short -eq 0 ] && [ $long_running -eq 0 ]; then
            log "$c: at $t -- submitting short ${SHORT_PART} job"
            submit "$dir" "$name" "$SHORT_PART" "$SHORT_TIME"
        fi
        if [ $have_long -eq 0 ]; then
            log "$c: at $t -- submitting long ${LONG_PART} job"
            submit "$dir" "$name" "$LONG_PART" "$LONG_TIME"
        fi
        [ $have_long -eq 1 ] && [ $have_short -eq 1 ] && \
            log "$c: at $t -- long+short already queued [$jobs]"
    done

    if [ $all_done -eq 1 ]; then
        log "ALL CASES REACHED ${TARGET_END} -- campaign complete"
        exit 0
    fi
    [ $ONCE -eq 1 ] && { log "--once given, exiting"; exit 0; }
    log "sleeping ${POLL_SECS}s"
    sleep "$POLL_SECS"
done
