from graphviz import Digraph
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
OUTPUT_PATH = BASE_DIR / "docs" / "figs" / "validation_diag"

g = Digraph("Validation_diagram", format="svg")
g.attr(rankdir="LR")

with g.subgraph(name="cluster_ices") as c:
    c.attr(label="ICES database")
    c.node("ICES", "ICES InSitu", shape="cylinder")

with g.subgraph(name="cluster_wp4") as c:
    c.attr(label="CodeBlue WP4 Github")
    with c.subgraph(name="cluster_scripts") as c2:
        c2.attr(label="scr/validation/")
        c2.node("PARQUET", "ICES_to_parquet.py")
        c2.node("EXTRACT", "ICES_extract.py")

with g.subgraph(name="cluster_shared") as c:
    c.attr(label="Code Blue shared space")
    with c.subgraph(name="cluster_icesfolder") as c2:
        c2.attr(label="Formatted ICES In-situ data")
        c2.node("STRUCT", "ICES_<VAR>_<YEAR>.parquet", shape="cylinder")
    with c.subgraph(name="cluster_CBF") as c3:
        c3.attr(label="Code Blue Files", shape="folder")
        c3.node("CSV", "VALID_<VAR>_<YEAR>_<MODEL>.csv", shape="cylinder")

with g.subgraph(name="cluster_partner") as c:
    c.attr(label="Code Blue partner")
    c.node("SIM", "1 year simulation", shape="cylinder")

g.edges([
    ("ICES", "PARQUET"),
    ("PARQUET", "STRUCT"),
    ("STRUCT", "EXTRACT"),
    ("SIM", "EXTRACT"),
    ("EXTRACT", "CSV")
])

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