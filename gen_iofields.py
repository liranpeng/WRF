#!/usr/bin/env python3
"""
Generate my_iofields.txt for dual WRF output stream configuration.

Stream 0 (wrfout):  10-min, Both vars + 13 selected chem vars
                    (minus all-zero and static vars)
Stream 2 (auxhist2): 60-min, Both vars + all Chem vars (full WRF-Chem default)

Usage: python gen_iofields.py
Output: my_iofields.txt
"""

# Variables in BOTH standard WRF and WRF-Chem output
BOTH_VARS = [
    "Times", "XLAT", "XLONG", "XLAT_U", "XLONG_U", "XLAT_V", "XLONG_V",
    "XTIME", "LU_INDEX", "ZNU", "ZNW", "ZS", "DZS", "VAR_SSO",
    "BATHYMETRY_FLAG", "HGT", "LANDMASK", "LAKEMASK", "U", "V", "W",
    "PH", "PHB", "T", "THM", "MU", "MUB", "P", "PB", "P_HYD", "PSFC",
    "P_TOP", "PCB", "PC", "NEST_POS", "FNM", "FNP", "RDNW", "RDN",
    "DNW", "DN", "CFN", "CFN1", "CF1", "CF2", "CF3", "C1H", "C2H",
    "C3H", "C4H", "C1F", "C2F", "C3F", "C4F", "RDX", "RDY", "AREA2D",
    "DX2D", "RESM", "ZETATOP", "T00", "P00", "TLP", "TISO", "TLP_STRAT",
    "P_STRAT", "MAX_MSFTX", "MAX_MSFTY", "ITIMESTEP", "THIS_IS_AN_IDEAL_RUN",
    "GOT_VAR_SSO", "SAVE_TOPO_FROM_REAL", "MAPFAC_M", "MAPFAC_U", "MAPFAC_V",
    "MAPFAC_MX", "MAPFAC_MY", "MAPFAC_UX", "MAPFAC_UY", "MAPFAC_VX",
    "MAPFAC_VY", "MF_VX_INV", "F", "E", "SINALPHA", "COSALPHA",
    "Q2", "T2", "TH2", "U10", "V10", "U10E", "V10E", "TSK", "SST",
    "SST_INPUT", "SSTSK", "WATER_DEPTH", "TMN", "XLAND", "UST", "PBLH",
    "HFX", "QFX", "LH", "ACHFX", "ACLHF", "GRDFLX", "ACGRDFLX",
    "HFX_FORCE", "LH_FORCE", "TSK_FORCE", "HFX_FORCE_TEND",
    "LH_FORCE_TEND", "TSK_FORCE_TEND", "QVAPOR", "QCLOUD", "QRAIN",
    "QICE", "QSNOW", "QGRAUP", "QNICE", "QNSNOW", "QNRAIN", "QNGRAUPEL",
    "QNDROP", "RAINC", "RAINSH", "RAINNC", "SNOWNC", "GRAUPELNC",
    "HAILNC", "ACSNOM", "SR", "TSLB", "SMOIS", "SH2O", "SMCREL",
    "SEAICE", "XICEM", "SFROFF", "UDROFF", "IVGTYP", "ISLTYP", "VEGFRA",
    "SHDMAX", "SHDMIN", "SHDAVG", "SNOALB", "SNOW", "SNOWH", "SNOWC",
    "CANWAT", "COSZEN", "LAI", "ALBEDO", "ALBBCK", "EMISS", "NOAHRES",
    "CLAT", "SWDOWN", "GLW", "SWNORM", "OLR", "ACSWUPT", "ACSWUPTC",
    "ACSWDNT", "ACSWDNTC", "ACSWUPB", "ACSWUPBC", "ACSWDNB", "ACSWDNBC",
    "ACLWUPT", "ACLWUPTC", "ACLWDNT", "ACLWDNTC", "ACLWUPB", "ACLWUPBC",
    "ACLWDNB", "ACLWDNBC", "SWUPT", "SWUPTC", "SWDNT", "SWDNTC", "SWUPB",
    "SWUPBC", "SWDNB", "SWDNBC", "LWUPT", "LWUPTC", "LWDNT", "LWDNTC",
    "LWUPB", "LWUPBC", "LWDNB", "LWDNBC", "SZA", "GHI_ACCUM", "CLRNIDX",
    "O3_GFS_DU", "CLDFRA", "CLDFRAC2D", "REFL_10CM", "REFD_MAX", "WVP",
    "LWP", "IWP", "SWP", "WP_SUM", "LWP_TOT", "IWP_TOT", "WP_TOT_SUM",
    "RE_QC", "RE_QI", "RE_QS", "RE_QC_TOT", "RE_QI_TOT", "TAU_QC",
    "TAU_QI", "TAU_QS", "TAU_QC_TOT", "TAU_QI_TOT", "CBASEHT", "CTOPHT",
    "CBASEHT_TOT", "CTOPHT_TOT", "TKE_PBL", "ISEEDARR_SPPT",
    "ISEEDARR_SKEBS", "ISEEDARR_RAND_PERTURB", "ISEEDARRAY_SPP_CONV",
    "ISEEDARRAY_SPP_PBL", "ISEEDARRAY_SPP_LSM",
]

