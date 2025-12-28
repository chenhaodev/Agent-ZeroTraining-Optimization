"""
Text embedding service with caching.
"""

import pickle
from pathlib import Path
from typing import List, Dict
from loguru import logger
import hashlib

from autoeval.services.api_client import get_api_client
from autoeval.config.settings import get_settings


class Embedder:
    """Text embedding service with disk caching"""

    def __init__(self):
        self.settings = get_settings()
        self.api_client = get_api_client()
        self.cache_file = Path(self.settings.CACHE_DIR) / "embeddings" / "embedding_cache.pkl"
        self.cache: Dict[str, List[float]] = {}

        if self.settings.USE_EMBEDDING_CACHE:
            self._load_cache()

    def _load_cache(self):
        """Load embedding cache from disk"""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'rb') as f:
                    self.cache = pickle.load(f)
                logger.info(f"Loaded {len(self.cache)} embeddings from cache")
            except Exception as e:
                logger.warning(f"Failed to load cache: {e}")
                self.cache = {}
        else:
            logger.info("No embedding cache found, starting fresh")

    def _save_cache(self):
        """Save embedding cache to disk"""
        if not self.settings.USE_EMBEDDING_CACHE:
            return

        try:
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.cache_file, 'wb') as f:
                pickle.dump(self.cache, f)
            logger.debug(f"Saved {len(self.cache)} embeddings to cache")
        except Exception as e:
            logger.warning(f"Failed to save cache: {e}")

    def _get_cache_key(self, text: str) -> str:
        """Generate cache key for text"""
        return hashlib.md5(text.encode('utf-8')).hexdigest()

    def _truncate_text(self, text: str, max_chars: int = 5500) -> str:
        """
        Truncate text to fit within embedding model's token limit.

        Args:
            text: Text to truncate
            max_chars: Maximum characters (default 5500, very safe for medical text)
                      Medical text has ~1.3-1.4 tokens/char (numbers, English, special chars)
                      5500 chars ≈ 7150 tokens (well under 8192 limit)

        Returns:
            Truncated text
        """
        if len(text) <= max_chars:
            return text

        logger.warning(f"⚠️  TRUNCATING text from {len(text)} to {max_chars} chars")
        return text[:max_chars] + "..."

    def embed(self, text: str) -> List[float]:
        """
        Get embedding for text (with caching).

        Args:
            text: Text to embed

        Returns:
            Embedding vector
        """
        # Truncate text if needed
        text = self._truncate_text(text)

        cache_key = self._get_cache_key(text)

        # Check cache
        if self.settings.USE_EMBEDDING_CACHE and cache_key in self.cache:
            logger.debug("Cache hit")
            return self.cache[cache_key]

        # Generate embedding
        embedding = self.api_client.get_embedding(text)

        # Save to cache
        if self.settings.USE_EMBEDDING_CACHE:
            self.cache[cache_key] = embedding
            self._save_cache()

        return embedding

    def embed_batch(self, texts: List[str], show_progress: bool = True) -> List[List[float]]:
        """
        Get embeddings for multiple texts with error recovery.

        Args:
            texts: List of texts to embed
            show_progress: Whether to show progress

        Returns:
            List of embedding vectors (None for failed embeddings)
        """
        embeddings = []
        cache_hits = 0
        errors = 0

        for i, text in enumerate(texts):
            if show_progress and i % 10 == 0:
                logger.info(f"Embedding progress: {i}/{len(texts)} ({errors} errors so far)")

            try:
                # Truncate text if needed
                text = self._truncate_text(text)

                cache_key = self._get_cache_key(text)

                if self.settings.USE_EMBEDDING_CACHE and cache_key in self.cache:
                    embeddings.append(self.cache[cache_key])
                    cache_hits += 1
                else:
                    embedding = self.api_client.get_embedding(text)
                    embeddings.append(embedding)

                    if self.settings.USE_EMBEDDING_CACHE:
                        self.cache[cache_key] = embedding

            except Exception as e:
                logger.error(f"Failed to embed text {i}: {e}")
                logger.debug(f"Failed text preview: {text[:200]}...")
                # Use zero vector as placeholder for failed embeddings
                embeddings.append([0.0] * self.settings.EMBEDDING_DIMENSION)
                errors += 1
                continue

        # Save cache after batch
        if self.settings.USE_EMBEDDING_CACHE:
            self._save_cache()

        logger.info(f"Batch complete: {cache_hits}/{len(texts)} cache hits, {errors} errors")
        if errors > 0:
            logger.warning(f"⚠️  {errors} embeddings failed and were replaced with zero vectors")
        return embeddings


# Singleton
_embedder = None

def get_embedder() -> Embedder:
    """Get global embedder instance"""
    global _embedder
    if _embedder is None:
        _embedder = Embedder()
    return _embedder
