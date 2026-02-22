# WRF-Chem + FTorch container
# Base: NCAR Derecho WRF image (openSUSE Leap, GNU gfortran, NetCDF, HDF5)
#
# ── Pre-requisite: create docker-deps/ tarballs on Perlmutter ────────────────
#
# Run these commands on Perlmutter (after loading PrgEnv-gnu so gfortran
# is in PATH) to create the three files the COPY steps below need:
#
#   FTORCH_INSTALL="$HOME/opt/ftorch"
#   TORCH_ROOT="/global/homes/h/heroplr/opt/libtorch-cpu"   # adjust if different
#
#   # Find where FTorch Fortran source lives (the directory that has ftorch.f90)
#   FTORCH_SRC=$(dirname $(find $HOME -name "ftorch.f90" 2>/dev/null | head -1))
#
#   # 1. LibTorch CPU shared libraries
#   tar czf libtorch-cpu.tar.gz  -C "$(dirname $TORCH_ROOT)"  "$(basename $TORCH_ROOT)"
#
#   # 2. FTorch pre-built .so library (C++ layer, architecture-compatible)
#   tar czf ftorch-libs.tar.gz   -C "$FTORCH_INSTALL"  lib64/
#
#   # 3. FTorch Fortran source (must be recompiled with the container's gfortran
#   #    because .mod files are gfortran-version specific)
#   tar czf ftorch-src.tar.gz    -C "$FTORCH_SRC"  .
#
#   # Copy all three into docker-deps/ inside your WRF checkout
#   mkdir -p /path/to/WRF/docker-deps
#   cp libtorch-cpu.tar.gz ftorch-libs.tar.gz ftorch-src.tar.gz /path/to/WRF/docker-deps/
#
# Then build:
#   podman build --format docker -t wrf-ftorch:local /path/to/WRF/
#   docker build              -t wrf-ftorch:local /path/to/WRF/
#
# ── Why option 34, not 78 ────────────────────────────────────────────────────
# On Perlmutter the working build script selects option 78 then replaces
# mpif90→ftn and mpicc→cc (Cray wrappers). Those wrappers are not available
# in the container; option 34 (GNU gfortran/gcc dmpar) with OpenMPI's
# mpif90/mpicc is the equivalent.

FROM benjaminkirk/ncar-derecho-wrf:latest

SHELL ["/bin/bash", "-c"]

# ── Build-time knobs ─────────────────────────────────────────────────────────
# 34 = GNU (gfortran/gcc) dmpar – matches the compilers in this image.
ARG WRF_CONFIGURE_OPTION=34
ARG WRF_JOBS=8

# ── LibTorch / FTorch install paths inside the container ─────────────────────
ENV TORCH_ROOT=/opt/libtorch \
    FTORCH_INSTALL=/opt/ftorch

# ── 1. Install OpenMPI (provides mpif90 / mpicc for dmpar builds) ─────────────
# The base image ships gfortran but has no MPI wrappers in PATH.
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

# ── 2. Unpack LibTorch (pre-built CPU libraries from Perlmutter) ──────────────
# libtorch-cpu.tar.gz contains the full LibTorch directory tree,
# e.g. libtorch-cpu/lib/libtorch_cpu.so, libtorch-cpu/include/, etc.
# It is extracted so that /opt/libtorch/lib/libtorch_cpu.so exists.
COPY docker-deps/libtorch-cpu.tar.gz /tmp/
RUN TOPDIR=$(tar tzf /tmp/libtorch-cpu.tar.gz | head -1 | cut -d/ -f1) && \
    tar xzf /tmp/libtorch-cpu.tar.gz -C /opt/ && \
    # Normalise to /opt/libtorch regardless of the top-level dir name
    if [ "${TOPDIR}" != "libtorch" ]; then \
        mv /opt/${TOPDIR} /opt/libtorch; \
    fi && \
    rm /tmp/libtorch-cpu.tar.gz

# ── 3. Unpack FTorch C++ library (pre-built .so from Perlmutter) ─────────────
# ftorch-libs.tar.gz contains the lib64/ sub-tree from $HOME/opt/ftorch,
# i.e. lib64/libftorch.so (and any symlinks).
# The .so is a C++ shared object — architecture-compatible with x86_64 Linux
# regardless of the gfortran version used to build Perlmutter's WRF.
COPY docker-deps/ftorch-libs.tar.gz /tmp/
RUN mkdir -p ${FTORCH_INSTALL}/lib64 && \
    tar xzf /tmp/ftorch-libs.tar.gz -C ${FTORCH_INSTALL}/ && \
    # Ensure FTORCH_INSTALL/lib64 exists even if the tarball used "lib"
    { [ -d "${FTORCH_INSTALL}/lib64" ] || \
        ln -sf "${FTORCH_INSTALL}/lib" "${FTORCH_INSTALL}/lib64"; } && \
    rm /tmp/ftorch-libs.tar.gz

