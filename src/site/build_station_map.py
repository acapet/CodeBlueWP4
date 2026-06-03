# src/build_map.py

import pandas as pd
import folium
from pathlib import Path
import matplotlib.pyplot as plt

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_PATH = BASE_DIR / "data" / "stations.csv"
OUTPUT_PATH = BASE_DIR / "docs" / "maps" / "stations_map.html"

def rgb_to_hex(rgb_tuple):
    return '#%02x%02x%02x' % tuple(
        int(255 * x) for x in rgb_tuple
    )

df = pd.read_csv(DATA_PATH)

types = df["type"].unique()
colors = plt.cm.tab10.colors

color_map = {
    t: rgb_to_hex(colors[i % len(colors)])
    for i, t in enumerate(types)
}

m = folium.Map(
    location=[df["lat"].mean(), df["lon"].mean()],
    zoom_start=6,
    tiles="OpenStreetMap"
)

for _, r in df.iterrows():

    folium.CircleMarker(
        location=[r["lat"], r["lon"]],
        radius=5,
        color=color_map.get(r["type"], "gray"),
        fill_color=color_map.get(r["type"], "gray"),
        fill=True,
        fill_opacity=0.8,
        tooltip=f"{r['station']} ({r['type']}, {r['lat']}, {r['lon']})"
    ).add_to(m)

OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
m.save(str(OUTPUT_PATH))

print(f"Map saved to {OUTPUT_PATH}")