# Variables present ONLY in WRF-Chem output
CHEM_VARS = [
    "AOD_OUT", "AOD2D_OUT", "ATOP2D_OUT", "EXTCOF55", "CLDFRA2",
    "RAINPROD", "EVAPPROD", "ICN_DIAG", "NC_DIAG", "E_NH3", "EBIO_ISO",
    "EBIO_API", "ACTNH3", "DRY_DEP_LEN", "DRYDEPVEL", "dvel_o3", "UST_T",
    "ROUGH_COR", "SMOIS_COR", "LAI_VEGMASK", "DMS_0", "PM2_5_DRY", "PM10",
    "PHOTR2", "PHOTR4", "SNU", "SAC", "PV", "GAMN2O5", "CN2O5", "KN2O5",
    "YCLNO2", "so2", "sulf", "no2", "no", "o3", "hno3", "h2o2", "ald",
    "hcho", "op1", "op2", "paa", "ora1", "ora2", "nh3", "n2o5", "no3",
    "pan", "hc3", "hc5", "hc8", "eth", "co", "ol2", "olt", "oli", "tol",
    "xyl", "aco3", "tpan", "hono", "hno4", "ket", "gly", "mgly", "dcb",
    "onit", "csl", "iso", "hcl", "ho", "ho2",
    # Aerosol accumulation/Aitken mode ambient
    "so4aj", "so4ai", "nh4aj", "nh4ai", "no3aj", "no3ai", "naaj", "naai",
    "claj", "clai", "orgaro1j", "orgaro1i", "orgaro2j", "orgaro2i",
    "orgalk1j", "orgalk1i", "orgole1j", "orgole1i", "orgba1j", "orgba1i",
    "orgba2j", "orgba2i", "orgba3j", "orgba3i", "orgba4j", "orgba4i",
    "orgpaj", "orgpai", "ecj", "eci", "p25j", "p25i",
    # Coarse mode ambient
    "antha", "seas", "soila", "nu0", "ac0", "corn",
    # In-cloud aerosols
    "so4cwj", "so4cwi", "nh4cwj", "nh4cwi", "no3cwj", "no3cwi",
    "nacwj", "nacwi", "clcwj", "clcwi", "orgaro1cwj", "orgaro1cwi",
    "orgaro2cwj", "orgaro2cwi", "orgalk1cwj", "orgalk1cwi",
    "orgole1cwj", "orgole1cwi", "orgba1cwj", "orgba1cwi",
    "orgba2cwj", "orgba2cwi", "orgba3cwj", "orgba3cwi",
    "orgba4cwj", "orgba4cwi", "orgpacwj", "orgpacwi",
    "eccwj", "eccwi", "p25cwj", "p25cwi",
    "anthcw", "seascw", "soilcw", "nu0cw", "ac0cw", "corncw",
]

