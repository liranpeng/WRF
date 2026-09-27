#!/bin/bash
# build_wrf_with_ftorch.sh — WRF (dmpar, GNU) + FTorch + LibTorch on Perlmutter
# Fixes:
#  - Restores LMOD defaults before loading modules (Perlmutter requirement)
#  - Safely deactivates any active conda env (avoids "unbound variable" in hooks)
#  - Ensures Cray wrapper compilers (ftn/cc/CC) are used
#  - Uses installed FTorch include/lib paths
#  - Appends FTorch/LibTorch flags to configure.wrf

set -euo pipefail

########## Reset system modules cleanly (Perlmutter) ##########
if [ -f /opt/cray/pe/cpe/24.07/restore_lmod_system_defaults.sh ]; then
  set +u
  source /opt/cray/pe/cpe/24.07/restore_lmod_system_defaults.sh
  set -u
fi
# Make sure `module` exists for non-interactive shells
if ! type module &>/dev/null; then
  set +u
  [ -f /etc/profile.d/z00_lmod.sh ] && source /etc/profile.d/z00_lmod.sh
  [ -f /etc/profile.d/modules.sh ] && source /etc/profile.d/modules.sh
  set -u
fi

########## Leave any active conda env safely (its hooks can trip -u) ##########
if type conda &>/dev/null; then
  set +u
  conda deactivate || true
  conda deactivate || true
  set -u
fi

########## User toggles ##########
doclean=true          # true if WRF source changed since last build
doclean_all=false     # true if previously compiled with different options
runconf=true          # run ./configure
docompile=true        # run ./compile
debug=false           # build with -g and no O flags
imach="pm"            # Perlmutter label

########## Paths (EDIT if needed) ##########
# WRF source
export WRF_DIR="/pscratch/sd/h/heroplr/RGMA_homecopy/WRF_test_dm"

# FTorch (use your installed artifacts; adjust if different)
export FTORCH_MOD="$HOME/opt/ftorch/include/ftorch"   # has ftorch.mod
export FTORCH_LIB="$HOME/opt/ftorch/lib64"            # has libftorch.so

# LibTorch libs to link against (NERSC PyTorch 2.6.0 wheel libs work for linking)
export LIBTORCH_LIB="/global/common/software/nersc9/pytorch/2.6.0/lib/python3.12/site-packages/torch/lib"

# Auto-detect CUDA LibTorch (1 if libtorch_cuda.so present)
if [ -f "${LIBTORCH_LIB}/libtorch_cuda.so" ]; then
  export USE_FTORCH_CUDA="1"
else
  export USE_FTORCH_CUDA="0"
fi

# Optional: bake rpath so runtime doesn't need LD_LIBRARY_PATH
export LIBTORCH_RPATH="${LIBTORCH_LIB}"

########## Modules / toolchain ##########
module load cpu  
module load PrgEnv-gnu 

#module for WRF file I/O
#order of loading matters!
module load cray-hdf5  #required to load netcdf library
module load cray-netcdf 
module load cray-parallel-netcdf

module list

# Ensure Cray wrappers are first on PATH (avoid user 'cc' scripts)
hash -r
if ! which cc | grep -q '^/opt/cray/pe/'; then
  export PATH="/opt/cray/pe/craype/default/bin:/opt/cray/pe/bin:$PATH"
  hash -r
fi

echo "Compilers:"
ftn --version || true
cc  --version || true
CC  --version || true

########## NetCDF/HDF5 env ##########
export NETCDF_classic=1
export WRFIO_NCD_LARGE_FILE_SUPPORT=1
export USE_NETCDF4_FEATURES=0

export HDF5="$HDF5_DIR"
export HDF5_LIB="$HDF5_DIR/lib"
export HDF5_BIN="$HDF5_DIR/bin"

export NETCDF="$NETCDF_DIR"
export NETCDF_BIN="$NETCDF_DIR/bin"
export NETCDF_LIB="$NETCDF_DIR/lib"

export PNETCDF="$PNETCDF_DIR"
export PNETCDF_QUILT="0"

# Paths
export PATH="${NETCDF_BIN}:${HDF5_BIN}:${PATH}"
export LD_LIBRARY_PATH="${NETCDF_LIB}:${LD_LIBRARY_PATH:-}"

########## Sanity checks ##########
echo "---- Sanity checks ----"
for f in \
  "$FTORCH_MOD/ftorch.mod" \
  "$FTORCH_LIB/libftorch.so" \
  "${LIBTORCH_LIB}/libtorch.so" \
  "${LIBTORCH_LIB}/libc10.so"
