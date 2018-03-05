#!/bin/bash -l
#SBATCH -q regular
#SBATCH -N 2
#SBATCH -L cscratch1
#SBATCH -t 05:59:59

################################################################################
# WARNING: in order to run this script, you must ensure you have "calibrate.py"
# in your PATH!
################################################################################

set -o errexit
set -v

calibrate=$(which calibrate.py)

echo "Starting the script on $(date), directory is $(pwd)"

module swap PrgEnv-intel PrgEnv-gnu
module unload altd
module unload darshan

export PYTHONPATH=
module load python/3.6-anaconda-4.4

echo "Python executable: $(which python)"
echo "Python version: $(python --version &> /dev/stdout)"
echo "Calibrate script: ${calibrate}"
echo "----------------------------------------"
env | sort -d
echo "----------------------------------------"

for inifile in ini/pico_06h_cmbonly_{0A,0B}.ini; do
    logfile=./log/$(basename $inifile .ini).log
    echo "Going to run srun on $(date)"
    srun -n 48 python ${calibrate} $inifile 2>&1 | tee $logfile
done

echo "Script ended on $(date)"
