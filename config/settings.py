from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    deepseek_api_key: str
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    default_model: str = "deepseek-chat"

    tavily_api_key: str | None = None

    workspace_root: Path = Path("./workspace_sandbox").resolve()
    chroma_path: Path = Path("./chroma_data").resolve()

    max_retries: int = 3
    hard_max_retries: int = 8
    min_accept_score: float = 7.0
    max_dev_loops_per_cycle: int = 4
    require_human_approval: bool = False


settings = Settings()