import numpy as np
import pandas as pd
import xarray as xr
import datetime
import yaml
import argparse


# Deal with arguments
parser = argparse.ArgumentParser(
    description="Extract model values at ICES observation locations."
)

parser.add_argument(
    "modelid",
    type=str,
    help="Model configuration name (without .yml extension)"
)
parser.add_argument(
    "modyear",
    type=int,
    help="Simulation year to process"
)
args = parser.parse_args()
modelid = args.modelid
modyear = args.modyear

# Load model configuration 
with open("%s.yml"%modelid) as f:
    cfg = yaml.safe_load(f)

# Loading Model data    
modelfile = cfg["files"]["pattern"].format(year=modyear)
xmod = xr.open_dataset(modelfile)

# Compute composite variables ###
for newvar, spec in cfg.get("derived_variables", {}).items():
    expr = spec["expression"]
    for v in xmod.data_vars:
        expr = expr.replace(v, f"xmod['{v}']")
    xmod[newvar] = eval(expr)

# Get model extent
model_lon_min = float(xmod[lon_dim].min())
model_lon_max = float(xmod[lon_dim].max())

model_lat_min = float(xmod[lat_dim].min())
model_lat_max = float(xmod[lat_dim].max())

# This should contain the full list of validation variables
# TODO interface with validation.csv .. if needed
vars=['oxy','nox','nh4','chl','po4','sio']

for var in vars:
    # Shaping local in situ dataframe 
    dfl =pd.read_parquet(datadir+'%s_%s.parquet'%(var,yr))

    ## This shouldn't be needed ... 
    dflt=dfl[dfl['datetime'].dt.year == modyear]

    dflt = dflt[
        (dflt["lon"] >= model_lon_min) &
        (dflt["lon"] <= model_lon_max) &
        (dflt["lat"] >= model_lat_min) &
        (dflt["lat"] <= model_lat_max)
    ]
    dflt = dflt.dropna()

    # Get coordinaates
    lons  = xr.DataArray(dflt['lon'], dims="points")
    lats  = xr.DataArray(dflt['lat'], dims="points")
    times = xr.DataArray(dflt['datetime'], dims="points")
    depths = xr.DataArray(dflt['depth'], dims="points")

    # Get model specific coordinate variable names
    vcfg = cfg["variables"][var]
    mvar = vcfg["model_name"]
    conversion = vcfg.get("conversion", 1.0)
  
    time_dim = cfg["coordinates"]["time"]
    lat_dim = cfg["coordinates"]["lat"]
    lon_dim = cfg["coordinates"]["lon"]
    lev_dim = cfg["coordinates"]["vertical"]
    dep_dim = cfg["coordinates"]["dep"]

    # Local model data
    xmodv = xmod[[mvar, dep_dim]].copy()*conversion
    
    xmodv = xmodv.chunk({
        time_dim: 50,
        lat_dim: 100,
        lon_dim: 100,
        lev_dim: -1
    })

    # First horizontal interpolation, to get vertical columns
    tmp = xmodv.interp(lon_dim=lons, lat_dim=lats, time_dim=times)
    z = tmp[lev_dim] * tmp[dep_dim]
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

    dflt.to_parquet("%s/ICES_%s_%s.parquet"%(modeldir,modyear,var))