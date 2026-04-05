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

    # Multi-agent panel after planner (parallel openings + parallel replies + moderator).
    team_panel_enabled: bool = True
    # True: Microsoft AutoGen AgentChat round-robin (agents see full thread). False: LangChain parallel+fallback.
    team_use_autogen: bool = True
    # Safety cap on AutoGen team messages (user + N agent turns).
    team_autogen_max_messages: int = 28

    # Keyword + tree based workspace context (no vector DB / embeddings).
    vectorless_rag_enabled: bool = True
    vectorless_rag_max_chars: int = 22000
    vectorless_rag_max_files_scanned: int = 4000
    vectorless_rag_top_files: int = 22


settings = Settings()