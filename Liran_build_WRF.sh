#!/bin/bash
set -e
set -o pipefail 

#change the following boolean variables to run/skip certain compiling steps

doclean=true  #true if WRF source code is modified since the last compilation

doclean_all=true  #true if previously compiled with different configure options

runconf=true    #run WRF's configure script; should do this first before compiling

docompile=true  #run WRF's compile script; should do this after configure

debug=false  #true to compile WRF with debug flag (no optimizations, -g flag for debugger, etc.)

imach="stampede3"  #target system name.

#Modules --------------------------------------------------------------------
#general modules
  module load hdf5/1.14.4
  module load netcdf/4.9.2
  module load impi
  module load intel
#Shouldn't need this if y ou're using pnetcdf
#  module load parallel-netcdf/4.9.2
  module load pnetcdf/1.12.3
  module load cmake
  module load zlib/1.3.1

# set the top directory of the WRF source code as an environmental variable
export WRF_DIR="/scratch/07088/tg863871/WRF_dm"
export NETCDF_DIR=/opt/apps/intel24/netcdf/4.9.2
export NETCDFPATH=/opt/apps/intel24/netcdf/4.9.2
export PNETCDF_DIR=/opt/apps/intel24/impi21/pnetcdf/1.12.3
export HDF5_DIR=/opt/apps/intel24/hdf5/1.14.4/
export WRF_CHEM=1
export WRFIO_NCD_LARGE_FILE_SUPPORT=1
export USE_NETCDF4_FEATURES=0
export NETCDF_classic=1 


# For some rason, loading this loads a different hdf5
#  module load nclncarg/git2024

module list #check what modules are loaded

#set environmental variables used by WRF build system, 
#using the environmental variables set by the modules

#use classic (CDF1) as default
export NETCDF_classic=1 
#use 64-bit offset format (CDF2) of netcdf files              
export WRFIO_NCD_LARGE_FILE_SUPPORT=1 
#do not use netcdf4 compression (serial), need hdf5 module
export USE_NETCDF4_FEATURES=1         

#The module sets TACC versions of the envs
# export HDF5=$HDF5_DIR
# export HDF5_LIB="$HDF5_DIR/lib"
# export HDF5_BIN="$HDF5_DIR/bin"
export HDF5=$TACC_HDF5_DIR
export HDF5_LIB="$TACC_HDF5_DIR/lib"
export HDF5_BIN="$TACC_HDF5_DIR/bin"

# export NETCDF=$NETCDF_DIR
# export NETCDF_BIN="$NETCDF_DIR/bin"
# export NETCDF_LIB="$NETCDF_DIR/lib"
# export NETCDF4_DEP_LIB="$NETCDF_DIR/lib"
export NETCDF=$TACC_NETCDF_DIR
export NETCDF_BIN="$TACC_NETCDF_DIR/bin"
export NETCDF_LIB="$TACC_NETCDF_DIR/lib"
export NETCDF4_DEP_LIB="$TACC_NETCDF_DIR/lib"
#create PNETCDF environment variable to use the parallel netcdf library
#The TACC PNETCDF module sets this environment variable
#export PNETCDF=$PNETCDF_DIR  

#YOu don't have to set this, the module command takes care of this
# The command below is probably the one that breaks your link. 
#  You shouldn't put "/usr/lib64" first or maybe even in the LD_LIBRARY_PATH
#   
# export LD_LIBRARY_PATH="/usr/lib64":${LD_LIBRARY_PATH}
# export PATH=${NETCDF_BIN}:${HDF5_BIN}:${PATH}
# export LD_LIBRARY_PATH=${NETCDF_LIB}:${LD_LIBRARY_PATH}

#other special flags
export PNETCDF_QUILT="0"  #Quilt output is not stable, better not use it

#check environment variables
echo "LD_LIBRARY_PATH: "$LD_LIBRARY_PATH
echo "PATH: "$PATH
echo "MANPATH: "$MANPATH

echo "NETCDF is $NETCDF"
echo "NETCDF_LIB is $NETCDF_LIB"

echo "HDF5 is $HDF5"
echo "HDF5_LIB is $HDF5_LIB"

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

    #the sed commands below will change the following lines in configure.wrf
    #--- original
    #SFC             =       ifx
    #SCC             =       icx
    #CCOMP           =       icx
    #DM_FC           =       ifx
    #DM_CC           =       icpx

    #--- edited (FC and CC with MPI)
    #SFC             =       gfortran
    #SCC             =       gcc
    #CCOMP           =       cc
    #DM_FC           =       ftn
    #DM_CC           =       cc

    if [ -f "$configfile" ]; then
        echo "editing configure.wrf"
        #need to remove -cc=$(SCC) in DM_CC
        #sed -i 's/-cc=\$(SCC)/ /' ${configfile}
        sed -i 's/ifort/ifx/' ${configfile}
        sed -i 's/icc/icx/' ${configfile}
        sed -i 's/mpicx/mpicc/' ${configfile}
        #sed -i 's/mpfort/ mpif90 -f90=$(SFC)/' ${configfile}
        #sed -i 's/mpcc/mpicc/' ${configfile}
        sed -i 's/time $(DM_FC)/$(DM_FC)/' ${configfile}
        #also user can remove the flag -DWRF_USE_CLM 
        #from ARCH_LOCAL if not planning to 
        #use the CLM4 land model to speed up compilation
        #sed -i 's/-DWRF_USE_CLM/ /' ${configfile} 

    fi

fi

if [ "$docompile" = true ]; then
    export J="-j 4"  #build in parallel
    echo "J = $J"

    bldlog=compile_em_${idate}_${imach}.log
    echo  "compile log file is ${bldlog}"

    #run the compile script 
    #./compile em_real &> ${bldlog}
    #./compile em_real > compile.log 2>&1
    ./compile em_real ${J} &> ${bldlog}
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
