#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# gather_runtime.sh
#
# Run this script ON PERLMUTTER (or wherever WRF-Chem is compiled) to collect
# the pre-built executables and every shared library they depend on into a
# self-contained staging directory called  docker_context/
#
# Nothing in WRF_DIR is modified — this script only READS/COPIES from it.
#
# Usage (on Perlmutter):
#   bash gather_runtime.sh
#
# Then transfer docker_context/ to your Docker build host:
#   rsync -av docker_context/ <your-host>:/path/to/build/docker_context/
#
# Finally build the image on the Docker host:
#   docker build -f Dockerfile.prebuilt -t wrf-chem-prebuilt docker_context/
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

# ── Paths — edit only these if your layout differs ───────────────────────────
WRF_DIR="/pscratch/sd/h/heroplr/RGMA_homecopy/WRF_test_dm"

FTORCH_INSTALL="$HOME/opt/ftorch"           # has lib64/libftorch.so + include/
TORCH_ROOT="/global/homes/h/heroplr/opt/libtorch-cpu"   # has lib/libtorch*.so

STAGE_DIR="$(pwd)/docker_context"           # output staging directory

# ─────────────────────────────────────────────────────────────────────────────

echo "=== WRF-Chem container staging script ==="
echo "Source WRF   : $WRF_DIR"
echo "FTorch       : $FTORCH_INSTALL"
echo "LibTorch     : $TORCH_ROOT"
echo "Staging into : $STAGE_DIR"
echo ""

# ── 1. Create staging sub-directories ────────────────────────────────────────
mkdir -p \
    "$STAGE_DIR/wrf/main" \
    "$STAGE_DIR/wrf/run" \
    "$STAGE_DIR/ftorch_libs" \
    "$STAGE_DIR/libtorch_libs" \
    "$STAGE_DIR/runtime_libs"

# ── 2. Copy WRF executables ───────────────────────────────────────────────────
echo "[1/5] Copying WRF executables..."
for exe in wrf.exe real.exe ndown.exe; do
    src="$WRF_DIR/main/$exe"
    if [ -f "$src" ]; then
        cp -v "$src" "$STAGE_DIR/wrf/main/"
    fi
done

# ── 3. Copy WRF run-directory data files (input tables, chem data, etc.) ─────
# Copies only regular files / symlink targets — skips nested test sub-dirs.
echo "[2/5] Copying WRF run-directory data files..."
rsync -a --exclude='*.exe' \
    "$WRF_DIR/run/" "$STAGE_DIR/wrf/run/"

# ── 4. Copy FTorch shared libraries ──────────────────────────────────────────
echo "[3/5] Copying FTorch libraries..."
FTORCH_LIB_DIR=""
if   [ -d "$FTORCH_INSTALL/lib64" ]; then FTORCH_LIB_DIR="$FTORCH_INSTALL/lib64"
elif [ -d "$FTORCH_INSTALL/lib"   ]; then FTORCH_LIB_DIR="$FTORCH_INSTALL/lib"
else echo "WARNING: cannot find FTorch lib directory under $FTORCH_INSTALL"; fi

if [ -n "$FTORCH_LIB_DIR" ]; then
    find "$FTORCH_LIB_DIR" -name "*.so*" -exec cp -Pv {} "$STAGE_DIR/ftorch_libs/" \;
fi

# ── 5. Copy LibTorch shared libraries ────────────────────────────────────────
echo "[4/5] Copying LibTorch libraries..."
if [ -d "$TORCH_ROOT/lib" ]; then
    find "$TORCH_ROOT/lib" -name "*.so*" -exec cp -Pv {} "$STAGE_DIR/libtorch_libs/" \;
fi

# ── 6. Collect ALL other runtime shared-library dependencies via ldd ──────────
echo "[5/5] Collecting transitive runtime library dependencies via ldd..."

# Paths to skip — these will be provided by the container base image
SKIP_PREFIXES=(
    "/lib64/ld-"
    "linux-vdso"
    "libpthread"
    "libdl"
    "libc.so"
    "libm.so"
    "librt.so"
    "libutil"
    "libresolv"
    "libnsl"
)

copy_ldd_deps() {
    local exe="$1"
    ldd "$exe" 2>/dev/null | awk '{print $3}' | grep -E '^/' | while read -r lib; do
        skip=false
        for prefix in "${SKIP_PREFIXES[@]}"; do
            if [[ "$lib" == *"$prefix"* ]]; then
                skip=true
                break
            fi
        done
        # Also skip anything already in ftorch or libtorch staging
        [[ "$lib" == *ftorch* ]] && skip=true
        [[ "$lib" == *libtorch* ]] && skip=true
        [[ "$lib" == *torch* && "$lib" == *.so* ]] && skip=true

        if [ "$skip" = false ] && [ -f "$lib" ]; then
            dest="$STAGE_DIR/runtime_libs/$(basename "$lib")"
            if [ ! -e "$dest" ]; then
                cp -Pv "$lib" "$dest"
            fi
        fi
    done
}

for exe in "$STAGE_DIR/wrf/main/"*.exe; do
    [ -f "$exe" ] && copy_ldd_deps "$exe"
done

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo "=== Staging complete ==="
du -sh "$STAGE_DIR"/*/
echo ""
echo "Next steps:"
echo "  1. Transfer docker_context/ to your Docker build host"
echo "     rsync -av docker_context/ <host>:/path/to/build/docker_context/"
echo "  2. Copy Dockerfile.prebuilt to the same directory"
echo "  3. docker build -f Dockerfile.prebuilt -t wrf-chem-prebuilt docker_context/"
