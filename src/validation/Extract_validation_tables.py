# Script to extract corresponding model output values and add it into existing ICES data tabular files (.parquet)
# => VALIDATION TABLES

# Input file format: {model}.yaml
# Output file format: VALID_{var}_{year}_{model}.parquet

# The following script links your model output file with the ICES in situ data tabular files. 
# It adds a column with the model value corresponding to each existing data in you domain.
# In {model}.yaml, you need to adapt:
# - your model name
# - the paths to your model output, place where you store ICES data .parquet files, place you want to store the final
#    validation .parquet files.
# - your model specification: corresponding variable names, coordinate names, conversion factor

# THIS SCRIPT CAN BE RUN VIA: python3 Extract_validation_tables.py -v $MOD $YEAR

# Authors: Capet A. & Denis P.
###################################################################################################################

import numpy as np
import pandas as pd
import xarray as xr
import datetime
import yaml
import argparse
import re

from vertical_handling import (
    interpolate_to_observation_depths,
    mask_vertical_inputs,
    observation_match_diagnostics,
    prepare_vertical_coordinates,
    vertical_input_names,
)


def _utc_naive_datetime(values):
    """Normalize timestamps to UTC-naive values for model-time matching.

    The original observation column is retained in output tables.  This helper
    is used only for year selection, time-range diagnostics, and xarray
    interpolation against timezone-naive NetCDF coordinates.
    """
    converted = pd.to_datetime(values, errors="coerce", utc=True)
    if isinstance(converted, pd.Series):
        return converted.dt.tz_localize(None)
    return converted.tz_localize(None)

# Deal with arguments
parser = argparse.ArgumentParser(
    description="Extract model values at ICES observation locations."
)

parser.add_argument("modelid", type=str,
    help="Model configuration name (without .yml extension)")

parser.add_argument("modyear", type=int,
    help="Simulation year to process")

parser.add_argument("-v", "--verbose",action="store_true",
    help="Enable verbose output")

parser.add_argument("--match-diagnostics", action="store_true",
    help=("Write MATCH_STATUS sidecars and a summary without changing the "
          "VALID parquet schema or filling missing model values"))

args = parser.parse_args()
modelid = args.modelid
modyear = args.modyear
verbose = args.verbose
write_match_diagnostics = args.match_diagnostics

# Load model configuration 
with open("%s.yml"%modelid) as f:
    cfg = yaml.safe_load(f)

# Loading Model data    
modelfile = cfg["files"]["pattern"].format(year=modyear)
xmod = xr.open_dataset(modelfile)

if verbose: print("Read model file") 

# Compute composite variables ###
for newvar, spec in cfg.get("derived_variables", {}).items():
    if verbose : print("  Computing %s as :"%newvar) 
    expr = spec["expression"]
    for v in xmod.data_vars :
        expr = re.sub(
            rf"\b{re.escape(v)}\b",
            f"xmod['{v}']",
            expr
        )
    # ... should be a beter way than repeat this twice... 
    for v in xmod.coords :
        expr = re.sub(
            rf"\b{re.escape(v)}\b",
            f"xmod['{v}']",
            expr
        )
    if verbose : print("    %s"%expr)
    xmod[newvar] = eval(expr)
                        
if verbose: print("Added variables") 

# Acquire coordinate dimension names 
time_dim = cfg["coordinates"]["time"]
lat_dim = cfg["coordinates"]["lat"]
lon_dim = cfg["coordinates"]["lon"]
lev_dim = cfg["coordinates"]["vertical"]
#dep_dim = cfg["coordinates"]["dep"]

# Get model extent
model_lon_min = float(xmod[lon_dim].min())
model_lon_max = float(xmod[lon_dim].max())

model_lat_min = float(xmod[lat_dim].min())
model_lat_max = float(xmod[lat_dim].max())

model_times = _utc_naive_datetime(
    np.asarray(xmod[time_dim].values).reshape(-1)
)
model_times = model_times[~pd.isna(model_times)]
if len(model_times) == 0:
    raise ValueError(f"Model time coordinate {time_dim!r} has no valid timestamps")
model_time_min = model_times.min()
model_time_max = model_times.max()

# This should contain the full list of validation variables
#TODO: interface with validation.csv .. if needed
vars = ["oxy", "nox", "nh4", "po4", "sio", "chl", "temp", "sal", "talk"]
match_summary_rows = []

