from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ROOT_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    openai_api_key: str
    openai_base_url: str = "https://apinebula.ai/v1"
    model_name: str = "gpt-5.6-terra"
    context_window: int = 10000
    compress_remaining_ratio: float = 0.2
    keep_recent_messages: int = 2
    budget_max_rounds: int = 3
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174,http://127.0.0.1:5174,http://localhost:5175,http://127.0.0.1:5175"
    data_dir: Path = ROOT_DIR / "data"

    @property
    def compress_threshold(self) -> int:
        """已用 token 达到该值（窗口的 80%）即视为剩余不足 20%，需要压缩。"""
        return int(self.context_window * (1 - self.compress_remaining_ratio))

    @property
    def remaining_budget(self) -> int:
        return self.context_window - self.compress_threshold

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @property
    def checkpoint_path(self) -> Path:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        return self.data_dir / "checkpoints.db"

    @property
    def sessions_db_path(self) -> Path:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        return self.data_dir / "sessions.db"


settings = Settings()
