import os

import pandas as pd

from backend.data_sources.base import GridDataProvider
from backend.data_sources.normalization import normalize_district_dataframe


class CsvGridDataProvider(GridDataProvider):
    def __init__(self, csv_path: str) -> None:
        self.csv_path = csv_path

    @property
    def provider_name(self) -> str:
        return "csv"

    def load_district_dataframe(self) -> pd.DataFrame:
        if not self.csv_path:
            raise RuntimeError("GRID_DATA_CSV is not configured")
        if not os.path.exists(self.csv_path):
            raise RuntimeError(f"District stats CSV not found at: {self.csv_path}")

        district_df = pd.read_csv(self.csv_path)
        return normalize_district_dataframe(district_df)
