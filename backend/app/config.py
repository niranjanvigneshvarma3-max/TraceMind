from dataclasses import dataclass
import os
from pathlib import Path
from urllib.parse import quote

from dotenv import load_dotenv


load_dotenv(Path(__file__).resolve().parents[2] / ".env")


@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv("DATABASE_URL") or (
        "postgresql://tracemind:"
        + quote(os.getenv("POSTGRES_PASSWORD", "tracemind"), safe="")
        + "@localhost:5433/tracemind"
    )
    upload_dir: Path = Path(os.getenv("UPLOAD_DIR", "uploads")).resolve()
    demo_code: str = os.getenv("APP_DEMO_CODE") or os.getenv("DEMO_CODE", "")
    admin_code: str = os.getenv("APP_ADMIN_CODE") or os.getenv("ADMIN_CODE", "")
    ollama_url: str = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
    ollama_model: str = os.getenv("OLLAMA_MODEL", "qwen3:1.7b")
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "all-minilm")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


settings = Settings()
