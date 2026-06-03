python3 ./src/site/build_station_map.py
git add docs/maps/stations_map.html

python3 ./src/site/build_station_table.py
git add docs/tables/stations_table.md


git commit -m "Update site content"
git push

mkdocs gh-deploy
