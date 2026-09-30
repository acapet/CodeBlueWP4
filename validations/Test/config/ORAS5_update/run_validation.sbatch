#!/usr/bin/env bash
#SBATCH --job-name=codeblue_valid
#SBATCH --partition=LMEM
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=48G
#SBATCH --time=04:00:00
#SBATCH --output=/export/lv9/user/klarsen/model_out/CodeBlueWP4-KLL_update/validations/Test/logs/extract_%j.out
#SBATCH --error=/export/lv9/user/klarsen/model_out/CodeBlueWP4-KLL_update/validations/Test/logs/extract_%j.err

set -euo pipefail

# ---------------------------------------------------------------------------
# User settings
# ---------------------------------------------------------------------------

# Absolute path to a Python interpreter with the validation dependencies.
CODEBLUE_PYTHON="/export/lv9/user/klarsen/.conda/envs/codeblue/bin/python"

# Absolute path to the CodeBlueWP4 repository.
REPOSITORY_ROOT="/export/lv9/user/klarsen/model_out/CodeBlueWP4-KLL_update"

# Root of this validation setup.
SETUP_ROOT="/export/lv9/user/klarsen/model_out/CodeBlueWP4-KLL_update/validations/Test"

# Directory name below ${SETUP_ROOT}/config.
CONFIGURATION_NAME="ORAS5_update"

# MODEL_ID=test makes the extractor load test.yml and use "test" in outputs.
MODEL_ID="test"
YEAR="2014"

# ---------------------------------------------------------------------------
# Derived paths
# ---------------------------------------------------------------------------

VALIDATION_SOURCE="${REPOSITORY_ROOT}/src/validation"
CONFIG_DIR="${SETUP_ROOT}/config/${CONFIGURATION_NAME}"
CONFIG_FILE="${CONFIG_DIR}/${MODEL_ID}.yml"

# TABLE_DIR must match files.outdir in the YAML.
TABLE_DIR="${SETUP_ROOT}/output"
PROVENANCE_DIR="${SETUP_ROOT}/provenance"

# ---------------------------------------------------------------------------
# Basic safety checks
# ---------------------------------------------------------------------------

for required_file in \
    "${CODEBLUE_PYTHON}" \
    "${VALIDATION_SOURCE}/Extract_validation_tables.py" \
    "${VALIDATION_SOURCE}/vertical_handling.py" \
    "${CONFIG_FILE}"
do
    if ! test -r "${required_file}"; then
        printf 'STOP: required file is not readable: %s\n' \
            "${required_file}" >&2
        exit 1
    fi
done

mkdir -p "${TABLE_DIR}" "${PROVENANCE_DIR}"

existing_output=$(
    find "${TABLE_DIR}" -mindepth 1 -maxdepth 1 -print -quit
)

if test -n "${existing_output}"; then
    printf 'STOP: output directory is not empty: %s\n' \
        "${TABLE_DIR}" >&2
    exit 1
fi

# ---------------------------------------------------------------------------
# Minimal runtime provenance
# ---------------------------------------------------------------------------

printf 'Python:        %s\n' "${CODEBLUE_PYTHON}"
printf 'Source:        %s\n' "${VALIDATION_SOURCE}"
printf 'Configuration: %s\n' "${CONFIG_FILE}"
printf 'Output:        %s\n' "${TABLE_DIR}"
printf 'Model:         %s\n' "${MODEL_ID}"
printf 'Year:          %s\n' "${YEAR}"

"${CODEBLUE_PYTHON}" --version

sha256sum \
    "${VALIDATION_SOURCE}/Extract_validation_tables.py" \
    "${VALIDATION_SOURCE}/vertical_handling.py" \
    "${CONFIG_FILE}" \
    > "${PROVENANCE_DIR}/source_and_config_sha256.txt"

# ---------------------------------------------------------------------------
# Check the configured model and vertical coordinates
# ---------------------------------------------------------------------------

"${CODEBLUE_PYTHON}" -B \
    "${VALIDATION_SOURCE}/vertical_handling.py" \
    "${CONFIG_FILE}" \
    "${YEAR}" \
    --check

# ---------------------------------------------------------------------------
# Run the extraction
#
# The extractor looks for <MODEL_ID>.yml in the current directory.
# ---------------------------------------------------------------------------

cd "${CONFIG_DIR}"

"${CODEBLUE_PYTHON}" -B \
    "${VALIDATION_SOURCE}/Extract_validation_tables.py" \
    -v \
    --match-diagnostics \
    "${MODEL_ID}" \
    "${YEAR}"

# ---------------------------------------------------------------------------
# Confirm that the expected output was produced
# ---------------------------------------------------------------------------

valid_count=$(
    find "${TABLE_DIR}" -maxdepth 1 -type f \
        -name "VALID_*_${YEAR}_${MODEL_ID}.parquet" |
    wc -l
)

status_count=$(
    find "${TABLE_DIR}" -maxdepth 1 -type f \
        -name "MATCH_STATUS_*_${YEAR}_${MODEL_ID}.parquet" |
    wc -l
)

summary_count=$(
    find "${TABLE_DIR}" -maxdepth 1 -type f \
        -name "MATCH_STATUS_SUMMARY_${YEAR}_${MODEL_ID}.csv" |
    wc -l
)

printf 'Output counts: VALID=%s MATCH_STATUS=%s SUMMARY=%s\n' \
    "${valid_count}" "${status_count}" "${summary_count}"

if test "${valid_count}" -ne 9 \
    || test "${status_count}" -ne 9 \
    || test "${summary_count}" -ne 1
then
    printf 'STOP: expected 9 VALID files, 9 MATCH_STATUS files, and 1 summary.\n' >&2
    exit 1
fi

printf 'Validation completed successfully: model=%s year=%s\n' \
    "${MODEL_ID}" "${YEAR}"
