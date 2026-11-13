#!/usr/bin/env bash
#SBATCH --job-name=codeblue_valid
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=48G
#SBATCH --time=04:00:00
#SBATCH --output=slurm-%j.out

set -euo pipefail

if test "$#" -ne 2; then
    printf 'Usage: sbatch run_validation.sbatch MODEL_CONFIG.yml YEAR\n' >&2
    exit 2
fi

: "${CODEBLUE_PYTHON:?Set CODEBLUE_PYTHON to an absolute Python interpreter path}"
if [[ -n "${SLURM_SUBMIT_DIR:-}" && -d "${SLURM_SUBMIT_DIR}/src/validation" ]]; then
    SCRIPT_DIR=${SLURM_SUBMIT_DIR}/src/validation
else
    SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
fi

CONFIG_FILE=$(readlink -f "$1")
YEAR=$2
CONFIG_DIR=$(dirname -- "${CONFIG_FILE}")
MODEL_ID=$(basename -- "${CONFIG_FILE}" .yml)

OUTPUT_DIR=$(
    PYTHONPATH="${SCRIPT_DIR}" "${CODEBLUE_PYTHON}" - "${CONFIG_FILE}" <<'PY'
import sys
from pathlib import Path

from validation_input import load_validation_config

path = Path(sys.argv[1]).resolve()
output = Path(load_validation_config(path).values["files"]["outdir"])
if not output.is_absolute():
    output = path.parent / output
print(output.resolve())
PY
)

mkdir -p "${OUTPUT_DIR}"
shopt -s nullglob
existing=("${OUTPUT_DIR}"/VALID_*_"${YEAR}"_"${MODEL_ID}".parquet)
if test "${#existing[@]}" -ne 0; then
    printf 'STOP: validation output already exists in %s\n' "${OUTPUT_DIR}" >&2
    exit 1
fi

printf 'Python:     %s\n' "${CODEBLUE_PYTHON}"
printf 'Source:     %s\n' "${SCRIPT_DIR}"
printf 'Configuration: %s\n' "${CONFIG_FILE}"
printf 'Output:     %s\n' "${OUTPUT_DIR}"

cd "${CONFIG_DIR}"
"${CODEBLUE_PYTHON}" -B \
    "${SCRIPT_DIR}/Extract_validation_tables.py" \
    -v \
    --match-diagnostics \
    "${MODEL_ID}" \
    "${YEAR}"

printf 'Validation completed successfully.\n'
