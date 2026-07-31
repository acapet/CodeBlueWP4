# 2D Daily Layers

The **2D Daily Layers** files contain daily aggregated fields intended to support the development and evaluation of indicators requiring high temporal resolution.

## Purposes

**Daily Layers** address three main purposes:

1. Support indicators requiring flexible temporal aggregation periods.
2. Enable the calculation of indicators based on threshold exceedances, event duration, or bloom phenology.
3. Provide the temporal resolution necessary to investigate ecosystem dynamics that cannot be adequately captured by monthly averages.

Compared with the monthly layers, daily outputs retain a finer temporal resolution while maintaining full spatial resolution. Due to the associated storage requirements, daily outputs are restricted to a limited set of variables.

## Format

**Daily Layers** are NetCDF files containing daily mean values at native model horizontal resolution.

The native horizontal grid of each model is retained. To ensure interoperability between modelling systems, all files should follow common CF conventions and metadata standards.

The filenames are structured as:

`DAILY_<SCENARIO>_<YEAR>_<MODEL>.nc`

## Variables

The daily output files contain the following variables:

| ID | Variable | Unit |
|------|------|------|
| D1 | Chlorophyll (optical depth average) | mg Chl/m³ |
| D2 | Chlorophyll (water-column integrated) | mg Chl/m² |
| D3 | DIN | mol/m³ |
| D4 | DIP | mol/m³ |
| D5 | Silicate | mol/m³ |
| D6* | Cyanobacteria | mg Chl/m³ |
| D7* | Oxygen (3D field) | mmol O₂/m³ |
| D8* | Temperature (3D field) | °C |
| D9* | Salinity (3D field) | psu |
| D10* | Hydrogen sulphide (H₂S) | mmol/m³ |
| D11* | Ammonium (NH₄) | mmol/m³ |
| D12* | Sea surface height | m |
| D13 | Near-bottom oxygen | mmol O₂/m³ |
| D14 | Near-bottom temperature | °C |
| D15 | Near-bottom salinity | psu |
| D16 | Mixed layer depth | m |
| D17 | Surface temperature | °C |
| D18 | Bottom temperature | °C |

Variables marked with an asterisk (*) are only requested from models extending over the Baltic Sea. These variables constitute an exception to the general requirement of vertically aggregated outputs and may include full three-dimensional fields.

## Aggregation procedures

Most daily variables are reported as vertically aggregated two-dimensional fields.

Typical aggregation methods include:

- Mean concentration within the optical depth.
- Mean concentration within the lower 10 m above the seabed.
- Vertical integration over the full water column.

Daily values correspond to daily means computed from the native model output frequency.

## Baltic Sea specific variables

The Baltic Sea presents specific ecological and biogeochemical characteristics that require dedicated outputs.

For this reason, variables D6–D12 are only requested from models extending over the Baltic Sea. These variables support the development and assessment of Baltic Sea specific indicators, particularly those related to cyanobacterial blooms, deep-water oxygen depletion, and hypoxia.

## Mixed Layer Depth

Mixed Layer Depth (MLD) follows the same definition as adopted for the monthly layer products.

## Output structure

Each file contains daily fields for all requested variables on the native model grid.

Variables should be stored using CF-compliant metadata and naming conventions to facilitate automated processing and intercomparison across modelling systems.

## Example file

..TO BE COMPLETED..