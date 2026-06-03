# Stations

The **Stations files** consists of vertical profiles at fixed positions. 

## Purposes

**Stations files** addresses two main purposes:

1. Enable time series comparison with established monitoring stations from the OSPAR and HELCOM monitoring networks.  
2. Provide boundary conditions for local studies (WP6).

Whereas the two objectives are clearly distinct, they are treated jointly because they share the same data format.

## Format

**Stations files** are netcdf files with dimensions *time* and *depth*. 

The filenames are structured as \<STATION\>\_\<SCENARIO\>\_\<YEAR\>\_\<MODEL\>.nc.

## Variables

At this stage, a common list of variables has not been defined. Also, since storage shouldn't be an issue for these files, the files should inlcude all model output variables saved during the simulations, at native time resolution. 

## Station list

The files are processed automatically based on a central list of stations. The station list is contained in a .csv file in the github repository, and generated automatically from the file named 'Monitoring_Stations_Merged.xls' on the CodeBlue shared drive (WP4 folder).

For information purposes an interactive map can be found here:

[Station Map](maps/stations_map.html)

If spotting an error, please report the requested correction on the shared file directly, in the sheet named *correction log sheet*.

## Example file

Here's the structure of the example file W04_H1_2010_RBINS.nc

..TO BE COMPLETED.. 


