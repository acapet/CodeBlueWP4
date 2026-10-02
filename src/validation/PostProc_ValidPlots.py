import xarray as xr

import numpy as np
import pandas as pd

import matplotlib.pyplot as plt 
from  matplotlib.colors import LogNorm
from matplotlib.ticker import LogFormatter 
from matplotlib.colors import ListedColormap
from matplotlib.patches import Circle

import seaborn as sns

from cmocean import cm

from cartopy import crs as ccrs
import cartopy.feature as cf

import datetime

datadir = '/ec/res4/scratch/cvao/BGC/OUTPUTS/nos4_carb/'
regionfile = '/home/cvao/postprocessing-toolbox/NetCDF_manipulation/Geospatial/Bathymetry_NoS_with_regions_AC.nc'
model = 'coherens'
vars  = ["oxy", "nox", "nh4", "po4", "sio", "chl", "temp", "sal", "talk"]
years = [2011]


######################"

def buildstatlist(dflt):

    Nmin = 5
    
    stats_list = []  # Store results for each region

    dflt['diff']=dflt['mod'] - dflt[var]
    for reg in range(nreg):
        dfloc = dflt[dflt['reg'] == reg]

        if regdatacount[reg] > Nmin:
            # Compute statistics
            mod_mean = dfloc['mod'].mean()
            mod_std = dfloc['mod'].std()
            obs_mean = dfloc[var].mean()
            obs_std = dfloc[var].std()
            bias = mod_mean - obs_mean
            perc_bias = (bias / obs_mean) * 100
            corr = np.corrcoef(dfloc['mod'], dfloc[var], rowvar=False)[0, 1]
            nse = (1 - (dfloc['diff'] ** 2).sum() / ((dfloc[var] - obs_mean) ** 2).sum())
            rmsd = np.sqrt((dfloc['diff'] ** 2).mean())
            crmsd = np.sqrt((((dfloc[var]-obs_mean) - (dfloc['mod']-mod_mean)) ** 2).mean())
        else:
            mod_mean = np.nan
            mod_std = np.nan
            obs_mean = np.nan
            obs_std = np.nan
            bias = np.nan
            perc_bias = np.nan
            corr = np.nan
            nse = np.nan
            rmsd = np.nan
            crmsd = np.nan
        # Append results as a dictionary
        stats_list.append({
            "region": reg,
            "model_mean": mod_mean,
            "model_std": mod_std,
            "obs_mean": obs_mean,
            "obs_std": obs_std,
            "bias": bias,
            "perc_bias": perc_bias,
            "correlation": corr,
            "NSE": nse,
            "RMSD": rmsd,
            "cRMSD": crmsd,
            "N" : regdatacount[reg]  # Assuming reg starts from 1 and regdatacount is ordered by region ID
        })

    reg=-1

    dfloc = dflt

    # Compute statistics
    mod_mean = dfloc['mod'].mean()
    mod_std = dfloc['mod'].std()
    obs_mean = dfloc[var].mean()
    obs_std = dfloc[var].std()
    bias = mod_mean - obs_mean
    perc_bias = (bias / obs_mean) * 100
    corr = np.corrcoef(dfloc['mod'], dfloc[var], rowvar=False)[0, 1]
    nse = (1 - (dfloc['diff'] ** 2).sum() / ((dfloc[var] - obs_mean) ** 2).sum())
    rmsd = np.sqrt((dfloc['diff'] ** 2).mean())
    crmsd = np.sqrt((((dfloc[var]-obs_mean) - (dfloc['mod']-mod_mean)) ** 2).mean())

    # Append results as a dictionary
    stats_list.append({
        "region": reg,
        "model_mean": mod_mean,
        "model_std": mod_std,
        "obs_mean": obs_mean,
        "obs_std": obs_std,
        "bias": bias,
        "perc_bias": perc_bias,
        "correlation": corr,
        "NSE": nse,
        "RMSD": rmsd,
        "cRMSD": crmsd,
        "N" : regdatacount.sum()
    })

    # Convert to DataFrame
    stats_df = pd.DataFrame(stats_list)
    # Save results
    stats_df.to_csv(datadir + "validation_metrics_%s_%s.csv" % (year,var), index=False)

    return(stats_df)

