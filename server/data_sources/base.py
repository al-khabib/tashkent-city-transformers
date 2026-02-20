from abc import ABC, abstractmethod

import pandas as pd


class GridDataProvider(ABC):
    @property
    @abstractmethod
    def provider_name(self) -> str:
        pass

    @abstractmethod
    def load_district_dataframe(self) -> pd.DataFrame:
        pass
