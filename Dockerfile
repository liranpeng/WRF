# ─────────────────────────────────────────────────────────────────────────────
# WRF-Chem container with FTorch + LibTorch (CPU)
#
# Build:
#   docker build -t wrf-chem-ftorch .
#
# Override defaults at build time, e.g.:
#   docker build \
#     --build-arg LIBTORCH_VERSION=2.2.0 \
#     --build-arg FTORCH_TAG=v0.7.0      \
#     --build-arg WRF_BRANCH=master      \
#     -t wrf-chem-ftorch .
# ─────────────────────────────────────────────────────────────────────────────
FROM benjaminkirk/ncar-derecho-wrf:latest
SHELL ["/bin/bash", "-c"]

# ── Build-time arguments ──────────────────────────────────────────────────────
# LibTorch: CPU-only, cxx11-ABI build  (https://pytorch.org/get-started/locally)
ARG LIBTORCH_VERSION=2.1.0
# FTorch: Fortran/C++ ↔ LibTorch bridge (https://github.com/Cambridge-ICCS/FTorch)
ARG FTORCH_TAG=v0.6.1
# WRF source branch from github.com/liranpeng/WRF
ARG WRF_BRANCH=master

# ── Fixed install prefixes (used both at build- and run-time) ─────────────────
ENV TORCH_ROOT=/opt/libtorch \
    FTORCH_INSTALL=/opt/ftorch

