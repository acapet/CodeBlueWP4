import numpy as np
import pandas as pd
import xarray as xr
import datetime
import yaml
import argparse
import re

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

args = parser.parse_args()
modelid = args.modelid
modyear = args.modyear
verbose = args.verbose

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

# This should contain the full list of validation variables
#TODO: interface with validation.csv .. if needed
vars=['oxy','nox','nh4','po4','sio','chl']

for var in vars:
    # Shaping local in situ dataframe   
    fname = cfg["files"]["insitudatadir"]+'%s_%s.parquet'%(var,modyear)
    if verbose: print('reading %s'%fname)
    dfl =pd.read_parquet(fname)
    if verbose : print(dfl.columns)

    # TO BE DELETED WHEN THE ISSUE OF HAVING DEPTH INTHE SINLGE YEAR FILE IS SOLVED.#
    fname2 = cfg["files"]["insitudatadir"]+'%s_%s.parquet'%(var,"2010_2015")
    if verbose: print('reading %s'%fname2)
    dfl2 =pd.read_parquet(fname2)
    if verbose : print(dfl2.columns)
    dfl=dfl2
    # # # # # # ## # # #  # # # #  ## 
    
    ## This shouldn't be needed ... 
    dflt=dfl[dfl['datetime'].dt.year == modyear]

    dflt = dflt[
        (dflt["lon"] >= model_lon_min) &
        (dflt["lon"] <= model_lon_max) &
        (dflt["lat"] >= model_lat_min) &
        (dflt["lat"] <= model_lat_max)
    ]
    dflt = dflt.dropna()

    # Get coordinates
    lons  = xr.DataArray(dflt['lon'], dims="points")
    lats  = xr.DataArray(dflt['lat'], dims="points")
    times = xr.DataArray(dflt['datetime'], dims="points")
    depths = xr.DataArray(dflt['depth'], dims="points")

    # Get model specific coordinate variable names
    vcfg = cfg["variables"][var]
    mvar = vcfg["model_name"]
    conversion = vcfg.get("conversion", 1.0)
   
    # Local model data
    xmodv = xmod[[mvar, 'z']].copy()*conversion
    
    xmodv = xmodv.chunk({
        time_dim: 50,
        lat_dim: 100,
        lon_dim: 100,
        lev_dim: -1
    })

    # First horizontal interpolation, to get vertical columns
    tmp = xmodv.interp({lon_dim:lons, lat_dim:lats, time_dim:times})
    z = tmp["z"]
    
    tmp = tmp.chunk({lev_dim: -1})
    z   = z.chunk({lev_dim: -1})
    
    # Organize the distribution of vertical interpolation 
    result = xr.apply_ufunc(
        np.interp,
        depths,
        z,
        tmp[mvar],
        input_core_dims=[[], [lev_dim], [lev_dim]],
        output_core_dims=[[]],
        vectorize=True,
        dask="parallelized",
        output_dtypes=[tmp[mvar].dtype],
    )

    # This is where the computation actually takes place. All the above is 'lazy'
    dflt['mod']=result

    ofname = "%s/VALID_%s_%s_%s.parquet"%(cfg["files"]["outdir"],var,modyear,modelid)
    if verbose : print(" Saving to %s"%ofname)
    dflt.to_parquet(ofname)