# WRF_ARG branch

Source snapshot of the **ARG (Abdul-Razzak & Ghan) baseline** WRF-Chem build used
for the 2017-07-14 aerosol–cloud cases on TACC Stampede3.

- Snapshot of: `/scratch/07088/tg863871/Model_Backup/WRF_ARG`
  (a byte-identical backup of `/scratch/07088/tg863871/WRF_dm`, taken 2026-07-31).
- Base commit: `d66e442fccc04111067e29274c9f9eaccc3cef28` (WRF V4.6.1, this fork's `master`).
- Aerosol activation: the stock ARG parameterisation in `phys/module_mixactivate.F`
  (no ML emulator in this branch).

## Changes relative to the base commit

| File | Change |
|------|--------|
| `chem/module_data_sorgam.F` | Initial geometric mean diameters of the MADE/SORGAM modes changed: `dginin` 0.01→0.04 µm, `dginia` 0.07→0.16 µm, `dginic` 1.0→1.2 µm. |
| `run/namelist.input` | Namelist used for the two-domain (15 km parent) 2017-07-14 case. |
| `Liran_build_WRF.sh` | Stampede3 build script (see below). |
| `test/wrf_campaign_arg.sh` | Auto-restart campaign driver for the four `20170714_{org,mid}_{1aer,3aer}_ARG` cases (races long `skx` jobs against short `skx-dev` jobs, re-points the namelist at the newest complete `wrfrst`). |
| `test/unstick_case_arg.sh` | Helper to recover a stalled case. |

Everything else is identical to the base commit. Build products, `configure.wrf`,
compile logs, case directories with model output, and generated files
(`Registry/Registry`, `frame/module_state_description.F`, `inc/*.h`, ...) are not
committed.

## Building on Stampede3

Modules (all available as of 2026-09): `intel/24.0`, `impi/21.11`, `hdf5/1.14.4`,
`netcdf/4.9.2`, `pnetcdf/1.12.3`, `zlib/1.3.1`, `cmake`.

Configure with WRF-Chem enabled (`WRF_CHEM=1`) and pick

    Enter selection [1-83] : 78    (INTEL ifx/icx, dmpar)
    Compile for nesting?    : 1     (basic)

then `./compile em_real -j 4`. The March 2026 build took about 25 minutes.

`Liran_build_WRF.sh` wraps these steps. Before using it:

1. Edit `WRF_DIR` to point at your checkout (it is hard-wired to `/scratch/07088/tg863871/WRF_dm`).
2. It runs `./configure` interactively; answer `78` and `1` as above, or set
   `doclean_all=false` and `runconf=false` to reuse an existing `configure.wrf`.

## Known issue in this build

`re_cloud`/`re_ice`/`re_snow` are not part of the `morr_two_moment` package in
`Registry/Registry.EM_COMMON`, so with `mp_physics=10`, `ra_sw_physics=4`,
`use_mp_re=1` the effective radii and hence `TAU_QC`, `TAU_QC_TOT`, `RE_QC*` are
identically zero in wrfout. The `WRF_dm_v2` tree (not in this repository) fixes
this with a Registry-only change; its runs reproduce this branch to within ~1%
for aerosol and microphysics fields but differ by 2–5% in shortwave cloud
radiative effect. Do not mix TAU-based quantities between the two.
