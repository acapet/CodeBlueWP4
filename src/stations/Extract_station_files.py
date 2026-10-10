# Script to extract model vertical profiles at predefined station locations (stations.csv)

# Input file format: {model}.yaml
# Output file format: STATION_{STATION}_{SCENARIO}_{YEAR}_{MODEL}.nc.

# Each output file contains:
#   dimensions: time, depth
#   variables: selected model variable(s), depth

# In {model}.yaml, you need to adapt:
# - your model name
# - the paths to your model output, station list (stations.csv), place you want to store the final
#    station netCDF files.
# - your model specification: corresponding variable names, coordinate names, conversion factor

# Authors: Capet A. & Denis P.
###################################################################################################################

import numpy as np
import pandas as pd
import xarray as xr
import datetime
import yaml
import argparse
import re
import os
import time as _time


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
    description="Extract model vertical profiles at predefined station locations."
)

parser.add_argument("modelid", type=str,
    help="Model configuration name (without .yml extension)")

parser.add_argument("modyear", type=int,
    help="Simulation year to process")

parser.add_argument("scenario", type=str,
    help="Scenario name")

parser.add_argument("-v", "--verbose",action="store_true",
    help="Enable verbose output")

args     = parser.parse_args()
modelid  = args.modelid
modyear  = args.modyear
scenario = args.scenario
verbose  = args.verbose

MAX_STATION_DISTANCE_KM = 5


def nearest_grid_point(lon, lat, station_lon, station_lat):
    """
    Return nearest grid indices (j, i) for either:
      - 1D lon + 1D lat structured grid
      - 2D lon + 2D lat curvilinear grid
    """

    lon = np.asarray(lon)
    lat = np.asarray(lat)

    # Regular / rectilinear grid
    if lon.ndim == 1 and lat.ndim == 1:

        i = np.nanargmin(np.abs(lon - station_lon))
        j = np.nanargmin(np.abs(lat - station_lat))

    # Curvilinear grid
    elif lon.ndim == 2 and lat.ndim == 2:

        d2 = (lon - station_lon)**2 + (lat - station_lat)**2

        j, i = np.unravel_index(
            np.nanargmin(d2),
            d2.shape
        )

    else:
        raise ValueError(
            "lon and lat must both be 1D or both be 2D"
        )

    return int(j), int(i)


def distance_km(lon1, lat1, lon2, lat2):
    """
    Approximate great-circle distance using haversine formula.
    """
    R = 6371.0

    lon1, lat1, lon2, lat2 = map(
        np.deg2rad,
        [lon1, lat1, lon2, lat2]
    )

    dlon = lon2 - lon1
    dlat = lat2 - lat1

    a = (
        np.sin(dlat / 2)**2
        + np.cos(lat1)
        * np.cos(lat2)
        * np.sin(dlon / 2)**2
    )

    return 2 * R * np.arcsin(np.sqrt(a))


# Load model configuration 
with open("../modelspecifics/%s.yml"%modelid) as f:
    cfg = yaml.safe_load(f)

# Loading model output    
modelfile = cfg["files"]["pattern"].format(year=modyear,scenario=scenario)
xmod = xr.open_dataset(modelfile)

if verbose: print("Read model file") 

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


# Load stations
stations_file = cfg["files"]["stations"]

if verbose:
    print("Reading stations from:", stations_file)

stations = pd.read_csv(stations_file)

if verbose:
    print(stations)
    print("Number of stations:", len(stations))
    
# Model coordinates
model_lon = np.asarray(xmod[lon_dim])
model_lat = np.asarray(xmod[lat_dim])

# Work on a copy
stations = stations.copy()

# Columns to add
stations["i"] = pd.Series(dtype="Int64")
stations["j"] = pd.Series(dtype="Int64")

valid = []