# 13 WRF-Chem vars to KEEP in Stream 0 (high-frequency 10-min output)
STREAM0_CHEM_KEEP = {
    "AOD_OUT", "CLDFRA2", "RAINPROD", "NC_DIAG",
    "so4aj", "so4cwj", "anthcw", "so4ai", "so4cwi",
    "seascw", "nu0cw", "ac0cw", "corncw",
}

# Variables confirmed all-zero across all domains in this simulation
ALL_ZERO_VARS = {
    "ACGRDFLX", "ACLWDNT", "ACLWDNTC", "ACSNOM", "BATHYMETRY_FLAG",
    "CANWAT", "CON", "DTAUX3D", "DTAUY3D", "DUSFCG", "DVSFCG",
    "GOT_VAR_SSO", "GRDFLX", "HAILNC", "HFX_FORCE", "HFX_FORCE_TEND",
    "HGT", "ISEEDARRAY_SPP_CONV", "ISEEDARRAY_SPP_LSM", "ISEEDARRAY_SPP_PBL",
    "ISEEDARR_RAND_PERTURB", "ISEEDARR_SKEBS", "ISEEDARR_SPPT",
    "LAKEMASK", "LANDMASK", "LH_FORCE", "LH_FORCE_TEND", "LWDNT", "LWDNTC",
    "MAX_MSFTX", "MAX_MSFTY", "NEST_POS", "NOAHRES", "O3_GFS_DU",
    "OA1", "OA2", "OA3", "OA4", "OL1", "OL2", "OL3", "OL4",
    "PC", "PCB", "P_STRAT", "RAINC", "RAINSH", "REFD_MAX", "RESM",
    "RE_QC", "RE_QC_TOT", "RE_QI", "RE_QI_TOT", "RE_QS",
    "SAVE_TOPO_FROM_REAL", "SEAICE", "SFROFF", "SHDAVG", "SHDMAX", "SHDMIN",
    "SNOW", "SNOWC", "SNOWH", "SSTSK", "SST_INPUT", "SWNORM",
    "TAU_QC", "TAU_QC_TOT", "TAU_QI", "TAU_QI_TOT", "TAU_QS",
    "THIS_IS_AN_IDEAL_RUN", "TSK_FORCE", "TSK_FORCE_TEND",
    "UDROFF", "VAR", "VAR_SSO", "VEGFRA", "XICEM", "ZETATOP",
}

# Variables confirmed static (no change with time) across all domains
STATIC_VARS = {
    "BATHYMETRY_FLAG", "C1F", "C1H", "C2F", "C2H", "C3F", "C3H", "C4F", "C4H",
    "CF1", "CF2", "CF3", "CFN", "CFN1", "DN", "DNW", "DZS", "FNM", "FNP",
    "GOT_VAR_SSO", "HFX_FORCE", "HFX_FORCE_TEND",
    "ISEEDARRAY_SPP_CONV", "ISEEDARRAY_SPP_LSM", "ISEEDARRAY_SPP_PBL",
    "ISEEDARR_RAND_PERTURB", "ISEEDARR_SKEBS", "ISEEDARR_SPPT",
    "LH_FORCE", "LH_FORCE_TEND", "MAX_MSFTX", "MAX_MSFTY",
    "P00", "P_STRAT", "P_TOP", "RDN", "RDNW", "RESM",
    "SAVE_TOPO_FROM_REAL", "T00", "THIS_IS_AN_IDEAL_RUN", "TISO", "TLP",
    "TLP_STRAT", "TSK_FORCE", "TSK_FORCE_TEND", "ZETATOP",
    "ZNU", "ZNW", "ZS",
}

# Extra scheme-specific aerosol vars to remove from Stream 0
# (FN31-44, NA31-44, SG11-44, DL11-44, DH11-44, HG31-44)
STREAM0_EXTRA_REMOVE = [
    "FN31", "FN32", "FN33", "FN34", "FN41", "FN42", "FN43", "FN44",
    "NA31", "NA32", "NA33", "NA34", "NA41", "NA42", "NA43", "NA44",
    "SG11", "SG12", "SG13", "SG14", "SG21", "SG22", "SG23", "SG24",
    "SG31", "SG32", "SG33", "SG34", "SG41", "SG42", "SG43", "SG44",
    "DL11", "DL12", "DL13", "DL14", "DL21", "DL22", "DL23", "DL24",
    "DL31", "DL32", "DL33", "DL34", "DL41", "DL42", "DL43", "DL44",
    "DH11", "DH12", "DH13", "DH14", "DH21", "DH22", "DH23", "DH24",
    "DH31", "DH32", "DH33", "DH34", "DH41", "DH42", "DH43", "DH44",
    "HG31", "HG32", "HG33", "HG34", "HG41", "HG42", "HG43", "HG44",
]


