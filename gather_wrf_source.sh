#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# gather_wrf_source.sh
#
# Run this script ON PERLMUTTER to copy the WRF-Chem source code into the
# Docker build context.  The original installation is NEVER modified.
#
# What it copies:   all WRF source files (.F, .f90, .c, .h, Registry, etc.)
# What it excludes: compiled objects (.o, .a, .mod), executables, build logs
#
# Usage (on Perlmutter):
#   bash gather_wrf_source.sh
#
# Then transfer docker_context/ to your Docker build host:
#   rsync -av docker_context/ <your-host>:/path/to/build/docker_context/
#
# Then build the image on the Docker host (from the directory that contains
# both Dockerfile and docker_context/):
#   docker build -t wrf-chem-local .
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

# ── Only edit these paths if your layout differs ─────────────────────────────
WRF_SRC="/pscratch/sd/h/heroplr/RGMA_homecopy/WRF_test_dm"
STAGE_DIR="$(pwd)/docker_context/wrf_src"

echo "=== WRF source staging script ==="
echo "Source : $WRF_SRC"
echo "Dest   : $STAGE_DIR"
echo "(The source directory is opened read-only — nothing will be modified)"
echo ""

mkdir -p "$STAGE_DIR"

# rsync copies source files and excludes all build artefacts.
# --links preserves symlinks (WRF uses them in the run/ directory).
rsync -a --links \
    --exclude='*.o'            \
    --exclude='*.a'            \
    --exclude='*.mod'          \
    --exclude='*.exe'          \
    --exclude='compile_*.log'  \
    --exclude='.git/'          \
    --exclude='main/wrf.exe'   \
    --exclude='main/real.exe'  \
    --exclude='main/ndown.exe' \
    --exclude='main/ideal.exe' \
    "$WRF_SRC/" "$STAGE_DIR/"

echo ""
echo "=== Done ==="
du -sh "$STAGE_DIR"
echo ""
echo "Next steps:"
echo "  1. Transfer docker_context/ to your Docker build host:"
echo "     rsync -av docker_context/ <host>:/path/to/build/docker_context/"
echo "  2. Place Dockerfile in the same directory as docker_context/"
echo "  3. docker build -t wrf-chem-local ."
