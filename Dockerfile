# ─────────────────────────────────────────────────────────────────────────────
# Dockerfile
#
# Builds a WRF-Chem container from YOUR modified source code.
# The source is NOT re-downloaded from GitHub — it is copied from the
# docker_context/wrf_src/ directory produced by  gather_wrf_source.sh
# (run once on Perlmutter; the original installation is never modified).
#
# Build context layout required:
#   docker_context/
#     wrf_src/    ← your WRF source tree (produced by gather_wrf_source.sh)
#
# Build command (from the directory that contains this Dockerfile
# and the docker_context/ folder):
#
#   docker build -t wrf-chem-local .
#
# Override FTorch / LibTorch versions at build time if needed:
#   docker build \
#     --build-arg LIBTORCH_VERSION=2.2.0 \
#     --build-arg FTORCH_TAG=v0.7.0      \
#     -t wrf-chem-local .
# ─────────────────────────────────────────────────────────────────────────────
FROM benjaminkirk/ncar-derecho-wrf:latest
SHELL ["/bin/bash", "-c"]

# ── Build-time arguments ──────────────────────────────────────────────────────
ARG LIBTORCH_VERSION=2.1.0
ARG FTORCH_TAG=v0.6.1

# ── Fixed install paths ───────────────────────────────────────────────────────
ENV TORCH_ROOT=/opt/libtorch \
    FTORCH_INSTALL=/opt/ftorch

# ── 1. Ensure cmake / wget / unzip are available ──────────────────────────────
RUN if command -v yum &>/dev/null; then \
        yum install -y cmake3 wget unzip && \
        ln -sf /usr/bin/cmake3 /usr/local/bin/cmake; \
    else \
        apt-get update && \
        apt-get install -y --no-install-recommends cmake wget unzip && \
        rm -rf /var/lib/apt/lists/*; \
    fi

# ── 2. Download CPU-only LibTorch ─────────────────────────────────────────────
RUN wget -q \
      "https://download.pytorch.org/libtorch/cpu/libtorch-cxx11-abi-shared-with-deps-${LIBTORCH_VERSION}%2Bcpu.zip" \
      -O /tmp/libtorch.zip && \
    unzip -q /tmp/libtorch.zip -d /opt/ && \
    rm /tmp/libtorch.zip

# ── 3. Build and install FTorch ───────────────────────────────────────────────
RUN git clone --branch ${FTORCH_TAG} --depth 1 \
        https://github.com/Cambridge-ICCS/FTorch.git /tmp/ftorch-src && \
    cmake -B /tmp/ftorch-build -S /tmp/ftorch-src \
          -DCMAKE_INSTALL_PREFIX=${FTORCH_INSTALL} \
          -DCMAKE_PREFIX_PATH=${TORCH_ROOT} \
          -DCMAKE_BUILD_TYPE=Release && \
    cmake --build /tmp/ftorch-build -j$(nproc) && \
    cmake --install /tmp/ftorch-build && \
    [ -d ${FTORCH_INSTALL}/lib64 ] || ln -sf ${FTORCH_INSTALL}/lib ${FTORCH_INSTALL}/lib64 && \
    rm -rf /tmp/ftorch-src /tmp/ftorch-build

ENV FTORCH_MOD=${FTORCH_INSTALL}/include/ftorch \
    FTORCH_LIB=${FTORCH_INSTALL}/lib64 \
    LIBTORCH_LIB=${TORCH_ROOT}/lib

ENV LD_LIBRARY_PATH="${FTORCH_INSTALL}/lib64:${TORCH_ROOT}/lib:${LD_LIBRARY_PATH:-}"

# ── 4. Copy YOUR modified WRF source into the container ──────────────────────
# (produced by gather_wrf_source.sh — no git clone, no network needed)
RUN rm -rf /container/WRF
COPY docker_context/wrf_src/ /container/WRF/

# ── 5. Configure, patch configure.wrf for FTorch, and compile WRF-Chem ───────
RUN source /container/config_env.sh && \
    export WRF_CHEM=1                      \
           NETCDF_classic=1                \
           WRFIO_NCD_LARGE_FILE_SUPPORT=1  \
           USE_NETCDF4_FEATURES=0          \
           PNETCDF_QUILT=0                 && \
    \
    cd /container/WRF && \
    ./clean -a && \
    \
    # option 34 = dmpar (pure MPI, GNU gfortran/gcc) — matches base image env
    printf "34\n1\n" | ./configure && \
    \
    # ── Patch configure.wrf for FTorch ─────────────────────────────────────
    CFG=configure.wrf && \
    \
    # Prepend Makefile variable definitions and LIB_LOCAL hook
    { cat << 'MKEOF'
FTORCH_LIB   := /opt/ftorch/lib64
LIBTORCH_LIB := /opt/libtorch/lib
# ---- FTorch + libtorch (CPU) -----------------------------------------------
LIB_FTORCH = \
  -L$(FTORCH_LIB) -lftorch \
  -L$(LIBTORCH_LIB) -Wl,-rpath,$(LIBTORCH_LIB):$(FTORCH_LIB) \
  -ltorch_cpu -lc10 -lstdc++ -ldl -lpthread
LIB_LOCAL = $(LIB_FTORCH)

MKEOF
    cat "${CFG}"; } > "${CFG}.new" && mv "${CFG}.new" "${CFG}" && \
    \
    # Add FTorch module search path to Fortran compiler flags
    sed -i "s|^FCFLAGS[[:space:]]*=.*|& -I${FTORCH_MOD}|" "${CFG}" && \
    sed -i "s|^FFLAGS[[:space:]]*=.*|& -I${FTORCH_MOD}|"  "${CFG}" && \
    \
    # Remove -cc=$(SCC) (not accepted by standard OpenMPI mpif90 wrapper)
    sed -i 's/-cc=\$(SCC)/ /' "${CFG}" && \
    \
    # Append belt-and-suspenders LIB_FTORCH block at end of file
    cat >> "${CFG}" << 'MKEOF2'

# ---- FTorch + libtorch (appended) ------------------------------------------
LIB_FTORCH = \
  -L$(FTORCH_LIB) -lftorch \
  -L$(LIBTORCH_LIB) -Wl,-rpath,$(LIBTORCH_LIB):$(FTORCH_LIB) \
  -ltorch_cpu -lc10 -lstdc++ -ldl -lpthread
MKEOF2
    \
    # ── Compile ──────────────────────────────────────────────────────────────
    ./compile -j 8 em_real 2>&1 | tee /container/compile_wrf.log && \
    test -f ./main/wrf.exe  || { echo "ERROR: wrf.exe not built"; exit 1; } && \
    test -f ./main/real.exe || { echo "ERROR: real.exe not built"; exit 1; } && \
    chmod -R a+rx /container

CMD ["/bin/bash"]
