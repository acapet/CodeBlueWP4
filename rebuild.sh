python3 ./src/build_map.py
cp outputs/stations_map.html docs/maps/ 
git add docs/maps/stations_map.html
git commit -m "Update station map"
git push 
mkdocs gh-deploy