#########################################

def scatterplot(dflt,var):
    fig = plt.figure(figsize = (18,6))

    # Left panel wtih regions 
    ax= fig.add_subplot(1,3,1)
    
    dflt.plot.scatter(x=var,y='mod', c = 'reg', ax=ax, cmap=regcmap)
    ax.grid()
    
    xmin, xmax = min(dflt[var].min(), dflt['mod'].min()), max(dflt[var].max(), dflt['mod'].max()) 
    ax.set_xlim((xmin,xmax))
    ax.set_ylim((xmin,xmax))
    ax.set_ylabel('Model Values')
    ax.set_xlabel('Observed Values')
    
    ax.set_title(var)
    ax. plot([xmin,xmax], [xmin,xmax], 'r--')
    
    # Depth
    ax= fig.add_subplot(1,3,2)
    
    dflt.plot.scatter(x=var,y='mod', c = 'depth', ax=ax, cmap=cm.deep)
    ax.grid()
    
    xmin, xmax = min(dflt[var].min(), dflt['mod'].min()), max(dflt[var].max(), dflt['mod'].max()) 
    ax.set_xlim((xmin,xmax))
    ax.set_ylim((xmin,xmax))
    ax.set_ylabel('Model Values')
    ax.set_xlabel('Observed Values')
    
    ax.set_title(var)
    fig.suptitle(f'{var} - {model} - {year}')
    ax.plot([xmin,xmax], [xmin,xmax], 'r--')

    # Month
    ax= fig.add_subplot(1,3,3)

    months = list(range(1, 13))
    month_labels = ['Jan','Feb','Mar','Apr','May','Jun',
                'Jul','Aug','Sep','Oct','Nov','Dec']

    # Extract month
    dflt['month'] = pd.Categorical(
        dflt['datetime'].dt.strftime('%b'),
        categories=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'],ordered=True)
    
    dflt.plot.scatter(x=var,y='mod', c = 'month', ax=ax, cmap=cm.phase)
    ax.grid()
    
    xmin, xmax = min(dflt[var].min(), dflt['mod'].min()), max(dflt[var].max(), dflt['mod'].max()) 
    ax.set_xlim((xmin,xmax))
    ax.set_ylim((xmin,xmax))
    ax.set_ylabel('Model Values')
    ax.set_xlabel('Observed Values')
    
    ax.set_title(var)
    fig.suptitle(f'{var} - {model} - {year}')
    ax.plot([xmin,xmax], [xmin,xmax], 'r--')

    # Save the figure
    fig.savefig(datadir + 'Validation_Scatter_%s_%s.png'%(var, year))
    plt.close()

##############################
def plot_region_stat(stats_df):

    # Initialize an empty dictionary to store metric data
    metric_data = {}
    
    # Loop through each metric and store it in the dictionary
    for metric in ['bias', 'perc_bias', 'correlation', 'NSE', 'RMSD','cRMSD']:
        # Create a 2D array for each region
        metric_values = np.full_like(xreg['region_id'], np.nan, dtype=np.float32)
        
        # Fill metric values for each region
        for reg in range(nreg):
            # Get the metric value for the current region
            metric_values[xreg['region_id'] == reg] = stats_df.loc[stats_df['region'] == reg, metric]#.values
        
        # Add to the dictionary with the metric name
        metric_data[metric] = (['lat', 'lon'], metric_values)
    
    # Create the xarray Dataset
    metrics_ds = xr.Dataset(
        metric_data,
        coords={'lat': xreg.lat, 'lon': xreg.lon},
        attrs={'description': 'Validation metrics for satellite and model comparisons'}
    )
        
    metric_properties = {
        'bias': {'cmap': 'coolwarm',
                 'vmin': -np.max(np.abs(metrics_ds['bias'])).values,
                 'vmax': np.max(np.abs(metrics_ds['bias'])).values},
        'perc_bias': {'cmap': 'coolwarm',
                      'vmin': -np.max(np.abs(metrics_ds['perc_bias'])).values,
                      'vmax': np.max(np.abs(metrics_ds['perc_bias'])).values},
        'correlation': {'cmap': 'RdBu_r', 'vmin': -1, 'vmax': 1},
        'NSE': {'cmap': 'RdBu_r', 'vmin': -1, 'vmax': 1},
        'RMSD': {'cmap': 'viridis', 'vmin': 0, 'vmax': np.max(np.abs(metrics_ds['RMSD'])).values}
    }
        
    # Create a figure with 5 subplots (one for each metric)
    fig, axs = plt.subplots(2, 3, figsize=(13, 8))
    axs = axs.flatten()
    
    # Loop through each metric and plot it
    for i, metric in enumerate(['bias', 'perc_bias', 'correlation', 'NSE', 'RMSD']):
        # Retrieve colormap and limits from the dictionary
        cmap = metric_properties[metric]['cmap']
        vmin = metric_properties[metric]['vmin']
        vmax = metric_properties[metric]['vmax']
        
        # Plot each metric (use xarray's plot method with dynamic cmap and limits)
        metrics_ds[metric].plot(ax=axs[i], cmap=cmap, vmin=vmin, vmax=vmax, cbar_kwargs={'label': metric})
        
        # Set title for each subplot
        axs[i].set_title(f'{metric.capitalize()}')
    
    ax=axs[5]
    
    ax.scatter(stats_df['cRMSD']/stats_df['obs_std']*np.sign(1-stats_df['model_std']/stats_df['obs_std'] ),
                stats_df['bias']/stats_df['obs_std'], stats_df['N'], c = stats_df['region'], cmap=regcmap, alpha=0.7)
    
    for reg in range(nreg):
        dloc = stats_df[stats_df.region==reg]
        # ax.text(dloc['cRMSD'].item()/dloc['obs_std'].item()*np.sign(1-dloc['model_std'].item()/dloc['obs_std'].item()),
        #     dloc['bias'].item()/dloc['obs_std'].item(),
        #     '%s'%dloc['region'].item(), ha = 'center', va='center' )
    
    # Centering the axes and adding lines and circle
    scale=5
    ax.set_xlim([-scale,scale])  # Adjust the limits to fit your data
    ax.set_ylim([-scale,scale])
    
    # Adding vertical and horizontal lines at x=0, y=0
    ax.axhline(0, color='black',linewidth=1)
    ax.axvline(0, color='black',linewidth=1)
    
    # Adding a circle with radius 1 centered at (0, 0)
    circle = Circle((0, 0), 1, color='r', fill=False, linestyle='--')
    ax.add_patch(circle)
    
    # Set labels
    ax.set_xlabel('Normalized RMSD')
    ax.set_ylabel('Normalized Bias')
          
    # Adjust layout to make room for colorbars
    fig.tight_layout()
    
    # Save the figure
    fig.savefig(datadir + 'Validation_Metrics_%s_%s.png'%(var, year))
    plt.close()


##############################
def plot_timeseries(dflt, var):
    maxdepth = 20
    months = list(range(1, 13))
    month_labels = ['Jan','Feb','Mar','Apr','May','Jun',
                    'Jul','Aug','Sep','Oct','Nov','Dec']
    
    ncol = 1
    
    fig, axs = plt.subplots(int(np.ceil(nreg/ncol)), ncol, figsize=(10, 2*nreg), sharex=True)
    axs = axs.flatten()
    
    for reg in range(nreg):
        ax = axs[reg]
    
        dloc = dflt[(dflt['reg'] == reg) & (dflt['depth'] <= maxdepth)].copy()
    
        # Extract month
        dloc['month'] = pd.Categorical(
            dloc['datetime'].dt.strftime('%b'),
            categories=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'],ordered=True)
    
        dmed = dloc[['month','mod',var]].groupby(['month']).median()
    
        if not dloc.empty:
            # 👉 reshape to long format
            dlong = dloc.melt(
                id_vars='month',
                value_vars=[var, 'mod'],
                var_name='variable',
                value_name='value'
            )
    
            # 👉 seaborn boxplot
            sns.violinplot(
                data=dlong,
                x='month',
                y='value',
                hue='variable',
                ax=ax,
                palette={var: 'tab:blue', 'mod': 'tab:orange'},
                dodge = True
            )
    
            sns.lineplot(data=dmed, x='month', y=var, ax=ax,  color='tab:blue', marker='.')
            sns.lineplot(data=dmed, x='month', y='mod', ax=ax,  color='tab:orange', marker='.')
    
        else:
            # 👉 still create empty axis with full months
            ax.set_xticks(months)
    
        # 👉 formatting (applies to both empty & non-empty)
        ax.set_title(f'Region {reg}')
        ax.set_xticks(range(len(month_labels)))
        ax.set_xticklabels(month_labels)
    
        # minor ticks BETWEEN months
        ax.set_xticks(np.arange(0.5, 12.5, 1), minor=True)
    
        # grid on minor ticks (vertical separators)
        ax.grid(which='minor', axis='x', linestyle='-', alpha=0.3)
    
        # optional: keep horizontal grid
        ax.grid(which='major', axis='y', linestyle='--', alpha=0.5)
    
        # 👉 avoid repeating legends everywhere
        if reg != 0:
            ax.get_legend().remove() if ax.get_legend() else None
    
    ymin = np.min(dflt[var])
    ymax = np.max(dflt[var])
    for ax in axs:
        ax.set_ylim(ymin, ymax)
    
    # 👉 single legend for the whole figure
    handles, labels = axs[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc='upper right')
    
    # Adjust layout to make room for colorbars
    fig.tight_layout()
    
    # Save the figure
    fig.savefig(datadir + 'Validation_Series_%s_%s.png'%(var, year))
    plt.close()

#######################################################################
## Load Region Files

xreg = xr.load_dataset(regionfile)
nreg = (xreg.region_id.max().values+1).astype(int)
regcmap = ListedColormap(plt.cm.Spectral(np.linspace(0, 1, nreg)))

if True:
    fig = plt.figure(figsize = (15,8))
    ax= fig.add_subplot(111, projection =ccrs.PlateCarree())
    xreg.region_id.plot(cmap=regcmap)
    
    ax.gridlines()
    ax.coastlines(color='k')
    # Countries' borders
    ax.add_feature(cf.BORDERS, color = 'darkgrey')
    ax.add_feature(cf.RIVERS, color = 'darkblue')
    

## Loop on vars
for var in vars: 
    for year in years: 


        dflt = pd.read_parquet(datadir+'VALID_%s_%s_%s.parquet'%(var,year,model))
        
        # Get coordinaates
        lons  = xr.DataArray(dflt['lon'], dims="points")
        lats  = xr.DataArray(dflt['lat'], dims="points")
        times = xr.DataArray(dflt['datetime'], dims="points")
        depths = xr.DataArray(dflt['depth'], dims="points")
    
        # Get Region ID
        regs = xreg['region_id'].interp({'lon':lons, 'lat':lats})
        dflt['reg']=np.round(regs)
        
        dflt = dflt.dropna()

        regdatacount = np.zeros(nreg)
        for r in range(nreg):
            regdatacount[r] = dflt[dflt['reg'] == r].count()['lon']

        stats_df=buildstatlist(dflt)

        scatterplot(dflt, var)

        plot_region_stat(stats_df)

        plot_timeseries(dflt, var)







# Save results
# stats_df.to_csv("validation_metrics_%s_%s.csv" % (year,var), index=False)
