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
#
# ── Why option 34, not 78 ────────────────────────────────────────────────────
# On Perlmutter the working build script selects option 78 (INTEL ifx/icx
# oneAPI LLVM dmpar) and then immediately replaces mpif90→ftn and mpicc→cc
# in configure.wrf, so the actual compilers used are the Cray ftn/cc wrappers
# (backed by gfortran under PrgEnv-gnu).  Cray wrappers are NOT available
# inside a standalone container, so mirroring that trick is not possible.
# Option 34 (GNU gfortran/gcc dmpar) produces an identical configure.wrf
# except for the compiler-flag stanzas, and works directly with the OpenMPI
# mpif90/mpicc wrappers we install below.

FROM benjaminkirk/ncar-derecho-wrf:latest

SHELL ["/bin/bash", "-c"]

# ── Build-time knobs ─────────────────────────────────────────────────────────
ARG LIBTORCH_VERSION=2.1.0
ARG FTORCH_TAG=v1.0.0
# 34 = GNU (gfortran/gcc) dmpar – matches the compilers in this image.
# Override with --build-arg WRF_CONFIGURE_OPTION=35 for dm+sm, etc.
ARG WRF_CONFIGURE_OPTION=34
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
# The base image ships gfortran 7.5.0 but has no MPI wrappers in PATH.
# WRF's configcheck Makefile target calls `which mpif90` / `which mpicc` and
# aborts if they are missing.  On Perlmutter these come from the Cray ftn/cc
# wrappers; inside the container we use the distro OpenMPI packages instead.
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

# openSUSE installs OpenMPI wrappers under a versioned subdirectory.
# Add all common variants so mpif90 / mpicc are found regardless of the
# exact version that zypper selected.
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
WORKDIR /container/WRF
COPY . /container/WRF/

# ── 8. Verify MPI and configure WRF non-interactively ───────────────────────
# Compiler/MPI locations are printed first so any PATH problem is visible in
# the build log before we ever reach configcheck.
# printf pipes two newline-terminated answers to ./configure:
#   1st: compiler/parallel choice  (default 34 = GNU dmpar)
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
# This mirrors the working Perlmutter build script.
#
# (a) PREPEND Make variable definitions to configure.wrf (line 1 insertion).
#     We use printf + cat rather than `sed -i "1i ..."` to avoid the complex
#     multi-level escaping required to produce Makefile line-continuation
#     characters (\<newline>) inside a Dockerfile RUN string.
#
#     What gets prepended (shell vars are expanded to real paths):
#       FTORCH_LIB   := /opt/ftorch/lib64
#       LIBTORCH_LIB := /opt/libtorch/lib
#       LIB_FTORCH = \
#         -L$(FTORCH_LIB) -lftorch \
#         -L$(LIBTORCH_LIB) -Wl,-rpath,... -ltorch_cpu -lc10 -lstdc++ -ldl -lpthread
#       LIB_LOCAL = $(LIB_FTORCH)   ← hooks FTorch into WRF's standard link step
#
#     The printf format string is single-quoted so $(FTORCH_LIB) etc. are
#     passed literally to printf (Make variable references, not shell subshell).
#     The two %s conversion specifiers are filled by the shell-expanded vars
#     "${FTORCH_LIB}" and "${LIBTORCH_LIB}".
#     Inside single-quoted printf: \n = newline, \\ = backslash,
#     so \\\n = backslash + newline = Makefile line continuation.
#
# (b) Add the FTorch Fortran module search path to FCFLAGS and FFLAGS.
#
# (c) Remove -cc=$(SCC): the Perlmutter script also removes this; it is not
#     accepted by OpenMPI's mpif90 wrapper (or by the Cray ftn wrapper).
#
# NOTE: The Perlmutter script also runs:
#         sed -i 's/mpif90/ftn/'  configure.wrf
#         sed -i 's/mpicc/cc/'   configure.wrf
#       Those substitutions replace the generic MPI wrappers with Cray-specific
#       wrappers (ftn/cc) that are only available on Perlmutter.  Inside this
#       container we use OpenMPI's mpif90/mpicc instead, so we do NOT apply
#       those two sed commands.
RUN CFG=configure.wrf && \
    { printf 'FTORCH_LIB   := %s\nLIBTORCH_LIB := %s\n# ---- FTorch + libtorch ----\nLIB_FTORCH = \\\n  -L$(FTORCH_LIB) -lftorch \\\n  -L$(LIBTORCH_LIB) -Wl,-rpath,$(LIBTORCH_LIB):$(FTORCH_LIB) \\\n  -ltorch_cpu -lc10 -lstdc++ -ldl -lpthread\n# Hook FTorch into WRF standard link variable\nLIB_LOCAL = $(LIB_FTORCH)\n\n' \
          "${FTORCH_LIB}" "${LIBTORCH_LIB}"; \
      cat "${CFG}"; } > /tmp/cfg_patched && mv /tmp/cfg_patched "${CFG}" && \
    sed -i "s|^FCFLAGS[[:space:]]*=.*|& -I${FTORCH_MOD}|" "${CFG}" && \
    sed -i "s|^FFLAGS[[:space:]]*=.*|& -I${FTORCH_MOD}|"  "${CFG}" && \
    sed -i 's/-cc=\$(SCC)/ /'                              "${CFG}"

# ── 10. Compile WRF-Chem ─────────────────────────────────────────────────────
# Use ; (not &&) before the test-f checks: when ./compile is piped through tee
# bash sets $? to tee's exit code, not the compiler's.  Checking for the
# executables is the authoritative success indicator.
RUN ./compile -j "${WRF_JOBS}" em_real 2>&1 | tee /tmp/compile_wrf.log ; \
    test -f main/wrf.exe  || { echo "ERROR: wrf.exe not built";  tail -100 /tmp/compile_wrf.log; exit 1; } && \
    test -f main/real.exe || { echo "ERROR: real.exe not built"; tail -100 /tmp/compile_wrf.log; exit 1; }

# ── 11. Final verification and permissions ───────────────────────────────────
RUN ls -lh main/wrf.exe main/real.exe && \
    chmod -R a+rx /container

WORKDIR /container/WRF/run
CMD ["/bin/bash"]