def chunked(lst, n=10):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


def write_iofields(outfile="my_iofields.txt"):
    # Chem vars to REMOVE from Stream 0 (all except the 13 kept ones)
    chem_remove_s0 = [v for v in CHEM_VARS if v not in STREAM0_CHEM_KEEP]

    # Both vars to REMOVE from Stream 0: all-zero union static
    # Exclude any that are in STREAM0_CHEM_KEEP (safety check)
    diag_remove_set = ALL_ZERO_VARS | STATIC_VARS
    # Only remove vars that are actually in BOTH_VARS (stream 0 default output)
    both_vars_set = set(BOTH_VARS)
    diag_remove_s0 = sorted(
        v for v in diag_remove_set if v in both_vars_set and v not in STREAM0_CHEM_KEEP
    )

    # All vars to ADD to Stream 2 (Both + all Chem)
    stream2_add = BOTH_VARS + CHEM_VARS

    lines = []

    lines.append("# ============================================================")
    lines.append("# WRF dual-stream iofields configuration")
    lines.append("#")
    lines.append("# Stream 0 (wrfout):   10-min, Both + 13 selected chem vars")
    lines.append("#                      (minus all-zero and static vars)")
    lines.append("# Stream 2 (auxhist2): 60-min, Both + all Chem vars")
    lines.append("# ============================================================")
    lines.append("")

    # --- Stream 0: remove unwanted chem vars ---
    lines.append(f"# Stream 0: remove {len(chem_remove_s0)} WRF-Chem-only vars")
    lines.append(f"# Kept chem vars: {', '.join(sorted(STREAM0_CHEM_KEEP))}")
    for chunk in chunked(chem_remove_s0):
        lines.append("-:h:0:" + ",".join(chunk))
    lines.append("")

    # --- Stream 0: remove all-zero and static vars ---
    lines.append(f"# Stream 0: remove {len(diag_remove_s0)} all-zero / static vars")
    for chunk in chunked(diag_remove_s0):
        lines.append("-:h:0:" + ",".join(chunk))
    lines.append("")

    # --- Stream 0: remove extra scheme-specific aerosol vars ---
    lines.append(f"# Stream 0: remove {len(STREAM0_EXTRA_REMOVE)} extra scheme-specific vars")
    for chunk in chunked(STREAM0_EXTRA_REMOVE):
        lines.append("-:h:0:" + ",".join(chunk))
    lines.append("")

    # --- Stream 2: add all Both + Chem vars ---
    lines.append(f"# Stream 2: add {len(stream2_add)} vars (Both + all Chem)")
    for chunk in chunked(stream2_add):
        lines.append("+:h:2:" + ",".join(chunk))
    lines.append("")

    with open(outfile, "w") as f:
        f.write("\n".join(lines) + "\n")

    total_s0_remove = len(chem_remove_s0) + len(diag_remove_s0) + len(STREAM0_EXTRA_REMOVE)
    print(f"Written {outfile}")
    print(f"  Stream 0 removals : {total_s0_remove} vars total")
    print(f"    Chem-only vars   : {len(chem_remove_s0)}")
    print(f"    All-zero/static  : {len(diag_remove_s0)}")
    print(f"    Extra scheme vars: {len(STREAM0_EXTRA_REMOVE)}")
    print(f"  Stream 2 additions: {len(stream2_add)} vars")
    print(f"    Both vars        : {len(BOTH_VARS)}")
    print(f"    Chem vars        : {len(CHEM_VARS)}")
    print(f"  Stream 0 chem kept: {len(STREAM0_CHEM_KEEP)} vars")


if __name__ == "__main__":
    write_iofields()