for var in vars:
    # Shaping local in situ dataframe   
    fname = cfg["files"]["insitudatadir"]+'%s_%s.parquet'%(var,modyear)
    if verbose: print('reading %s'%fname)
    dfl =pd.read_parquet(fname)
    if verbose : print(dfl.columns)
    
    required_observation_columns = {"datetime", "lon", "lat", "depth", var}
    missing_observation_columns = sorted(
        required_observation_columns.difference(dfl.columns)
    )
    if missing_observation_columns:
        raise KeyError(
            f"Observation table for {var} is missing columns "
            f"{missing_observation_columns}"
        )

    observation_times = _utc_naive_datetime(dfl["datetime"])
    year_mask = observation_times.dt.year == modyear
    dyear = dfl.loc[year_mask].copy().reset_index(drop=True)
    dyear["_match_source_row"] = np.arange(len(dyear), dtype=np.int64)
    year_times = _utc_naive_datetime(dyear["datetime"])

    observation_lon = pd.to_numeric(dyear["lon"], errors="coerce")
    observation_lat = pd.to_numeric(dyear["lat"], errors="coerce")
    observation_depth = pd.to_numeric(dyear["depth"], errors="coerce")
    observation_value = pd.to_numeric(dyear[var], errors="coerce")
    required_values_valid = (
        year_times.notna().to_numpy()
        & np.isfinite(observation_lon.to_numpy())
        & np.isfinite(observation_lat.to_numpy())
        & np.isfinite(observation_depth.to_numpy())
        & np.isfinite(observation_value.to_numpy())
    )
    inside_horizontal_bounds = (
        (observation_lon >= model_lon_min)
        & (observation_lon <= model_lon_max)
        & (observation_lat >= model_lat_min)
        & (observation_lat <= model_lat_max)
    ).to_numpy()

    # Preserve the original VALID-table selection: rectangular horizontal
    # bounds followed by the legacy all-column dropna. The diagnostics sidecar
    # retains the excluded annual observations and records why they were not
    # candidates for model interpolation.
    dflt = dyear.loc[inside_horizontal_bounds].dropna().copy()
    dflt["mod"] = np.nan
    dflt_times = _utc_naive_datetime(dflt["datetime"])
    inside_model_time = (
        (dflt_times >= model_time_min)
        & (dflt_times <= model_time_max)
    )
    dwork = dflt.loc[inside_model_time].copy()

    # Get coordinates for rows that are eligible for interpolation.
    lons = xr.DataArray(dwork['lon'].to_numpy(), dims="points")
    lats = xr.DataArray(dwork['lat'].to_numpy(), dims="points")
    times = xr.DataArray(
        dflt_times.loc[dwork.index].to_numpy(dtype="datetime64[ns]"),
        dims="points",
    )
    depths = xr.DataArray(dwork['depth'].to_numpy(), dims="points")

    # Get model specific coordinate variable names
    vcfg = cfg["variables"][var]
    mvar = vcfg["model_name"]
    conversion = vcfg.get("conversion", 1.0)

    # The legacy behavior is preserved when this block is absent.
    vertical_cfg = cfg.get(
        "vertical_coordinate",
        {
            "method": "existing_z",
            "z_variable": "z",
            "positive": "down",
            "reference": "instantaneous_surface",
            "observation_reference": "instantaneous_surface",
            "outside_column": "missing",
        },
    )
    vertical_variables = vertical_input_names(vertical_cfg)
    required_variables = list(dict.fromkeys([mvar] + vertical_variables))
    missing_variables = [
        name for name in required_variables if name not in xmod
    ]
    if missing_variables:
        raise KeyError(
            f"Configured model inputs are missing for {var}: "
            f"{missing_variables}"
        )

    # Mask configured fill values before horizontal/time interpolation.
    # Apply the unit conversion to the tracer only; physical depths remain m.
    xmodv = xmod[required_variables].copy()
    tracer_valid = np.isfinite(xmodv[mvar])
    tracer_missing_values = vcfg.get(
        "missing_values",
        vertical_cfg.get("missing_values", [-9998.0, -9999.0]),
    )
    for missing_value in tracer_missing_values:
        tracer_valid = tracer_valid & (xmodv[mvar] != float(missing_value))
    xmodv[mvar] = xmodv[mvar].where(tracer_valid) * conversion
    xmodv = mask_vertical_inputs(xmodv, vertical_cfg)

    chunking = {
        dimension: size
        for dimension, size in (
            (time_dim, 50),
            (lat_dim, 100),
            (lon_dim, 100),
            (lev_dim, -1),
        )
        if dimension in xmodv.dims
    }
    for dimension in xmodv.dims:
        if "interface" in dimension.lower():
            chunking[dimension] = -1
    xmodv = xmodv.chunk(chunking)

    if not dwork.empty:
        # First horizontal/time interpolation, to get vertical columns.
        tmp = xmodv.interp({lon_dim:lons, lat_dim:lats, time_dim:times})

        z_center, z_interface, model_bottom_depth, wet_profile = (
            prepare_vertical_coordinates(tmp, vertical_cfg, lev_dim)
        )
        result = interpolate_to_observation_depths(
            tmp[mvar],
            depths,
            z_center,
            model_bottom_depth,
            wet_profile,
            lev_dim,
            vertical_cfg,
        )
        diagnostics = observation_match_diagnostics(
            tmp[mvar],
            depths,
            z_center,
            model_bottom_depth,
            wet_profile,
            lev_dim,
            vertical_cfg,
            result,
        )

        # Compute the model result and its diagnostic masks in the same graph.
        computed = diagnostics.assign(mod=result).compute()
        dflt.loc[dwork.index, "mod"] = computed["mod"].values

    if write_match_diagnostics:
        audit = dyear.copy()
        audit["mod"] = np.nan
        audit["match_status"] = "not_evaluated"
        audit["model_bottom_depth"] = np.nan
        audit["depth_minus_model_bottom"] = np.nan

        audit.loc[~required_values_valid, "match_status"] = "invalid_observation"
        audit.loc[
            required_values_valid & ~inside_horizontal_bounds, "match_status"
        ] = "outside_horizontal_bounds"

        legacy_rows = set(dflt["_match_source_row"].to_numpy())
        excluded_by_dropna = (
            required_values_valid
            & inside_horizontal_bounds
            & ~audit["_match_source_row"].isin(legacy_rows).to_numpy()
        )
        audit.loc[
            excluded_by_dropna, "match_status"
        ] = "excluded_by_legacy_dropna"

        outside_time_rows = dflt.loc[~inside_model_time, "_match_source_row"]
        audit.loc[
            audit["_match_source_row"].isin(outside_time_rows), "match_status"
        ] = "outside_model_time_range"

        if not dwork.empty:
            work_rows = dwork["_match_source_row"].to_numpy()
            valid_column = computed["valid_model_column"].values.astype(bool)
            finite_tracer = computed["finite_tracer_profile"].values.astype(bool)
            above_surface = computed["above_model_surface"].values.astype(bool)
            below_bottom = computed["below_model_bottom"].values.astype(bool)
            transformed_finite = computed["transformed_finite"].values.astype(bool)
            bottom_values = computed["model_bottom_depth"].values.astype(float)

            evaluated_status = np.full(len(dwork), "matched", dtype=object)
            evaluated_status[~valid_column] = "no_valid_model_column"
            evaluated_status[valid_column & above_surface] = "above_model_surface"
            evaluated_status[valid_column & below_bottom] = "below_model_bottom"
            in_bounds = valid_column & ~above_surface & ~below_bottom
            evaluated_status[in_bounds & ~finite_tracer] = (
                "missing_model_tracer_profile"
            )
            evaluated_status[
                in_bounds & finite_tracer & ~transformed_finite
            ] = "vertical_transform_missing"

            audit_row_mask = audit["_match_source_row"].isin(work_rows)
            audit.loc[audit_row_mask, "match_status"] = evaluated_status
            audit.loc[audit_row_mask, "mod"] = computed["mod"].values
            audit.loc[audit_row_mask, "model_bottom_depth"] = bottom_values
            audit.loc[audit_row_mask, "depth_minus_model_bottom"] = (
                pd.to_numeric(
                    audit.loc[audit_row_mask, "depth"], errors="coerce"
                ).to_numpy()
                - bottom_values
            )

        audit = audit.rename(columns={"_match_source_row": "source_row_in_year"})
        diagnostic_name = (
            f"{cfg['files']['outdir']}/MATCH_STATUS_{var}_{modyear}_{modelid}.parquet"
        )
        if verbose:
            print(f" Saving match diagnostics to {diagnostic_name}")
            print(audit["match_status"].value_counts(dropna=False).to_string())
        audit.to_parquet(diagnostic_name, index=False)

        counts = audit["match_status"].value_counts(dropna=False)
        for status, count in counts.items():
            match_summary_rows.append({
                "variable": var,
                "match_status": status,
                "N": int(count),
                "percent_of_annual_observations": 100.0 * count / len(audit),
            })

    ofname = "%s/VALID_%s_%s_%s.parquet"%(cfg["files"]["outdir"],var,modyear,modelid)
    if verbose : print(" Saving to %s"%ofname)
    dflt.drop(columns="_match_source_row").to_parquet(ofname)

if write_match_diagnostics:
    summary_name = (
        f"{cfg['files']['outdir']}/MATCH_STATUS_SUMMARY_{modyear}_{modelid}.csv"
    )
    pd.DataFrame(match_summary_rows).to_csv(summary_name, index=False)
    if verbose:
        print(f"Saved match-status summary to {summary_name}")
