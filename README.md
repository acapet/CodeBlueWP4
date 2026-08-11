# CodeBlueWP4

Tools and workflows developped in the framework of Work Package 4 (WP4: Policy-oriented synthesis) of the CodeBlue project (project info : [CodeBlue](https://www.smhi.se/codeblue)).
This colaborative repository is intended for modellers who run simulations and conduct postprocessing.

## Overview

This repository contains scripts and examples used to produce the **CodeBlue files** as well as the files required to create and maintain the related webpage: `https://acapet.github.io/CodeBlueWP4/`.   

Where to find what?  
* Postprocessing scripts --> [GitHub repository](https://github.com/acapet/CodeBlueWP4/tree/main)  
* Needed data --> [Google Drive CodeBlue/WP4](https://drive.google.com/drive/folders/1Jal64dDYsOwVKbPaytRpogjmDrIzorxy)  
* Documentation, tables and visualisation --> [GitHub webpage](https://acapet.github.io/CodeBlueWP4/)  

/!\ **Disclaimer**: these are **suggested** workflows and postprocessing scripts. Their use is not mandatory. You are free to use other scripts as long as the final files comply with the required format, variables, units, etc.

## Repository structure

* `data/`, `docs/`, `outputs/`, `site`, `scr/site/`, `rebuild.sh` contain the files used to build and update the content displayed on the webpage. **Please do not modify these files, as they are maintained by the WP4 team.**
  
* `scr/`: contains the commun postprocessing scripts, needed files and output example for all Codeblue files.
* `scr/daily2D`: postprocessing scripts to produce **2D Daily Data Layers**.
* `scr/daily3D`: postprocessing scripts to produce **3D Daily Data Layers** (only for Baltic models).
* `scr/monthly`: postprocessing scripts to produce **2D Monthly Data Layers**.
* `scr/indicators`: postprocessing scripts to produce **Annual Indicator Tables**.
* `scr/validation`: postprocessing scripts to produce **Validation Tables**.
* `scr/stations`: postprocessing scripts to produce **Station Files**.

## Required modules

See `requirements.txt`.

## Environment setup

Create your environment via:  
_module load conda_  
_conda env create -f `environment.yml`_