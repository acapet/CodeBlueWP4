# Monthly Layers

The **Monthly Layers** files contain monthly aggregated two-dimensional fields derived from model outputs at native horizontal resolution.

## Purposes

**Monthly Layers** address three main purposes:

1. Support the scientific analyses and research questions of the CodeBlue project.
2. Provide the information required to develop and evaluate candidate HELCOM and OSPAR indicators.
3. Enable the reconstruction of harmonized pan-European data layers across all participating modelling systems.

Compared with the annual indicators, monthly layers retain a lower level of aggregation and preserve the full horizontal resolution of each model. This allows detailed analyses while maintaining manageable storage requirements.

## Format

**Monthly Layers** are NetCDF files containing monthly mean values of vertically aggregated variables.

The native horizontal grid of each model is retained. To ensure interoperability between modelling systems, all files should follow common CF conventions and metadata standards.

Recommended filenames are structured as:

`MONTHLY_<SCENARIO>_<YEAR>_<MODEL>.nc`

## Variables

The monthly output files contain a predefined set of two-dimensional variables obtained through vertical averaging or integration procedures.

The current list includes:

| ID     | Variable                                         |
| ------ | ------------------------------------------------ |
| M1     | Surface salinity                                 |
| M2     | Average salinity                                 |
| M3     | Bottom salinity                                  |
| M4     | Surface temperature                              |
| M5     | Average temperature                              |
| M6     | Bottom temperature                               |
| M7     | Potential energy anomaly – thermal component     |
| M8     | Potential energy anomaly – haline component      |
| M9     | Mixed layer depth                                |
| M10    | Surface DIN                                      |
| M11    | Surface DIP                                      |
| M12    | Surface Si                                       |
| M13    | Total N                                          |
| M14    | Total P                                          |
| M15    | Chlorophyll                                      |
| M16    | Total phytoplankton biomass                      |
| M16a–n | Individual phytoplankton functional type biomass |
| M17    | Total zooplankton biomass                        |
| M18    | Pelagic detrital organic carbon                  |
| M19    | Dissolved inorganic carbon (DIC)                 |
| M20    | Benthic detrital organic carbon                  |
| M21    | Net primary production                           |
| M22    | Benthic carbon fluxes (particulate)              |
| M23    | Benthic carbon fluxes (dissolved)                |
| M24    | Atmospheric carbon fluxes                        |
| M25    | Near-bottom oxygen                               |
| M26    | Benthic oxygen fluxes                            |
| M27    | Atmospheric oxygen fluxes                        |
| M28    | Secchi depth                                     |
| M29    | Suspended particulate matter                     |
| M30    | Surface pH                                       |
| M31    | Surface DIC                                      |
| M32    | Surface alkalinity                               |
| M33    | Bottom pH                                        |
| M34    | Bottom DIC                                       |
| M35    | Bottom alkalinity                                |

The complete list of variables, units, and aggregation procedures is maintained in the CodeBlue reporting specifications.

## Aggregation procedures

All variables are reported as monthly means after applying the prescribed vertical aggregation.

Typical vertical aggregation methods include:

* Mean concentration within the upper 10 m.
* Mean concentration within the lower 10 m above the seabed.
* Mean concentration over the entire water column.
* Vertical integration over the entire water column.

Monthly averaging is applied after the vertical aggregation step.

## Vertical integration

Differences in vertical discretization between models can complicate the calculation of vertically integrated quantities.

To ensure consistency across modelling systems, the recommended procedure is:

1. Interpolate model outputs from the native vertical grid onto a regular 1 m vertical grid using linear interpolation.
2. Apply the required vertical averaging or integration on the interpolated profiles.
3. Compute the monthly mean from the resulting daily or instantaneous values.

## Specific diagnostics

### Potential energy anomaly

Potential Energy Anomaly (PEA, $\Phi$) is used as a measure of water column stratification.

Following Holt et al. (2005), PEA is defined such that:

$$
\Phi = - \frac{g}{H} \int\limits_{z=-H}^{0} z\cdot (\rho(T,S) - \rho(\overbar{T},\overbar{S}))
$$

, where : 

* $g$ is gravitional accelaration, 
* $H$ is the water depth, 
* $\rho(T,S)$ is the seawater density deriving from [TEOS-10](https://www.teos-10.org/) standard formulaes.
* $\overbar{T}$ represents the depth-averaged temperature.

$\Phi$ is defined such that it is positive under stably stratified conditions and approach zero under vertically mixed conditions.

Both thermal and haline components should be reported separately:

$$
\Phi_T = - \frac{g}{H} \int\limits_{z=-H}^{0} z\cdot (\rho(T,\overbar{S}) - \rho(\overbar{T},\overbar{S}))
$$

$$
\Phi_S = \Phi - \Phi_T
$$





### Mixed layer depth

Mixed Layer Depth (MLD) follows the density-based definition commonly used in NEMO.

The mixed layer depth is defined as the shallowest depth at which the density difference relative to a reference depth exceeds a specified threshold.

The recommended parameters are:

* $z_{ref}$ : Reference depth: 3 m
* $\Delta \rho_{ref}$ : Density difference threshold, 0.03 kg m⁻³

This corresponds to the depth where:

$$
z_{MLD} = min(z) | \rho(z)- \rho(z_{ref}) > \Delta \rho_{ref}
$$

### Secchi depth

Secchi depth is derived from the photosynthetically active radiation (PAR) attenuation coefficient.

The recommended definition is:

$$
 z_{secchi} = \frac{1}{K_d}
$$

where:

* $z_{secchi}$ is the Secchi depth.
* $K_d$ is the PAR attenuation coefficient.

## Output structure

Each file contains monthly fields for all requested variables on the native horizontal grid of the model.

The files should include all metadata necessary to ensure compliance with CF conventions and facilitate automated processing by downstream workflows.

## Example file

..TO BE COMPLETED..
