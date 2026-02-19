import os
from dataclasses import dataclass
from dotenv import load_dotenv


def _resolve_base_dir() -> str:
    return os.path.dirname(os.path.dirname(__file__))


def _resolve_path(base_dir: str, filename: str) -> str:
    return os.path.join(base_dir, filename)


def load_environment(base_dir: str) -> None:
    candidates = [
        os.path.join(base_dir, ".env"),
        os.path.join(base_dir, "server", ".env"),
    ]
    for env_path in candidates:
        if os.path.exists(env_path):
            load_dotenv(dotenv_path=env_path)


@dataclass(frozen=True)
class Settings:
    base_dir: str
    csv_path: str
    model_path: str
    data_source_provider: str
    company_api_base_url: str
    company_api_token: str
    company_api_timeout_s: int
    ollama_base_url: str
    ollama_llm_model: str
    allowed_origins: list[str]



def get_settings() -> Settings:
    base_dir = _resolve_base_dir()
    load_environment(base_dir)

    csv_path = _resolve_path(base_dir, os.getenv("GRID_DATA_CSV", "tashkent_grid_historic_data.csv"))
    model_path = _resolve_path(base_dir, os.getenv("GRID_MODEL_PATH", "grid_load_rf.joblib"))

    allowed_origins = [
        origin.strip()
        for origin in os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
        if origin.strip()
    ]

    return Settings(
        base_dir=base_dir,
        csv_path=csv_path,
        model_path=model_path,
        data_source_provider=os.getenv("DATA_SOURCE_PROVIDER", "csv").strip().lower(),
        company_api_base_url=os.getenv("COMPANY_API_BASE_URL", "").strip(),
        company_api_token=os.getenv("COMPANY_API_TOKEN", "").strip(),
        company_api_timeout_s=int(os.getenv("COMPANY_API_TIMEOUT_S", "15")),
        ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        ollama_llm_model=os.getenv("OLLAMA_LLM_MODEL", "llama3.1:8b"),
        allowed_origins=allowed_origins,
    )
