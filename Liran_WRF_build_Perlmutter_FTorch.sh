#!/bin/bash
set -e
set -o pipefail 

#change the following boolean variables to run/skip certain compiling steps

doclean=true  #true if WRF source code is modified since the last compilation

doclean_all=false  #true if previously compiled with different configure options

runconf=false    #run WRF's configure script; should do this first before compiling

docompile=true  #run WRF's compile script; should do this after configure

debug=false  #true to compile WRF with debug flag (no optimizations, -g flag for debugger, etc.)

imach="pm"  #target system name. "pm" for Perlmutter.

# set the top directory of the WRF source code as an environmental variable
export WRF_DIR="/pscratch/sd/h/heroplr/RGMA_homecopy/WRF_stam3_ml_mixout_bce_lr1e-4_cosine"

#Modules --------------------------------------------------------------------
#general modules
module load cpu  
module load PrgEnv-gnu 

#module for WRF file I/O
#order of loading matters!
module load cray-hdf5  #required to load netcdf library
module load cray-netcdf 
module load cray-parallel-netcdf

module list #check what modules are loaded

#set environmental variables used by WRF build system, 
#using the environmental variables set by the modules

#use classic (CDF1) as default
export NETCDF_classic=1 
#use 64-bit offset format (CDF2) of netcdf files              
export WRFIO_NCD_LARGE_FILE_SUPPORT=1 
#do not use netcdf4 compression (serial), need hdf5 module
export USE_NETCDF4_FEATURES=0         

export HDF5=$HDF5_DIR
export HDF5_LIB="$HDF5_DIR/lib"
export HDF5_BIN="$HDF5_DIR/bin"

export NETCDF=$NETCDF_DIR
export NETCDF_BIN="$NETCDF_DIR/bin"
export NETCDF_LIB="$NETCDF_DIR/lib"

# FTorch (use your installed artifacts; adjust if different)
export FTORCH_MOD="$HOME/opt/ftorch/include/ftorch"   # has ftorch.mod
export FTORCH_LIB="$HOME/opt/ftorch/lib64"            # has libftorch.so

export TORCH_ROOT="/global/homes/h/heroplr/opt/libtorch-cpu"   # contains lib/ with libtorch*.so
export LIBTORCH_LIB="${TORCH_ROOT}/lib"
export LIBTORCH_RPATH="${LIBTORCH_LIB}"

#create PNETCDF environment variable to use the parallel netcdf library
export PNETCDF=$PNETCDF_DIR  

export LD_LIBRARY_PATH="/usr/lib64":${LD_LIBRARY_PATH}
export PATH=${NETCDF_BIN}:${HDF5_BIN}:${PATH}
export CRAYPE_LINK_TYPE=dynamic
#export LD_LIBRARY_PATH="${FTORCH_LIB}:${LIBTORCH_LIB}:${LD_LIBRARY_PATH}"
export LD_LIBRARY_PATH="$FTORCH_LIB:$LIBTORCH_LIB:$LD_LIBRARY_PATH"
#other special flags
export PNETCDF_QUILT="0"  #Quilt output is not stable, better not use it

# Runtime search path for the linker/loader
#export LD_LIBRARY_PATH="${FTORCH_LIB}:${LIBTORCH_LIB}:${LD_LIBRARY_PATH}"

#check environment variables
echo "LD_LIBRARY_PATH: "$LD_LIBRARY_PATH
echo "PATH: "$PATH
echo "MANPATH: "$MANPATH
echo "NETCDF is $NETCDF"
echo "NETCDF_LIB is $NETCDF_LIB"
echo "HDF5 is $HDF5"
echo "HDF5_LIB is $HDF5_LIB"
echo "FTORCH_MOD: ${FTORCH_MOD}"
echo "FTORCH_LIB: ${FTORCH_LIB}"
echo "PNETCDF: ${PNETCDF}"
echo "PNETCDF_QUILT: ${PNETCDF_QUILT}"

##capture the date and time for log file name
idate=$(date "+%Y-%m-%d-%H_%M")
#
##run WRF build scripts located in the top WRF directory
cd $WRF_DIR

if [ "$doclean_all" = true ]; then
    ./clean -a
    #"The './clean –a' command is required if you have edited the configure.wrf 
    #or any of the Registry files.", but this deletes configure.wrf....

fi

if [ "$doclean" = true ]; then
    ./clean
fi

#echo "running configure"
if [ "$runconf" = true ]; then

    if [ "$debug" = true ]; then
        echo "configure debug mode"
        ./configure -d
    else
        ./configure
    fi

   ##configure options selected are:
   # 32. (serial)  33. (smpar)  34. (dmpar)  35. (dm+sm)   GNU (gfortran/gcc)
   # choose 35 for real (not idealized) cases

    configfile="${WRF_DIR}/configure.wrf"

