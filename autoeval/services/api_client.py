"""
Unified API client for OpenAI (GPT-4.1) and DeepSeek with retry logic.
"""

from openai import OpenAI
from typing import List, Dict, Optional
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from loguru import logger
import time

from autoeval.config.settings import get_settings


class APIClient:
    """Unified client for OpenAI and DeepSeek APIs"""

    def __init__(self):
        self.settings = get_settings()

        # Initialize OpenAI client (for GPT-4.1 chat and embeddings)
        if not self.settings.OPENAI_API_KEY:
            logger.warning("OPENAI_API_KEY not set. OpenAI API calls will fail.")
        self.openai_client = OpenAI(
            api_key=self.settings.OPENAI_API_KEY,
            base_url=self.settings.OPENAI_BASE_URL,
            timeout=self.settings.API_TIMEOUT
        )

        # Initialize DeepSeek client
        if not self.settings.DEEPSEEK_API_KEY:
            logger.warning("DEEPSEEK_API_KEY not set. DeepSeek API calls will fail.")
        self.deepseek_client = OpenAI(
            api_key=self.settings.DEEPSEEK_API_KEY,
            base_url=self.settings.DEEPSEEK_BASE_URL,
            timeout=self.settings.API_TIMEOUT
        )

        logger.info("API clients initialized (OpenAI + DeepSeek)")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((Exception,)),
        reraise=True
    )
    def call_openai(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> str:
        """
        Call OpenAI API (for GPT-4.1 or other models).

        Args:
            model: Model name (e.g., "gpt-4.1", "gpt-4o")
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            **kwargs: Additional parameters

        Returns:
            Generated text
        """
        try:
            logger.debug(f"Calling OpenAI API with model={model}")
            start_time = time.time()

            response = self.openai_client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs
            )

            elapsed = time.time() - start_time
            content = response.choices[0].message.content

            logger.debug(f"OpenAI API call successful ({elapsed:.2f}s)")
            return content

        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((Exception,)),
        reraise=True
    )
    def call_deepseek(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> str:
        """
        Call DeepSeek API.

        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            **kwargs: Additional parameters

        Returns:
            Generated text
        """
        try:
            logger.debug(f"Calling DeepSeek API")
            start_time = time.time()

            response = self.deepseek_client.chat.completions.create(
                model=self.settings.ANSWER_GEN_MODEL,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs
            )

            elapsed = time.time() - start_time
            content = response.choices[0].message.content

            logger.debug(f"DeepSeek API call successful ({elapsed:.2f}s)")
            return content

        except Exception as e:
            logger.error(f"DeepSeek API error: {e}")
            raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((Exception,)),
        reraise=True
    )
    def get_embedding(self, text: str) -> List[float]:
        """
        Get text embedding via OpenAI API.

        Args:
            text: Text to embed

        Returns:
            Embedding vector
        """
        try:
            logger.debug(f"Getting embedding (length={len(text)})")
            start_time = time.time()

            response = self.openai_client.embeddings.create(
                model=self.settings.EMBEDDING_MODEL,
                input=text
            )

            elapsed = time.time() - start_time
            embedding = response.data[0].embedding

            logger.debug(f"Embedding generated ({elapsed:.2f}s, dim={len(embedding)})")
            return embedding

        except Exception as e:
            logger.error(f"Embedding API error: {e}")
            raise

    def get_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Get embeddings for multiple texts (batched).

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors
        """
        embeddings = []
        batch_size = self.settings.BATCH_SIZE

        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            logger.info(f"Processing embedding batch {i // batch_size + 1}/{(len(texts) - 1) // batch_size + 1}")

            for text in batch:
                embedding = self.get_embedding(text)
                embeddings.append(embedding)

            # Small delay between batches to avoid rate limiting
            if i + batch_size < len(texts):
                time.sleep(0.5)

        return embeddings


# Singleton instance
_api_client: Optional[APIClient] = None


def get_api_client() -> APIClient:
    """Get the global API client instance"""
    global _api_client
    if _api_client is None:
        _api_client = APIClient()
    return _api_client
