python3 ./src/site/build_station_map.py
git add docs/maps/stations_map.html

python3 ./src/site/build_station_table.py
git add docs/tables/stations_table.md

python3 ./src/site/build_indicator_table.py
git add docs/tables/indicators_table.md

python3 ./src/site/build_indicator_table.py
git add docs/tables/indicators_table.md

# # # # #

python3 ./src/site/build_validation_diagram.py
git add docs/figs/validation_diagram.png

python3 ./src/site/build_general_diagram.py
git add docs/figs/general_diagram.png

# # # # #

git commit -m "Update site content"
git push

# # # # #

mkdocs gh-deploy
