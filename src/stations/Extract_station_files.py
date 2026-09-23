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

args = parser.parse_args()
modelid = args.modelid
modyear = args.modyear
scenario = args.scenario
verbose = args.verbose

# Load model configuration 
with open("%s.yml"%modelid) as f:
    cfg = yaml.safe_load(f)

# Load stations
stations_file = cfg["files"]["stations"]

if verbose:
    print("Reading stations from:", stations_file)

stations = pd.read_csv(stations_file)

if verbose:
    print(stations)
    print("Number of stations:", len(stations))


# Loading model output    
modelfile = cfg["files"]["pattern"].format(year=modyear,scenario=scenario)
xmod = xr.open_dataset(modelfile)

if verbose: print("Read model file") 

# Compute derived variables
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

# Vertical coordinate in the model
z_name = cfg["coordinates"].get("depth", "z")

# Get model extent
model_lon_min = float(xmod[lon_dim].min())
model_lon_max = float(xmod[lon_dim].max())

model_lat_min = float(xmod[lat_dim].min())
model_lat_max = float(xmod[lat_dim].max())

# This should contain the full list of validation variables
vars=['oxy','nox','nh4','po4','sio','chl', 'temp', 'sal']#, 'secchi', 'ph', 'talk', 'dic']

# for var in vars:
#     # Shaping local in situ dataframe   
#     fname = cfg["files"]["insitudatadir"]+'%s_%s.parquet'%(var,modyear)
#     if verbose: print('reading %s'%fname)
#     dfl =pd.read_parquet(fname)
#     if verbose : print(dfl.columns)

    
#     ## This shouldn't be needed ... 
#     dflt=dfl[dfl['datetime'].dt.year == modyear]

#     dflt = dflt[
#         (dflt["lon"] >= model_lon_min) &
#         (dflt["lon"] <= model_lon_max) &
#         (dflt["lat"] >= model_lat_min) &
#         (dflt["lat"] <= model_lat_max)
#     ]
#     dflt = dflt.dropna()

#     # Get coordinates
#     lons  = xr.DataArray(dflt['lon'], dims="points")
#     lats  = xr.DataArray(dflt['lat'], dims="points")
#     times = xr.DataArray(dflt['datetime'], dims="points")
#     depths = xr.DataArray(dflt['depth'], dims="points")

#     # Get model specific coordinate variable names
#     vcfg = cfg["variables"][var]
#     mvar = vcfg["model_name"]
#     conversion = vcfg.get("conversion", 1.0)
   
#     # Local model data
#     xmodv = xmod[[mvar, 'z']].copy()*conversion
    
#     xmodv = xmodv.chunk({
#         time_dim: 50,
#         lat_dim: 100,
#         lon_dim: 100,
#         lev_dim: -1
#     })

#     # First horizontal interpolation, to get vertical columns
#     tmp = xmodv.interp({lon_dim:lons, lat_dim:lats, time_dim:times})
#     z = tmp["z"]
    
#     tmp = tmp.chunk({lev_dim: -1})
#     z   = z.chunk({lev_dim: -1})
    
#     # Organize the distribution of vertical interpolation 
#     result = xr.apply_ufunc(
#         np.interp,
#         depths,
#         z,
#         tmp[mvar],
#         input_core_dims=[[], [lev_dim], [lev_dim]],
#         output_core_dims=[[]],
#         vectorize=True,
#         dask="parallelized",
#         output_dtypes=[tmp[mvar].dtype],
#     )

#     # This is where the computation actually takes place. All the above is 'lazy'
#     dflt['mod']=result

#     ofname = "%s/VALID_%s_%s_%s.parquet"%(cfg["files"]["outdir"],var,modyear,modelid)
#     if verbose : print(" Saving to %s"%ofname)
#     dflt.to_parquet(ofname)

# Prepare output directory
outdir = cfg["files"]["outdir"]
os.makedirs(outdir, exist_ok=True)

for _, station in stations.iterrows():

    station_name = str(station["station"])
    station_lon = float(station["lon"])
    station_lat = float(station["lat"])

    if verbose:
        print("\n========================================")
        print("Station:", station_name)
        print("Longitude:", station_lon)
        print("Latitude :", station_lat)

    #################################################################
    # Check station location
    #################################################################

    if not (
        model_lon_min <= station_lon <= model_lon_max
        and
        model_lat_min <= station_lat <= model_lat_max
    ):

        print(
            f"WARNING: Station {station_name} "
            f"is outside model domain. Skipping."
        )

        continue


    #################################################################
    # Extract all variables
    #################################################################

    station_data = {}

    for var in vars:

        if verbose:
            print("  Processing:", var)

        #################################################################
        # Model variable name and conversion
        #################################################################

        vcfg = cfg["variables"][var]

        mvar = vcfg["model_name"]
        conversion = vcfg.get("conversion", 1.0)

        #################################################################
        # Check variable exists
        #################################################################

        if mvar not in xmod:

            print(
                f"WARNING: {mvar} not found in model file. "
                f"Skipping {var}."
            )

            continue

        #################################################################
        # Extract model variable
        #################################################################

        model_var = xmod[mvar] * conversion

        #################################################################
        # Horizontal interpolation
        #
        # The entire vertical profile is retained.
        #################################################################

        profile = model_var.interp(
            {
                lon_dim: station_lon,
                lat_dim: station_lat
            }
        )

        #################################################################
        # Store with ICES-style variable name
        #################################################################

        station_data[var] = profile


    #################################################################
    # Create Dataset
    #################################################################

    ds_station = xr.Dataset(station_data)


    #################################################################
    # Rename vertical coordinate to "depth"
    #################################################################

    if z_name in ds_station.coords:

        ds_station = ds_station.rename(
            {z_name: "depth"}
        )

    elif z_name in ds_station.data_vars:

        ds_station = ds_station.rename(
            {z_name: "depth"}
        )

    elif lev_dim in ds_station.coords:

        ds_station = ds_station.rename(
            {lev_dim: "depth"}
        )


    #################################################################
    # Add station coordinates / metadata
    #################################################################

    ds_station.attrs["station"] = station_name
    ds_station.attrs["latitude"] = station_lat
    ds_station.attrs["longitude"] = station_lon
    ds_station.attrs["scenario"] = scenario
    ds_station.attrs["year"] = modyear
    ds_station.attrs["model"] = modelid


    #################################################################
    # Output filename
    #################################################################

    ofname = (
        f"{outdir}/"
        f"STATION_{station_name}_{scenario}_"
        f"{modyear}_{modelid}.nc"
    )


    #################################################################
    # Save NetCDF
    #################################################################

    if verbose:
        print("  Saving:", ofname)

    ds_station.to_netcdf(ofname)

    if verbose:
        print("  Done")


#####################################################################
# Close model
#####################################################################

xmod.close()

if verbose:
    print("\nFinished.")
