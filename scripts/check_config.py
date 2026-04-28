from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from app.core.config import settings


def mask(value: str) -> str:
    if not value:
        return "<empty>"
    if value == "replace_me":
        return "replace_me"
    if len(value) <= 8:
        return "***"
    return f"{value[:4]}...{value[-4:]}"


def main() -> None:
    print("AI RAG configuration")
    print(f"EMBEDDING_BACKEND={settings.embedding_backend}")
    print(f"LLM_BACKEND={settings.llm_backend}")
    print()
    print("Effective selection")
    embedding_url = (
        settings.ollama_base_url
        if settings.embedding_backend == "ollama"
        else settings.cloud_embedding_base_url
    )
    embedding_model = (
        settings.ollama_embedding_model
        if settings.embedding_backend == "ollama"
        else settings.cloud_embedding_model
    )
    llm_url = (
        settings.ollama_base_url
        if settings.llm_backend == "ollama"
        else settings.cloud_llm_base_url
    )
    llm_model = (
        settings.ollama_llm_model
        if settings.llm_backend == "ollama"
        else settings.cloud_llm_model
    )
    print(f"  embedding_url={embedding_url}")
    print(f"  embedding_model={embedding_model}")
    print(f"  llm_url={llm_url}")
    print(f"  llm_model={llm_model}")
    print()
    print("Ollama")
    print(f"  base_url={settings.ollama_base_url}")
    print(f"  llm_model={settings.ollama_llm_model}")
    print(f"  embedding_model={settings.ollama_embedding_model}")
    print()
    print("Cloud")
    print(f"  shared_base_url={settings.cloud_base_url}")
    print(f"  shared_api_key={mask(settings.cloud_api_key)}")
    print(f"  embedding_base_url={settings.cloud_embedding_base_url}")
    print(f"  embedding_model={settings.cloud_embedding_model}")
    print(f"  embedding_api_key={mask(settings.cloud_embedding_api_key)}")
    print(f"  llm_base_url={settings.cloud_llm_base_url}")
    print(f"  llm_model={settings.cloud_llm_model}")
    print(f"  llm_api_key={mask(settings.cloud_llm_api_key)}")

    if settings.embedding_backend == "cloud" and settings.cloud_embedding_api_key in {"", "replace_me"}:
        print()
        print("WARNING: CLOUD_EMBEDDING_API_KEY or CLOUD_API_KEY is not configured.")
    if settings.llm_backend == "cloud" and settings.cloud_llm_api_key in {"", "replace_me"}:
        print()
        print("WARNING: CLOUD_LLM_API_KEY or CLOUD_API_KEY is not configured.")


if __name__ == "__main__":
    main()
