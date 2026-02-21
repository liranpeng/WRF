# WRF-Chem + FTorch container
# Base: NCAR Derecho WRF image (openSUSE Leap, Intel/GNU compilers, MPI, NetCDF, HDF5)
FROM benjaminkirk/ncar-derecho-wrf:latest

SHELL ["/bin/bash", "-c"]

# ── Build-time arguments ────────────────────────────────────────────────────
# LibTorch CPU-only ABI-stable wheel
ARG LIBTORCH_VERSION=2.1.0
# FTorch Fortran→PyTorch bridge – v0.6.1 never existed; use the first stable release
ARG FTORCH_TAG=v1.0.0

# ── Runtime paths ──────────────────────────────────────────────────────────
ENV TORCH_ROOT=/opt/libtorch \
    FTORCH_INSTALL=/opt/ftorch

# ── 1. Ensure cmake, wget, unzip are present (distro-agnostic) ─────────────
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
    { echo "No package manager found; installing cmake binary" && \
        wget -q https://github.com/Kitware/CMake/releases/download/v3.27.9/cmake-3.27.9-linux-x86_64.sh \
            -O /tmp/cmake.sh && \
        sh /tmp/cmake.sh --prefix=/usr/local --skip-license && \
        rm /tmp/cmake.sh; }

# ── 2. Download LibTorch (CPU, cxx11 ABI) ──────────────────────────────────
RUN wget -q \
      "https://download.pytorch.org/libtorch/cpu/libtorch-cxx11-abi-shared-with-deps-${LIBTORCH_VERSION}%2Bcpu.zip" \
      -O /tmp/libtorch.zip && \
    unzip -q /tmp/libtorch.zip -d /opt/ && \
    rm /tmp/libtorch.zip

# ── 3. Build FTorch (Fortran→LibTorch bridge) ──────────────────────────────
# NOTE: tag v0.6.1 never existed upstream; v1.0.0 is the first stable release.
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

# ── 4. Set linker/include environment so WRF's build system finds FTorch ───
ENV FTORCH_DIR=${FTORCH_INSTALL} \
    LD_LIBRARY_PATH=${FTORCH_INSTALL}/lib:${FTORCH_INSTALL}/lib64:/opt/libtorch/lib:${LD_LIBRARY_PATH:-} \
    LIBRARY_PATH=${FTORCH_INSTALL}/lib:${FTORCH_INSTALL}/lib64:/opt/libtorch/lib:${LIBRARY_PATH:-} \
    CPATH=${FTORCH_INSTALL}/include:${TORCH_ROOT}/include:${CPATH:-}

# ── 5. Copy WRF source tree ─────────────────────────────────────────────────
WORKDIR /wrf
COPY . /wrf/

# ── 6. Configure WRF (non-interactive: GNU + dmpar, option 34) ─────────────
# The configure script asks two questions interactively.  We pipe answers:
#   - compiler choice  (34 = GNU dmpar on most installs; adjust if needed)
#   - nesting option   (1 = basic)
RUN echo -e "34\n1" | ./configure 2>&1 | tee /tmp/configure.log && \
    grep -i "configuration" /tmp/configure.log || true

# ── 7. Patch configure.wrf to link FTorch + LibTorch ──────────────────────
# Append FTorch/LibTorch libraries to the linker flags in configure.wrf so
# the chem modules that call ftorch compile and link correctly.
RUN sed -i \
      "s|^LDFLAGS_LOCAL\s*=.*|& -L${FTORCH_INSTALL}/lib -L${FTORCH_INSTALL}/lib64 -L${TORCH_ROOT}/lib -lftorch -ltorch -ltorch_cpu -lc10|" \
      configure.wrf && \
    sed -i \
      "s|^FCDEBUG\s*=.*|& -I${FTORCH_INSTALL}/include|" \
      configure.wrf || true

# ── 8. Compile WRF-Chem ─────────────────────────────────────────────────────
ARG WRF_JOBS=4
RUN ./compile -j ${WRF_JOBS} em_real 2>&1 | tee /tmp/compile.log && \
    ls main/wrf.exe main/real.exe

# ── 9. Verify the executables were built ────────────────────────────────────
RUN ls -lh main/wrf.exe main/real.exe

# ── Default working directory for runtime ───────────────────────────────────
WORKDIR /wrf/run
