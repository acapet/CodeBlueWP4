# Stations

The **Stations files** consists of vertical profiles at fixed positions. 

## Purposes

**Stations files** addresses two main purposes:

1. Enable time series comparison with established monitoring stations from the OSPAR and HELCOM monitoring networks.  
2. Provide boundary conditions for local studies (WP6).

Whereas the two objectives are clearly distinct, they are treated jointly because they share the same data format.

## Format

**Stations files** are netcdf files with dimensions *time* and *depth*. 

The filenames are structured as `STATION_<STATION>_<SCENARIO>_<YEAR>_<MODEL>.nc`.

## Variables

At this stage, a common list includes the following variables:

| Variable     | Unit       | Data Unit | VAR |
| ------------ | ---------- | --------- | --- |
| Oxygen       | mmol.O₂/m³ | ml/l      | oxy |
| NOx          | mmol.N/m³  | µmol/l    | nox |
| NH₄          | mmol.N/m³  | µmol/l    | nh4 |
| PO₄          | mmol.P/m³  | µmol/l    | po4 |
| SiO          | mmol.Si/m³ | µmol/l    | sio |
| Chlorophyll  | mg Chl/m³  | µg/l      | chl |
| Temperature  | °C         | °C        | temp|
| Salinity     | psu        | psu       | sal |
| Secchi depth | m          | m ?       | secchi|
| pH           |total scale | -         | ph|
| Total Alkalinity | mol/m³ | mEq/l     | talk|
| DIC          | mmol.C/m³  |mmol.C/m³ ?| dic|

Also, since storage shouldn't be an issue for these files, the files should inlcude all model output variables saved during the simulations, at native time resolution. 

## Stations

The files are processed automatically based on a central list of stations. The station list is contained in a .csv file in the Github repository, and generated automatically from the file named 'CodeBlue_Stations_Merged.xls' on the CodeBlue GoogleDrive (WP4 folder).    

**/!\ If spotting an error, please report the requested correction on the shared file directly, in the sheet named *correction log sheet* and please inform WP4, as updates are not synchronised automatically between Drive and GitHub.**  

### Station map

For information purposes an interactive map can be found here: [Station Map](maps/stations_map.html)

### Station list

--8<-- "tables/stations_table.md"

**/!\ The last station of the list (Archipelago_Cornerb4) seems to be on land.**

## Workflow and scripts

Related scripts are located in `./scr/stations/`  

The suggested workflow is as follows:  
- ...To be completed...  
- ...

## Additional validation

In addition, ICES data (previously converted into .parquet files for the entire Codeblue area and covering the period 1960–2025; see [Validation tables](../validation_tables)) were extracted for each station for the following variables: 'oxy', “nox”, “nh4”, “po4”, “sio”, “chl”, “temp”, “sal”, “spm”, “ph”, “talk”. (using script `ICES_station_extraction.ipynb`).  

New parquet files have been created (one file per station) containing all available data for each station (and the surrounding 5 km area _(to be discussed)_): the parquet files (+ station_summary.csv) are available for download in the Drive folder: `WP4/ICESData_for_stations`.

## Example file

Exemple of a station file (model: coherens, year: 2010, station: W04, scenario: H1) is available: `./scr/stations/W04_H1_2010_RBINS.nc`   
..TO BE COMPLETED.. 


