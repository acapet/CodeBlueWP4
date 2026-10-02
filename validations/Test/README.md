# CodeBlue validation setup template

This directory is a template for configuring and running the
CodeBlue validation workflow using the code in `src/validation/`. 
The setup and examples were made using GETM_ERSEM_BFM (NIOZ). 
Other models must verify their coordinates, vertical-grid, variable, 
and unit conventions before using the results.
Supporting a new model may require changes to the YAML configuration 
or, for unsupported vertical coordinates, `vertical_handling.py`.

## 1. Install the package

Download or clone the CodeBlueWP4 package into the desired location. If a ZIP
archive is supplied, unpack it first. In the commands below,
`<repository-root>` means the absolute path to `CodeBlueWP4`.

Configuration files are separated from the reusable Python
source in the CodeBlueWP4/validations/ folder. 
This allows multiple model/run configurations without duplicating or
editing source code scripts in `src/validation/`.

The example configuration is under:

```text
validations/Test/config/ORAS5_update/ 
```

For a new configuration, copy that directory and give the copy a descriptive
name, i.e. a name containing both the model and the run or experiment, for example:

```bash
cp -a \
  <repository-root>/validations/Test/config/ORAS5_update \
  <repository-root>/validations/Test/config/my_model_my_run
```

Copy and rename the YAML file inside the new directory:

```bash
cp GETM_ERSEM_BFM_ORAS5_update.yml my_model_my_run.yml
```

Set `MODEL_ID="my_model_my_run"` in the Slurm script. The extractor loads
`<MODEL_ID>.yml`, and the same identifier is included in output filenames.
Keep `model.name` equal to MODEL_ID for consistency and provenance.

## 2. Adapt the model configuration

The validation observations supply time, longitude, latitude, depth below the
instantaneous surface, and an observed value. The model configuration must map
your model output to match.

The main vertical-coordinate implementation is:

```text
src/validation/vertical_handling.py
```

It is called by the extraction workflow in:

```text
src/validation/Extract_validation_tables.py
```

There are a few pre-existing supported YAML methods:

- `existing_z`: the model provides layer-center depths;
- `layer_thickness`: the model provides layer thicknesses; or
- `interface_variable`: the model provides layer-interface depths.

GETM-ERSEM-BFM uses `layer_thickness`; the included COHERENS configuration is
an example of `existing_z`. *These examples do not guarantee compatibility with
another model*. Confirm the depth sign, vertical order, inactive levels, surface
reference, dry cells, missing values, and behavior outside the local water
column. Then map each model tracer and document any unit conversion in YAML.

- Existing pathways may require extension for a model with an unsupported
  vertical-coordinate convention.
- The current pathways do not support unstructured grids.

The rest of YAML file is for mapping model output variables names to validation names
and providing an required conversion factors for converting your model output
into comparable units for the ICES validation dataset.

## 3. Paths to update
Assuming the repository structure is unchanged, review the below paths.
These example pathways are relative to the root CodeBlueWP4 folder.

Items 1–5 and 9–12 are configured in the Slurm wrapper:

  `<repository-root>/validations/Test/config/ORAS5_update/run_validation.sbatch`

Items 6–8 are configured in the YAML file:

  `<repository-root>/validations/Test/config/ORAS5_update/test.yml`


Or your similar named pathway

1. **Python interpreter — Slurm script**

   ```bash
   CODEBLUE_PYTHON="/absolute/path/to/python"
   ```

   This path is external to the repository. Use an environment containing the
   packages required by the validation workflow.
   
   Your python environment must have the dependencies listed in 
   ~/CodeBlueWP4/environment.yml


2. **Repository root — Slurm script**

Location of your CodeBlueWP4 folder. This is important as it sets up relative path
compatibility if you copy an existing folder.

   ```bash
   REPOSITORY_ROOT="/absolute/path/to/CodeBlueWP4"
   ```

3. **Validation setup root — Slurm script**

Location of your /validations/<setup-name> folder with your configuration files. 
Not the src/validation source code folder

   ```bash
   SETUP_ROOT="${REPOSITORY_ROOT}/validations/<setup-name>"
   ```

4. **Configuration directory — Slurm script**

Location of the specific configuration folder for each specific validation run.

   ```bash
   CONFIG_DIR="${SETUP_ROOT}/config/<configuration-name>"
   ```

5. **YAML configuration — Slurm script**

