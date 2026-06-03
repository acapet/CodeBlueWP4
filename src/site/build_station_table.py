# src/build_map.py

import pandas as pd
from pathlib import Path
import matplotlib.pyplot as plt

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_PATH = BASE_DIR / "data" / "stations.csv"
OUTPUT_PATH = BASE_DIR / "docs" / "tables" / "stations_table.md"

df = pd.read_csv(DATA_PATH)

OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

df.to_markdown(OUTPUT_PATH, index=False)


print(f"Station table saved to {OUTPUT_PATH}")