for idx, station in stations.iterrows():

    station_name = str(station["station"])
    station_lon = float(station["lon"])
    station_lat = float(station["lat"])

    if False:
        print("\n========================================")
        print("Station:", station_name)
        print("Longitude:", station_lon)
        print("Latitude :", station_lat)

    try:
        j, i = nearest_grid_point(
            model_lon,
            model_lat,
            station_lon,
            station_lat
        )

    except ValueError:
        if False: 
            print(
                f"WARNING: Station {station_name} "
                "cannot be located in model grid. Skipping."
            )
        continue

    # Verify that the nearest grid point is actually valid
    if model_lon.ndim == 1:
        grid_lon = model_lon[i]
        grid_lat = model_lat[j]
    else:
        grid_lon = model_lon[j, i]
        grid_lat = model_lat[j, i]

    dist = distance_km(
        station_lon,
        station_lat,
        grid_lon,
        grid_lat
    )

    if dist > MAX_STATION_DISTANCE_KM:
        if False:
            print(
                f"WARNING: Station {station_name} "
                f"is {dist:.1f} km from nearest model grid point. "
                "Skipping."
            )
        continue

    stations.loc[idx, "i"] = i
    stations.loc[idx, "j"] = j
    valid.append(idx)


# Keep only stations that could be mapped
stations = stations.loc[valid].copy()

jj = stations["j"].values.astype(int)
ii = stations["i"].values.astype(int)

j = xr.DataArray(jj, dims="station", coords={"station": stations["station"].values})
i = xr.DataArray(ii, dims="station", coords={"station": stations["station"].values})

# ---------------------------------------------------------------
# Sequential extraction: read the file once, in time blocks
# ---------------------------------------------------------------
hvars = [v for v in xmod.data_vars if {lat_dim, lon_dim} <= set(xmod[v].dims)]
tvars = [v for v in hvars if time_dim in xmod[v].dims]       # time-dependent
svars = [v for v in hvars if time_dim not in xmod[v].dims]   # static (e.g. depth)
ovars = [v for v in xmod.data_vars if v not in hvars]        # no horizontal dims

nt    = xmod.sizes[time_dim]
step  = 30        # time steps per block; ~110 MB per variable per block (float32)
t_ref = _time.time()

pieces = []
for t0 in range(0, nt, step):
    tsl = slice(t0, min(t0 + step, nt))
    sub = {}
    for v in tvars:
        blk = xmod[v].isel({time_dim: tsl}).load()          # one big contiguous read
        sub[v] = blk.isel({lat_dim: j, lon_dim: i})         # in-memory pointwise pick
        del blk
    pieces.append(xr.Dataset(sub))
    if verbose:
        print(f"  time {tsl.start}-{tsl.stop} / {nt}  ({_time.time() - t_ref:.0f} s)")

xsta = xr.concat(pieces, dim=time_dim, data_vars="minimal",
                 coords="minimal", compat="override")
del pieces

# Static horizontal variables (read once)
if svars:
    xsta = xsta.assign({v: xmod[v].load().isel({lat_dim: j, lon_dim: i}) for v in svars})

# Variables without horizontal dimensions (time-only, level-only, ...)
if ovars:
    xsta = xr.merge([xsta, xmod[ovars].load()], compat="override")

xsta.attrs.update(xmod.attrs)

if verbose: print("Extraction done, %.0f s" % (_time.time() - t_ref))
    
namespace = {name: xsta[name] for name in xsta.variables}

for newvar, spec in cfg.get("derived_variables", {}).items():

    if verbose:
        print(f"  Computing {newvar} as:")
    expr = spec["expression"]

    if verbose:
        print(f"    {expr}")
    xsta[newvar] = eval(expr, {"__builtins__": {}}, namespace)

    # make newly derived variable available to subsequent expressions
    namespace[newvar] = xsta[newvar]


# Prepare output directory
outdir = cfg["files"]["outdir"]
os.makedirs(outdir, exist_ok=True)

# Output filename
ofname = (
    f"{outdir}/"
    f"STATION_{scenario}_"
    f"{modyear}_{modelid}.nc"
)

# Save NetCDF
if verbose:
    print("Saving:", ofname)

xsta.to_netcdf(ofname)

if verbose:
    print("Done")