Derived path, however, MODEL_ID must be consistent throughout the project.

   ```bash
   CONFIG_FILE="${CONFIG_DIR}/${MODEL_ID}.yml"
   ```

   The YAML filename without `.yml` must match `MODEL_ID`.




6. **Model input — YAML `files.pattern`**

This is the location of your model output. The native .nc file your model creates.
ie what you want to compare to the ICES dataset

   ```yaml
   files:
     pattern: "/absolute/path/to/model_output.nc"
   ```

   A recommended local symbolic link is works well:

   ```text
   validations/<setup-name>/input_data/model_input/model_input.nc
   ```

7. **Observation directory — YAML `files.insitudatadir`**

Location of the ICES validation dataset. This should be available
through the WP4 google drive.

   ```yaml
   files:
     insitudatadir: "/absolute/path/to/CodeBlueWP4/ICES_validation_data"
   ```

   It must contain files named `<variable>_<year>.parquet`, such as
   `oxy_2014.parquet`, `temp_2014.parquet`, and `sal_2014.parquet`.
   This has been done for some of the variables already
   
   This extractor currently expects all nine files:

  oxy, nox, nh4, po4, sio, chl, temp, sal, talk

8. **Validation-table output — YAML `files.outdir`**

Location of where you want output data saved.

   ```yaml
   files:
     outdir: "/absolute/path/to/validation/output/"
   ```

9. **Table directory — Slurm script**

Directory where validation tables will be written. It must be empty before a new extraction.

   ```bash
   TABLE_DIR="${SETUP_ROOT}/output"
   ```

   This must resolve to exactly the same directory as YAML `files.outdir`.

10. **Provenance directory — Slurm script**

Tracks where data and scripts came from for future verification and validation.

    ```bash
    PROVENANCE_DIR="${SETUP_ROOT}/provenance"
    ```

11. **Slurm standard output — `#SBATCH` header**

Where log output files will be saved.

    ```bash
    #SBATCH --output=/absolute/path/to/validations/<setup-name>/logs/extract_%j.out
    ```

12. **Slurm standard error — `#SBATCH` header**

Where log error files will be saved.

    ```bash
    #SBATCH --error=/absolute/path/to/validations/<setup-name>/logs/extract_%j.err
    ```

    The log directory must exist before `sbatch` starts the job.

13. (OPTIONAL) **Model-input symlink target — filesystem**

    If you don't want to move a large source file into the model_input folder use a symlink

    ```
      <repository-root>/validations/<setup-name>/input_data/model_input/model_input.nc
    ```

Also review the HPC-specific Slurm partition, CPU count, memory, wall time, job
name, `MODEL_ID`, and `YEAR`. These are not paths, but they are site/run
settings that commonly require changes.

## 4. Create local runtime directories

Model inputs, ICES data, NetCDF/ZIP regional assets, logs, outputs, reviews,
tables, and provenance products are intentionally not versioned. Create the
required directories for a new setup:

```bash
mkdir -p \
  <repository-root>/validations/<setup-name>/input_data/model_input \
  <repository-root>/validations/<setup-name>/input_data/ICES \
  <repository-root>/validations/<setup-name>/logs \
  <repository-root>/validations/<setup-name>/output \
  <repository-root>/validations/<setup-name>/provenance
```

Do not overwrite an accepted model file, symlink target, or nonempty output
directory when preparing another run.

## 5. Check and run

Run the read-only configuration check before submitting extraction:

```bash
/absolute/path/to/python -B \
  <repository-root>/src/validation/vertical_handling.py \
  <repository-root>/validations/<setup-name>/config/<configuration-name>/<MODEL_ID>.yml \
  <year> --check
```

The check must end with:

```text
CHECK PASSED (read-only; no NetCDF or Parquet written)
```

Check the wrapper syntax and submit it:

```bash
bash -n <absolute-path-to-wrapper.sbatch>
sbatch <absolute-path-to-wrapper.sbatch>
```

The current extractor expects nine validation variables and, with match
diagnostics enabled, produces nine `VALID` Parquets, nine `MATCH_STATUS`
Parquets, and one match-status summary.

## Notebook status

The included notebook has been cleared of saved execution state and personal
paths. Its original calculations are preserved for portability review, but its
scientific cleanup is not complete. Before using its metrics for acceptance,
review finite-pair filtering, categorical nearest-neighbor region assignment,
and the target-diagram variability sign.

## Notebook setup and postprocessing

After validation extraction is complete, follow the
[notebook setup and running instructions](config/ORAS5_update/notebooks/README.md)
to configure and run the validation notebook.
