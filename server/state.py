from dataclasses import dataclass, field
from typing import Any, Dict

import joblib
import pandas as pd
from langchain_community.llms import Ollama

from server.config import Settings
from server.data_sources.factory import build_data_provider


@dataclass
class RuntimeState:
    district_df: pd.DataFrame
    model: Any
    known_districts: list[str]
    llm: Ollama
    data_provider_name: str
    future_state: Dict[str, Any] = field(default_factory=dict)



def create_runtime_state(settings: Settings) -> RuntimeState:
    if not settings.model_path:
        raise RuntimeError("GRID_MODEL_PATH is not configured")

    data_provider = build_data_provider(settings)
    district_df = data_provider.load_district_dataframe()

    model = joblib.load(settings.model_path)
    known_districts = sorted(district_df["district"].dropna().unique().tolist())

    llm = Ollama(
        model=settings.ollama_llm_model,
        base_url=settings.ollama_base_url,
        temperature=0.2,
    )

    return RuntimeState(
        district_df=district_df,
        model=model,
        known_districts=known_districts,
        llm=llm,
        data_provider_name=data_provider.provider_name,
    )