sed -i "1i FTORCH_LIB := ${FTORCH_LIB}\nLIBTORCH_LIB := ${LIBTORCH_LIB}\n# ---- FTorch + libtorch ----\nLIB_FTORCH = \\\n  -L\$(FTORCH_LIB) -lftorch \\\n  -L\$(LIBTORCH_LIB) -Wl,-rpath,\$(LIBTORCH_LIB):\$(FTORCH_LIB) \\\n  -ltorch_cpu -lc10 -lstdc++ -ldl -lpthread\n# Hook into WRF's standard link variables\nLIB_LOCAL = \$(LIB_FTORCH)\n" "$configfile"

    
    if [ ! -f "$configfile" ]; then
        echo "ERROR: ${configfile} not found after ./configure"
        exit 1
    fi

    echo "Patching ${configfile} for Perlmutter + FTorch"
    #the sed commands below will change the following lines in configure.wrf
    #--- original
    #SFC             =       gfortran
    #SCC             =       gcc
    #CCOMP           =       gcc
    #DM_FC           =       mpif90
    #DM_CC           =       mpicc
    # ---- Include FTorch Fortran module path ----
    #sed -i "s|^FFLAGS\s*=.*|& -I${FTORCH_MOD}|" "${configfile}"
    #sed -i "s|^FCFLAGS\s*=.*|& -I${FTORCH_MOD}|" "${configfile}"

    sed -i "s|^FCFLAGS[[:space:]]*=.*|& -I${FTORCH_MOD}|" "$configfile"
    sed -i "s|^FFLAGS[[:space:]]*=.*|& -I${FTORCH_MOD}|" "$configfile"

    
    #grep -q '^LIB_FTORCH' "$configfile" || cat >> "$configfile" <<'EOF'


    #sed -i "s|^WRF_LIB *=.*|& -L${FTORCH_LIB} -lftorch -L${LIBTORCH_LIB} -Wl,-rpath,${LIBTORCH_LIB}:${FTORCH_LIB} -ltorch_cpu -lc10 -lstdc++ -ldl -lpthread|" configure.wrf
    #sed -i "s|^LIB_EXTERNAL *=.*|& -L${FTORCH_LIB} -lftorch -L${LIBTORCH_LIB} -Wl,-rpath,${LIBTORCH_LIB}:${FTORCH_LIB} -ltorch_cpu -lc10 -lstdc++ -ldl -lpthread|" configure.wrf
    # ---- Link FTorch + LibTorch (CPU or CUDA) ----
    #if [ "${USE_FTORCH_CUDA}" = "1" ]; then
    #    APPEND_LIBS="-L${FTORCH_LIB} -lftorch \
    #-L${LIBTORCH_LIB} -Wl,-rpath,${LIBTORCH_RPATH} \
    #-ltorch -ltorch_cpu -ltorch_cuda -lc10 \
    #-lstdc++ -ldl -lpthread -lcudart -lcuda -lnvToolsExt"
    #else

    #fi
    #--- edited (FC and CC with MPI)
    #SFC             =       gfortran
    #SCC             =       gcc
    #CCOMP           =       cc
    #DM_FC           =       ftn
    #DM_CC           =       cc

    if [ -f "$configfile" ]; then
        echo "editing configure.wrf"
        #need to remove -cc=$(SCC) in DM_CCf
        sed -i 's/-cc=\$(SCC)/ /' ${configfile}
        sed -i 's/mpif90/ftn/' ${configfile}
        sed -i 's/mpicc/cc/' ${configfile}

cat >> "$configfile" <<'EOF'

# ---- FTorch + libtorch (auto-appended) ----
LIB_FTORCH = \
  -L$(FTORCH_LIB) -lftorch \
  -L$(LIBTORCH_LIB) -Wl,-rpath,$(LIBTORCH_LIB):$(FTORCH_LIB) \
  -ltorch_cpu -lc10 -lstdc++ -ldl -lpthread
# If your FTorch was built against CUDA libtorch, also add:  -ltorch_cuda
EOF

        #also user can remove the flag -DWRF_USE_CLM 
        #from ARCH_LOCAL if not planning to 
        #use the CLM4 land model to speed up compilation
        #sed -i 's/-DWRF_USE_CLM/ /' ${configfile} 

    fi

fi

if [ "$docompile" = true ]; then
    export J="-j 4"  #build in parallel
    echo "J = $J"

    # ./clean (without -a) does NOT delete tools/gen_comms.c, so the stub
    # persists and gen_comms_rsllite's "if [ ! -e ... ]" guard never fires.
    # Without the real RSL_LITE gen_comms.c, the registry tool skips generating
    # HALO_EM_*.inc and REGISTRY_COMM_*.inc files, causing the build to fail.
    # Write the correct file here so it is newer than gen_comms.stub and the
    # tools/Makefile rule won't overwrite it.
    cat ${WRF_DIR}/tools/gen_comms_warning ${WRF_DIR}/external/RSL_LITE/gen_comms.c \
        > ${WRF_DIR}/tools/gen_comms.c

    bldlog=compile_em_${idate}_${imach}.log
    echo  "compile log file is ${bldlog}"

    #run the compile script
    ./compile em_real &> ${bldlog}

    #check if there is an error in the compile log
    #grep command exits the script in case of nomatch
    #after the 2022-12 maintenance
    set +e #release the exit flag before grep

    grep "Problems building executables" ${bldlog}    
    RESULT=$?

    #set the exit flag again
    set -e  

    if [ $RESULT -eq 0 ]; then
        echo "compile failed, check ${bldlog}"      
    else
        echo "compile success"
        #sometimes renaming executable with descriptive information is useful
        #cp $WRF_DIR/main/ideal.exe $WRF_DIR/main/ideal_${idate}_${imach}.exe
        #cp $WRF_DIR/main/real.exe $WRF_DIR/main/real_${idate}_${imach}.exe
        #cp $WRF_DIR/main/wrf.exe $WRF_DIR/main/wrf_${idate}_${imach}.exe
        #cp $WRF_DIR/main/ndown.exe $WRF_DIR/main/ndown_${idate}_${imach}.exe
    fi

fi
