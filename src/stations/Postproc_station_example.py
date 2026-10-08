#!/usr/bin/env python3
"""Depth x time plot of chl (top) and nitrate (bottom) at one station,
from consecutive yearly STATION_*.nc files."""

import argparse
import numpy as np
import xarray as xr
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from cmocean import cm

p = argparse.ArgumentParser()
p.add_argument("model")
p.add_argument("scenario")
p.add_argument("year0", type=int)
p.add_argument("year1", type=int)
p.add_argument("station")
p.add_argument("--indir", default=".")
p.add_argument("--log", action="store_true", help="log colour scale for chl")
args = p.parse_args()

years = range(args.year0, args.year1 + 1)
files = [f"{args.indir}/STATION_{args.scenario}_{y}_{args.model}.nc" for y in years]

# Files are small (time x lev x station), so load everything
ds = xr.open_mfdataset(files, combine="by_coords", data_vars="minimal",
                       coords="minimal", compat="override").load()

if args.station not in ds["station"].values:
    raise SystemExit(f"Station {args.station!r} not found. Available:\n"
                     + ", ".join(map(str, ds["station"].values)))

s = ds.sel(station=args.station)

time  = s["time"].values
depth = s["z"].values                      # (lev,), time-independent (sigma levels)
chl   = s["chl"].transpose("lev", "time")
no3   = (s["no3"] * 1000.0).transpose("lev", "time")   # mol m-3 -> mmol m-3

# Order levels so that depth is monotonic increasing for pcolormesh
order = np.argsort(depth)
depth, chl, no3 = depth[order], chl.isel(lev=order), no3.isel(lev=order)

fig, axs = plt.subplots(2, 1, figsize=(12, 7), sharex=True, constrained_layout=True)

panels = [
    (axs[0], chl, "Chlorophyll (mg chl m$^{-3}$)", "YlGn"),
    (axs[1], no3, "Nitrate (mmol N m$^{-3}$)", "viridis"),
]
for ax, da, label, cmap in panels:
    vmax = np.nanpercentile(da.values, 98)
    kw = dict(cmap=cmap, shading="nearest")
    if da is chl and args.log:
        vmin = max(np.nanpercentile(da.values, 2), 1e-2)
        kw["norm"] = matplotlib.colors.LogNorm(vmin=vmin, vmax=vmax)
    else:
        kw.update(vmin=0, vmax=vmax)
    m = ax.pcolormesh(time, depth, da.values, **kw)
    fig.colorbar(m, ax=ax, label=label, pad=0.01)
    ax.set_ylabel("Depth (m)")

axs[0].set_title(f"{args.station} - {args.model} {args.scenario} "
                 f"({args.year0}-{args.year1})")
axs[1].set_xlabel("Time")

out = f"{args.station}_{args.model}_{args.scenario}_{args.year0}-{args.year1}.png"
fig.savefig(out, dpi=200)
print("Saved", out)