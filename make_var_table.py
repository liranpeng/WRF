import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

# (name, dimensions, description, units, source)
# source: "WRF" = standard WRF only, "Chem" = WRF-Chem only, "Both" = in both
variables = [
    # ---------- Coordinate / Grid ----------
    ("Times",           "Time, DateStrLen",                          "Time string",                                              "",                          "Both"),
    ("XLAT",            "Time, south_north, west_east",              "LATITUDE, SOUTH IS NEGATIVE",                              "degree_north",              "Both"),
    ("XLONG",           "Time, south_north, west_east",              "LONGITUDE, WEST IS NEGATIVE",                              "degree_east",               "Both"),
    ("XLAT_U",          "Time, south_north, west_east_stag",         "LATITUDE, SOUTH IS NEGATIVE",                              "degree_north",              "Both"),
    ("XLONG_U",         "Time, south_north, west_east_stag",         "LONGITUDE, WEST IS NEGATIVE",                              "degree_east",               "Both"),
    ("XLAT_V",          "Time, south_north_stag, west_east",         "LATITUDE, SOUTH IS NEGATIVE",                              "degree_north",              "Both"),
    ("XLONG_V",         "Time, south_north_stag, west_east",         "LONGITUDE, WEST IS NEGATIVE",                              "degree_east",               "Both"),
    ("XTIME",           "Time",                                      "minutes since 2017-07-14 00:00:00",                        "minutes",                   "Both"),
    ("LU_INDEX",        "Time, south_north, west_east",              "LAND USE CATEGORY",                                        "",                          "Both"),
    ("ZNU",             "Time, bottom_top",                          "eta values on half (mass) levels",                         "",                          "Both"),
    ("ZNW",             "Time, bottom_top_stag",                     "eta values on full (w) levels",                            "",                          "Both"),
    ("ZS",              "Time, soil_layers_stag",                    "DEPTHS OF CENTERS OF SOIL LAYERS",                         "m",                         "Both"),
    ("DZS",             "Time, soil_layers_stag",                    "THICKNESSES OF SOIL LAYERS",                               "m",                         "Both"),
    ("VAR_SSO",         "Time, south_north, west_east",              "variance of subgrid-scale orography",                      "m2",                        "Both"),
    ("BATHYMETRY_FLAG", "Time",                                      "Flag for bathymetry in the global attributes for metgrid", "-",                         "Both"),
    ("HGT",             "Time, south_north, west_east",              "Terrain Height",                                           "m",                         "Both"),
    ("LANDMASK",        "Time, south_north, west_east",              "LAND MASK (1 FOR LAND, 0 FOR WATER)",                      "",                          "Both"),
    ("LAKEMASK",        "Time, south_north, west_east",              "LAKE MASK (1 FOR LAKE, 0 FOR NON-LAKE)",                   "",                          "Both"),
    # ---------- Dynamics ----------
    ("U",               "Time, bottom_top, south_north, west_east_stag",   "x-wind component",                                  "m s-1",                     "Both"),
    ("V",               "Time, bottom_top, south_north_stag, west_east",   "y-wind component",                                  "m s-1",                     "Both"),
    ("W",               "Time, bottom_top_stag, south_north, west_east",   "z-wind component",                                  "m s-1",                     "Both"),
    ("PH",              "Time, bottom_top_stag, south_north, west_east",   "perturbation geopotential",                         "m2 s-2",                    "Both"),
    ("PHB",             "Time, bottom_top_stag, south_north, west_east",   "base-state geopotential",                           "m2 s-2",                    "Both"),
    ("T",               "Time, bottom_top, south_north, west_east",        "perturbation potential temperature theta-t0",        "K",                         "Both"),
    ("THM",             "Time, bottom_top, south_north, west_east",        "pert moist/dry pot temp",                            "K",                         "Both"),
    ("MU",              "Time, south_north, west_east",                    "perturbation dry air mass in column",                "Pa",                        "Both"),
    ("MUB",             "Time, south_north, west_east",                    "base state dry air mass in column",                  "Pa",                        "Both"),
    ("P",               "Time, bottom_top, south_north, west_east",        "perturbation pressure",                              "Pa",                        "Both"),
    ("PB",              "Time, bottom_top, south_north, west_east",        "BASE STATE PRESSURE",                                "Pa",                        "Both"),
    ("P_HYD",           "Time, bottom_top, south_north, west_east",        "hydrostatic pressure",                               "Pa",                        "Both"),
    ("PSFC",            "Time, south_north, west_east",                    "SFC PRESSURE",                                       "Pa",                        "Both"),
    ("P_TOP",           "Time",                                            "PRESSURE TOP OF THE MODEL",                          "Pa",                        "Both"),
    ("PCB",             "Time, south_north, west_east",                    "base state dry air mass in column",                  "Pa",                        "Both"),
    ("PC",              "Time, south_north, west_east",                    "perturbation dry air mass in column",                "Pa",                        "Both"),
    ("NEST_POS",        "Time, south_north, west_east",                    "-",                                                  "-",                         "Both"),
    # ---------- Vertical coordinates / constants ----------
    ("FNM",             "Time, bottom_top",   "upper weight for vertical stretching",                  "",               "Both"),
    ("FNP",             "Time, bottom_top",   "lower weight for vertical stretching",                  "",               "Both"),
    ("RDNW",            "Time, bottom_top",   "inverse d(eta) values between full (w) levels",         "",               "Both"),
    ("RDN",             "Time, bottom_top",   "inverse d(eta) values between half (mass) levels",      "",               "Both"),
    ("DNW",             "Time, bottom_top",   "d(eta) values between full (w) levels",                 "",               "Both"),
    ("DN",              "Time, bottom_top",   "d(eta) values between half (mass) levels",              "",               "Both"),
    ("CFN",             "Time",               "extrapolation constant",                                 "",               "Both"),
    ("CFN1",            "Time",               "extrapolation constant",                                 "",               "Both"),
    ("CF1",             "Time",               "2nd order extrapolation constant",                       "",               "Both"),
    ("CF2",             "Time",               "2nd order extrapolation constant",                       "",               "Both"),
    ("CF3",             "Time",               "2nd order extrapolation constant",                       "",               "Both"),
    ("C1H",             "Time, bottom_top",         "half levels, c1h = d bf / d eta, using znw",      "Dimensionless",  "Both"),
    ("C2H",             "Time, bottom_top",         "half levels, c2h = (1-c1h)*(p0-pt)",              "Pa",             "Both"),
    ("C3H",             "Time, bottom_top",         "half levels, c3h = bh",                           "Dimensionless",  "Both"),
    ("C4H",             "Time, bottom_top",         "half levels, c4h = (eta-bh)*(p0-pt), using znu", "Pa",             "Both"),
    ("C1F",             "Time, bottom_top_stag",    "full levels, c1f = d bf / d eta, using znu",      "Dimensionless",  "Both"),
    ("C2F",             "Time, bottom_top_stag",    "full levels, c2f = (1-c1f)*(p0-pt)",              "Pa",             "Both"),
    ("C3F",             "Time, bottom_top_stag",    "full levels, c3f = bf",                           "Dimensionless",  "Both"),
    ("C4F",             "Time, bottom_top_stag",    "full levels, c4f = (eta-bf)*(p0-pt), using znw", "Pa",             "Both"),
    ("RDX",             "Time",               "INVERSE X GRID LENGTH",                                 "m-1",            "Both"),
    ("RDY",             "Time",               "INVERSE Y GRID LENGTH",                                 "m-1",            "Both"),
    ("AREA2D",          "Time, south_north, west_east", "Horizontal grid cell area",                  "m2",             "Both"),
    ("DX2D",            "Time, south_north, west_east", "Horizontal grid distance: sqrt(area2d)",     "m",              "Both"),
    ("RESM",            "Time",               "TIME WEIGHT CONSTANT FOR SMALL STEPS",                  "",               "Both"),
    ("ZETATOP",         "Time",               "ZETA AT MODEL TOP",                                     "",               "Both"),
    ("T00",             "Time",               "BASE STATE TEMPERATURE",                                 "K",              "Both"),
    ("P00",             "Time",               "BASE STATE PRESSURE",                                    "Pa",             "Both"),
    ("TLP",             "Time",               "BASE STATE LAPSE RATE",                                  "",               "Both"),
    ("TISO",            "Time",               "TEMP AT WHICH THE BASE T TURNS CONST",                  "K",              "Both"),
    ("TLP_STRAT",       "Time",               "BASE STATE LAPSE RATE IN STRATOSPHERE",                 "K",              "Both"),
    ("P_STRAT",         "Time",               "BASE STATE PRESSURE AT BOTTOM OF STRATOSPHERE",         "Pa",             "Both"),
    ("MAX_MSFTX",       "Time",               "Max map factor in domain",                               "",               "Both"),
    ("MAX_MSFTY",       "Time",               "Max map factor in domain",                               "",               "Both"),
    ("ITIMESTEP",       "Time",               "Time step counter",                                      "",               "Both"),
    ("THIS_IS_AN_IDEAL_RUN", "Time",          "T/F flag: this is an ARW ideal simulation",             "-",              "Both"),
    ("GOT_VAR_SSO",     "Time",               "whether VAR_SSO was included in WPS output",            "",               "Both"),
    ("SAVE_TOPO_FROM_REAL", "Time",           "1=original topo from real / 0=topo modified by WRF",   "flag",           "Both"),
    # ---------- Map factors / Coriolis ----------
    ("MAPFAC_M",        "Time, south_north, west_east",          "Map scale factor on mass grid",              "",  "Both"),
    ("MAPFAC_U",        "Time, south_north, west_east_stag",     "Map scale factor on u-grid",                 "",  "Both"),
    ("MAPFAC_V",        "Time, south_north_stag, west_east",     "Map scale factor on v-grid",                 "",  "Both"),
    ("MAPFAC_MX",       "Time, south_north, west_east",          "Map scale factor on mass grid, x direction", "",  "Both"),
    ("MAPFAC_MY",       "Time, south_north, west_east",          "Map scale factor on mass grid, y direction", "",  "Both"),
    ("MAPFAC_UX",       "Time, south_north, west_east_stag",     "Map scale factor on u-grid, x direction",   "",  "Both"),
    ("MAPFAC_UY",       "Time, south_north, west_east_stag",     "Map scale factor on u-grid, y direction",   "",  "Both"),
    ("MAPFAC_VX",       "Time, south_north_stag, west_east",     "Map scale factor on v-grid, x direction",   "",  "Both"),
    ("MAPFAC_VY",       "Time, south_north_stag, west_east",     "Map scale factor on v-grid, y direction",   "",  "Both"),
    ("MF_VX_INV",       "Time, south_north_stag, west_east",     "Inverse map scale factor on v-grid, x",     "",  "Both"),
    ("F",               "Time, south_north, west_east",          "Coriolis sine latitude term",                "s-1", "Both"),
    ("E",               "Time, south_north, west_east",          "Coriolis cosine latitude term",              "s-1", "Both"),
    ("SINALPHA",        "Time, south_north, west_east",          "Local sine of map rotation",                 "",  "Both"),
    ("COSALPHA",        "Time, south_north, west_east",          "Local cosine of map rotation",               "",  "Both"),
    # ---------- Thermodynamics / surface ----------
    ("Q2",              "Time, south_north, west_east",   "QV at 2 M",                         "kg kg-1",  "Both"),
    ("T2",              "Time, south_north, west_east",   "TEMP at 2 M",                       "K",        "Both"),
    ("TH2",             "Time, south_north, west_east",   "POT TEMP at 2 M",                   "K",        "Both"),
    ("U10",             "Time, south_north, west_east",   "U at 10 M",                         "m s-1",    "Both"),
    ("V10",             "Time, south_north, west_east",   "V at 10 M",                         "m s-1",    "Both"),
    ("U10E",            "Time, south_north, west_east",   "Special U at 10 M from MYJSFC",     "m s-1",    "Both"),
    ("V10E",            "Time, south_north, west_east",   "Special V at 10 M from MYJSFC",     "m s-1",    "Both"),
    ("TSK",             "Time, south_north, west_east",   "SURFACE SKIN TEMPERATURE",          "K",        "Both"),
    ("SST",             "Time, south_north, west_east",   "SEA SURFACE TEMPERATURE",           "K",        "Both"),
    ("SST_INPUT",       "Time, south_north, west_east",   "SEA SURFACE TEMPERATURE FROM WRFLOWINPUT FILE", "K", "Both"),
    ("SSTSK",           "Time, south_north, west_east",   "SKIN SEA SURFACE TEMPERATURE",      "K",        "Both"),
    ("WATER_DEPTH",     "Time, south_north, west_east",   "global water depth",                "m",        "Both"),
    ("TMN",             "Time, south_north, west_east",   "SOIL TEMPERATURE AT LOWER BOUNDARY","K",        "Both"),
    ("XLAND",           "Time, south_north, west_east",   "LAND MASK (1 FOR LAND, 2 FOR WATER)","",       "Both"),
    ("UST",             "Time, south_north, west_east",   "U* IN SIMILARITY THEORY",           "m s-1",    "Both"),
    ("PBLH",            "Time, south_north, west_east",   "PBL HEIGHT",                        "m",        "Both"),
    ("HFX",             "Time, south_north, west_east",   "UPWARD HEAT FLUX AT THE SURFACE",   "W m-2",    "Both"),
    ("QFX",             "Time, south_north, west_east",   "UPWARD MOISTURE FLUX AT THE SURFACE","kg m-2 s-1","Both"),
    ("LH",              "Time, south_north, west_east",   "LATENT HEAT FLUX AT THE SURFACE",   "W m-2",    "Both"),
    ("ACHFX",           "Time, south_north, west_east",   "ACCUMULATED UPWARD HEAT FLUX AT THE SURFACE","J m-2","Both"),
    ("ACLHF",           "Time, south_north, west_east",   "ACCUMULATED UPWARD LATENT HEAT FLUX AT THE SURFACE","J m-2","Both"),
    ("GRDFLX",          "Time, south_north, west_east",   "GROUND HEAT FLUX",                  "W m-2",    "Both"),
    ("ACGRDFLX",        "Time, south_north, west_east",   "ACCUMULATED GROUND HEAT FLUX",      "J m-2",    "Both"),
    ("HFX_FORCE",       "Time",  "SCM ideal surface sensible heat flux",          "W m-2",    "Both"),
    ("LH_FORCE",        "Time",  "SCM ideal surface latent heat flux",            "W m-2",    "Both"),
    ("TSK_FORCE",       "Time",  "SCM ideal surface skin temperature",            "W m-2",    "Both"),
    ("HFX_FORCE_TEND",  "Time",  "SCM ideal surface sensible heat flux tendency", "W m-2 s-1","Both"),
    ("LH_FORCE_TEND",   "Time",  "SCM ideal surface latent heat flux tendency",   "W m-2 s-1","Both"),
    ("TSK_FORCE_TEND",  "Time",  "SCM ideal surface skin temperature tendency",   "W m-2 s-1","Both"),
    # ---------- Moisture ----------
    ("QVAPOR",          "Time, bottom_top, south_north, west_east", "Water vapor mixing ratio",   "kg kg-1", "Both"),
    ("QCLOUD",          "Time, bottom_top, south_north, west_east", "Cloud water mixing ratio",   "kg kg-1", "Both"),
    ("QRAIN",           "Time, bottom_top, south_north, west_east", "Rain water mixing ratio",    "kg kg-1", "Both"),
    ("QICE",            "Time, bottom_top, south_north, west_east", "Ice mixing ratio",           "kg kg-1", "Both"),
    ("QSNOW",           "Time, bottom_top, south_north, west_east", "Snow mixing ratio",          "kg kg-1", "Both"),
    ("QGRAUP",          "Time, bottom_top, south_north, west_east", "Graupel mixing ratio",       "kg kg-1", "Both"),
    ("QNICE",           "Time, bottom_top, south_north, west_east", "Ice Number concentration",   "kg-1",    "Both"),
    ("QNSNOW",          "Time, bottom_top, south_north, west_east", "Snow Number concentration",  "kg-1",    "Both"),
    ("QNRAIN",          "Time, bottom_top, south_north, west_east", "Rain Number concentration",  "kg-1",    "Both"),
    ("QNGRAUPEL",       "Time, bottom_top, south_north, west_east", "Graupel Number concentration","kg-1",   "Both"),
    ("QNDROP",          "Time, bottom_top, south_north, west_east", "Droplet number mixing ratio","kg-1",    "Both"),
    # ---------- Precipitation ----------
    ("RAINC",           "Time, south_north, west_east", "ACCUMULATED TOTAL CUMULUS PRECIPITATION",    "mm", "Both"),
    ("RAINSH",          "Time, south_north, west_east", "ACCUMULATED SHALLOW CUMULUS PRECIPITATION",  "mm", "Both"),
    ("RAINNC",          "Time, south_north, west_east", "ACCUMULATED TOTAL GRID SCALE PRECIPITATION", "mm", "Both"),
    ("SNOWNC",          "Time, south_north, west_east", "ACCUMULATED TOTAL GRID SCALE SNOW AND ICE",  "mm", "Both"),
    ("GRAUPELNC",       "Time, south_north, west_east", "ACCUMULATED TOTAL GRID SCALE GRAUPEL",       "mm", "Both"),
    ("HAILNC",          "Time, south_north, west_east", "ACCUMULATED TOTAL GRID SCALE HAIL",          "mm", "Both"),
    ("ACSNOM",          "Time, south_north, west_east", "ACCUMULATED MELTED SNOW",                    "kg m-2", "Both"),
    ("SR",              "Time, south_north, west_east", "fraction of frozen precipitation",            "-",  "Both"),
    # ---------- Land surface ----------
    ("TSLB",   "Time, soil_layers_stag, south_north, west_east", "SOIL TEMPERATURE",              "K",        "Both"),
    ("SMOIS",  "Time, soil_layers_stag, south_north, west_east", "SOIL MOISTURE",                 "m3 m-3",   "Both"),
    ("SH2O",   "Time, soil_layers_stag, south_north, west_east", "SOIL LIQUID WATER",             "m3 m-3",   "Both"),
    ("SMCREL", "Time, soil_layers_stag, south_north, west_east", "RELATIVE SOIL MOISTURE",        "",         "Both"),
    ("SEAICE",          "Time, south_north, west_east", "SEA ICE FLAG",                           "",  "Both"),
    ("XICEM",           "Time, south_north, west_east", "SEA ICE FLAG (PREVIOUS STEP)",           "",  "Both"),
    ("SFROFF",          "Time, south_north, west_east", "SURFACE RUNOFF",                         "mm","Both"),
    ("UDROFF",          "Time, south_north, west_east", "UNDERGROUND RUNOFF",                     "mm","Both"),
    ("IVGTYP",          "Time, south_north, west_east", "DOMINANT VEGETATION CATEGORY",           "",  "Both"),
    ("ISLTYP",          "Time, south_north, west_east", "DOMINANT SOIL CATEGORY",                 "",  "Both"),
    ("VEGFRA",          "Time, south_north, west_east", "VEGETATION FRACTION",                    "",  "Both"),
    ("SHDMAX",          "Time, south_north, west_east", "ANNUAL MAX VEG FRACTION",                "",  "Both"),
    ("SHDMIN",          "Time, south_north, west_east", "ANNUAL MIN VEG FRACTION",                "",  "Both"),
    ("SHDAVG",          "Time, south_north, west_east", "ANNUAL AVG VEG FRACTION",                "",  "Both"),
    ("SNOALB",          "Time, south_north, west_east", "ANNUAL MAX SNOW ALBEDO IN FRACTION",     "",  "Both"),
    ("SNOW",            "Time, south_north, west_east", "SNOW WATER EQUIVALENT",                  "kg m-2", "Both"),
    ("SNOWH",           "Time, south_north, west_east", "PHYSICAL SNOW DEPTH",                    "m", "Both"),
    ("SNOWC",           "Time, south_north, west_east", "FLAG INDICATING SNOW COVERAGE",          "",  "Both"),
    ("CANWAT",          "Time, south_north, west_east", "CANOPY WATER",                           "kg m-2", "Both"),
    ("COSZEN",          "Time, south_north, west_east", "COS of SOLAR ZENITH ANGLE",              "dimensionless", "Both"),
    ("LAI",             "Time, south_north, west_east", "LEAF AREA INDEX",                        "m-2/m-2", "Both"),
    ("ALBEDO",          "Time, south_north, west_east", "ALBEDO",                                 "-",  "Both"),
    ("ALBBCK",          "Time, south_north, west_east", "BACKGROUND ALBEDO",                      "",   "Both"),
    ("EMISS",           "Time, south_north, west_east", "SURFACE EMISSIVITY",                     "",   "Both"),
    ("NOAHRES",         "Time, south_north, west_east", "RESIDUAL OF THE NOAH SURFACE ENERGY BUDGET","W m-2","Both"),
    ("CLAT",            "Time, south_north, west_east", "COMPUTATIONAL GRID LATITUDE, SOUTH IS NEGATIVE","degree_north","Both"),
    # ---------- Radiation ----------
    ("SWDOWN",   "Time, south_north, west_east", "DOWNWARD SHORT WAVE FLUX AT GROUND SURFACE",     "W m-2",  "Both"),
    ("GLW",      "Time, south_north, west_east", "DOWNWARD LONG WAVE FLUX AT GROUND SURFACE",      "W m-2",  "Both"),
    ("SWNORM",   "Time, south_north, west_east", "NORMAL SHORT WAVE FLUX AT GROUND SURFACE",       "W m-2",  "Both"),
    ("OLR",      "Time, south_north, west_east", "TOA OUTGOING LONG WAVE",                         "W m-2",  "Both"),
    ("ACSWUPT",  "Time, south_north, west_east", "ACCUMULATED UPWELLING SHORTWAVE FLUX AT TOP",    "J m-2",  "Both"),
    ("ACSWUPTC", "Time, south_north, west_east", "ACCUMULATED UPWELLING CLEAR SKY SW AT TOP",      "J m-2",  "Both"),
    ("ACSWDNT",  "Time, south_north, west_east", "ACCUMULATED DOWNWELLING SHORTWAVE FLUX AT TOP",  "J m-2",  "Both"),
    ("ACSWDNTC", "Time, south_north, west_east", "ACCUMULATED DOWNWELLING CLEAR SKY SW AT TOP",    "J m-2",  "Both"),
    ("ACSWUPB",  "Time, south_north, west_east", "ACCUMULATED UPWELLING SHORTWAVE FLUX AT BOTTOM", "J m-2",  "Both"),
    ("ACSWUPBC", "Time, south_north, west_east", "ACCUMULATED UPWELLING CLEAR SKY SW AT BOTTOM",   "J m-2",  "Both"),
    ("ACSWDNB",  "Time, south_north, west_east", "ACCUMULATED DOWNWELLING SHORTWAVE FLUX AT BOTTOM","J m-2", "Both"),
    ("ACSWDNBC", "Time, south_north, west_east", "ACCUMULATED DOWNWELLING CLEAR SKY SW AT BOTTOM", "J m-2",  "Both"),
    ("ACLWUPT",  "Time, south_north, west_east", "ACCUMULATED UPWELLING LONGWAVE FLUX AT TOP",     "J m-2",  "Both"),
    ("ACLWUPTC", "Time, south_north, west_east", "ACCUMULATED UPWELLING CLEAR SKY LW AT TOP",      "J m-2",  "Both"),
    ("ACLWDNT",  "Time, south_north, west_east", "ACCUMULATED DOWNWELLING LONGWAVE FLUX AT TOP",   "J m-2",  "Both"),
    ("ACLWDNTC", "Time, south_north, west_east", "ACCUMULATED DOWNWELLING CLEAR SKY LW AT TOP",    "J m-2",  "Both"),
    ("ACLWUPB",  "Time, south_north, west_east", "ACCUMULATED UPWELLING LONGWAVE FLUX AT BOTTOM",  "J m-2",  "Both"),
    ("ACLWUPBC", "Time, south_north, west_east", "ACCUMULATED UPWELLING CLEAR SKY LW AT BOTTOM",   "J m-2",  "Both"),
    ("ACLWDNB",  "Time, south_north, west_east", "ACCUMULATED DOWNWELLING LONGWAVE FLUX AT BOTTOM","J m-2",  "Both"),
    ("ACLWDNBC", "Time, south_north, west_east", "ACCUMULATED DOWNWELLING CLEAR SKY LW AT BOTTOM", "J m-2",  "Both"),
    ("SWUPT",    "Time, south_north, west_east", "INSTANTANEOUS UPWELLING SHORTWAVE FLUX AT TOP",  "W m-2",  "Both"),
    ("SWUPTC",   "Time, south_north, west_east", "INSTANTANEOUS UPWELLING CLEAR SKY SW AT TOP",    "W m-2",  "Both"),
    ("SWDNT",    "Time, south_north, west_east", "INSTANTANEOUS DOWNWELLING SW FLUX AT TOP",       "W m-2",  "Both"),
    ("SWDNTC",   "Time, south_north, west_east", "INSTANTANEOUS DOWNWELLING CLEAR SKY SW AT TOP",  "W m-2",  "Both"),
    ("SWUPB",    "Time, south_north, west_east", "INSTANTANEOUS UPWELLING SW FLUX AT BOTTOM",      "W m-2",  "Both"),
    ("SWUPBC",   "Time, south_north, west_east", "INSTANTANEOUS UPWELLING CLEAR SKY SW AT BOTTOM", "W m-2",  "Both"),
    ("SWDNB",    "Time, south_north, west_east", "INSTANTANEOUS DOWNWELLING SW FLUX AT BOTTOM",    "W m-2",  "Both"),
    ("SWDNBC",   "Time, south_north, west_east", "INSTANTANEOUS DOWNWELLING CLEAR SKY SW AT BOTTOM","W m-2", "Both"),
    ("LWUPT",    "Time, south_north, west_east", "INSTANTANEOUS UPWELLING LONGWAVE FLUX AT TOP",   "W m-2",  "Both"),
    ("LWUPTC",   "Time, south_north, west_east", "INSTANTANEOUS UPWELLING CLEAR SKY LW AT TOP",    "W m-2",  "Both"),
    ("LWDNT",    "Time, south_north, west_east", "INSTANTANEOUS DOWNWELLING LW FLUX AT TOP",       "W m-2",  "Both"),
    ("LWDNTC",   "Time, south_north, west_east", "INSTANTANEOUS DOWNWELLING CLEAR SKY LW AT TOP",  "W m-2",  "Both"),
    ("LWUPB",    "Time, south_north, west_east", "INSTANTANEOUS UPWELLING LW FLUX AT BOTTOM",      "W m-2",  "Both"),
    ("LWUPBC",   "Time, south_north, west_east", "INSTANTANEOUS UPWELLING CLEAR SKY LW AT BOTTOM", "W m-2",  "Both"),
    ("LWDNB",    "Time, south_north, west_east", "INSTANTANEOUS DOWNWELLING LW FLUX AT BOTTOM",    "W m-2",  "Both"),
    ("LWDNBC",   "Time, south_north, west_east", "INSTANTANEOUS DOWNWELLING CLEAR SKY LW AT BOTTOM","W m-2", "Both"),
    ("SZA",      "Time, south_north, west_east", "SOLAR ZENITH ANGLE",                             "deg",    "Both"),
    ("GHI_ACCUM","Time, south_north, west_east", "ACCUMULATED GHI",                                "J m-2",  "Both"),
    ("CLRNIDX",  "Time, south_north, west_east", "CLEARNESS INDEX",                                "",       "Both"),
    ("O3_GFS_DU","Time, south_north, west_east", "Total ozone from GFS",                           "Dobson Units", "Both"),
    # ---------- Clouds / diagnostics ----------
    ("CLDFRA",      "Time, bottom_top, south_north, west_east", "CLOUD FRACTION",                    "",     "Both"),
    ("CLDFRAC2D",   "Time, south_north, west_east",             "2-D MAX CLOUD FRACTION",            "%",    "Both"),
    ("REFL_10CM",   "Time, bottom_top, south_north, west_east", "Radar reflectivity (lamda = 10 cm)","dBZ",  "Both"),
    ("REFD_MAX",    "Time, south_north, west_east",             "MAX DERIVED RADAR REFL",            "dbZ",  "Both"),
    ("WVP",         "Time, south_north, west_east", "WATER VAPOR PATH",                              "kg m-2","Both"),
    ("LWP",         "Time, south_north, west_east", "LIQUID CLOUD WATER PATH",                       "kg m-2","Both"),
    ("IWP",         "Time, south_north, west_east", "ICE CLOUD WATER PATH",                          "kg m-2","Both"),
    ("SWP",         "Time, south_north, west_east", "SNOW CLOUD WATER PATH",                         "kg m-2","Both"),
    ("WP_SUM",      "Time, south_north, west_east", "SUM OF LWP+IWP+SWP",                           "kg m-2","Both"),
    ("LWP_TOT",     "Time, south_north, west_east", "LIQUID CLOUD WATER PATH RESOLVED + UNRESOLVED", "kg m-2","Both"),
    ("IWP_TOT",     "Time, south_north, west_east", "ICE CLOUD WATER PATH RESOLVED + UNRESOLVED",    "kg m-2","Both"),
    ("WP_TOT_SUM",  "Time, south_north, west_east", "SUM OF LWP+IWP+SWP RESOLVED + UNRESOLVED",      "kg m-2","Both"),
    ("RE_QC",       "Time, south_north, west_east", "MASS-WEIGHTED LIQUID CLOUD EFFECTIVE RADIUS",    "m",    "Both"),
    ("RE_QI",       "Time, south_north, west_east", "MASS-WEIGHTED ICE EFFECTIVE RADIUS",             "m",    "Both"),
    ("RE_QS",       "Time, south_north, west_east", "MASS-WEIGHTED SNOW EFFECTIVE RADIUS",            "m",    "Both"),
    ("RE_QC_TOT",   "Time, south_north, west_east", "MASS-WEIGHTED LIQUID CLOUD EFF. RADIUS RESOLVED + UNRESOLVED","m","Both"),
    ("RE_QI_TOT",   "Time, south_north, west_east", "MASS-WEIGHTED ICE EFF. RADIUS RESOLVED + UNRESOLVED","m","Both"),
    ("TAU_QC",      "Time, south_north, west_east", "MASS-WEIGHTED LIQUID CLOUD OPTICAL THICKNESS",   "",     "Both"),
    ("TAU_QI",      "Time, south_north, west_east", "MASS-WEIGHTED ICE OPTICAL THICKNESS",            "",     "Both"),
    ("TAU_QS",      "Time, south_north, west_east", "MASS-WEIGHTED SNOW OPTICAL THICKNESS",           "",     "Both"),
    ("TAU_QC_TOT",  "Time, south_north, west_east", "MASS-WEIGHTED LIQUID CLOUD OPT. THICKNESS RESOLVED + UNRESOLVED","","Both"),
    ("TAU_QI_TOT",  "Time, south_north, west_east", "MASS-WEIGHTED ICE OPT. THICKNESS RESOLVED + UNRESOLVED","","Both"),
    ("CBASEHT",     "Time, south_north, west_east", "CLOUD BASE HEIGHT",                             "m agl","Both"),
    ("CTOPHT",      "Time, south_north, west_east", "CLOUD TOP HEIGHT",                              "m agl","Both"),
    ("CBASEHT_TOT", "Time, south_north, west_east", "CLOUD BASE HEIGHT RESOLVED + UNRESOLVED",       "m agl","Both"),
    ("CTOPHT_TOT",  "Time, south_north, west_east", "CLOUD TOP HEIGHT RESOLVED + UNRESOLVED",        "m agl","Both"),
    # ---------- GWD / PBL ----------
    ("TKE_PBL",  "Time, bottom_top_stag, south_north, west_east", "TKE from PBL",                     "m2 s-2","Both"),
    ("DTAUX3D",  "Time, bottom_top, south_north, west_east",       "LOCAL U GWDO STRESS",              "m s-1", "WRF"),
    ("DTAUY3D",  "Time, bottom_top, south_north, west_east",       "LOCAL V GWDO STRESS",              "m s-1", "WRF"),
    ("DUSFCG",   "Time, south_north, west_east",                   "COLUMN-INTEGRATED U GWDO STRESS",  "Pa m s-1","WRF"),
    ("DVSFCG",   "Time, south_north, west_east",                   "COLUMN-INTEGRATED V GWDO STRESS",  "Pa m s-1","WRF"),
    ("VAR",      "Time, south_north, west_east",                   "STANDARD DEVIATION OF SUBGRID-SCALE OROGRAPHY","m","WRF"),
    ("CON",      "Time, south_north, west_east",                   "OROGRAPHIC CONVEXITY",             "",      "WRF"),
    ("OA1",      "Time, south_north, west_east",                   "ASYMMETRY OF SUBGRID-SCALE OROGRAPHY FOR WESTERLY FLOW","","WRF"),
    ("OA2",      "Time, south_north, west_east",                   "ASYMMETRY OF SUBGRID-SCALE OROGRAPHY FOR SOUTHERLY FLOW","","WRF"),
    ("OA3",      "Time, south_north, west_east",                   "ASYMMETRY OF SUBGRID-SCALE OROGRAPHY FOR SOUTH-WESTERLY FLOW","","WRF"),
    ("OA4",      "Time, south_north, west_east",                   "ASYMMETRY OF SUBGRID-SCALE OROGRAPHY FOR NORTH-WESTERLY FLOW","","WRF"),
    ("OL1",      "Time, south_north, west_east",                   "NON-DIMENSIONAL EFFECTIVE OROGRAPHIC LENGTH FOR WESTERLY FLOW","","WRF"),
    ("OL2",      "Time, south_north, west_east",                   "NON-DIMENSIONAL EFFECTIVE OROGRAPHIC LENGTH FOR SOUTHERLY FLOW","","WRF"),
    ("OL3",      "Time, south_north, west_east",                   "NON-DIMENSIONAL EFFECTIVE OROGRAPHIC LENGTH FOR SOUTH-WESTERLY FLOW","","WRF"),
    ("OL4",      "Time, south_north, west_east",                   "NON-DIMENSIONAL EFFECTIVE OROGRAPHIC LENGTH FOR NORTH-WESTERLY FLOW","","WRF"),
    # ---------- Random seeds ----------
    ("ISEEDARR_SPPT",        "Time, seed_dim_stag", "Array to hold seed for restart, SPPT",      "", "Both"),
    ("ISEEDARR_SKEBS",       "Time, seed_dim_stag", "Array to hold seed for restart, SKEBS",     "", "Both"),
    ("ISEEDARR_RAND_PERTURB","Time, seed_dim_stag", "Array to hold seed for restart, RAND_PERT", "", "Both"),
    ("ISEEDARRAY_SPP_CONV",  "Time, seed_dim_stag", "Array to hold seed for restart, RAND_PERT2","", "Both"),
    ("ISEEDARRAY_SPP_PBL",   "Time, seed_dim_stag", "Array to hold seed for restart, RAND_PERT3","", "Both"),
    ("ISEEDARRAY_SPP_LSM",   "Time, seed_dim_stag", "Array to hold seed for restart, RAND_PERT4","", "Both"),
    # ================================================================
    # WRF-Chem only variables
    # ================================================================
    # -- Aerosol optical properties --
    ("AOD_OUT",     "Time, bottom_top, south_north, west_east", "Aerosol Optical Depth (3D)",         "",        "Chem"),
    ("AOD2D_OUT",   "Time, south_north, west_east",             "Aerosol Optical Depth, 2D column",   "",        "Chem"),
    ("ATOP2D_OUT",  "Time, south_north, west_east",             "Aerosol Optical Depth, top",         "",        "Chem"),
    ("EXTCOF55",    "Time, bottom_top, south_north, west_east", "Extinction coefficients for 0.55 um","km^-1",   "Chem"),
    # -- Cloud / rain diagnostics --
    ("CLDFRA2",     "Time, bottom_top, south_north, west_east", "CLOUD FRACTION (chem)",              "-",       "Chem"),
    ("RAINPROD",    "Time, bottom_top, south_north, west_east", "TOTAL RAIN PRODUCTION RATE",         "s-1",     "Chem"),
    ("EVAPPROD",    "Time, bottom_top, south_north, west_east", "RAIN EVAPORATION RATE",              "s-1",     "Chem"),
    ("ICN_DIAG",    "Time, bottom_top, south_north, west_east", "Ice nuclei diagnostic",              "",        "Chem"),
    ("NC_DIAG",     "Time, bottom_top, south_north, west_east", "Cloud droplet number diagnostic",   "",        "Chem"),
    # -- Emissions --
    ("E_NH3",       "Time, emissions_zdim, south_north, west_east", "NH3 Emissions",                 "mol km^-2 hr^-1","Chem"),
    ("EBIO_ISO",    "Time, south_north, west_east",             "Actual biogenic isoprene emiss",     "mol km^-2 hr^-1","Chem"),
    ("EBIO_API",    "Time, south_north, west_east",             "Actual biogenic alpha-pinene emiss", "mol km^-2 hr^-1","Chem"),
    ("ACTNH3",      "Time, months_per_year_stag, south_north, west_east","The activity of NH3",      "0-1 fraction","Chem"),
    # -- Deposition --
    ("DRY_DEP_LEN", "Time, bio_emissions_dimension_stag, south_north, west_east","Dry deposition velocity","cm/s","Chem"),
    ("DRYDEPVEL",   "Time, south_north, west_east",             "Dust dry deposition velocity",       "m/s",     "Chem"),
    ("dvel_o3",     "Time, klevs_for_dvel, south_north, west_east","O3 deposition velocity",         "cm/s",    "Chem"),
    # -- Dust / roughness --
    ("UST_T",       "Time, south_north, west_east",   "Threshold Friction Velocity",              "m s-1","Chem"),
    ("ROUGH_COR",   "Time, south_north, west_east",   "roughness elements correction",            "",     "Chem"),
    ("SMOIS_COR",   "Time, south_north, west_east",   "soil moisture correction",                 "",     "Chem"),
    ("LAI_VEGMASK", "Time, south_north, west_east",   "MODIS LAI vegetation mask; 0=no dust",    "none", "Chem"),
    ("DMS_0",       "Time, south_north, west_east",   "DMS oceanic concentrations",               "nM/L", "Chem"),
    # -- PM / bulk aerosol mass --
    ("PM2_5_DRY",   "Time, bottom_top, south_north, west_east", "PM2.5 aerosol dry mass",           "ug m^-3","Chem"),
    ("PM10",        "Time, bottom_top, south_north, west_east", "PM10 dry mass",                    "ug m^-3","Chem"),
    # -- Photolysis --
    ("PHOTR2",      "Time, bottom_top, south_north, west_east", "O31D Photolysis Rate",             "min-1",  "Chem"),
    ("PHOTR4",      "Time, bottom_top, south_north, west_east", "NO2 Photolysis Rate",              "min-1",  "Chem"),
    # -- Aerosol surface area --
    ("SNU",         "Time, bottom_top, south_north, west_east", "2nd moment Aitken mode",           "m2 m-3","Chem"),
    ("SAC",         "Time, bottom_top, south_north, west_east", "2nd moment Accumulation mode",     "m2 m-3","Chem"),
    # -- Potential vorticity --
    ("PV",          "Time, bottom_top, south_north, west_east", "Potential Vorticity",              "pvu",   "Chem"),
    # -- N2O5 heterogeneous chemistry --
    ("GAMN2O5",     "Time, bottom_top, south_north, west_east", "N2O5 uptake by aerosol",           "numerical value","Chem"),
    ("CN2O5",       "Time, bottom_top, south_north, west_east", "N2O5 velocity",                    "m/s",   "Chem"),
    ("KN2O5",       "Time, bottom_top, south_north, west_east", "N2O5 het reaction rate",           "s-1",   "Chem"),
    ("YCLNO2",      "Time, bottom_top, south_north, west_east", "ClNO2 yield from N2O5 het",        "numerical value","Chem"),
    # -- Gas-phase chemistry (RADM2/RACM mechanism) --
    ("so2",         "Time, bottom_top, south_north, west_east", "SO2 mixing ratio",                 "ppmv", "Chem"),
    ("sulf",        "Time, bottom_top, south_north, west_east", "Sulfuric acid (SULF) mixing ratio","ppmv", "Chem"),
    ("no2",         "Time, bottom_top, south_north, west_east", "NO2 mixing ratio",                 "ppmv", "Chem"),
    ("no",          "Time, bottom_top, south_north, west_east", "NO mixing ratio",                  "ppmv", "Chem"),
    ("o3",          "Time, bottom_top, south_north, west_east", "O3 mixing ratio",                  "ppmv", "Chem"),
    ("hno3",        "Time, bottom_top, south_north, west_east", "HNO3 mixing ratio",                "ppmv", "Chem"),
    ("h2o2",        "Time, bottom_top, south_north, west_east", "H2O2 mixing ratio",                "ppmv", "Chem"),
    ("ald",         "Time, bottom_top, south_north, west_east", "ALD (higher aldehydes) mixing ratio","ppmv","Chem"),
    ("hcho",        "Time, bottom_top, south_north, west_east", "HCHO (formaldehyde) mixing ratio", "ppmv", "Chem"),
    ("op1",         "Time, bottom_top, south_north, west_east", "OP1 (methyl hydrogen peroxide) mixing ratio","ppmv","Chem"),
    ("op2",         "Time, bottom_top, south_north, west_east", "OP2 (higher organic peroxides) mixing ratio","ppmv","Chem"),
    ("paa",         "Time, bottom_top, south_north, west_east", "PAA (peroxyacetic acid) mixing ratio","ppmv","Chem"),
    ("ora1",        "Time, bottom_top, south_north, west_east", "ORA1 (formic acid) mixing ratio",  "ppmv", "Chem"),
    ("ora2",        "Time, bottom_top, south_north, west_east", "ORA2 (acetic acid) mixing ratio",  "ppmv", "Chem"),
    ("nh3",         "Time, bottom_top, south_north, west_east", "NH3 mixing ratio",                 "ppmv", "Chem"),
    ("n2o5",        "Time, bottom_top, south_north, west_east", "N2O5 mixing ratio",                "ppmv", "Chem"),
    ("no3",         "Time, bottom_top, south_north, west_east", "NO3 mixing ratio",                 "ppmv", "Chem"),
    ("pan",         "Time, bottom_top, south_north, west_east", "PAN (peroxyacetyl nitrate) mixing ratio","ppmv","Chem"),
    ("hc3",         "Time, bottom_top, south_north, west_east", "HC3 (alkanes, C3) mixing ratio",   "ppmv", "Chem"),
    ("hc5",         "Time, bottom_top, south_north, west_east", "HC5 (alkanes, C5) mixing ratio",   "ppmv", "Chem"),
    ("hc8",         "Time, bottom_top, south_north, west_east", "HC8 (alkanes, C8+) mixing ratio",  "ppmv", "Chem"),
    ("eth",         "Time, bottom_top, south_north, west_east", "ETH (ethylene) mixing ratio",      "ppmv", "Chem"),
    ("co",          "Time, bottom_top, south_north, west_east", "CO mixing ratio",                  "ppmv", "Chem"),
    ("ol2",         "Time, bottom_top, south_north, west_east", "OL2 (terminal alkenes) mixing ratio","ppmv","Chem"),
    ("olt",         "Time, bottom_top, south_north, west_east", "OLT (internal alkenes) mixing ratio","ppmv","Chem"),
    ("oli",         "Time, bottom_top, south_north, west_east", "OLI (internal diene) mixing ratio","ppmv", "Chem"),
    ("tol",         "Time, bottom_top, south_north, west_east", "TOL (toluene) mixing ratio",       "ppmv", "Chem"),
    ("xyl",         "Time, bottom_top, south_north, west_east", "XYL (xylene) mixing ratio",        "ppmv", "Chem"),
    ("aco3",        "Time, bottom_top, south_north, west_east", "ACO3 (acetylperoxy radical) mixing ratio","ppmv","Chem"),
    ("tpan",        "Time, bottom_top, south_north, west_east", "TPAN (higher PANs) mixing ratio",  "ppmv", "Chem"),
    ("hono",        "Time, bottom_top, south_north, west_east", "HONO (nitrous acid) mixing ratio", "ppmv", "Chem"),
    ("hno4",        "Time, bottom_top, south_north, west_east", "HNO4 (pernitric acid) mixing ratio","ppmv","Chem"),
    ("ket",         "Time, bottom_top, south_north, west_east", "KET (ketones) mixing ratio",       "ppmv", "Chem"),
    ("gly",         "Time, bottom_top, south_north, west_east", "GLY (glyoxal) mixing ratio",       "ppmv", "Chem"),
    ("mgly",        "Time, bottom_top, south_north, west_east", "MGLY (methylglyoxal) mixing ratio","ppmv", "Chem"),
    ("dcb",         "Time, bottom_top, south_north, west_east", "DCB (dicarbonyls) mixing ratio",   "ppmv", "Chem"),
    ("onit",        "Time, bottom_top, south_north, west_east", "ONIT (organic nitrates) mixing ratio","ppmv","Chem"),
    ("csl",         "Time, bottom_top, south_north, west_east", "CSL (cresols) mixing ratio",       "ppmv", "Chem"),
    ("iso",         "Time, bottom_top, south_north, west_east", "ISO (isoprene) mixing ratio",      "ppmv", "Chem"),
    ("hcl",         "Time, bottom_top, south_north, west_east", "HCL mixing ratio",                 "ppmv", "Chem"),
    ("ho",          "Time, bottom_top, south_north, west_east", "HO (hydroxyl radical) mixing ratio","ppmv","Chem"),
    ("ho2",         "Time, bottom_top, south_north, west_east", "HO2 (hydroperoxyl radical) mixing ratio","ppmv","Chem"),
    # -- Aerosol species (MADE/SORGAM, ambient) --
    ("so4aj",       "Time, bottom_top, south_north, west_east", "Sulfate conc. Accumulation mode",  "ug/kg-dryair","Chem"),
    ("so4ai",       "Time, bottom_top, south_north, west_east", "Sulfate conc. Aitken mode",        "ug/kg-dryair","Chem"),
    ("nh4aj",       "Time, bottom_top, south_north, west_east", "Ammonium conc. Accumulation mode", "ug/kg-dryair","Chem"),
    ("nh4ai",       "Time, bottom_top, south_north, west_east", "Ammonium conc. Aitken mode",       "ug/kg-dryair","Chem"),
    ("no3aj",       "Time, bottom_top, south_north, west_east", "Nitrate conc. Accumulation mode",  "ug/kg-dryair","Chem"),
    ("no3ai",       "Time, bottom_top, south_north, west_east", "Nitrate conc. Aitken mode",        "ug/kg-dryair","Chem"),
    ("naaj",        "Time, bottom_top, south_north, west_east", "Sodium conc. Accumulation mode",   "ug/kg-dryair","Chem"),
    ("naai",        "Time, bottom_top, south_north, west_east", "Sodium conc. Aitken mode",         "ug/kg-dryair","Chem"),
    ("claj",        "Time, bottom_top, south_north, west_east", "Chloride conc. Accumulation mode", "ug/kg-dryair","Chem"),
    ("clai",        "Time, bottom_top, south_north, west_east", "Chloride conc. Aitken mode",       "ug/kg-dryair","Chem"),
    ("orgaro1j",    "Time, bottom_top, south_north, west_east", "SOA Anth. org. from aromatics Acc. mode",   "ug/kg-dryair","Chem"),
    ("orgaro1i",    "Time, bottom_top, south_north, west_east", "SOA Anth. org. from aromatics Aitken mode", "ug/kg-dryair","Chem"),
    ("orgaro2j",    "Time, bottom_top, south_north, west_east", "SOA Anth. org. from aromatics Acc. mode 2", "ug/kg-dryair","Chem"),
    ("orgaro2i",    "Time, bottom_top, south_north, west_east", "SOA Anth. org. from aromatics Aitken mode 2","ug/kg-dryair","Chem"),
    ("orgalk1j",    "Time, bottom_top, south_north, west_east", "SOA Anth. org. from alkanes Acc. mode",     "ug/kg-dryair","Chem"),
    ("orgalk1i",    "Time, bottom_top, south_north, west_east", "SOA Anth. org. from alkanes Aitken mode",   "ug/kg-dryair","Chem"),
    ("orgole1j",    "Time, bottom_top, south_north, west_east", "SOA Anth. org. from alkenes Acc. mode",     "ug/kg-dryair","Chem"),
    ("orgole1i",    "Time, bottom_top, south_north, west_east", "SOA Anth. org. from alkenes Aitken mode",   "ug/kg-dryair","Chem"),
    ("orgba1j",     "Time, bottom_top, south_north, west_east", "SOA Biog. org. from aromatics Acc. mode 1", "ug/kg-dryair","Chem"),
    ("orgba1i",     "Time, bottom_top, south_north, west_east", "SOA Biog. org. from aromatics Aitken mode 1","ug/kg-dryair","Chem"),
    ("orgba2j",     "Time, bottom_top, south_north, west_east", "SOA Biog. org. from aromatics Acc. mode 2", "ug/kg-dryair","Chem"),
    ("orgba2i",     "Time, bottom_top, south_north, west_east", "SOA Biog. org. from aromatics Aitken mode 2","ug/kg-dryair","Chem"),
    ("orgba3j",     "Time, bottom_top, south_north, west_east", "SOA Biog. org. from aromatics Acc. mode 3", "ug/kg-dryair","Chem"),
    ("orgba3i",     "Time, bottom_top, south_north, west_east", "SOA Biog. org. from aromatics Aitken mode 3","ug/kg-dryair","Chem"),
    ("orgba4j",     "Time, bottom_top, south_north, west_east", "SOA Biog. org. from aromatics Acc. mode 4", "ug/kg-dryair","Chem"),
    ("orgba4i",     "Time, bottom_top, south_north, west_east", "SOA Biog. org. from aromatics Aitken mode 4","ug/kg-dryair","Chem"),
    ("orgpaj",      "Time, bottom_top, south_north, west_east", "Prim. anth. org. Accumulation mode","ug/kg-dryair","Chem"),
    ("orgpai",      "Time, bottom_top, south_north, west_east", "Prim. anth. org. Aitken mode",     "ug/kg-dryair","Chem"),
    ("ecj",         "Time, bottom_top, south_north, west_east", "Elemental carbon Accumulation mode","ug/kg-dryair","Chem"),
    ("eci",         "Time, bottom_top, south_north, west_east", "Elemental carbon Aitken mode",     "ug/kg-dryair","Chem"),
    ("p25j",        "Time, bottom_top, south_north, west_east", "Primary PM2.5 Accumulation mode",  "ug/kg-dryair","Chem"),
    ("p25i",        "Time, bottom_top, south_north, west_east", "Primary PM2.5 Aitken mode",        "ug/kg-dryair","Chem"),
    ("antha",       "Time, bottom_top, south_north, west_east", "Coarse anthropogenic aerosols",    "ug/kg-dryair","Chem"),
    ("seas",        "Time, bottom_top, south_north, west_east", "Coarse marine aerosols",           "ug/kg-dryair","Chem"),
    ("soila",       "Time, bottom_top, south_north, west_east", "Coarse soil-derived aerosols",     "ug/kg-dryair","Chem"),
    ("nu0",         "Time, bottom_top, south_north, west_east", "Aitken mode number",               "/kg-dryair",  "Chem"),
    ("ac0",         "Time, bottom_top, south_north, west_east", "Accumulation mode number",         "/kg-dryair",  "Chem"),
    ("corn",        "Time, bottom_top, south_north, west_east", "Coarse mode number",               "/kg-dryair",  "Chem"),
    # -- Aerosol species (in-cloud) --
    ("so4cwj",      "Time, bottom_top, south_north, west_east", "Sulfate conc. Acc. mode in cloud",  "ug/kg-dryair","Chem"),
    ("so4cwi",      "Time, bottom_top, south_north, west_east", "Sulfate conc. Aitken mode in cloud","ug/kg-dryair","Chem"),
    ("nh4cwj",      "Time, bottom_top, south_north, west_east", "Ammonium conc. Acc. mode in cloud", "ug/kg-dryair","Chem"),
    ("nh4cwi",      "Time, bottom_top, south_north, west_east", "Ammonium conc. Aitken mode in cloud","ug/kg-dryair","Chem"),
    ("no3cwj",      "Time, bottom_top, south_north, west_east", "Nitrate conc. Acc. mode in cloud",  "ug/kg-dryair","Chem"),
    ("no3cwi",      "Time, bottom_top, south_north, west_east", "Nitrate conc. Aitken mode in cloud","ug/kg-dryair","Chem"),
    ("nacwj",       "Time, bottom_top, south_north, west_east", "Sodium conc. Acc. mode in cloud",   "ug/kg-dryair","Chem"),
    ("nacwi",       "Time, bottom_top, south_north, west_east", "Sodium conc. Aitken mode in cloud", "ug/kg-dryair","Chem"),
    ("clcwj",       "Time, bottom_top, south_north, west_east", "Chloride conc. Acc. mode in cloud", "ug/kg-dryair","Chem"),
    ("clcwi",       "Time, bottom_top, south_north, west_east", "Chloride conc. Aitken mode in cloud","ug/kg-dryair","Chem"),
    ("orgaro1cwj",  "Time, bottom_top, south_north, west_east", "SOA Anth. org. aromatics Acc. in cloud",    "ug/kg-dryair","Chem"),
    ("orgaro1cwi",  "Time, bottom_top, south_north, west_east", "SOA Anth. org. aromatics Aitken in cloud",  "ug/kg-dryair","Chem"),
    ("orgaro2cwj",  "Time, bottom_top, south_north, west_east", "SOA Anth. org. aromatics Acc. in cloud 2",  "ug/kg-dryair","Chem"),
    ("orgaro2cwi",  "Time, bottom_top, south_north, west_east", "SOA Anth. org. aromatics Aitken in cloud 2","ug/kg-dryair","Chem"),
    ("orgalk1cwj",  "Time, bottom_top, south_north, west_east", "SOA Anth. org. alkanes Acc. in cloud",      "ug/kg-dryair","Chem"),
    ("orgalk1cwi",  "Time, bottom_top, south_north, west_east", "SOA Anth. org. alkanes Aitken in cloud",    "ug/kg-dryair","Chem"),
    ("orgole1cwj",  "Time, bottom_top, south_north, west_east", "SOA Anth. org. alkenes Acc. in cloud",      "ug/kg-dryair","Chem"),
    ("orgole1cwi",  "Time, bottom_top, south_north, west_east", "SOA Anth. org. alkenes Aitken in cloud",    "ug/kg-dryair","Chem"),
    ("orgba1cwj",   "Time, bottom_top, south_north, west_east", "SOA Biog. org. aromatics Acc. in cloud 1",  "ug/kg-dryair","Chem"),
    ("orgba1cwi",   "Time, bottom_top, south_north, west_east", "SOA Biog. org. aromatics Aitken in cloud 1","ug/kg-dryair","Chem"),
    ("orgba2cwj",   "Time, bottom_top, south_north, west_east", "SOA Biog. org. aromatics Acc. in cloud 2",  "ug/kg-dryair","Chem"),
    ("orgba2cwi",   "Time, bottom_top, south_north, west_east", "SOA Biog. org. aromatics Aitken in cloud 2","ug/kg-dryair","Chem"),
    ("orgba3cwj",   "Time, bottom_top, south_north, west_east", "SOA Biog. org. aromatics Acc. in cloud 3",  "ug/kg-dryair","Chem"),
    ("orgba3cwi",   "Time, bottom_top, south_north, west_east", "SOA Biog. org. aromatics Aitken in cloud 3","ug/kg-dryair","Chem"),
    ("orgba4cwj",   "Time, bottom_top, south_north, west_east", "SOA Biog. org. aromatics Acc. in cloud 4",  "ug/kg-dryair","Chem"),
    ("orgba4cwi",   "Time, bottom_top, south_north, west_east", "SOA Biog. org. aromatics Aitken in cloud 4","ug/kg-dryair","Chem"),
    ("orgpacwj",    "Time, bottom_top, south_north, west_east", "Prim. anth. org. Acc. in cloud",    "ug/kg-dryair","Chem"),
    ("orgpacwi",    "Time, bottom_top, south_north, west_east", "Prim. anth. org. Aitken in cloud",  "ug/kg-dryair","Chem"),
    ("eccwj",       "Time, bottom_top, south_north, west_east", "Elemental carbon Acc. in cloud",    "ug/kg-dryair","Chem"),
    ("eccwi",       "Time, bottom_top, south_north, west_east", "Elemental carbon Aitken in cloud",  "ug/kg-dryair","Chem"),
    ("p25cwj",      "Time, bottom_top, south_north, west_east", "Primary PM2.5 Acc. in cloud",       "ug/kg-dryair","Chem"),
    ("p25cwi",      "Time, bottom_top, south_north, west_east", "Primary PM2.5 Aitken in cloud",     "ug/kg-dryair","Chem"),
    ("anthcw",      "Time, bottom_top, south_north, west_east", "Coarse anthropogenic aerosols in cloud","ug/kg-dryair","Chem"),
    ("seascw",      "Time, bottom_top, south_north, west_east", "Coarse marine aerosols in cloud",   "ug/kg-dryair","Chem"),
    ("soilcw",      "Time, bottom_top, south_north, west_east", "Coarse soil-derived aerosols in cloud","ug/kg-dryair","Chem"),
    ("nu0cw",       "Time, bottom_top, south_north, west_east", "Aitken mode number in cloud",       "/kg-dryair","Chem"),
    ("ac0cw",       "Time, bottom_top, south_north, west_east", "Accumulation mode number in cloud", "/kg-dryair","Chem"),
    ("corncw",      "Time, bottom_top, south_north, west_east", "Coarse mode number in cloud",       "/kg-dryair","Chem"),
    # ================================================================
    # Additional variables that CAN be added to output (from registry.chem)
    # These have no 'h' flag in their I/O field — add via iofields_filename
    # ================================================================
    # -- Dust emissions (accumulated, per bin) --
    ("EDUST1",          "Time, south_north, west_east", "Accumulated dust emission bin 1 (0.1-1 um)",   "kg m-2",      "Optional"),
    ("EDUST2",          "Time, south_north, west_east", "Accumulated dust emission bin 2 (1-2.5 um)",   "kg m-2",      "Optional"),
    ("EDUST3",          "Time, south_north, west_east", "Accumulated dust emission bin 3 (2.5-5 um)",   "kg m-2",      "Optional"),
    ("EDUST4",          "Time, south_north, west_east", "Accumulated dust emission bin 4 (5-10 um)",    "kg m-2",      "Optional"),
    ("EDUST5",          "Time, south_north, west_east", "Accumulated dust emission bin 5 (10-20 um)",   "kg m-2",      "Optional"),
    # -- Dust loading --
    ("dustload_1",      "Time, south_north, west_east", "Dust column loading bin 1",                    "ug m-2",      "Optional"),
    ("dustload_2",      "Time, south_north, west_east", "Dust column loading bin 2",                    "ug m-2",      "Optional"),
    ("dustload_3",      "Time, south_north, west_east", "Dust column loading bin 3",                    "ug m-2",      "Optional"),
    ("dustload_4",      "Time, south_north, west_east", "Dust column loading bin 4",                    "ug m-2",      "Optional"),
    ("dustload_5",      "Time, south_north, west_east", "Dust column loading bin 5",                    "ug m-2",      "Optional"),
    # -- Dust dry deposition (accumulated) --
    ("dustdrydep_1",    "Time, south_north, west_east", "Accumulated dust dry deposition bin 1",        "kg m-2",      "Optional"),
    ("dustdrydep_2",    "Time, south_north, west_east", "Accumulated dust dry deposition bin 2",        "kg m-2",      "Optional"),
    ("dustdrydep_3",    "Time, south_north, west_east", "Accumulated dust dry deposition bin 3",        "kg m-2",      "Optional"),
    ("dustdrydep_4",    "Time, south_north, west_east", "Accumulated dust dry deposition bin 4",        "kg m-2",      "Optional"),
    ("dustdrydep_5",    "Time, south_north, west_east", "Accumulated dust dry deposition bin 5",        "kg m-2",      "Optional"),
    # -- Dust wet deposition (accumulated) --
    ("dustwdload_1",    "Time, south_north, west_east", "Dust load loss by wet deposition bin 1",       "ug m-2",      "Optional"),
    ("dustwdload_2",    "Time, south_north, west_east", "Dust load loss by wet deposition bin 2",       "ug m-2",      "Optional"),
    ("dustwdload_3",    "Time, south_north, west_east", "Dust load loss by wet deposition bin 3",       "ug m-2",      "Optional"),
    ("dustwdload_4",    "Time, south_north, west_east", "Dust load loss by wet deposition bin 4",       "ug m-2",      "Optional"),
    ("dustwdload_5",    "Time, south_north, west_east", "Dust load loss by wet deposition bin 5",       "ug m-2",      "Optional"),
    # -- Aerosol optical properties at other wavelengths --
    ("EXTCOF3",         "Time, bottom_top, south_north, west_east", "Extinction coefficient at 0.3 um", "km-1",        "Optional"),
    ("EXTCOF106",       "Time, bottom_top, south_north, west_east", "Extinction coefficient at 1.06 um","km-1",        "Optional"),
    ("EXTCOF3_5",       "Time, bottom_top, south_north, west_east", "Band-avg extinction 3-5 um",       "km-1",        "Optional"),
    ("EXTCOF8_12",      "Time, bottom_top, south_north, west_east", "Band-avg extinction 8-12 um",      "km-1",        "Optional"),
    ("BSCOF3",          "Time, bottom_top, south_north, west_east", "Backscatter coefficient at 0.3 um","km-1",        "Optional"),
    ("BSCOF106",        "Time, bottom_top, south_north, west_east", "Backscatter coefficient at 1.06 um","km-1",       "Optional"),
    ("ASYMPAR3",        "Time, bottom_top, south_north, west_east", "Asymmetry parameter at 0.3 um",    "",            "Optional"),
    ("ASYMPAR55",       "Time, bottom_top, south_north, west_east", "Asymmetry parameter at 0.55 um",   "",            "Optional"),
    ("ASYMPAR106",      "Time, bottom_top, south_north, west_east", "Asymmetry parameter at 1.06 um",   "",            "Optional"),
    # -- PM composition (not in history by default) --
    ("PM2_5_EC_DRY",    "Time, bottom_top, south_north, west_east", "PM2.5 elemental carbon dry mass",  "ug m-3",      "Optional"),
    ("PM2_5_WATER",     "Time, bottom_top, south_north, west_east", "PM2.5 aerosol liquid water content","ug m-3",     "Optional"),
    # -- Deposition fluxes (accumulated) --
    ("ddflx",           "Time, south_north, west_east", "Dry deposition flux for chemical species",     "mol m-2 or ug m-2","Optional"),
    ("wdflx",           "Time, south_north, west_east", "Column wet scavenging flux for species",       "mmol m-2 or ug m-2","Optional"),
    # -- Biomass burning emissions --
    ("ebu_pm25",        "Time, south_north, west_east", "PM2.5 from biomass burning",                   "ug m-2 s-1",  "Optional"),
    ("ebu_pm10",        "Time, south_north, west_east", "PM10 from biomass burning",                    "ug m-2 s-1",  "Optional"),
    ("ebu_bc",          "Time, south_north, west_east", "Black carbon from biomass burning",             "ug m-2 s-1",  "Optional"),
    ("ebu_co",          "Time, south_north, west_east", "CO from biomass burning",                      "mol km-2 hr-1","Optional"),
    # -- Tropopause diagnostics --
    ("tropo_p",         "Time, south_north, west_east", "Tropopause pressure",                          "Pa",          "Optional"),
    ("tropo_z",         "Time, south_north, west_east", "Tropopause height",                            "m",           "Optional"),
    # -- Standard WRF variables not in history by default --
    ("RAINNCV",         "Time, south_north, west_east", "TIME-STEP NONCONVECTIVE PRECIPITATION (restart only, not history)", "mm", "Optional"),
    ("PREC_ACC_NC",     "Time, south_north, west_east", "Accumulated precip over interval (requires PREC_ACC_DT > 0 in namelist)", "mm", "Optional"),
    ("den",             "Time, bottom_top, south_north, west_east", "Air density (computed internally, not output by default)", "kg m-3", "Optional"),
    ("alt",             "Time, bottom_top, south_north, west_east", "Inverse density / specific volume (not output by default)", "m3 kg-1","Optional"),
]

