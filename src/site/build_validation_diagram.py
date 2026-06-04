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
        c2.attr(label="scr/validation/", shape="folder")
        c2.node("PARQUET", "ICES_to_parquet.py")
        c2.node("EXTRACT", "ICES_extract.py")

with g.subgraph(name="cluster_shared") as c:
    c.attr(label="Code Blue shared space")
    c.node("STRUCT", "ICES_<VAR>_<YEAR>.parquet")
    c.node("CSV", "<VAR>_<YEAR>_<MODEL>.csv")

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
