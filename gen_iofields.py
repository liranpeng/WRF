#!/usr/bin/env python3
"""
Generate my_iofields.txt for dual WRF output stream configuration.

Stream 0 (wrfout):  10-min, Both vars + 13 selected chem vars
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


def chunked(lst, n=10):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


def write_iofields(outfile="my_iofields.txt"):
    # Chem vars to REMOVE from Stream 0 (all except the 13 kept ones)
    chem_remove_s0 = [v for v in CHEM_VARS if v not in STREAM0_CHEM_KEEP]

    # All vars to ADD to Stream 2 (Both + all Chem)
    stream2_add = BOTH_VARS + CHEM_VARS

    lines = []

    lines.append("# ============================================================")
    lines.append("# WRF dual-stream iofields configuration")
    lines.append("#")
    lines.append("# Stream 0 (wrfout):   10-min, Both + 13 selected chem vars")
    lines.append("# Stream 2 (auxhist2): 60-min, Both + all Chem vars")
    lines.append("# ============================================================")
    lines.append("")

    # --- Stream 0: remove unwanted chem vars ---
    lines.append(f"# Stream 0: remove {len(chem_remove_s0)} WRF-Chem-only vars")
    lines.append(f"# Kept chem vars: {', '.join(sorted(STREAM0_CHEM_KEEP))}")
    for chunk in chunked(chem_remove_s0):
        lines.append("-:h:0:" + ",".join(chunk))
    lines.append("")

    # --- Stream 2: add all Both + Chem vars ---
    lines.append(f"# Stream 2: add {len(stream2_add)} vars (Both + all Chem)")
    for chunk in chunked(stream2_add):
        lines.append("+:h:2:" + ",".join(chunk))
    lines.append("")

    with open(outfile, "w") as f:
        f.write("\n".join(lines) + "\n")

    print(f"Written {outfile}")
    print(f"  Stream 0 removals : {len(chem_remove_s0)} vars")
    print(f"  Stream 2 additions: {len(stream2_add)} vars")
    print(f"    Both vars        : {len(BOTH_VARS)}")
    print(f"    Chem vars        : {len(CHEM_VARS)}")
    print(f"  Stream 0 chem kept: {len(STREAM0_CHEM_KEEP)} vars")


if __name__ == "__main__":
    write_iofields()