# ─────────────────────────────────────────────────────────────────────────────
# 1. Make sure cmake / wget / unzip / git are available
#    (the base image may already have some of these)
# ─────────────────────────────────────────────────────────────────────────────
RUN if command -v yum &>/dev/null; then \
        yum install -y cmake3 wget unzip git && \
        ln -sf /usr/bin/cmake3 /usr/local/bin/cmake; \
    else \
        apt-get update && \
        apt-get install -y --no-install-recommends cmake wget unzip git && \
        rm -rf /var/lib/apt/lists/*; \
    fi

# ─────────────────────────────────────────────────────────────────────────────
# 2. Download CPU-only LibTorch (cxx11-ABI build, required by gfortran stack)
# ─────────────────────────────────────────────────────────────────────────────
RUN wget -q \
      "https://download.pytorch.org/libtorch/cpu/libtorch-cxx11-abi-shared-with-deps-${LIBTORCH_VERSION}%2Bcpu.zip" \
      -O /tmp/libtorch.zip && \
    unzip -q /tmp/libtorch.zip -d /opt/ && \
    rm /tmp/libtorch.zip && \
    echo "LibTorch ${LIBTORCH_VERSION} installed at ${TORCH_ROOT}"

# ─────────────────────────────────────────────────────────────────────────────
# 3. Build and install FTorch
#    FTorch generates ftorch.mod (Fortran module) and libftorch.so
# ─────────────────────────────────────────────────────────────────────────────
RUN git clone --branch ${FTORCH_TAG} --depth 1 \
        https://github.com/Cambridge-ICCS/FTorch.git /tmp/ftorch-src && \
    cmake -B /tmp/ftorch-build -S /tmp/ftorch-src \
          -DCMAKE_INSTALL_PREFIX=${FTORCH_INSTALL} \
          -DCMAKE_PREFIX_PATH=${TORCH_ROOT} \
          -DCMAKE_BUILD_TYPE=Release && \
    cmake --build /tmp/ftorch-build -j$(nproc) && \
    cmake --install /tmp/ftorch-build && \
    # Normalise: guarantee lib64/ exists regardless of what cmake chose
    [ -d ${FTORCH_INSTALL}/lib64 ] || ln -sf ${FTORCH_INSTALL}/lib ${FTORCH_INSTALL}/lib64 && \
    rm -rf /tmp/ftorch-src /tmp/ftorch-build && \
    echo "FTorch ${FTORCH_TAG} installed at ${FTORCH_INSTALL}"

# ── Runtime paths for FTorch / LibTorch ──────────────────────────────────────
ENV FTORCH_MOD=${FTORCH_INSTALL}/include/ftorch \
    FTORCH_LIB=${FTORCH_INSTALL}/lib64 \
    LIBTORCH_LIB=${TORCH_ROOT}/lib

ENV LD_LIBRARY_PATH="${FTORCH_INSTALL}/lib64:${TORCH_ROOT}/lib:${LD_LIBRARY_PATH}"

# ─────────────────────────────────────────────────────────────────────────────
# 4. Clone, configure, patch configure.wrf, and compile WRF-Chem
#
# Key differences vs the Perlmutter build script:
#   • No Cray-wrapper substitution (mpif90/mpicc kept as-is; no ftn/cc swap)
#   • -cc=$(SCC) flag removed (not compatible with standard OpenMPI)
#   • WRF_CHEM=1 exported so chemistry code is compiled in
#   • NetCDF classic / large-file-support / no-NC4-compression flags set
# ─────────────────────────────────────────────────────────────────────────────
RUN source /container/config_env.sh && \
    \
    export WRF_CHEM=1                       \
           NETCDF_classic=1                 \
           WRFIO_NCD_LARGE_FILE_SUPPORT=1   \
           USE_NETCDF4_FEATURES=0           \
           PNETCDF_QUILT=0                  && \
    \
    rm -rf /container/WRF && \
    git clone --branch ${WRF_BRANCH} --single-branch \
        https://github.com/liranpeng/WRF.git /container/WRF && \
    cd /container/WRF && \
    \
    ./clean -a && \
    \
    # Configure: option 35 = dm+sm GNU (gfortran/gcc + MPI + OpenMP)
    # option 1  = basic nesting
    printf "35\n1\n" | ./configure && \
    \
    # ── Patch configure.wrf for FTorch ───────────────────────────────────────
    CFG=configure.wrf && \
    \
    # Step A: prepend Makefile variable definitions (FTORCH_LIB, LIBTORCH_LIB)
    # and the LIB_FTORCH / LIB_LOCAL hook.
    # Single-quoted heredoc keeps $(…) as literal Makefile syntax.
    { cat << 'MKEOF'
FTORCH_LIB   := /opt/ftorch/lib64
LIBTORCH_LIB := /opt/libtorch/lib
# ---- FTorch + libtorch (CPU) ------------------------------------------------
LIB_FTORCH = \
  -L$(FTORCH_LIB) -lftorch \
  -L$(LIBTORCH_LIB) -Wl,-rpath,$(LIBTORCH_LIB):$(FTORCH_LIB) \
  -ltorch_cpu -lc10 -lstdc++ -ldl -lpthread
# Hook into WRF's standard local-library variable
LIB_LOCAL = $(LIB_FTORCH)

MKEOF
    cat "${CFG}"; } > "${CFG}.new" && mv "${CFG}.new" "${CFG}" && \
    \
    # Step B: append FTorch Fortran module search path to compiler flags
    sed -i "s|^FCFLAGS[[:space:]]*=.*|& -I${FTORCH_MOD}|" "${CFG}" && \
    sed -i "s|^FFLAGS[[:space:]]*=.*|& -I${FTORCH_MOD}|"  "${CFG}" && \
    \
    # Step C: remove -cc=$(SCC) (OpenMPI variant of mpif90 does not accept it)
    sed -i 's/-cc=\$(SCC)/ /' "${CFG}" && \
    \
    # Step D: append an explicit lib block at the end as belt-and-suspenders
    cat >> "${CFG}" << 'MKEOF2'

# ---- FTorch + libtorch (auto-appended, belt-and-suspenders) -----------------
LIB_FTORCH = \
  -L$(FTORCH_LIB) -lftorch \
  -L$(LIBTORCH_LIB) -Wl,-rpath,$(LIBTORCH_LIB):$(FTORCH_LIB) \
  -ltorch_cpu -lc10 -lstdc++ -ldl -lpthread
MKEOF2
    \
    # ── Compile ───────────────────────────────────────────────────────────────
    export J="-j 8" && \
    ./compile em_real 2>&1 | tee /container/compile_wrf.log && \
    \
    # Verify executables were produced
    test -f ./main/wrf.exe  || { echo "ERROR: wrf.exe not built — check /container/compile_wrf.log"; exit 1; } && \
    test -f ./main/real.exe || { echo "ERROR: real.exe not built — check /container/compile_wrf.log"; exit 1; } && \
    \
    chmod -R a+rx /container

CMD ["/bin/bash"]
