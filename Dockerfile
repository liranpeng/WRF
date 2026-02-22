# WRF-Chem + FTorch container
# Base: NCAR Derecho WRF image (openSUSE Leap, Intel oneAPI compilers, MPI, NetCDF, HDF5)
#
# Build (Podman – rootless):
#   podman build --format docker \
#     -f /path/to/Dockerfile \
#     -t <image>:<tag> \
#     /path/to/wrf_source_dir
#
# Build (Docker):
#   docker build -t <image>:<tag> /path/to/wrf_source_dir
#
# --format docker is required by Podman to honour the SHELL instruction.
# Without it Podman falls back to /bin/sh and breaks bash-specific syntax.

FROM benjaminkirk/ncar-derecho-wrf:latest

SHELL ["/bin/bash", "-c"]

# ── Build-time knobs ─────────────────────────────────────────────────────────
# LibTorch CPU-only cxx11-ABI wheel version
ARG LIBTORCH_VERSION=2.1.0
# FTorch tag – v1.0.0 is the first stable release (v0.6.x tags do not exist)
ARG FTORCH_TAG=v1.0.0
# WRF ./configure compiler option
#   78 = INTEL (ifx/icx) : oneAPI LLVM  dmpar   <-- default for this image
#   34 = GNU   (gfortran/gcc)            dmpar
ARG WRF_CONFIGURE_OPTION=78
# Parallel jobs for ./compile
ARG WRF_JOBS=8

# ── Intel oneAPI root (adjust if the image installs to a different prefix) ───
ARG ONEAPI_ROOT=/opt/intel/oneapi
ENV ONEAPI_ROOT=${ONEAPI_ROOT}

# Bake the oneAPI compiler + MPI wrapper directories into PATH so that every
# subsequent RUN step and the final container image can find ifx, icx,
# mpif90, and mpicc without needing to source setvars.sh each time.
ENV PATH="${ONEAPI_ROOT}/compiler/latest/linux/bin:\
${ONEAPI_ROOT}/compiler/latest/linux/bin/intel64:\
${ONEAPI_ROOT}/mpi/latest/bin:\
${PATH}"

ENV LD_LIBRARY_PATH="${ONEAPI_ROOT}/compiler/latest/linux/lib:\
${ONEAPI_ROOT}/mpi/latest/lib/release:\
${ONEAPI_ROOT}/mpi/latest/lib:\
${LD_LIBRARY_PATH:-}"

# ── LibTorch / FTorch install paths ─────────────────────────────────────────
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

ENV LD_LIBRARY_PATH="${FTORCH_INSTALL}/lib64:${TORCH_ROOT}/lib:${LD_LIBRARY_PATH}" \
    LIBRARY_PATH="${FTORCH_INSTALL}/lib64:${TORCH_ROOT}/lib:${LIBRARY_PATH:-}" \
    CPATH="${FTORCH_INSTALL}/include/ftorch:${TORCH_ROOT}/include:${CPATH:-}"

# ── 5. WRF-Chem compile-time flags ───────────────────────────────────────────
ENV WRF_CHEM=1 \
    WRF_EM_CORE=1 \
    NETCDF_classic=1 \
    WRFIO_NCD_LARGE_FILE_SUPPORT=1 \
    USE_NETCDF4_FEATURES=0 \
    PNETCDF_QUILT=0

# ── 6. Copy WRF source tree ──────────────────────────────────────────────────
# The build context must be the root of the WRF source tree.
# Consider a .dockerignore to exclude *.o / *.a / .git from the context.
WORKDIR /container/WRF
COPY . /container/WRF/

# ── Helper: source Intel oneAPI setvars.sh if present ────────────────────────
# setvars.sh initialises many variables beyond PATH (I_MPI_ROOT, FI_PROVIDER_PATH,
# etc.) that Intel MPI needs at link and run time.  We source it at the start of
# every RUN step that invokes the compiler or linker.
# The PATH ENV layer above guarantees mpif90/ifx are found even on systems where
# setvars.sh lives in a non-standard location.
#
# Macro used in steps 7 and 9 (repeated inline to avoid shell-function scope issues):
#   source "${ONEAPI_ROOT}/setvars.sh" --force 2>/dev/null || true

