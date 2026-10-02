 ## Running the validation notebook

  Run this workflow only after run_validation.sbatch or Extract_validation_tables.py has completed successfully.

  1. Confirm that validation extraction completed.

     The output directory should contain nine VALID Parquet files:

     <repository-root>/validations/Test/output/

     Expected variables:

     oxy, nox, nh4, po4, sio, chl, temp, sal, talk

     The filenames should follow:

     VALID_<variable>_<year>_<model>.parquet

  2. Supply the regional NetCDF file.

     Place:

     Bathymetry_NoS_with_regions_AC.nc

     at:

     <repository-root>/validations/Test/input_data/regions/Bathymetry_NoS_with_regions_AC.nc

     This NetCDF file is not stored in Git and must be copied separately.

  3. Start Jupyter using your CodeBlue Python environment.

     Use the same environment used to run the validation extraction:

     /absolute/path/to/codeblue/bin/python -m jupyter lab

     The environment must include the packages listed in:

     <repository-root>/environment.yml

  4. Open the validation notebook.

     <repository-root>/validations/Test/config/ORAS5_update/notebooks/Postproc_validation_tables_original_output.ipynb

  5. Restart the kernel before beginning.

     Run the import and setup cells at the beginning of the notebook.

  6. Configure Manager Cell 1.

     Set the absolute validation setup path:

     setup_root = Path(
         "/absolute/path/to/CodeBlueWP4/validations/Test"
     )

     Then set the variable, year, and model:

     var = "oxy"
     year = 2014
     model = "test"

     The model value must exactly match the model identifier used in the Parquet filenames:

     VALID_<variable>_<year>_<model>.parquet

  7. Configure the regional-workflow options.

     refresh_region_ids = True
     maxdepth = 20
     save_original_outputs = True
     overwrite_original_outputs = False

     *Keep overwriting disabled unless you deliberately want to replace previously generated products.

  8. Run the Manager Cell 1 workflow for every variable.

     Run the complete first workflow—Cells 1–15 in the current notebook—for each of the following variables:

     variables = [
         "oxy", "nox", "nh4", "po4", "sio",
         "chl", "temp", "sal", "talk"
     ]

     Start with:

     var = "oxy"

     Run the complete regional-workflow section. Then change only var:

     var = "nox"

     Rerun the regional-workflow cells. Repeat this process for all nine variables.

     Do not restart the kernel between variables. Confirm that the expected regional products are created before
     continuing to Manager Cell 2.

  9. Configure Manager Cell 2.

     After completing the first workflow for all nine variables, configure the Tier 1 review:

     review_mode = "create_new"
     overwrite_review_outputs = False

     Confirm that year and model match Manager Cell 1:

     year = 2014
     model = "test"

     Confirm that all nine variables are included:

     variables = [
         "oxy", "nox", "nh4", "po4", "sio",
         "chl", "temp", "sal", "talk"
     ]

  10. Run the Manager Cell 2 workflow once.

     Run Manager Cell 2 and every cell below it.

     Manager Cell 2 loops through all nine variables automatically. It does not need to be run separately for each
     variable.

  11. Check the regional outputs.

     The Manager Cell 1 workflow produces files such as:

     validation_metrics_<year>_<variable>.csv
     Validation_Metrics_Maps_xarray_<variable>_<year>.png
     Validation_Metrics_Target_<variable>_<year>.png

     Confirm that these products were created for all nine variables.

  12. Check the review outputs.

     Manager Cell 2 writes its products under:

     <repository-root>/validations/Test/review/

     Important products include:

     tier1_input_checksums.csv
     tier1_all_variables_depth_metrics.csv
     tier1_depth_bias_all_variables.png
     tier1_depth_rmsd_all_variables.png
     tier1_review_flags.csv

     Each variable also receives its own directory containing:
      - depth-bin metrics;
      - finite observation/model pairs;
      - point-level diagnostics;
      - geographic residual maps.
