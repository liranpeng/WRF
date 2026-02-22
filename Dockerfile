# WRF-Chem + FTorch container
# Base: NCAR Derecho WRF image (openSUSE Leap, GNU compilers, MPI, NetCDF, HDF5)
#
# Build (Podman – rootless, network filesystem):
#   podman build --format docker \
#     -f /path/to/Dockerfile \
#     -t <image>:<tag> \
#     /path/to/wrf_source_dir
#
# Build (Docker / Podman with docker format):
#   docker build -t <image>:<tag> /path/to/wrf_source_dir
#
# --format docker is required by Podman to honour the SHELL instruction.
# Without it, /bin/sh is used and bash-specific syntax (source, [[, etc.) fails.

FROM benjaminkirk/ncar-derecho-wrf:latest

SHELL ["/bin/bash", "-c"]

# ── Build-time knobs ─────────────────────────────────────────────────────────
# LibTorch CPU-only cxx11-ABI wheel version
ARG LIBTORCH_VERSION=2.1.0
# FTorch tag – v1.0.0 is the first stable release (v0.6.x tags do not exist)
ARG FTORCH_TAG=v1.0.0
# WRF ./configure compiler option (34 = GNU dmpar on most installs)
ARG WRF_CONFIGURE_OPTION=34
# Parallel jobs for ./compile
ARG WRF_JOBS=8

# ── Install paths ────────────────────────────────────────────────────────────
ENV TORCH_ROOT=/opt/libtorch \
    FTORCH_INSTALL=/opt/ftorch