# ── 7. Configure WRF non-interactively ──────────────────────────────────────
# ./clean -a removes any pre-compiled objects from the source tree.
# printf supplies two newline-terminated answers to ./configure:
#   1st: compiler/parallel choice  (ARG WRF_CONFIGURE_OPTION, default 78)
#   2nd: nesting option            (1 = basic nesting)
RUN source "${ONEAPI_ROOT}/setvars.sh" --force 2>/dev/null || true && \
    echo "mpif90: $(command -v mpif90 || echo NOT FOUND)" && \
    echo "mpicc:  $(command -v mpicc  || echo NOT FOUND)" && \
    echo "ifx:    $(command -v ifx    || echo NOT FOUND)" && \
    echo "icx:    $(command -v icx    || echo NOT FOUND)" && \
    ./clean -a 2>/dev/null || true && \
    printf '%s\n%s\n' "${WRF_CONFIGURE_OPTION}" "1" | \
        ./configure 2>&1 | tee /tmp/configure.log && \
    grep -i "configuration" /tmp/configure.log || true

# ── 8. Patch configure.wrf to integrate FTorch + LibTorch ───────────────────
# All edits use sed or printf – NO heredocs.
# Heredocs inside Dockerfile RUN instructions are unreliable: the line-joiner
# strips backslash-newlines before bash sees the command, so the heredoc
# delimiter is never matched and the build fails with:
#   "here-document at line 0 delimited by end-of-file (wanted `MKEOF')"
#
# a) Add FTorch .mod search path to Fortran compiler flags.
# b) Add FTorch .mod search path to the free-form Fortran flags.
# c) Remove -cc=$(SCC) – Intel MPI wrappers (mpif90/mpicc) do not accept it.
# d) Extend LDFLAGS_LOCAL with FTorch + LibTorch shared libraries + rpath.
# e) Append a LIB_FTORCH make-variable block for downstream Makefile rules.
#    printf uses single quotes so $(FTORCH_LIB) stays as a Make variable
#    reference in the file rather than being expanded by bash.
RUN CFG=configure.wrf && \
    sed -i "s|^FCFLAGS[[:space:]]*=.*|& -I${FTORCH_MOD}|"  "${CFG}" && \
    sed -i "s|^FFLAGS[[:space:]]*=.*|& -I${FTORCH_MOD}|"   "${CFG}" && \
    sed -i 's/-cc=\$(SCC)/ /'                               "${CFG}" && \
    sed -i "s|^LDFLAGS_LOCAL[[:space:]]*=.*|& -L${FTORCH_LIB} -L${LIBTORCH_LIB} -lftorch -ltorch_cpu -lc10 -Wl,-rpath,${FTORCH_LIB}:${LIBTORCH_LIB}|" "${CFG}" && \
    printf '\n# ---- FTorch + LibTorch (appended by Dockerfile) --------------------\nLIB_FTORCH = \\\n  -L$(FTORCH_LIB) -lftorch \\\n  -L$(LIBTORCH_LIB) -Wl,-rpath,$(LIBTORCH_LIB):$(FTORCH_LIB) \\\n  -ltorch_cpu -lc10 -lstdc++ -ldl -lpthread\n' >> "${CFG}"

# ── 9. Compile WRF-Chem ──────────────────────────────────────────────────────
# setvars.sh is sourced again because each RUN starts a fresh shell and the
# ENV PATH layer may not cover every variable Intel MPI needs internally
# (I_MPI_ROOT, FI_PROVIDER_PATH, …).
#
# Use ; (not &&) before the test-f checks: when ./compile output is piped
# through tee, bash sets $? to tee's exit code, not the compiler's.  The
# presence of wrf.exe and real.exe is the authoritative success indicator.
RUN source "${ONEAPI_ROOT}/setvars.sh" --force 2>/dev/null || true && \
    ./compile -j "${WRF_JOBS}" em_real 2>&1 | tee /tmp/compile_wrf.log ; \
    test -f main/wrf.exe  || { echo "ERROR: wrf.exe not built";  tail -100 /tmp/compile_wrf.log; exit 1; } && \
    test -f main/real.exe || { echo "ERROR: real.exe not built"; tail -100 /tmp/compile_wrf.log; exit 1; }

# ── 10. Final verification and permissions ───────────────────────────────────
RUN ls -lh main/wrf.exe main/real.exe && \
    chmod -R a+rx /container

WORKDIR /container/WRF/run
CMD ["/bin/bash"]
