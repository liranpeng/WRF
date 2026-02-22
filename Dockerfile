# WRF-Chem + FTorch container
# Base: NCAR Derecho WRF image (openSUSE Leap, GNU gfortran, NetCDF, HDF5)
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
#   34 = GNU (gfortran/gcc)  dmpar  <-- safe default: image ships gfortran 7.5.0
#        and we install OpenMPI below, so mpif90/mpicc are always available.
#   78 = INTEL (ifx/icx) oneAPI LLVM dmpar -- only works if Intel oneAPI MPI
#        is actually installed in the image (it is NOT in the base image).
ARG WRF_CONFIGURE_OPTION=34
# Parallel jobs for ./compile
ARG WRF_JOBS=8

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

# ── 2. Install OpenMPI (provides mpif90 / mpicc for dmpar builds) ─────────────
# The base image ships gfortran 7.5.0 but has NO MPI wrappers in PATH.
# WRF's configcheck Makefile target calls `which mpif90` and `which mpicc`
# and aborts with "Error 1" when they are missing, even though configure
# itself accepts the option number.
#
# We install OpenMPI from the distro repository.  On openSUSE Leap the
# package is openmpi4-devel (or openmpi3-devel on older releases).
# The binaries land in /usr/lib64/mpi/gcc/openmpi4/bin/ (openSUSE convention).
RUN if command -v zypper >/dev/null 2>&1; then \
        zypper --non-interactive install openmpi4-devel 2>/dev/null || \
        zypper --non-interactive install openmpi3-devel 2>/dev/null || \
        zypper --non-interactive install openmpi-devel  2>/dev/null || \
        { echo "ERROR: could not install OpenMPI via zypper"; exit 1; }; \
    elif command -v apt-get >/dev/null 2>&1; then \
        apt-get update && \
        apt-get install -y --no-install-recommends libopenmpi-dev openmpi-bin && \
        rm -rf /var/lib/apt/lists/*; \
    else \
        echo "ERROR: no supported package manager found"; exit 1; \
    fi

# openSUSE installs MPI wrappers in a versioned subdirectory; add all
# common variants to PATH so mpif90 / mpicc are always found regardless
# of which OpenMPI version zypper selected.
ENV PATH="/usr/lib64/mpi/gcc/openmpi4/bin:\
/usr/lib64/mpi/gcc/openmpi3/bin:\
/usr/lib64/mpi/gcc/openmpi2/bin:\
/usr/lib/openmpi/bin:\
/usr/lib64/openmpi/bin:\
${PATH}"

ENV LD_LIBRARY_PATH="/usr/lib64/mpi/gcc/openmpi4/lib:\
/usr/lib64/mpi/gcc/openmpi3/lib:\
/usr/lib/openmpi/lib:\
${LD_LIBRARY_PATH:-}"

# ── 3. Download LibTorch (CPU-only, cxx11 ABI) ───────────────────────────────
RUN wget -q \
      "https://download.pytorch.org/libtorch/cpu/libtorch-cxx11-abi-shared-with-deps-${LIBTORCH_VERSION}%2Bcpu.zip" \
      -O /tmp/libtorch.zip && \
    unzip -q /tmp/libtorch.zip -d /opt/ && \
    rm /tmp/libtorch.zip

# ── 4. Build and install FTorch ──────────────────────────────────────────────
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

# ── 5. Expose FTorch / LibTorch to WRF's build system ───────────────────────
ENV FTORCH_MOD="${FTORCH_INSTALL}/include/ftorch" \
    FTORCH_LIB="${FTORCH_INSTALL}/lib64" \
    LIBTORCH_LIB="${TORCH_ROOT}/lib"

ENV LD_LIBRARY_PATH="${FTORCH_INSTALL}/lib64:${TORCH_ROOT}/lib:${LD_LIBRARY_PATH}" \
    LIBRARY_PATH="${FTORCH_INSTALL}/lib64:${TORCH_ROOT}/lib:${LIBRARY_PATH:-}" \
    CPATH="${FTORCH_INSTALL}/include/ftorch:${TORCH_ROOT}/include:${CPATH:-}"

# ── 6. WRF-Chem compile-time flags ───────────────────────────────────────────
ENV WRF_CHEM=1 \
    WRF_EM_CORE=1 \
    NETCDF_classic=1 \
    WRFIO_NCD_LARGE_FILE_SUPPORT=1 \
    USE_NETCDF4_FEATURES=0 \
    PNETCDF_QUILT=0

# ── 7. Copy WRF source tree ──────────────────────────────────────────────────
# The build context must be the root of the WRF source tree.
# Consider adding a .dockerignore to exclude *.o / *.a / .git from the context.
WORKDIR /container/WRF
COPY . /container/WRF/

# ── 8. Verify MPI and configure WRF non-interactively ───────────────────────
# Print compiler/MPI locations so problems are visible in the build log.
# ./clean -a removes any pre-compiled objects from the source tree.
# printf supplies two newline-terminated answers to ./configure:
#   1st: compiler/parallel choice  (ARG WRF_CONFIGURE_OPTION, default 34 = GNU dmpar)
#   2nd: nesting option            (1 = basic nesting)
RUN echo "=== Compiler / MPI sanity check ===" && \
    echo "gfortran : $(command -v gfortran || echo NOT FOUND)" && \
    echo "gcc      : $(command -v gcc      || echo NOT FOUND)" && \
    echo "mpif90   : $(command -v mpif90   || echo NOT FOUND)" && \
    echo "mpicc    : $(command -v mpicc    || echo NOT FOUND)" && \
    echo "PATH     : ${PATH}" && \
    echo "======================================" && \
    ./clean -a 2>/dev/null || true && \
    printf '%s\n%s\n' "${WRF_CONFIGURE_OPTION}" "1" | \
        ./configure 2>&1 | tee /tmp/configure.log && \
    grep -i "configuration" /tmp/configure.log || true

# ── 9. Patch configure.wrf to integrate FTorch + LibTorch ───────────────────
# All edits use sed or printf – NO heredocs.
# Heredocs inside Dockerfile RUN instructions are unreliable: the line-joiner
# strips backslash-newlines before bash sees the command, so the heredoc
# delimiter is never matched and the build fails with:
#   "here-document at line 0 delimited by end-of-file (wanted `MKEOF')"
#
# a) Add FTorch .mod search path to Fortran compiler flags.
# b) Add FTorch .mod search path to the free-form Fortran flags.
# c) Remove -cc=$(SCC) – OpenMPI mpif90 wrappers do not accept this flag.
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

# ── 10. Compile WRF-Chem ─────────────────────────────────────────────────────
# Use ; (not &&) before test-f checks: when ./compile output is piped through
# tee, bash sets $? to tee's exit code, not the compiler's.
# The presence of wrf.exe and real.exe is the authoritative success indicator.
RUN ./compile -j "${WRF_JOBS}" em_real 2>&1 | tee /tmp/compile_wrf.log ; \
    test -f main/wrf.exe  || { echo "ERROR: wrf.exe not built";  tail -100 /tmp/compile_wrf.log; exit 1; } && \
    test -f main/real.exe || { echo "ERROR: real.exe not built"; tail -100 /tmp/compile_wrf.log; exit 1; }

# ── 11. Final verification and permissions ───────────────────────────────────
RUN ls -lh main/wrf.exe main/real.exe && \
    chmod -R a+rx /container

WORKDIR /container/WRF/run
CMD ["/bin/bash"]