do
  if [ ! -f "$f" ]; then
    echo "ERROR: Missing required file: $f"
    exit 1
  fi
done

echo "LD_LIBRARY_PATH: $LD_LIBRARY_PATH"
echo "PATH: $PATH"
echo "NETCDF: $NETCDF  | NETCDF_LIB: $NETCDF_LIB"
echo "HDF5:   $HDF5    | HDF5_LIB:   $HDF5_LIB"
echo "PNETCDF: ${PNETCDF}"
echo "PNETCDF_QUILT: ${PNETCDF_QUILT}"
echo "FTORCH_MOD: ${FTORCH_MOD}"
echo "FTORCH_LIB: ${FTORCH_LIB}"
echo "LIBTORCH_LIB: ${LIBTORCH_LIB}"
echo "USE_FTORCH_CUDA: ${USE_FTORCH_CUDA}"

########## Build WRF ##########
idate=$(date "+%Y-%m-%d-%H_%M")
cd "$WRF_DIR"

if [ "$doclean_all" = true ]; then
  ./clean -a
fi
if [ "$doclean" = true ]; then
  ./clean
fi

if [ "$runconf" = true ]; then
  if [ "$debug" = true ]; then
    ./configure -d
  else
    ./configure
  fi

  configfile="${WRF_DIR}/configure.wrf"
  if [ ! -f "$configfile" ]; then
    echo "ERROR: ${configfile} not found after ./configure"
    exit 1
  fi

  echo "Patching ${configfile} for Perlmutter + FTorch"

  # Use Cray wrappers in MPI builds (GNU option 34 expected)
  sed -i 's/-cc=\$(SCC)/ /' "${configfile}"
  sed -i 's/mpif90/ftn/'    "${configfile}"
  sed -i 's/mpicc/cc/'      "${configfile}"

  # ---- Include FTorch Fortran module path ----
  sed -i "s|^FFLAGS\s*=.*|& -I${FTORCH_MOD}|" "${configfile}"
  sed -i "s|^FCFLAGS\s*=.*|& -I${FTORCH_MOD}|" "${configfile}"

  # ---- Link FTorch + LibTorch (CPU or CUDA) ----
  if [ "${USE_FTORCH_CUDA}" = "1" ]; then
    APPEND_LIBS="-L${FTORCH_LIB} -lftorch \
 -L${LIBTORCH_LIB} -Wl,-rpath,${LIBTORCH_RPATH} \
 -ltorch -ltorch_cpu -ltorch_cuda -lc10 \
 -lstdc++ -ldl -lpthread -lcudart -lcuda -lnvToolsExt"
  else
    APPEND_LIBS="-L${FTORCH_LIB} -lftorch \
 -L${LIBTORCH_LIB} -Wl,-rpath,${LIBTORCH_RPATH} \
 -ltorch -ltorch_cpu -lc10 \
 -lstdc++ -ldl -lpthread"
  fi

  if grep -q '^LIB_EXTERNAL\s*=' "${configfile}"; then
    sed -i "s|^LIB_EXTERNAL\s*=.*|& ${APPEND_LIBS}|" "${configfile}"
  else
    printf "\nLIB_EXTERNAL = %s\n" "${APPEND_LIBS}" >> "${configfile}"
  fi

  # Also extend final linker flags for safety
  if grep -q '^LDFLAGS\s*=' "${configfile}"; then
    sed -i "s|^LDFLAGS\s*=.*|& -L${FTORCH_LIB} -Wl,-rpath,${LIBTORCH_RPATH}|" "${configfile}"
  fi
fi

if [ "$docompile" = true ]; then
  export J="-j 4"
  bldlog="compile_em_${idate}_${imach}.log"
  echo "compile log file is ${bldlog}"

  ./compile em_real &> "${bldlog}" || true

  set +e
  grep "Problems building executables" "${bldlog}" >/dev/null 2>&1
  RESULT=$?
  set -e

  if [ $RESULT -eq 0 ]; then
    echo "compile failed, check ${bldlog}"
    tail -n 120 "${bldlog}" || true
    exit 1
  else
    echo "compile success"
  fi
fi

########## Runtime note ##########
# If you did not embed an rpath elsewhere, you may need at run time:
#   export LD_LIBRARY_PATH=${FTORCH_LIB}:${LIBTORCH_LIB}:$LD_LIBRARY_PATH
