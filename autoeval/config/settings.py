"""
Configuration management using Pydantic Settings.
"""

from pydantic_settings import BaseSettings
from typing import Optional
from pathlib import Path


class Settings(BaseSettings):
    """Application settings"""

    # API Configuration
    OPENAI_API_KEY: str = ""  # For GPT-4.1 (question gen) and embeddings
    DEEPSEEK_API_KEY: str = ""
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"

    # Model Configuration
    QUESTION_GEN_MODEL: str = "gpt-4.1"  # OpenAI for question generation
    EVALUATOR_MODEL: str = "deepseek-chat"  # DeepSeek for evaluation (cost-effective)
    ANSWER_GEN_MODEL: str = "deepseek-chat"  # DeepSeek for answering
    EMBEDDING_MODEL: str = "text-embedding-3-large"  # OpenAI embeddings

    # Sampling Configuration
    DEFAULT_SAMPLE_SIZE: int = 100
    QUESTIONS_PER_ENTITY: int = 5
    STRATIFIED_SAMPLING: bool = True
    RANDOM_SEED: int = 42

    # RAG Configuration
    EMBEDDING_DIMENSION: int = 3072  # text-embedding-3-large
    RETRIEVAL_TOP_K: int = 5
    RAG_RELEVANCE_THRESHOLD: float = 0.65  # Minimum similarity score (0.0 = disabled, 0.65 = recommended)
    USE_SMART_ROUTING: bool = False  # Enable smart routing to skip RAG for predicted OOD questions
    VECTOR_STORE_TYPE: str = "faiss"  # or "chroma"
    USE_EMBEDDING_CACHE: bool = True
    REBUILD_VECTOR_INDEX: bool = False  # Set to True to rebuild index from scratch

    # Evaluation Configuration
    ERROR_SEVERITY_THRESHOLD: str = "minor"  # critical, major, minor
    ACCEPTABLE_SCORE_THRESHOLD: float = 3.0
    MIN_OVERALL_SCORE: float = 1.0
    MAX_OVERALL_SCORE: float = 5.0

    # Paths
    DATA_DIR: str = "refs/golden-refs/dxys"  # Fixed: was golden-refs/dxys
    OUTPUT_DIR: str = "outputs"
    CACHE_DIR: str = "outputs/cache"
    PROMPT_DIR: str = "autoeval/config/prompts"  # Fixed: was config/prompts
    REPORTS_DIR: str = "outputs/reports"
    PROMPTS_OUTPUT_DIR: str = "outputs/prompts"
    LOGS_DIR: str = "outputs/logs"

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "outputs/logs/evaluation.log"
    LOG_TO_CONSOLE: bool = True

    # API Rate Limiting
    API_RETRY_ATTEMPTS: int = 3
    API_RETRY_WAIT_MIN: int = 1  # seconds
    API_RETRY_WAIT_MAX: int = 10  # seconds
    API_TIMEOUT: int = 60  # seconds

    # Batch Processing
    BATCH_SIZE: int = 10  # For embedding generation
    SAVE_INTERMEDIATE_RESULTS: bool = True

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
        "extra": "ignore"  # Ignore ROUTER_* and other extra env vars in shared .env
    }

    def get_prompt_path(self, prompt_name: str) -> Path:
        """Get path to a prompt template file"""
        return Path(self.PROMPT_DIR) / f"{prompt_name}.yaml"

    def get_report_dir(self, report_id: str) -> Path:
        """Get path to a report directory"""
        return Path(self.REPORTS_DIR) / report_id

    def ensure_dirs(self):
        """Ensure all required directories exist"""
        dirs = [
            self.OUTPUT_DIR,
            self.CACHE_DIR,
            f"{self.CACHE_DIR}/vector_store",
            f"{self.CACHE_DIR}/embeddings",
            self.REPORTS_DIR,
            self.PROMPTS_OUTPUT_DIR,
            self.LOGS_DIR,
            self.PROMPT_DIR
        ]
        for dir_path in dirs:
            Path(dir_path).mkdir(parents=True, exist_ok=True)


# Singleton instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get the global settings instance"""
    global _settings
    if _settings is None:
        _settings = Settings()
        _settings.ensure_dirs()
    return _settings
