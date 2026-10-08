#!/bin/bash
#SBATCH --job-name=CB4_ExSta
#SBATCH --time=01:00:00
#SBATCH --ntasks=1
#SBATCH --qos=np

set -euo pipefail

MOD=coherens
YEAR=2010
SCENARIO=BASE

module load conda
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate codeblueWP4

python3 Extract_station_files.py -v $MOD $YEAR $SCENARIO
