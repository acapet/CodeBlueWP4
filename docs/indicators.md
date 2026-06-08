# Indicators

The **Indicators files** contain annually aggregated reporting indicators computed from model outputs for predefined OSPAR and HELCOM assessment regions.

## Purposes

The main purpose of the **Indicators files** is to store HELCOM and OSPAR core indicators for comparison across models, scenarios, and years, in order to facilitate regional assessments and post-processing activities within the CodeBlue project.

The indicators are diagnostics derived from model outputs through prescribed spatial, temporal, and vertical aggregation procedures. Each indicator consists of a single value per assessment region, model, scenario, and year.

## Format

**Indicators files** are structured tabular files containing annual indicator values aggregated at the assessment-region scale.

The recommended filenames are structured as:

`IND_<MODEL>_<SCENARIO>_<YEAR>.csv`

The use of structured `.csv` files is preferred over spreadsheet formats to facilitate automated processing and management of the large number of expected files.

## Indicator definitions

The reporting indicators currently include established HELCOM and OSPAR core indicators together with several region-specific indicators. Indicator calculations follow predefined temporal and vertical aggregation protocols.

The current list includes:

--8<-- "tables/indicators_table.md"

Detailed aggregation rules, units, and indicator definitions are described in D4.1.

## Aggregation procedures

Indicators are calculated through successive aggregation steps:

1. Spatial aggregation within predefined OSPAR and HELCOM assessment regions.
2. Vertical aggregation according to the indicator-specific protocol.
3. Temporal aggregation according to the prescribed reporting period.

Depth aggregation operations should always be completed before temporal aggregation operations.

For regions where OSPAR and HELCOM assessment areas overlap (e.g. Kattegat), indicators should be reported for both regional frameworks.

## Output structure

Each file contains one annual value for each reporting indicator and assessment region.

The general structure is:

| Indicator | OSPAR Region 1 | ... | OSPAR Region N | HELCOM Region 1 | ... | HELCOM Region N |
| --------- | -------------- | --- | -------------- | --------------- | --- | --------------- |
| A1        |                |     |                |                 |     |                 |
| A2        |                |     |                |                 |     |                 |
| ...       |                |     |                |                 |     |                 |
| An        |                |     |                |                 |     |                 |

Indicator values should include the prescribed statistical summaries (e.g. mean and standard deviation) where required by the reporting protocol.

## Methodological considerations

Several HELCOM and OSPAR indicators remain under active methodological development. In particular, chlorophyll- and oxygen-based indicators may be subject to ongoing discussions regarding their exact computation procedures.

To support these activities, monthly and daily output layers are retained separately, allowing:

* Application of existing indicator computation guidelines.
* Evaluation of alternative indicator definitions.
* Comparison of methodological approaches across models and regions.

The role of CodeBlue is to document and support these methodological discussions rather than to prescribe final indicator definitions in advance.

## Example file

..TO BE COMPLETED..
