# Validation input modes

The validation calculations are unchanged. `validation_input.py` only controls
which raw model records and ICES observations are supplied to those
calculations.

One self-contained YAML file defines the model mapping, input files, selected
months, observation directory, and output directory. The command-line interface
remains:

```bash
/absolute/path/to/python Extract_validation_tables.py MODEL_ID YEAR \
    -v --match-diagnostics
```

For an HPC run, submit from the repository root and pass the YAML file and
requested year to the batch wrapper:

```bash
export CODEBLUE_PYTHON=/absolute/path/to/python
sbatch --export=ALL,CODEBLUE_PYTHON="${CODEBLUE_PYTHON}" \
    src/validation/run_validation.sbatch \
    /absolute/path/MODEL_ID.yml \
    2014
```

## Input configuration

Yearly input opens one file for every calendar year needed by the selected
period:

```yaml
input:
  mode: yearly
  pattern: "/model/output/model_{year}.nc"
```

Monthly input opens the selected raw monthly files lazily:

```yaml
input:
  mode: monthly
  pattern: "/model/output/{year}/{month:02d}/model_output.3d.nc"
  months: [9, 10, 11]
```

If `months` is omitted, January through December are selected. The requested
year is the ending year for a wrapped period, so `[12, 1, 2]` with `YEAR=2014`
means December 2013 and January-February 2014.

Month values must be unique integers from 1 through 12. Non-contiguous lists
are allowed, with at most one year wrap. When adjacent files contain the same
boundary timestamp, the record from the later file is retained. Records are
then sorted and required to have unique timestamps.

Model data remain lazy through xarray/Dask. No averaging or resampling is
performed. Model records and annual ICES Parquet files are restricted to the
same configured year/month pairs.

Legacy YAML files that contain `files.pattern` but no `input` section continue
to run as full-year yearly configurations.

See `config_examples/GETM_ERSEM_BFM_monthly.yml` for a complete monthly
configuration template.
