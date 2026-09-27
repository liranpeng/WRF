# WRF_ML branch

Source snapshot of the **ML-emulated aerosol activation** WRF-Chem build used for
the 2017-07-14 aerosol–cloud cases on TACC Stampede3. The Abdul-Razzak & Ghan
(ARG) activation scheme is replaced, for the Aitken and accumulation modes, by a
PyTorch MLP called from Fortran through FTorch.

- Snapshot of: `/scratch/07088/tg863871/Model_Backup/WRF_ML`, itself a copy
  (taken 2026-08-04) of
  `/scratch/07088/tg863871/Perlm_Backup/WRF_stam3_ml_mixout_bce_lr1e-4_cosine_more_fix`.
- Base commit: `d66e442fccc04111067e29274c9f9eaccc3cef28` (WRF V4.6.1, this fork's `master`).
- Companion baseline: the `WRF_ARG` branch (same base, stock ARG activation).

## What the emulator does

`phys/module_mixactivate.F` gains `activate_ml`, which is called from
`mixactivate` at the two activation call sites (new-cloud and grow/shrink).
For each grid cell it

1. runs the original ARG code to obtain `fn`, `fs`, `fm` and fluxes for every mode;
2. builds a 16-element input vector: air temperature (K), dry-air pressure (hPa),
   relative humidity (%), updraft `wbar` (cm/s), then per-mode number
   concentration, mean radius and hygroscopicity (4 slots each, WRF-native mode
   order, Aitken first);
3. calls the TorchScript model `mlp_wrapper.pt` (16 in, 4 out) through FTorch;
4. overwrites `fn` for the Aitken (m=1) and accumulation (m=2) modes with the
   emulator output, clipped to [0,1], and recomputes `fs`, `fm` and the fluxes
   for those modes only. The coarse mode keeps its ARG values.

Implementation notes that matter when modifying this code:

- The model path is **hard-coded** in `activate_ml`:
  `/scratch/07088/tg863871/Perlm_Backup/WRF_stam3_ml_mixout_bce_lr1e-4_cosine_more_fix/ml_models/mlp_wrapper.pt`.
  A copy of that file and three alternative trainings are committed under
  `ml_models/` (`mlp_wrapper.pt` is the one used; `_org`, `_DP`, `_alldist_BEST`
  and the top-level `mlp_wrapper_moredata_BEST.pt` are earlier/alternative fits).
  Edit the path before running from another location.
- FTorch tensors wrap two `SAVE`d, fixed-size host buffers and are bound once.
  Re-wrapping per call, or using non-saved allocatables, produced a
  double-free abort inside `ftorch_tensor ... for_finalize` and silently
  returned zeros. Do not "simplify" this back.
- An earlier Aitken/accumulation slot swap on inputs and outputs is disabled
  (left commented). The model was trained in native order; swapping collapsed
  the inline skill (R² 0.998 without swap vs. negative with).
- `fn13/fn14/fn23/fn24` are persistent diagnostic arrays. They are now written
  at the grow/shrink call site too, so they stay in step with `fn11/fn21`.
- `RH_ML` (`grid%rhml`) is a new 3-D state variable computed in
  `module_radiation_driver.F` (`cal_cldfra1`, liquid-only `QV/QVSW`) and passed
  down through the microphysics driver, `chem_driver`, `dry_dep_driver` and
  `module_mixactivate_wrappers` to the activation routine.

## Changes relative to the base commit

| Area | Files | Change |
|------|-------|--------|
| Activation emulator | `phys/module_mixactivate.F`, `phys/module_cam_mp_microp_aero.F` | `activate_ml` + FTorch model loading and inference; extensive `wrf_debug(15,...)` tracing. |
| Plumbing | `chem/module_mixactivate_wrappers.F`, `chem/dry_dep_driver.F`, `chem/chem_driver.F`, `phys/module_microphysics_driver.F`, `phys/module_radiation_driver.F`, `dyn_em/module_first_rk_step_part1.F` | Pass `rh_ml`, moisture tendencies and the new diagnostics through the call chain. |
| Registry | `Registry/registry.chem` | New per-mode activation diagnostics written to wrfout: `fn`, `na`, `vo`, `dl`, `dh`, `sg`, `hg` (4×4 each), `ccn1..6`, and the emulator inputs `emtair`, `empres`, `emrh`, `emwbar`. |
| Registry | `Registry/Registry.EM_COMMON` | `re_cloud/re_ice/re_snow` become history variables and are added to the `morr_two_moment` package; `RHML` added. |
| Radiation coupling | `phys/module_mp_morr_two_moment.F`, `phys/module_physics_init.F` | Morrison effective radius `EFFC` is passed to RRTMG via `re_cloud` (clipped to 1–50 µm). **This is what makes `TAU_QC` non-zero here but zero in `WRF_ARG`.** |
| Aerosol init | `chem/module_data_sorgam.F` | Same SORGAM initial mode diameter change as `WRF_ARG` (`dginin` 0.04, `dginia` 0.16, `dginic` 1.2 µm). |
| Build | `configure`, `compile` | `WRF_CHEM=1` forced on. |
| Scripts | `Liran_WRF_build_Stampede3_FTorch.sh`, `Liran_WRF_build_Perlmutter*.sh`, `WRF_build_Perlmutter.sh`, `gather_runtime.sh`, `liran_testWRF.sh` | Build drivers (Stampede3 with FTorch, Perlmutter variants) and runtime gathering. |
| Runs / analysis | `run/namelist.input`, `test/wrf_campaign.sh`, `test/unstick_case.sh`, `test/check_jobs.sh`, `test/setup_online_dirs.sh`, `test/*.py`, `test/run_all_analysis.sh` | Campaign driver for `20170714_{1aer,3aer}_{org,mid,mid2}`, and the ARG-vs-ML analysis/plot scripts. |

Several files also carry `Liran ...` debug prints (`solve_em.F`, `module_integrate.F`,
`chemics_init.F`, `module_optical_averaging.F`, `module_cu_mskf.F`,
`solve_em_ad.F`). They are harmless but noisy at high debug levels.

Not committed: build products, `configure.wrf`, compile logs, `docker_context/`
(a bundled libtorch), case directories with model output, paper drafts and
figures that lived in `test/`.

## Building on Stampede3

Prerequisites outside this repository, under `$HOME`:

- libtorch 2.4.1 CPU at `~/opt/libtorch-2.4.1-cpu`
- FTorch v1.1.0 source at `~/src/FTorch`, installed to `~/opt/ftorch`
  (must be built with the **same Intel oneAPI compilers** as WRF, otherwise
  the finalizer double-free appears at run time).

Then run `Liran_WRF_build_Stampede3_FTorch.sh` after editing `WRF_DIR`. It loads
`intel/24.0`, `impi/21.11`, `hdf5/1.14.4`, `netcdf/4.9.2`, `pnetcdf/1.12.3`,
`zlib/1.3.1`, `cmake`; optionally rebuilds FTorch (`dobuild_ftorch`); runs
configure (choose `78` INTEL ifx/icx dmpar, nesting `1`) and patches
`configure.wrf` to add `-I$FTORCH_MOD` and link `-lftorch -ltorch_cpu -lc10`
with an rpath to libtorch; then compiles `em_real`.
