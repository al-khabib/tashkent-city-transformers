from typing import Iterable

import pandas as pd

REQUIRED_COLUMNS = [
    "district",
    "snapshot_date",
    "district_rating",
    "population_density",
    "avg_temp",
    "asset_age",
    "commercial_infra_count",
    "current_capacity_mw",
    "actual_peak_load_mw",
]



def normalize_district_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    missing = [column for column in REQUIRED_COLUMNS if column not in df.columns]
    if missing:
        raise RuntimeError(f"Grid data is missing required columns: {', '.join(missing)}")

    normalized = df.copy()
    normalized["district"] = normalized["district"].astype(str).str.strip().str.lower()
    normalized["snapshot_date"] = normalized["snapshot_date"].astype(str)
    return normalized