# Color map per source
SOURCE_COLORS = {
    "Both":     "FFFFFF",   # white
    "WRF":      "D6E4F0",   # light blue
    "Chem":     "E2EFDA",   # light green
    "Optional": "FFF2CC",   # light yellow
}
SOURCE_HEADER_COLORS = {
    "Both":     "1F4E79",   # dark blue
    "WRF":      "2E75B6",   # mid blue
    "Chem":     "375623",   # dark green
    "Optional": "7F6000",   # dark yellow/brown
}

wb = openpyxl.Workbook()
ws = wb.active
ws.title = "All Variables"

from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

thin = Side(style="thin", color="BFBFBF")
border = Border(left=thin, right=thin, top=thin, bottom=thin)

header_font = Font(name="Calibri", bold=True, color="FFFFFF", size=11)
header_fill = PatternFill("solid", fgColor="1F4E79")
header_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
cell_align  = Alignment(horizontal="left",   vertical="center", wrap_text=True)
center_align= Alignment(horizontal="center", vertical="center", wrap_text=True)

headers   = ["#", "Variable Name", "Dimensions", "Description", "Units", "Source"]
col_widths= [5,    22,              45,            60,            20,       12]

for col, (h, w) in enumerate(zip(headers, col_widths), 1):
    cell = ws.cell(row=1, column=col, value=h)
    cell.font      = header_font
    cell.fill      = header_fill
    cell.alignment = header_align
    cell.border    = border
    ws.column_dimensions[get_column_letter(col)].width = w
