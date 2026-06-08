from graphviz import Digraph
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
OUTPUT_PATH = BASE_DIR / "docs" / "figs" / "general_diag"

g = Digraph("Validation_diagram", format="svg")
g.attr(rankdir="LR", compound="true")

with g.subgraph(name="cluster_wp4") as c:
    c.attr(label="CodeBlue WP4 Github")
    with c.subgraph(name="cluster_scripts") as c2:
        c2.attr(label="Scripts")
        c2.node("SCR_G", "Generic scripts (Python)", shape="folder")
        c2.node("SCR_S", "Model-specific namesheets (Yaml/Json)", shape="folder")
    with c.subgraph(name="cluster_lists") as c2:
        c2.attr(label="Lists")
        c2.node("list_station", "Station.csv", shape="note")
        c2.node("list_indicators", "Indicator.csv", shape="note")
        c2.node("list_others", " ... ", shape = "plaintext")

with g.subgraph(name="cluster_shared") as c:
    c.attr(label="Code Blue shared space")
    with c.subgraph(name="cluster_icesfolder") as c2:
        c2.attr(label="Formatted ICES In-situ data")
        c2.node("STRUCT", "ICES_<VAR>_<YEAR>.parquet", shape="component")
    with c.subgraph(name="cluster_CBF") as c3:
        c3.attr(label="Code Blue Files", shape="folder")
        c3.node("INDICATORS", "IND_<SCENARIO>_<YEAR>_<MODEL>.csv", shape="note")
        c3.node("MONTHLY", "MONTHLY_<SCENARIO>_<YEAR>_<MODEL>.nc", shape="cylinder")
        c3.node("DAILY", "DAILY_<SCENARIO>_<YEAR>_<MODEL>.nc", shape="cylinder")
        c3.node("VALID", "VALID_<VAR>_<YEAR>_<MODEL>.csv", shape="component")
        c3.node("STATION", "STATION_<STATION>_<SCENARIO>_<YEAR>_<MODEL>.nc", shape="cylinder")

with g.subgraph(name="cluster_partner") as c:
    c.attr(label="Code Blue partner")
    c.node("SIM", "1 year simulation", shape="cylinder")

g.node("WEB", "This webpage", shape="folder")

## Edges

g.edge("SIM", "SCR_S", lhead="cluster_scripts")
g.edge("list_station", "WEB", ltail="cluster_lists")


for n in ['INDICATORS', 'MONTHLY', 'DAILY', 'VALID', 'STATION']:
    g.edge("SCR_G", n, ltail="cluster_scripts")

g.edge("list_station", "SCR_G", lhead="cluster_scripts", ltail="cluster_lists")

g.edge("SCR_S", "SCR_G")

g.render(
    filename=OUTPUT_PATH,
    format="svg",
    cleanup=True
)

print(g.render(
    filename=str(OUTPUT_PATH),
    format="svg",
    cleanup=True
))