# ── 4. Compile FTorch Fortran module with the container's gfortran ────────────
# ftorch.mod is a binary format specific to the gfortran major version that
# produced it.  We cannot copy the .mod from Perlmutter if its gfortran differs
# from the one in this image.  Instead we compile the Fortran source files
# (ftorch.f90, ftorch_tensor.f90, …) that were packed from the Perlmutter
# build tree.  This produces a .mod that matches the container's gfortran,
# while still linking against the pre-built libftorch.so from Perlmutter.
#
# ftorch-src.tar.gz was created on Perlmutter with:
#   FTORCH_SRC=$(dirname $(find $HOME -name "ftorch.f90" | head -1))
#   tar czf ftorch-src.tar.gz -C "$FTORCH_SRC" .
COPY docker-deps/ftorch-src.tar.gz /tmp/
RUN mkdir -p /tmp/ftorch-src ${FTORCH_INSTALL}/include/ftorch && \
    tar xzf /tmp/ftorch-src.tar.gz -C /tmp/ftorch-src/ && \
    cd /tmp/ftorch-src && \
    echo "=== FTorch Fortran source files ===" && ls -la && \
    # Compile sub-modules first (ftorch_tensor.f90 if present), then ftorch.f90.
    # -J writes .mod files to the include directory; -c skips linking.
    for f in ftorch_tensor.f90 ftorch_c_binding.f90; do \
        [ -f "$f" ] && \
        gfortran -c "$f" \
            -J${FTORCH_INSTALL}/include/ftorch \
            -I${FTORCH_INSTALL}/include/ftorch \
            -o /dev/null && \
        echo "  compiled $f"; \
    done; \
    gfortran -c ftorch.f90 \
        -J${FTORCH_INSTALL}/include/ftorch \
        -I${FTORCH_INSTALL}/include/ftorch \
        -o /dev/null && \
    echo "=== Generated .mod files ===" && \
    ls -la ${FTORCH_INSTALL}/include/ftorch/ && \
    rm -rf /tmp/ftorch-src /tmp/ftorch-src.tar.gz

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

# ── 8. Verify environment and configure WRF non-interactively ────────────────
RUN echo "=== Compiler / MPI sanity check ===" && \
    echo "gfortran : $(command -v gfortran || echo NOT FOUND)" && \
    echo "gcc      : $(command -v gcc      || echo NOT FOUND)" && \
    echo "mpif90   : $(command -v mpif90   || echo NOT FOUND)" && \
    echo "mpicc    : $(command -v mpicc    || echo NOT FOUND)" && \
    echo "=== FTorch / LibTorch libraries ===" && \
    ls -lh "${FTORCH_LIB}/libftorch"* && \
    ls -lh "${LIBTORCH_LIB}/libtorch_cpu"* && \
    ls -lh "${FTORCH_MOD}/"*.mod && \
    echo "======================================" && \
    ./clean -a 2>/dev/null || true && \
    printf '%s\n%s\n' "${WRF_CONFIGURE_OPTION}" "1" | \
        ./configure 2>&1 | tee /tmp/configure.log && \
    grep -i "configuration" /tmp/configure.log || true

# ── 9. Patch configure.wrf to integrate FTorch + LibTorch ───────────────────
# Mirrors the working Perlmutter build script approach.
# (a) Prepend Make variable definitions so LIB_LOCAL picks up FTorch.
# (b) Add -I${FTORCH_MOD} to FCFLAGS/FFLAGS so gfortran finds ftorch.mod.
# (c) Remove -cc=$(SCC): not accepted by OpenMPI's mpif90.
# NOTE: mpif90→ftn and mpicc→cc are NOT applied here (Cray-only wrappers).
RUN CFG=configure.wrf && \
    { printf 'FTORCH_LIB   := %s\nLIBTORCH_LIB := %s\n# ---- FTorch + libtorch ----\nLIB_FTORCH = \\\n  -L$(FTORCH_LIB) -lftorch \\\n  -L$(LIBTORCH_LIB) -Wl,-rpath,$(LIBTORCH_LIB):$(FTORCH_LIB) \\\n  -ltorch_cpu -lc10 -lstdc++ -ldl -lpthread\n# Hook FTorch into WRF standard link variable\nLIB_LOCAL = $(LIB_FTORCH)\n\n' \
          "${FTORCH_LIB}" "${LIBTORCH_LIB}"; \
      cat "${CFG}"; } > /tmp/cfg_patched && mv /tmp/cfg_patched "${CFG}" && \
    sed -i "s|^FCFLAGS[[:space:]]*=.*|& -I${FTORCH_MOD}|" "${CFG}" && \
    sed -i "s|^FFLAGS[[:space:]]*=.*|& -I${FTORCH_MOD}|"  "${CFG}" && \
    sed -i 's/-cc=\$(SCC)/ /'                              "${CFG}"

# ── 10. Compile WRF-Chem ─────────────────────────────────────────────────────
RUN ./compile -j "${WRF_JOBS}" em_real 2>&1 | tee /tmp/compile_wrf.log ; \
    if ! test -f main/wrf.exe; then \
        echo "=== Compiler / linker errors ===" ; \
        grep -iE "(error:|undefined reference|cannot find -l|ld returned|fatal error)" \
            /tmp/compile_wrf.log | tail -40 ; \
        echo "=== Last 30 lines ===" ; \
        tail -30 /tmp/compile_wrf.log ; \
        exit 1 ; \
    fi && \
    test -f main/real.exe || { echo "ERROR: real.exe not built"; exit 1; }

# ── 11. Final verification ───────────────────────────────────────────────────
RUN ls -lh main/wrf.exe main/real.exe && \
    chmod -R a+rx /container

WORKDIR /container/WRF/run
CMD ["/bin/bash"]
