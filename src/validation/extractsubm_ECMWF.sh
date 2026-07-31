#!/bin/bash
#SBATCH --job-name=CB4_IcesExtract
#SBATCH --time=01:00:00
#SBATCH --ntasks=1
#SBATCH --qos=np

set -euo pipefail

MOD=coherens
YEAR=2010

module load conda
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate codeblueWP4

python3 ICES_Extract.py -v $MOD $YEAR 

