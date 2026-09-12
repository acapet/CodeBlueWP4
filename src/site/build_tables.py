# src/build_map.py

import pandas as pd
from pathlib import Path
import matplotlib.pyplot as plt

BASE_DIR = Path(__file__).resolve().parent.parent.parent


csvs = ['indicators', 'monthly','daily', 'daily_baltic','stations']

for cc in csvs:
    DATA_PATH = BASE_DIR / "data" / f"{cc}.csv"
    OUTPUT_PATH = BASE_DIR / "docs" / "tables" / f"{cc}_table.md"

    df = pd.read_csv(DATA_PATH)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    df.to_markdown(OUTPUT_PATH, index=False)

    print(f"{cc} table saved to {OUTPUT_PATH}")