ws.row_dimensions[1].height = 25

source_label = {
    "Both":     "Both",
    "WRF":      "WRF only",
    "Chem":     "WRF-Chem only",
    "Optional": "Can be added",
}

for row_idx, (name, dims, desc, units, src) in enumerate(variables, 2):
    fill_color = SOURCE_COLORS.get(src, "FFFFFF")
    fill = PatternFill("solid", fgColor=fill_color)
    row_data = [row_idx-1, name, dims, desc, units, source_label[src]]
    aligns   = [center_align, cell_align, cell_align, cell_align, center_align, center_align]
    for col, (val, aln) in enumerate(zip(row_data, aligns), 1):
        cell = ws.cell(row=row_idx, column=col, value=val)
        cell.fill      = fill
        cell.alignment = aln
        cell.border    = border
        cell.font      = Font(name="Calibri", size=10)
    ws.row_dimensions[row_idx].height = 18

ws.freeze_panes = "A2"
ws.auto_filter.ref = f"A1:F{len(variables)+1}"

# ---- Legend sheet ----
ls = wb.create_sheet("Legend")
legend = [
    ("Color",        "Source",        "Meaning"),
    ("White",        "Both",          "Variable present in both standard WRF and WRF-Chem output"),
    ("Light Blue",   "WRF only",      "Variable present in standard WRF output only"),
    ("Light Green",  "WRF-Chem only", "Variable present in WRF-Chem output only"),
    ("Light Yellow", "Can be added",  "Variable computed by WRF/WRF-Chem but NOT in history output by default; can be enabled via namelist or iofields_filename"),
]
lcolors = ["1F4E79", "FFFFFF", "D6E4F0", "E2EFDA", "FFF2CC"]
for r, (row, color) in enumerate(zip(legend, lcolors), 1):
    for c, val in enumerate(row, 1):
        cell = ls.cell(row=r, column=c, value=val)
        cell.fill   = PatternFill("solid", fgColor=color)
        cell.border = border
        cell.font   = Font(name="Calibri", bold=(r==1), color="FFFFFF" if r==1 else "000000", size=11)
        cell.alignment = Alignment(horizontal="center", vertical="center")
        ls.column_dimensions[get_column_letter(c)].width = 20
    ls.row_dimensions[r].height = 22

output_path = "/home/user/WRF/wrfout_variables.xlsx"
wb.save(output_path)

wrf_only  = sum(1 for v in variables if v[4]=="WRF")
chem_only = sum(1 for v in variables if v[4]=="Chem")
both      = sum(1 for v in variables if v[4]=="Both")
optional  = sum(1 for v in variables if v[4]=="Optional")
print(f"Saved: {output_path}")
print(f"  Both (shared):    {both}")
print(f"  WRF only:         {wrf_only}")
print(f"  WRF-Chem only:    {chem_only}")
print(f"  Can be added:     {optional}")
print(f"  Total:            {len(variables)}")
