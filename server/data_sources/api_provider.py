import json
from urllib import request

import pandas as pd

from server.data_sources.base import GridDataProvider
from server.data_sources.normalization import normalize_district_dataframe


class CompanyApiGridDataProvider(GridDataProvider):
    def __init__(self, base_url: str, token: str | None = None, timeout_s: int = 15) -> None:
        self.base_url = base_url.rstrip("/") if base_url else ""
        self.token = token
        self.timeout_s = timeout_s

    @property
    def provider_name(self) -> str:
        return "company_api"

    def load_district_dataframe(self) -> pd.DataFrame:
        if not self.base_url:
            raise RuntimeError("COMPANY_API_BASE_URL is required when DATA_SOURCE_PROVIDER=company_api")

        endpoint = f"{self.base_url}/grid/historic"
        req = request.Request(endpoint, headers=self._build_headers(), method="GET")

        try:
            with request.urlopen(req, timeout=self.timeout_s) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception as error:
            raise RuntimeError(f"Failed to fetch historic data from company API: {error}") from error

        records = self._extract_records(payload)
        if not records:
            raise RuntimeError("Company API returned no district records")

        return normalize_district_dataframe(pd.DataFrame(records))

    def _build_headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _extract_records(self, payload: object) -> list[dict]:
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if isinstance(payload, dict):
            data = payload.get("data")
            if isinstance(data, list):
                return [item for item in data if isinstance(item, dict)]
        return []

