import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

variables = [
    # (name, dimensions, description, units)
    ("Times", "Time, DateStrLen", "Time string", ""),
    ("XLAT", "Time, south_north, west_east", "LATITUDE, SOUTH IS NEGATIVE", "degree_north"),
    ("XLONG", "Time, south_north, west_east", "LONGITUDE, WEST IS NEGATIVE", "degree_east"),
    ("LU_INDEX", "Time, south_north, west_east", "LAND USE CATEGORY", ""),
    ("ZNU", "Time, bottom_top", "eta values on half (mass) levels", ""),
    ("ZNW", "Time, bottom_top_stag", "eta values on full (w) levels", ""),
    ("ZS", "Time, soil_layers_stag", "DEPTHS OF CENTERS OF SOIL LAYERS", "m"),
    ("DZS", "Time, soil_layers_stag", "THICKNESSES OF SOIL LAYERS", "m"),
    ("VAR_SSO", "Time, south_north, west_east", "variance of subgrid-scale orography", "m2"),
    ("BATHYMETRY_FLAG", "Time", "Flag for bathymetry in the global attributes for metgrid data", "-"),
    ("U", "Time, bottom_top, south_north, west_east_stag", "x-wind component", "m s-1"),
    ("V", "Time, bottom_top, south_north_stag, west_east", "y-wind component", "m s-1"),
    ("W", "Time, bottom_top_stag, south_north, west_east", "z-wind component", "m s-1"),
    ("PH", "Time, bottom_top_stag, south_north, west_east", "perturbation geopotential", "m2 s-2"),
    ("PHB", "Time, bottom_top_stag, south_north, west_east", "base-state geopotential", "m2 s-2"),
    ("T", "Time, bottom_top, south_north, west_east", "perturbation potential temperature theta-t0", "K"),
    ("THM", "Time, bottom_top, south_north, west_east", "either 1) pert moist pot temp=(1+Rv/Rd Qv)*(theta)-T0, or 2) pert dry pot temp=t", "K"),
    ("HFX_FORCE", "Time", "SCM ideal surface sensible heat flux", "W m-2"),
    ("LH_FORCE", "Time", "SCM ideal surface latent heat flux", "W m-2"),
    ("TSK_FORCE", "Time", "SCM ideal surface skin temperature", "W m-2"),
    ("HFX_FORCE_TEND", "Time", "SCM ideal surface sensible heat flux tendency", "W m-2 s-1"),
    ("LH_FORCE_TEND", "Time", "SCM ideal surface latent heat flux tendency", "W m-2 s-1"),
    ("TSK_FORCE_TEND", "Time", "SCM ideal surface skin temperature tendency", "W m-2 s-1"),
    ("MU", "Time, south_north, west_east", "perturbation dry air mass in column", "Pa"),
    ("MUB", "Time, south_north, west_east", "base state dry air mass in column", "Pa"),
    ("NEST_POS", "Time, south_north, west_east", "-", "-"),
    ("P", "Time, bottom_top, south_north, west_east", "perturbation pressure", "Pa"),
    ("PB", "Time, bottom_top, south_north, west_east", "BASE STATE PRESSURE", "Pa"),
    ("FNM", "Time, bottom_top", "upper weight for vertical stretching", ""),
    ("FNP", "Time, bottom_top", "lower weight for vertical stretching", ""),
    ("RDNW", "Time, bottom_top", "inverse d(eta) values between full (w) levels", ""),
    ("RDN", "Time, bottom_top", "inverse d(eta) values between half (mass) levels", ""),
    ("DNW", "Time, bottom_top", "d(eta) values between full (w) levels", ""),
    ("DN", "Time, bottom_top", "d(eta) values between half (mass) levels", ""),
    ("CFN", "Time", "extrapolation constant", ""),
    ("CFN1", "Time", "extrapolation constant", ""),
    ("THIS_IS_AN_IDEAL_RUN", "Time", "T/F flag: this is an ARW ideal simulation", "-"),
    ("P_HYD", "Time, bottom_top, south_north, west_east", "hydrostatic pressure", "Pa"),
    ("Q2", "Time, south_north, west_east", "QV at 2 M", "kg kg-1"),
    ("T2", "Time, south_north, west_east", "TEMP at 2 M", "K"),
    ("TH2", "Time, south_north, west_east", "POT TEMP at 2 M", "K"),
    ("PSFC", "Time, south_north, west_east", "SFC PRESSURE", "Pa"),
    ("U10", "Time, south_north, west_east", "U at 10 M", "m s-1"),
    ("V10", "Time, south_north, west_east", "V at 10 M", "m s-1"),
    ("RDX", "Time", "INVERSE X GRID LENGTH", "m-1"),
    ("RDY", "Time", "INVERSE Y GRID LENGTH", "m-1"),
    ("AREA2D", "Time, south_north, west_east", "Horizontal grid cell area, using dx, dy, and map factors", "m2"),
    ("DX2D", "Time, south_north, west_east", "Horizontal grid distance: sqrt(area2d)", "m"),
    ("RESM", "Time", "TIME WEIGHT CONSTANT FOR SMALL STEPS", ""),
    ("ZETATOP", "Time", "ZETA AT MODEL TOP", ""),
    ("CF1", "Time", "2nd order extrapolation constant", ""),
    ("CF2", "Time", "2nd order extrapolation constant", ""),
    ("CF3", "Time", "2nd order extrapolation constant", ""),
    ("ITIMESTEP", "Time", "Time step counter", ""),
    ("XTIME", "Time", "minutes since 2017-07-14 00:00:00", "minutes since 2017-07-14 00:00:00"),
    ("QVAPOR", "Time, bottom_top, south_north, west_east", "Water vapor mixing ratio", "kg kg-1"),
    ("QCLOUD", "Time, bottom_top, south_north, west_east", "Cloud water mixing ratio", "kg kg-1"),
    ("QRAIN", "Time, bottom_top, south_north, west_east", "Rain water mixing ratio", "kg kg-1"),
    ("QICE", "Time, bottom_top, south_north, west_east", "Ice mixing ratio", "kg kg-1"),
    ("QSNOW", "Time, bottom_top, south_north, west_east", "Snow mixing ratio", "kg kg-1"),
    ("QGRAUP", "Time, bottom_top, south_north, west_east", "Graupel mixing ratio", "kg kg-1"),
    ("QNICE", "Time, bottom_top, south_north, west_east", "Ice Number concentration", "kg-1"),
    ("QNSNOW", "Time, bottom_top, south_north, west_east", "Snow Number concentration", "kg-1"),
    ("QNRAIN", "Time, bottom_top, south_north, west_east", "Rain Number concentration", "kg-1"),
    ("QNGRAUPEL", "Time, bottom_top, south_north, west_east", "Graupel Number concentration", "kg-1"),
    ("QNDROP", "Time, bottom_top, south_north, west_east", "Droplet number mixing ratio", "kg-1"),
    ("SHDMAX", "Time, south_north, west_east", "ANNUAL MAX VEG FRACTION", ""),
    ("SHDMIN", "Time, south_north, west_east", "ANNUAL MIN VEG FRACTION", ""),
    ("SHDAVG", "Time, south_north, west_east", "ANNUAL AVG VEG FRACTION", ""),
    ("SNOALB", "Time, south_north, west_east", "ANNUAL MAX SNOW ALBEDO IN FRACTION", ""),
    ("TSLB", "Time, soil_layers_stag, south_north, west_east", "SOIL TEMPERATURE", "K"),
    ("SMOIS", "Time, soil_layers_stag, south_north, west_east", "SOIL MOISTURE", "m3 m-3"),
    ("SH2O", "Time, soil_layers_stag, south_north, west_east", "SOIL LIQUID WATER", "m3 m-3"),
    ("SMCREL", "Time, soil_layers_stag, south_north, west_east", "RELATIVE SOIL MOISTURE", ""),
    ("SEAICE", "Time, south_north, west_east", "SEA ICE FLAG", ""),
    ("XICEM", "Time, south_north, west_east", "SEA ICE FLAG (PREVIOUS STEP)", ""),
    ("SFROFF", "Time, south_north, west_east", "SURFACE RUNOFF", "mm"),
    ("UDROFF", "Time, south_north, west_east", "UNDERGROUND RUNOFF", "mm"),
    ("IVGTYP", "Time, south_north, west_east", "DOMINANT VEGETATION CATEGORY", ""),
    ("ISLTYP", "Time, south_north, west_east", "DOMINANT SOIL CATEGORY", ""),
    ("VEGFRA", "Time, south_north, west_east", "VEGETATION FRACTION", ""),
    ("GRDFLX", "Time, south_north, west_east", "GROUND HEAT FLUX", "W m-2"),
    ("ACGRDFLX", "Time, south_north, west_east", "ACCUMULATED GROUND HEAT FLUX", "J m-2"),
    ("ACSNOM", "Time, south_north, west_east", "ACCUMULATED MELTED SNOW", "kg m-2"),
    ("SNOW", "Time, south_north, west_east", "SNOW WATER EQUIVALENT", "kg m-2"),
    ("SNOWH", "Time, south_north, west_east", "PHYSICAL SNOW DEPTH", "m"),
    ("CANWAT", "Time, south_north, west_east", "CANOPY WATER", "kg m-2"),
    ("SSTSK", "Time, south_north, west_east", "SKIN SEA SURFACE TEMPERATURE", "K"),
    ("WATER_DEPTH", "Time, south_north, west_east", "global water depth", "m"),
    ("COSZEN", "Time, south_north, west_east", "COS of SOLAR ZENITH ANGLE", "dimensionless"),
    ("LAI", "Time, south_north, west_east", "LEAF AREA INDEX", "m-2/m-2"),
    ("U10E", "Time, south_north, west_east", "Special U at 10 M from MYJSFC", "m s-1"),
    ("V10E", "Time, south_north, west_east", "Special V at 10 M from MYJSFC", "m s-1"),
    ("DTAUX3D", "Time, bottom_top, south_north, west_east", "LOCAL U GWDO STRESS", "m s-1"),
    ("DTAUY3D", "Time, bottom_top, south_north, west_east", "LOCAL V GWDO STRESS", "m s-1"),
    ("DUSFCG", "Time, south_north, west_east", "COLUMN-INTEGRATED U GWDO STRESS", "Pa m s-1"),
    ("DVSFCG", "Time, south_north, west_east", "COLUMN-INTEGRATED V GWDO STRESS", "Pa m s-1"),
    ("VAR", "Time, south_north, west_east", "STANDARD DEVIATION OF SUBGRID-SCALE OROGRAPHY", "m"),
    ("CON", "Time, south_north, west_east", "OROGRAPHIC CONVEXITY", ""),
    ("OA1", "Time, south_north, west_east", "ASYMMETRY OF SUBGRID-SCALE OROGRAPHY FOR WESTERLY FLOW", ""),
    ("OA2", "Time, south_north, west_east", "ASYMMETRY OF SUBGRID-SCALE OROGRAPHY FOR SOUTHERLY FLOW", ""),
    ("OA3", "Time, south_north, west_east", "ASYMMETRY OF SUBGRID-SCALE OROGRAPHY FOR SOUTH-WESTERLY FLOW", ""),
    ("OA4", "Time, south_north, west_east", "ASYMMETRY OF SUBGRID-SCALE OROGRAPHY FOR NORTH-WESTERLY FLOW", ""),
    ("OL1", "Time, south_north, west_east", "NON-DIMENSIONAL EFFECTIVE OROGRAPHIC LENGTH FOR WESTERLY FLOW", ""),
    ("OL2", "Time, south_north, west_east", "NON-DIMENSIONAL EFFECTIVE OROGRAPHIC LENGTH FOR SOUTHERLY FLOW", ""),
    ("OL3", "Time, south_north, west_east", "NON-DIMENSIONAL EFFECTIVE OROGRAPHIC LENGTH FOR SOUTH-WESTERLY FLOW", ""),
    ("OL4", "Time, south_north, west_east", "NON-DIMENSIONAL EFFECTIVE OROGRAPHIC LENGTH FOR NORTH-WESTERLY FLOW", ""),
    ("TKE_PBL", "Time, bottom_top_stag, south_north, west_east", "TKE from PBL", "m2 s-2"),
    ("O3_GFS_DU", "Time, south_north, west_east", "Total ozone from GFS", "Dobson Units"),
    ("MAPFAC_M", "Time, south_north, west_east", "Map scale factor on mass grid", ""),
    ("MAPFAC_U", "Time, south_north, west_east_stag", "Map scale factor on u-grid", ""),
    ("MAPFAC_V", "Time, south_north_stag, west_east", "Map scale factor on v-grid", ""),
    ("MAPFAC_MX", "Time, south_north, west_east", "Map scale factor on mass grid, x direction", ""),
    ("MAPFAC_MY", "Time, south_north, west_east", "Map scale factor on mass grid, y direction", ""),
    ("MAPFAC_UX", "Time, south_north, west_east_stag", "Map scale factor on u-grid, x direction", ""),
    ("MAPFAC_UY", "Time, south_north, west_east_stag", "Map scale factor on u-grid, y direction", ""),
    ("MAPFAC_VX", "Time, south_north_stag, west_east", "Map scale factor on v-grid, x direction", ""),
    ("MF_VX_INV", "Time, south_north_stag, west_east", "Inverse map scale factor on v-grid, x direction", ""),
    ("MAPFAC_VY", "Time, south_north_stag, west_east", "Map scale factor on v-grid, y direction", ""),
    ("F", "Time, south_north, west_east", "Coriolis sine latitude term", "s-1"),
    ("E", "Time, south_north, west_east", "Coriolis cosine latitude term", "s-1"),
    ("SINALPHA", "Time, south_north, west_east", "Local sine of map rotation", ""),
    ("COSALPHA", "Time, south_north, west_east", "Local cosine of map rotation", ""),
    ("HGT", "Time, south_north, west_east", "Terrain Height", "m"),
    ("TSK", "Time, south_north, west_east", "SURFACE SKIN TEMPERATURE", "K"),
    ("P_TOP", "Time", "PRESSURE TOP OF THE MODEL", "Pa"),
    ("GOT_VAR_SSO", "Time", "whether VAR_SSO was included in WPS output (beginning V3.4)", ""),
    ("T00", "Time", "BASE STATE TEMPERATURE", "K"),
    ("P00", "Time", "BASE STATE PRESSURE", "Pa"),
    ("TLP", "Time", "BASE STATE LAPSE RATE", ""),
    ("TISO", "Time", "TEMP AT WHICH THE BASE T TURNS CONST", "K"),
    ("TLP_STRAT", "Time", "BASE STATE LAPSE RATE (DT/D(LN(P)) IN STRATOSPHERE", "K"),
    ("P_STRAT", "Time", "BASE STATE PRESSURE AT BOTTOM OF STRATOSPHERE", "Pa"),
    ("MAX_MSFTX", "Time", "Max map factor in domain", ""),
    ("MAX_MSFTY", "Time", "Max map factor in domain", ""),
    ("RAINC", "Time, south_north, west_east", "ACCUMULATED TOTAL CUMULUS PRECIPITATION", "mm"),
    ("RAINSH", "Time, south_north, west_east", "ACCUMULATED SHALLOW CUMULUS PRECIPITATION", "mm"),
    ("RAINNC", "Time, south_north, west_east", "ACCUMULATED TOTAL GRID SCALE PRECIPITATION", "mm"),
    ("SNOWNC", "Time, south_north, west_east", "ACCUMULATED TOTAL GRID SCALE SNOW AND ICE", "mm"),
    ("GRAUPELNC", "Time, south_north, west_east", "ACCUMULATED TOTAL GRID SCALE GRAUPEL", "mm"),
    ("HAILNC", "Time, south_north, west_east", "ACCUMULATED TOTAL GRID SCALE HAIL", "mm"),
    ("REFL_10CM", "Time, bottom_top, south_north, west_east", "Radar reflectivity (lamda = 10 cm)", "dBZ"),
    ("CLDFRA", "Time, bottom_top, south_north, west_east", "CLOUD FRACTION", ""),
    ("SWDOWN", "Time, south_north, west_east", "DOWNWARD SHORT WAVE FLUX AT GROUND SURFACE", "W m-2"),
    ("GLW", "Time, south_north, west_east", "DOWNWARD LONG WAVE FLUX AT GROUND SURFACE", "W m-2"),
    ("SWNORM", "Time, south_north, west_east", "NORMAL SHORT WAVE FLUX AT GROUND SURFACE (SLOPE-DEPENDENT)", "W m-2"),
    ("ACSWUPT", "Time, south_north, west_east", "ACCUMULATED UPWELLING SHORTWAVE FLUX AT TOP", "J m-2"),
    ("ACSWUPTC", "Time, south_north, west_east", "ACCUMULATED UPWELLING CLEAR SKY SHORTWAVE FLUX AT TOP", "J m-2"),
    ("ACSWDNT", "Time, south_north, west_east", "ACCUMULATED DOWNWELLING SHORTWAVE FLUX AT TOP", "J m-2"),
    ("ACSWDNTC", "Time, south_north, west_east", "ACCUMULATED DOWNWELLING CLEAR SKY SHORTWAVE FLUX AT TOP", "J m-2"),
    ("ACSWUPB", "Time, south_north, west_east", "ACCUMULATED UPWELLING SHORTWAVE FLUX AT BOTTOM", "J m-2"),
    ("ACSWUPBC", "Time, south_north, west_east", "ACCUMULATED UPWELLING CLEAR SKY SHORTWAVE FLUX AT BOTTOM", "J m-2"),
    ("ACSWDNB", "Time, south_north, west_east", "ACCUMULATED DOWNWELLING SHORTWAVE FLUX AT BOTTOM", "J m-2"),
    ("ACSWDNBC", "Time, south_north, west_east", "ACCUMULATED DOWNWELLING CLEAR SKY SHORTWAVE FLUX AT BOTTOM", "J m-2"),
    ("ACLWUPT", "Time, south_north, west_east", "ACCUMULATED UPWELLING LONGWAVE FLUX AT TOP", "J m-2"),
    ("ACLWUPTC", "Time, south_north, west_east", "ACCUMULATED UPWELLING CLEAR SKY LONGWAVE FLUX AT TOP", "J m-2"),
    ("ACLWDNT", "Time, south_north, west_east", "ACCUMULATED DOWNWELLING LONGWAVE FLUX AT TOP", "J m-2"),
    ("ACLWDNTC", "Time, south_north, west_east", "ACCUMULATED DOWNWELLING CLEAR SKY LONGWAVE FLUX AT TOP", "J m-2"),
    ("ACLWUPB", "Time, south_north, west_east", "ACCUMULATED UPWELLING LONGWAVE FLUX AT BOTTOM", "J m-2"),
    ("ACLWUPBC", "Time, south_north, west_east", "ACCUMULATED UPWELLING CLEAR SKY LONGWAVE FLUX AT BOTTOM", "J m-2"),
    ("ACLWDNB", "Time, south_north, west_east", "ACCUMULATED DOWNWELLING LONGWAVE FLUX AT BOTTOM", "J m-2"),
    ("ACLWDNBC", "Time, south_north, west_east", "ACCUMULATED DOWNWELLING CLEAR SKY LONGWAVE FLUX AT BOTTOM", "J m-2"),
    ("SWUPT", "Time, south_north, west_east", "INSTANTANEOUS UPWELLING SHORTWAVE FLUX AT TOP", "W m-2"),
    ("SWUPTC", "Time, south_north, west_east", "INSTANTANEOUS UPWELLING CLEAR SKY SHORTWAVE FLUX AT TOP", "W m-2"),
    ("SWDNT", "Time, south_north, west_east", "INSTANTANEOUS DOWNWELLING SHORTWAVE FLUX AT TOP", "W m-2"),
    ("SWDNTC", "Time, south_north, west_east", "INSTANTANEOUS DOWNWELLING CLEAR SKY SHORTWAVE FLUX AT TOP", "W m-2"),
    ("SWUPB", "Time, south_north, west_east", "INSTANTANEOUS UPWELLING SHORTWAVE FLUX AT BOTTOM", "W m-2"),
    ("SWUPBC", "Time, south_north, west_east", "INSTANTANEOUS UPWELLING CLEAR SKY SHORTWAVE FLUX AT BOTTOM", "W m-2"),
    ("SWDNB", "Time, south_north, west_east", "INSTANTANEOUS DOWNWELLING SHORTWAVE FLUX AT BOTTOM", "W m-2"),
    ("SWDNBC", "Time, south_north, west_east", "INSTANTANEOUS DOWNWELLING CLEAR SKY SHORTWAVE FLUX AT BOTTOM", "W m-2"),
    ("LWUPT", "Time, south_north, west_east", "INSTANTANEOUS UPWELLING LONGWAVE FLUX AT TOP", "W m-2"),
    ("LWUPTC", "Time, south_north, west_east", "INSTANTANEOUS UPWELLING CLEAR SKY LONGWAVE FLUX AT TOP", "W m-2"),
    ("LWDNT", "Time, south_north, west_east", "INSTANTANEOUS DOWNWELLING LONGWAVE FLUX AT TOP", "W m-2"),
    ("LWDNTC", "Time, south_north, west_east", "INSTANTANEOUS DOWNWELLING CLEAR SKY LONGWAVE FLUX AT TOP", "W m-2"),
    ("LWUPB", "Time, south_north, west_east", "INSTANTANEOUS UPWELLING LONGWAVE FLUX AT BOTTOM", "W m-2"),
    ("LWUPBC", "Time, south_north, west_east", "INSTANTANEOUS UPWELLING CLEAR SKY LONGWAVE FLUX AT BOTTOM", "W m-2"),
    ("LWDNB", "Time, south_north, west_east", "INSTANTANEOUS DOWNWELLING LONGWAVE FLUX AT BOTTOM", "W m-2"),
    ("LWDNBC", "Time, south_north, west_east", "INSTANTANEOUS DOWNWELLING CLEAR SKY LONGWAVE FLUX AT BOTTOM", "W m-2"),
    ("OLR", "Time, south_north, west_east", "TOA OUTGOING LONG WAVE", "W m-2"),
    ("XLAT_U", "Time, south_north, west_east_stag", "LATITUDE, SOUTH IS NEGATIVE", "degree_north"),
    ("XLONG_U", "Time, south_north, west_east_stag", "LONGITUDE, WEST IS NEGATIVE", "degree_east"),
    ("XLAT_V", "Time, south_north_stag, west_east", "LATITUDE, SOUTH IS NEGATIVE", "degree_north"),
    ("XLONG_V", "Time, south_north_stag, west_east", "LONGITUDE, WEST IS NEGATIVE", "degree_east"),
    ("ALBEDO", "Time, south_north, west_east", "ALBEDO", "-"),
    ("CLAT", "Time, south_north, west_east", "COMPUTATIONAL GRID LATITUDE, SOUTH IS NEGATIVE", "degree_north"),
    ("ALBBCK", "Time, south_north, west_east", "BACKGROUND ALBEDO", ""),
    ("EMISS", "Time, south_north, west_east", "SURFACE EMISSIVITY", ""),
    ("NOAHRES", "Time, south_north, west_east", "RESIDUAL OF THE NOAH SURFACE ENERGY BUDGET", "W m-2"),
    ("TMN", "Time, south_north, west_east", "SOIL TEMPERATURE AT LOWER BOUNDARY", "K"),
    ("XLAND", "Time, south_north, west_east", "LAND MASK (1 FOR LAND, 2 FOR WATER)", ""),
    ("UST", "Time, south_north, west_east", "U* IN SIMILARITY THEORY", "m s-1"),
    ("PBLH", "Time, south_north, west_east", "PBL HEIGHT", "m"),
    ("HFX", "Time, south_north, west_east", "UPWARD HEAT FLUX AT THE SURFACE", "W m-2"),
    ("QFX", "Time, south_north, west_east", "UPWARD MOISTURE FLUX AT THE SURFACE", "kg m-2 s-1"),
    ("LH", "Time, south_north, west_east", "LATENT HEAT FLUX AT THE SURFACE", "W m-2"),
    ("ACHFX", "Time, south_north, west_east", "ACCUMULATED UPWARD HEAT FLUX AT THE SURFACE", "J m-2"),
    ("ACLHF", "Time, south_north, west_east", "ACCUMULATED UPWARD LATENT HEAT FLUX AT THE SURFACE", "J m-2"),
    ("SNOWC", "Time, south_north, west_east", "FLAG INDICATING SNOW COVERAGE (1 FOR SNOW COVER)", ""),
    ("SR", "Time, south_north, west_east", "fraction of frozen precipitation", "-"),
    ("SAVE_TOPO_FROM_REAL", "Time", "1=original topo from real/0=topo modified by WRF", "flag"),
    ("REFD_MAX", "Time, south_north, west_east", "MAX DERIVED RADAR REFL", "dbZ"),
    ("ISEEDARR_SPPT", "Time, seed_dim_stag", "Array to hold seed for restart, SPPT", ""),
    ("ISEEDARR_SKEBS", "Time, seed_dim_stag", "Array to hold seed for restart, SKEBS", ""),
    ("ISEEDARR_RAND_PERTURB", "Time, seed_dim_stag", "Array to hold seed for restart, RAND_PERT", ""),
    ("ISEEDARRAY_SPP_CONV", "Time, seed_dim_stag", "Array to hold seed for restart, RAND_PERT2", ""),
    ("ISEEDARRAY_SPP_PBL", "Time, seed_dim_stag", "Array to hold seed for restart, RAND_PERT3", ""),
    ("ISEEDARRAY_SPP_LSM", "Time, seed_dim_stag", "Array to hold seed for restart, RAND_PERT4", ""),
    ("C1H", "Time, bottom_top", "half levels, c1h = d bf / d eta, using znw", "Dimensionless"),
    ("C2H", "Time, bottom_top", "half levels, c2h = (1-c1h)*(p0-pt)", "Pa"),
    ("C1F", "Time, bottom_top_stag", "full levels, c1f = d bf / d eta, using znu", "Dimensionless"),
    ("C2F", "Time, bottom_top_stag", "full levels, c2f = (1-c1f)*(p0-pt)", "Pa"),
    ("C3H", "Time, bottom_top", "half levels, c3h = bh", "Dimensionless"),
    ("C4H", "Time, bottom_top", "half levels, c4h = (eta-bh)*(p0-pt), using znu", "Pa"),
    ("C3F", "Time, bottom_top_stag", "full levels, c3f = bf", "Dimensionless"),
    ("C4F", "Time, bottom_top_stag", "full levels, c4f = (eta-bf)*(p0-pt), using znw", "Pa"),
    ("PCB", "Time, south_north, west_east", "base state dry air mass in column", "Pa"),
    ("PC", "Time, south_north, west_east", "perturbation dry air mass in column", "Pa"),
    ("CLDFRAC2D", "Time, south_north, west_east", "2-D MAX CLOUD FRACTION", "%"),
    ("WVP", "Time, south_north, west_east", "WATER VAPOR PATH", "kg m-2"),
    ("LWP", "Time, south_north, west_east", "LIQUID CLOUD WATER PATH", "kg m-2"),
    ("IWP", "Time, south_north, west_east", "ICE CLOUD WATER PATH", "kg m-2"),
    ("SWP", "Time, south_north, west_east", "SNOW CLOUD WATER PATH", "kg m-2"),
    ("WP_SUM", "Time, south_north, west_east", "SUM OF LWP+IWP+SWP", "kg m-2"),
    ("LWP_TOT", "Time, south_north, west_east", "LIQUID CLOUD WATER PATH RESOLVED + UNRESOLVED", "kg m-2"),
    ("IWP_TOT", "Time, south_north, west_east", "ICE CLOUD WATER PATH RESOLVED + UNRESOLVED", "kg m-2"),
    ("WP_TOT_SUM", "Time, south_north, west_east", "SUM OF LWP+IWP+SWP RESOLVED + UNRESOLVED", "kg m-2"),
    ("RE_QC", "Time, south_north, west_east", "MASS-WEIGHTED LIQUID CLOUD EFFECTIVE RADIUS", "m"),
    ("RE_QI", "Time, south_north, west_east", "MASS-WEIGHTED ICE EFFECTIVE RADIUS", "m"),
    ("RE_QS", "Time, south_north, west_east", "MASS-WEIGHTED SNOW EFFECTIVE RADIUS", "m"),
    ("RE_QC_TOT", "Time, south_north, west_east", "MASS-WEIGHTED LIQUID CLOUD EFFECTIVE RADIUS RESOLVED + UNRESOLVED", "m"),
    ("RE_QI_TOT", "Time, south_north, west_east", "MASS-WEIGHTED ICE EFFECTIVE RADIUS RESOLVED + UNRESOLVED", "m"),
    ("TAU_QC", "Time, south_north, west_east", "MASS-WEIGHTED LIQUID CLOUD OPTICAL THICKNESS", ""),
    ("TAU_QI", "Time, south_north, west_east", "MASS-WEIGHTED ICE OPTICAL THICKNESS", ""),
    ("TAU_QS", "Time, south_north, west_east", "MASS-WEIGHTED SNOW OPTICAL THICKNESS", ""),
    ("TAU_QC_TOT", "Time, south_north, west_east", "MASS-WEIGHTED LIQUID CLOUD OPTICAL THICKNESS RESOLVED + UNRESOLVED", ""),
    ("TAU_QI_TOT", "Time, south_north, west_east", "MASS-WEIGHTED ICE OPTICAL THICKNESS RESOLVED + UNRESOLVED", ""),
    ("CBASEHT", "Time, south_north, west_east", "CLOUD BASE HEIGHT", "m agl"),
    ("CTOPHT", "Time, south_north, west_east", "CLOUD TOP HEIGHT", "m agl"),
    ("CBASEHT_TOT", "Time, south_north, west_east", "CLOUD BASE HEIGHT RESOLVED + UNRESOLVED", "m agl"),
    ("CTOPHT_TOT", "Time, south_north, west_east", "CLOUD TOP HEIGHT RESOLVED + UNRESOLVED", "m agl"),
    ("CLRNIDX", "Time, south_north, west_east", "CLEARNESS INDEX", ""),
    ("SZA", "Time, south_north, west_east", "SOLAR ZENITH ANGLE", "deg"),
    ("GHI_ACCUM", "Time, south_north, west_east", "ACCUMULATED GHI", "J m-2"),
    ("LANDMASK", "Time, south_north, west_east", "LAND MASK (1 FOR LAND, 0 FOR WATER)", ""),
    ("LAKEMASK", "Time, south_north, west_east", "LAKE MASK (1 FOR LAKE, 0 FOR NON-LAKE)", ""),
    ("SST", "Time, south_north, west_east", "SEA SURFACE TEMPERATURE", "K"),
    ("SST_INPUT", "Time, south_north, west_east", "SEA SURFACE TEMPERATURE FROM WRFLOWINPUT FILE", "K"),
]