# ── 1. Ensure cmake / wget / unzip are present (distro-agnostic) ─────────────
RUN cmake --version >/dev/null 2>&1 && echo "cmake already present" || \
    { command -v dnf >/dev/null 2>&1 && \
          dnf install -y cmake wget unzip; } || \
    { command -v yum >/dev/null 2>&1 && \
          yum install -y cmake3 wget unzip && \
          ln -sf "$(command -v cmake3 || echo /usr/bin/cmake3)" /usr/local/bin/cmake; } || \
    { command -v zypper >/dev/null 2>&1 && \
          zypper --non-interactive install cmake wget unzip; } || \
    { command -v apt-get >/dev/null 2>&1 && \
          apt-get update && \
          apt-get install -y --no-install-recommends cmake wget unzip && \
          rm -rf /var/lib/apt/lists/*; } || \
    { wget -q \
          https://github.com/Kitware/CMake/releases/download/v3.27.9/cmake-3.27.9-linux-x86_64.sh \
          -O /tmp/cmake.sh && \
      sh /tmp/cmake.sh --prefix=/usr/local --skip-license && \
      rm /tmp/cmake.sh; }

# ── 2. Download LibTorch (CPU-only, cxx11 ABI) ───────────────────────────────
RUN wget -q \
      "https://download.pytorch.org/libtorch/cpu/libtorch-cxx11-abi-shared-with-deps-${LIBTORCH_VERSION}%2Bcpu.zip" \
      -O /tmp/libtorch.zip && \
    unzip -q /tmp/libtorch.zip -d /opt/ && \
    rm /tmp/libtorch.zip

# ── 3. Build and install FTorch ──────────────────────────────────────────────
RUN git clone --branch "${FTORCH_TAG}" --depth 1 \
        https://github.com/Cambridge-ICCS/FTorch.git /tmp/ftorch-src && \
    cmake -B /tmp/ftorch-build -S /tmp/ftorch-src \
          -DCMAKE_INSTALL_PREFIX="${FTORCH_INSTALL}" \
          -DCMAKE_PREFIX_PATH="${TORCH_ROOT}" \
          -DCMAKE_BUILD_TYPE=Release && \
    cmake --build /tmp/ftorch-build -j"$(nproc)" && \
    cmake --install /tmp/ftorch-build && \
    { [ -d "${FTORCH_INSTALL}/lib64" ] || \
        ln -sf "${FTORCH_INSTALL}/lib" "${FTORCH_INSTALL}/lib64"; } && \
    rm -rf /tmp/ftorch-src /tmp/ftorch-build

# ── 4. Expose FTorch / LibTorch to WRF's build system ───────────────────────
ENV FTORCH_MOD="${FTORCH_INSTALL}/include/ftorch" \
    FTORCH_LIB="${FTORCH_INSTALL}/lib64" \
    LIBTORCH_LIB="${TORCH_ROOT}/lib"

ENV LD_LIBRARY_PATH="${FTORCH_INSTALL}/lib64:${TORCH_ROOT}/lib:${LD_LIBRARY_PATH:-}" \
    LIBRARY_PATH="${FTORCH_INSTALL}/lib64:${TORCH_ROOT}/lib:${LIBRARY_PATH:-}" \
    CPATH="${FTORCH_INSTALL}/include/ftorch:${TORCH_ROOT}/include:${CPATH:-}"

# ── 5. WRF-Chem compile-time flags ───────────────────────────────────────────
ENV WRF_CHEM=1 \
    NETCDF_classic=1 \
    WRFIO_NCD_LARGE_FILE_SUPPORT=1 \
    USE_NETCDF4_FEATURES=0 \
    PNETCDF_QUILT=0

# ── 6. Copy WRF source tree ──────────────────────────────────────────────────
# Run:  podman build ... /path/to/wrf_source
# The build context must be the root of the WRF source tree.
# Create a .dockerignore there to exclude *.o / *.a / .git before building.
WORKDIR /container/WRF
COPY . /container/WRF/

# ── 7. Configure WRF non-interactively ──────────────────────────────────────
# ./clean -a removes any pre-compiled objects carried in from the source tree.
# printf supplies two newline-terminated answers to ./configure:
#   1st answer: compiler/parallel choice (WRF_CONFIGURE_OPTION, default 34 = GNU dmpar)
#   2nd answer: nesting option (1 = basic nesting)
RUN ./clean -a 2>/dev/null || true && \
    printf '%s\n%s\n' "${WRF_CONFIGURE_OPTION}" "1" | \
        ./configure 2>&1 | tee /tmp/configure.log && \
    grep -i "configuration" /tmp/configure.log || true

# ── 8. Patch configure.wrf to integrate FTorch + LibTorch ───────────────────
# All edits use sed or printf – NO heredocs.
# Heredocs inside Dockerfile RUN instructions are unreliable: the Docker/Podman
# line-joiner processes backslash continuations before bash sees the command,
# which breaks heredoc delimiter detection and produces:
#   "here-document at line 0 delimited by end-of-file (wanted `MKEOF')"
#
# a) Add FTorch .mod search path to Fortran compiler flags.
# b) Add FTorch .mod search path to the free-form Fortran flags.
# c) Remove -cc=$(SCC) – not accepted by the standard OpenMPI mpif90 wrapper.
# d) Extend LDFLAGS_LOCAL with FTorch + LibTorch shared libraries + rpath.
# e) Append a LIB_FTORCH make-variable block (belt-and-suspenders).
#    Note: printf uses single quotes so $(FTORCH_LIB) etc. remain as literal
#    Make variable references in the file, not expanded by bash.
RUN CFG=configure.wrf && \
    sed -i "s|^FCFLAGS[[:space:]]*=.*|& -I${FTORCH_MOD}|"  "${CFG}" && \
    sed -i "s|^FFLAGS[[:space:]]*=.*|& -I${FTORCH_MOD}|"   "${CFG}" && \
    sed -i 's/-cc=\$(SCC)/ /'                               "${CFG}" && \
    sed -i "s|^LDFLAGS_LOCAL[[:space:]]*=.*|& -L${FTORCH_LIB} -L${LIBTORCH_LIB} -lftorch -ltorch_cpu -lc10 -Wl,-rpath,${FTORCH_LIB}:${LIBTORCH_LIB}|" "${CFG}" && \
    printf '\n# ---- FTorch + LibTorch (appended by Dockerfile) --------------------\nLIB_FTORCH = \\\n  -L$(FTORCH_LIB) -lftorch \\\n  -L$(LIBTORCH_LIB) -Wl,-rpath,$(LIBTORCH_LIB):$(FTORCH_LIB) \\\n  -ltorch_cpu -lc10 -lstdc++ -ldl -lpthread\n' >> "${CFG}"

# ── 9. Compile WRF-Chem ──────────────────────────────────────────────────────
# Use ; instead of && before the test so that even if ./compile exits non-zero
# (which can happen when output is piped through tee), we still check the real
# indicator of success: the presence of the executables.
RUN ./compile -j "${WRF_JOBS}" em_real 2>&1 | tee /tmp/compile_wrf.log ; \
    test -f main/wrf.exe  || { echo "ERROR: wrf.exe not built";  tail -100 /tmp/compile_wrf.log; exit 1; } && \
    test -f main/real.exe || { echo "ERROR: real.exe not built"; tail -100 /tmp/compile_wrf.log; exit 1; }

# ── 10. Final verification and permissions ───────────────────────────────────
RUN ls -lh main/wrf.exe main/real.exe && \
    chmod -R a+rx /container

WORKDIR /container/WRF/run
CMD ["/bin/bash"]
