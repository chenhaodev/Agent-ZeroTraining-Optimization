"""
Router configuration settings.
"""

from pydantic_settings import BaseSettings
from pathlib import Path
from typing import Optional


class RouterSettings(BaseSettings):
    """Configuration for Smart Router API"""

    # ===== Data Paths (Read-Only) =====
    ENTITY_NAMES_PATH: Path = Path("refs/entity_names.json")
    WEAKNESSES_PATH: Path = Path("optimizer/config/deepseek_weaknesses.json")  # Fixed: was refs/
    EVAL_LOG_PATH: Path = Path("outputs/autoeval/logs/evaluation.log")

    # ===== Router Decision Settings =====
    RAG_MIN_CONFIDENCE: float = 0.70
    WEAKNESS_TOP_K: int = 2
    WEAKNESS_MIN_FREQUENCY: float = 0.15

    # ===== Hot-Reload Settings =====
    ENABLE_HOT_RELOAD: bool = True
    WATCH_INTERVAL: int = 30  # Check for updates every 30 seconds
    AUTO_RELOAD_ON_WEAKNESS_UPDATE: bool = True

    # ===== API Server Settings =====
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    LOG_LEVEL: str = "INFO"
    WORKERS: int = 4

    # ===== Performance Settings =====
    ENABLE_CACHE: bool = True
    CACHE_TTL: int = 300  # Cache routing decisions for 5 minutes
    MAX_CACHE_SIZE: int = 10000

    # ===== Monitoring Settings =====
    ENABLE_METRICS: bool = True
    METRICS_PORT: int = 9090
    LOG_DIR: Path = Path("outputs/router/logs")

    class Config:
        env_file = ".env"
        env_prefix = "ROUTER_"
        case_sensitive = True
        extra = "ignore"  # Ignore extra env vars (for autoeval settings in same .env)


# Singleton instance
_settings: Optional[RouterSettings] = None


def get_router_settings() -> RouterSettings:
    """Get the global router settings instance"""
    global _settings
    if _settings is None:
        _settings = RouterSettings()
    return _settings
