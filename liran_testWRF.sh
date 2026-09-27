#!/bin/bash
#SBATCH --job-name=WRF
#SBATCH --nodes=2  # Adjust as necessary
#SBATCH --ntasks-per-node=32
#SBATCH --time=04:00:00
#SBATCH --account=<your_account>

module load cpu
module load PrgEnv-gnu
module load cray-netcdf
srun ./wrf.exe
