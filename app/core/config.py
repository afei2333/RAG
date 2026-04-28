from dataclasses import dataclass
import os
from pathlib import Path


def _load_dotenv(path: str = ".env") -> None:
    env_path = Path(path)
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def _get_int(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return int(raw_value)


def _get_float(name: str, default: float) -> float:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return float(raw_value)


def _get_env(name: str, default: str) -> str:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return value


_load_dotenv()


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "AI RAG")
    app_env: str = os.getenv("APP_ENV", "development")
    app_host: str = os.getenv("APP_HOST", "0.0.0.0")
    app_port: int = _get_int("APP_PORT", 8000)

    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./data/rag.db")
    storage_dir: Path = Path(os.getenv("STORAGE_DIR", "./data/uploads"))

    qdrant_url: str = os.getenv("QDRANT_URL", "http://localhost:6333")
    qdrant_collection: str = os.getenv("QDRANT_COLLECTION", "rag_chunks")

    embedding_backend: str = os.getenv("EMBEDDING_BACKEND", "ollama")
    llm_backend: str = os.getenv("LLM_BACKEND", "ollama")

    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    ollama_llm_model: str = os.getenv("OLLAMA_LLM_MODEL", "qwen2.5:7b")
    ollama_embedding_model: str = os.getenv(
        "OLLAMA_EMBEDDING_MODEL", "nomic-embed-text"
    )

    cloud_base_url: str = _get_env("CLOUD_BASE_URL", "https://api.openai.com/v1")
    cloud_api_key: str = _get_env("CLOUD_API_KEY", "")
    cloud_embedding_base_url: str = _get_env(
        "CLOUD_EMBEDDING_BASE_URL",
        _get_env("CLOUD_BASE_URL", "https://api.openai.com/v1"),
    )
    cloud_embedding_api_key: str = _get_env(
        "CLOUD_EMBEDDING_API_KEY",
        _get_env("CLOUD_API_KEY", ""),
    )
    cloud_embedding_model: str = _get_env(
        "CLOUD_EMBEDDING_MODEL",
        "text-embedding-3-small",
    )

    cloud_llm_base_url: str = _get_env(
        "CLOUD_LLM_BASE_URL",
        _get_env("CLOUD_BASE_URL", "https://api.openai.com/v1"),
    )
    cloud_llm_api_key: str = _get_env(
        "CLOUD_LLM_API_KEY",
        _get_env("CLOUD_API_KEY", ""),
    )
    cloud_llm_model: str = _get_env(
        "CLOUD_LLM_MODEL",
        "gpt-4.1-mini",
    )

    default_top_k: int = _get_int("DEFAULT_TOP_K", 5)
    default_score_threshold: float = _get_float("DEFAULT_SCORE_THRESHOLD", 0.2)
    max_context_chunks: int = _get_int("MAX_CONTEXT_CHUNKS", 8)
    chunk_size: int = _get_int("CHUNK_SIZE", 1000)
    chunk_overlap: int = _get_int("CHUNK_OVERLAP", 150)
    min_chunk_chars: int = _get_int("MIN_CHUNK_CHARS", 120)
    context_window_chunks: int = _get_int("CONTEXT_WINDOW_CHUNKS", 1)
    pdf_parser: str = os.getenv("PDF_PARSER", "docling")
    pdf_fallback_parser: str = os.getenv("PDF_FALLBACK_PARSER", "pypdf")


settings = Settings()
