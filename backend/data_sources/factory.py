from backend.config import Settings
from backend.data_sources.api_provider import CompanyApiGridDataProvider
from backend.data_sources.base import GridDataProvider
from backend.data_sources.csv_provider import CsvGridDataProvider



def build_data_provider(settings: Settings) -> GridDataProvider:
    if settings.data_source_provider == "csv":
        return CsvGridDataProvider(csv_path=settings.csv_path)

    if settings.data_source_provider == "company_api":
        return CompanyApiGridDataProvider(
            base_url=settings.company_api_base_url,
            token=settings.company_api_token,
            timeout_s=settings.company_api_timeout_s,
        )

    raise RuntimeError(
        "Unsupported DATA_SOURCE_PROVIDER. Use 'csv' or 'company_api'. "
        f"Received: {settings.data_source_provider}"
    )