# Create workbook
wb = openpyxl.Workbook()
ws = wb.active
ws.title = "WRF Variables"

# Styles
header_font = Font(name="Calibri", bold=True, color="FFFFFF", size=11)
header_fill = PatternFill("solid", fgColor="1F4E79")
header_align = Alignment(horizontal="center", vertical="center", wrap_text=True)

alt_fill = PatternFill("solid", fgColor="D6E4F0")
normal_fill = PatternFill("solid", fgColor="FFFFFF")

cell_align = Alignment(horizontal="left", vertical="center", wrap_text=True)
center_align = Alignment(horizontal="center", vertical="center", wrap_text=True)

thin = Side(style="thin", color="BFBFBF")
border = Border(left=thin, right=thin, top=thin, bottom=thin)

# Headers
headers = ["#", "Variable Name", "Dimensions", "Description", "Units"]
col_widths = [5, 22, 45, 60, 20]

for col, (h, w) in enumerate(zip(headers, col_widths), 1):
    cell = ws.cell(row=1, column=col, value=h)
    cell.font = header_font
    cell.fill = header_fill
    cell.alignment = header_align
    cell.border = border
    ws.column_dimensions[get_column_letter(col)].width = w

ws.row_dimensions[1].height = 25

# Data rows
for row_idx, (name, dims, desc, units) in enumerate(variables, 2):
    fill = alt_fill if row_idx % 2 == 0 else normal_fill
    row_data = [row_idx - 1, name, dims, desc, units]
    aligns = [center_align, cell_align, cell_align, cell_align, center_align]
    for col, (val, aln) in enumerate(zip(row_data, aligns), 1):
        cell = ws.cell(row=row_idx, column=col, value=val)
        cell.fill = fill
        cell.alignment = aln
        cell.border = border
        cell.font = Font(name="Calibri", size=10)
    ws.row_dimensions[row_idx].height = 18

# Freeze header row
ws.freeze_panes = "A2"

# Auto-filter
ws.auto_filter.ref = f"A1:E{len(variables)+1}"

output_path = "/home/user/WRF/wrfout_variables.xlsx"
wb.save(output_path)
print(f"Saved: {output_path} ({len(variables)} variables)")
