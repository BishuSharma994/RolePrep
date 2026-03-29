import os
from pathlib import Path

from dotenv import dotenv_values, load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"
ENV_CANDIDATES = (ROOT_DIR / ".env", BACKEND_DIR / ".env")


def load_environment() -> list[str]:
    loaded_files: list[str] = []
    for env_path in ENV_CANDIDATES:
        if env_path.exists():
            load_dotenv(dotenv_path=env_path, override=False)
            loaded_files.append(str(env_path))
    return loaded_files


def merged_env_values() -> dict[str, str]:
    merged: dict[str, str] = {}
    for env_path in ENV_CANDIDATES:
        if env_path.exists():
            values = dotenv_values(env_path)
            merged.update({key: value for key, value in values.items() if value is not None})
    return merged


def env_search_paths() -> str:
    return ", ".join(str(path) for path in ENV_CANDIDATES)


def get_env_value(key: str, fallback: dict[str, str] | None = None) -> str | None:
    value = os.getenv(key)
    if isinstance(value, str):
        cleaned = value.strip()
        if cleaned:
            return cleaned

    if fallback:
        for config_key, config_value in fallback.items():
            if config_key.strip().upper() == key and isinstance(config_value, str):
                cleaned = config_value.strip()
                if cleaned:
                    return cleaned

    return None
