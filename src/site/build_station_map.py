# src/build_map.py

import pandas as pd
import folium
from pathlib import Path
import matplotlib.pyplot as plt
from shapely.geometry import Polygon, MultiPolygon
import geopandas as gpd
import geodatasets

import cartopy.io.shapereader as shpreader


BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_PATH = BASE_DIR / "data" / "stations.csv"
OUTPUT_PATH = BASE_DIR / "docs" / "maps" / "stations_map.html"

def rgb_to_hex(rgb_tuple):
    return '#%02x%02x%02x' % tuple(
        int(255 * x) for x in rgb_tuple
    )



fname = shpreader.natural_earth(
    resolution="10m",
    category="physical",
    name="land"
)
land = gpd.read_file(fname)
# land = gpd.read_file(
#     gpd.datasets.get_path("naturalearth")
# )
land_geom = land.union_all()

## Station data info
df = pd.read_csv(DATA_PATH)

types = df["type"].unique()
colors = plt.cm.tab10.colors

color_map = {
    t: rgb_to_hex(colors[i % len(colors)])
    for i, t in enumerate(types)
}

## Modal domain info
polydic = {
    'SMHI' : Polygon([(-4.15278, 48.4917), (30.18021,48.4917), (30.18021,65.89142), (15,65.89142), (5.29157,59.491524), (-4.15278, 59.491524),  (-4.15278, 55.0),(0, 51),(-4.15278, 51)]),  # SMHI
    'Marine Institute'  : Polygon([(-27.96, 42.7), (-4.39, 36.85), (12.226,54.79), (-21.25,63.58)]),
    'RBINS': Polygon([(-4, 48.5), (-4, 51), (0, 51),(-4, 57), (9, 57), (9, 48.5)]), # RBINS
    '+ATLANTIC' : Polygon([(-12.6, 34.38), (-12.6, 44.76), (-5.1, 44.76), (-5.1, 34.38)]), # ATLANTIC-CoLAB
    'IMR' : Polygon([(-30.72, 55.95), (-15.64, 63.88), (9.48,51.21), (-5.6, 40.13)]), # Marine Institute
    'IOW'      : Polygon([(8.03, 53.6), (8.03, 62.0), (15, 66.0), (30.08,66.0), (30.08, 53.6)]),# IOW 
    'IEO-CSIC' : Polygon([(-17.7, 36.76), (-17.7, 47.98), (0.29, 47.98), (0.29, 42.5), (-5, 36.76)]), # IEO-CSIC
    'NIOZ'     : Polygon([(-17.5, 46.5), (-17.5, 63), (8, 63), (13.0, 57), (13.0, 54.44), (-1.793, 46.5)]), # NIOZ
    'IFREMER'  : Polygon([(-18.05, 41.0), (-18.05, 55.0), (9.5, 55.0), (9.5, 50.0), (-5, 41.0)]), # IFREMER
}

## OSPAR & HELCOM info

gdf_OSPAR = gpd.read_file(BASE_DIR / "data" / "COMP4_assessment_areas_v8b" / "COMP4_assessment_areas_v8b.shp")
# gdf_HELCOM = gpd.read_file(BASE_DIR / "data" / "HELCOM_subbasin_with_coastal_WFD_waterbodies_or_watertypes_2022_eutro" / "HELCOM_subbasin_with_coastal_WFD_waterbodies_or_watertypes_2022_eutro.shp")

gdf_OSPAR = gdf_OSPAR.to_crs(4326)
# gdf_HELCOM = gdf_HELCOM.to_crs(4326)

# gdf_OSPAR["geometry"] = gdf_OSPAR.geometry.simplify(
#     tolerance=5000,    # meters
#     preserve_topology=True
# )

# gdf_HELCOM["geometry"] = gdf_HELCOM.geometry.simplify(
#     tolerance=5000,    # meters
#     preserve_topology=True
# )

print(gdf_OSPAR.crs)
# print(gdf_HELCOM.crs)

# Map

m = folium.Map(
    location=[df["lat"].mean(), df["lon"].mean()],
    zoom_start=6,
    tiles="OpenStreetMap"
)

## Create layers
stations_layer = folium.FeatureGroup(name="Stations", show=True)

domains_layers = []
for i,name in enumerate(polydic.keys()):
    domains_layers.append(folium.FeatureGroup(name=f"Model domain : {name}", show=True))

OSPAR_layer = folium.FeatureGroup(
    name="Regional units OSPAR",
    show=False
)

# HELCOM_layer = folium.FeatureGroup(
#     name="Regional units HELCOM",
#     show=False
# )

# Map content

## Stations
for _, r in df.iterrows():

    folium.CircleMarker(
        location=[r["lat"], r["lon"]],
        radius=5,
        color=color_map.get(r["type"], "gray"),
        fill_color=color_map.get(r["type"], "gray"),
        fill=True,
        fill_opacity=0.8,
        tooltip=f"{r['station']} ({r['type']}, {r['lat']}, {r['lon']})"
    ).add_to(stations_layer)

## Domains
domain_colors = {
    name: rgb_to_hex(colors[i % len(colors)])
    for i, name in enumerate(polydic)
}

for i, (name, poly) in enumerate(polydic.items()):

    marine_poly = poly.difference(land_geom)

    if isinstance(marine_poly, Polygon):
        geoms = [marine_poly]
    elif isinstance(marine_poly, MultiPolygon):
        geoms = marine_poly.geoms
    else:
        geoms = []

    for g in geoms:
        coords = [[lat, lon] for lon, lat in g.exterior.coords]

        folium.Polygon(
            locations=coords,
            color=domain_colors[name],
            weight=1,
            fill=True,
            fill_color=domain_colors[name],
            fill_opacity=0.12,
            tooltip=None
        ).add_to(domains_layers[i])

## Regional units

folium.GeoJson(
    gdf_OSPAR,
    style_function=lambda x: {
        "color": "black",
        "weight": 1,
        "fillOpacity": 0,
    },
).add_to(OSPAR_layer)

# folium.GeoJson(
#     gdf_HELCOM,
#     style_function=lambda x: {
#         "color": "black",
#         "weight": 1,
#         "fillOpacity": 0,
#     },
# ).add_to(HELCOM_layer)


# Adding Layer

## Add OSPAR and HELCOM layers
OSPAR_layer.add_to(m)
# HELCOM_layer.add_to(m)

## Domains layers
for layer in domains_layers:
    layer.add_to(m)

## Station layer
stations_layer.add_to(m)

folium.LayerControl(collapsed=False).add_to(m)

OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
m.save(str(OUTPUT_PATH))

print(f"Map saved to {OUTPUT_PATH}")