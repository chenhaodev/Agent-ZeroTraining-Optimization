"""
LLM API client for calling external LLMs (DeepSeek, OpenAI, etc.)
"""
import os
import time
import uuid
from typing import List, Dict, Any, Optional, AsyncIterator
from openai import OpenAI, AsyncOpenAI
from loguru import logger
from router.api.llm_schemas import (
    ChatMessage,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatCompletionChoice,
    ChatCompletionUsage,
    ChatCompletionChunk
)


class LLMClient:
    """Client for calling external LLM APIs"""

    def __init__(self):
        """Initialize LLM clients"""
        # DeepSeek client
        self.deepseek_api_key = os.getenv("DEEPSEEK_API_KEY")
        self.deepseek_base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

        if self.deepseek_api_key:
            self.deepseek_client = OpenAI(
                api_key=self.deepseek_api_key,
                base_url=self.deepseek_base_url
            )
            self.async_deepseek_client = AsyncOpenAI(
                api_key=self.deepseek_api_key,
                base_url=self.deepseek_base_url
            )
            logger.info("✓ DeepSeek client initialized")
        else:
            self.deepseek_client = None
            self.async_deepseek_client = None
            logger.warning("DeepSeek API key not found, DeepSeek calls will fail")

        # OpenAI client
        self.openai_api_key = os.getenv("OPENAI_API_KEY") or os.getenv("POE_API_KEY")
        self.openai_base_url = os.getenv("OPENAI_BASE_URL") or os.getenv("POE_BASE_URL", "https://api.openai.com/v1")

        if self.openai_api_key:
            self.openai_client = OpenAI(
                api_key=self.openai_api_key,
                base_url=self.openai_base_url
            )
            self.async_openai_client = AsyncOpenAI(
                api_key=self.openai_api_key,
                base_url=self.openai_base_url
            )
            logger.info("✓ OpenAI client initialized")
        else:
            self.openai_client = None
            self.async_openai_client = None
            logger.warning("OpenAI API key not found, OpenAI calls will fail")

    def _get_client(self, model: str) -> Optional[OpenAI]:
        """Get appropriate client for model"""
        if "deepseek" in model.lower():
            return self.deepseek_client
        elif "gpt" in model.lower() or "o1" in model.lower():
            return self.openai_client
        else:
            # Default to DeepSeek for unknown models
            logger.warning(f"Unknown model '{model}', using DeepSeek client")
            return self.deepseek_client

    def _get_async_client(self, model: str) -> Optional[AsyncOpenAI]:
        """Get appropriate async client for model"""
        if "deepseek" in model.lower():
            return self.async_deepseek_client
        elif "gpt" in model.lower() or "o1" in model.lower():
            return self.async_openai_client
        else:
            logger.warning(f"Unknown model '{model}', using async DeepSeek client")
            return self.async_deepseek_client

    def chat_completion(
        self,
        request: ChatCompletionRequest,
        enhanced_messages: Optional[List[ChatMessage]] = None
    ) -> ChatCompletionResponse:
        """
        Call LLM API for chat completion (synchronous).

        Args:
            request: Original chat completion request
            enhanced_messages: Optional enhanced messages (with routing improvements)

        Returns:
            ChatCompletionResponse
        """
        client = self._get_client(request.model)
        if not client:
            raise ValueError(f"No API client available for model: {request.model}")

        # Use enhanced messages if provided, otherwise use original
        messages = enhanced_messages or request.messages

        # Convert to dict format for OpenAI SDK
        messages_dict = [{"role": m.role, "content": m.content} for m in messages]

        # Build API parameters
        params = {
            "model": request.model,
            "messages": messages_dict,
            "temperature": request.temperature,
            "top_p": request.top_p,
            "n": request.n,
            "stream": False,  # Non-streaming
            "max_tokens": request.max_tokens,
            "presence_penalty": request.presence_penalty,
            "frequency_penalty": request.frequency_penalty,
        }

        # Add optional params
        if request.stop:
            params["stop"] = request.stop
        if request.logit_bias:
            params["logit_bias"] = request.logit_bias
        if request.user:
            params["user"] = request.user

        # Call LLM API
        logger.info(f"Calling {request.model} API (sync)...")
        start_time = time.time()

        try:
            response = client.chat.completions.create(**params)
            elapsed = time.time() - start_time
            logger.info(f"✓ LLM response received in {elapsed:.2f}s")

            # Convert to our response format
            return ChatCompletionResponse(
                id=response.id,
                created=response.created,
                model=response.model,
                choices=[
                    ChatCompletionChoice(
                        index=choice.index,
                        message=ChatMessage(
                            role=choice.message.role,
                            content=choice.message.content
                        ),
                        finish_reason=choice.finish_reason
                    )
                    for choice in response.choices
                ],
                usage=ChatCompletionUsage(
                    prompt_tokens=response.usage.prompt_tokens,
                    completion_tokens=response.usage.completion_tokens,
                    total_tokens=response.usage.total_tokens
                )
            )

        except Exception as e:
            logger.error(f"LLM API call failed: {e}")
            raise

    async def async_chat_completion(
        self,
        request: ChatCompletionRequest,
        enhanced_messages: Optional[List[ChatMessage]] = None
    ) -> ChatCompletionResponse:
        """
        Call LLM API for chat completion (asynchronous).

        Args:
            request: Original chat completion request
            enhanced_messages: Optional enhanced messages (with routing improvements)

        Returns:
            ChatCompletionResponse
        """
        client = self._get_async_client(request.model)
        if not client:
            raise ValueError(f"No async API client available for model: {request.model}")

        # Use enhanced messages if provided
        messages = enhanced_messages or request.messages
        messages_dict = [{"role": m.role, "content": m.content} for m in messages]

        # Build API parameters
        params = {
            "model": request.model,
            "messages": messages_dict,
            "temperature": request.temperature,
            "top_p": request.top_p,
            "n": request.n,
            "stream": False,
            "max_tokens": request.max_tokens,
            "presence_penalty": request.presence_penalty,
            "frequency_penalty": request.frequency_penalty,
        }

        if request.stop:
            params["stop"] = request.stop
        if request.logit_bias:
            params["logit_bias"] = request.logit_bias
        if request.user:
            params["user"] = request.user

        # Call LLM API
        logger.info(f"Calling {request.model} API (async)...")
        start_time = time.time()

        try:
            response = await client.chat.completions.create(**params)
            elapsed = time.time() - start_time
            logger.info(f"✓ LLM response received in {elapsed:.2f}s")

            return ChatCompletionResponse(
                id=response.id,
                created=response.created,
                model=response.model,
                choices=[
                    ChatCompletionChoice(
                        index=choice.index,
                        message=ChatMessage(
                            role=choice.message.role,
                            content=choice.message.content
                        ),
                        finish_reason=choice.finish_reason
                    )
                    for choice in response.choices
                ],
                usage=ChatCompletionUsage(
                    prompt_tokens=response.usage.prompt_tokens,
                    completion_tokens=response.usage.completion_tokens,
                    total_tokens=response.usage.total_tokens
                )
            )

        except Exception as e:
            logger.error(f"Async LLM API call failed: {e}")
            raise

    async def async_chat_completion_stream(
        self,
        request: ChatCompletionRequest,
        enhanced_messages: Optional[List[ChatMessage]] = None,
        routing_decision: Optional[Dict[str, Any]] = None
    ) -> AsyncIterator[str]:
        """
        Call LLM API for streaming chat completion.

        Args:
            request: Original chat completion request
            enhanced_messages: Optional enhanced messages (with routing improvements)
            routing_decision: Routing decision to include in first chunk

        Yields:
            Server-sent events (SSE) formatted chunks
        """
        client = self._get_async_client(request.model)
        if not client:
            raise ValueError(f"No async API client available for model: {request.model}")

        messages = enhanced_messages or request.messages
        messages_dict = [{"role": m.role, "content": m.content} for m in messages]

        params = {
            "model": request.model,
            "messages": messages_dict,
            "temperature": request.temperature,
            "top_p": request.top_p,
            "stream": True,  # Enable streaming
            "max_tokens": request.max_tokens,
        }

        if request.stop:
            params["stop"] = request.stop

        logger.info(f"Calling {request.model} API (streaming)...")

        try:
            stream = await client.chat.completions.create(**params)

            # Generate unique ID
            completion_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"
            created = int(time.time())
            first_chunk = True

            async for chunk in stream:
                # Build chunk response
                chunk_data = {
                    "id": completion_id,
                    "object": "chat.completion.chunk",
                    "created": created,
                    "model": request.model,
                    "choices": []
                }

                # Add routing decision to first chunk
                if first_chunk and routing_decision:
                    chunk_data["x_routing_decision"] = routing_decision
                    first_chunk = False

                # Add delta content
                for choice in chunk.choices:
                    chunk_data["choices"].append({
                        "index": choice.index,
                        "delta": {
                            "role": choice.delta.role if choice.delta.role else None,
                            "content": choice.delta.content if choice.delta.content else ""
                        },
                        "finish_reason": choice.finish_reason
                    })

                # Format as SSE
                import json
                yield f"data: {json.dumps(chunk_data)}\n\n"

            # Send [DONE] marker
            yield "data: [DONE]\n\n"

        except Exception as e:
            logger.error(f"Streaming LLM API call failed: {e}")
            raise


# Global instance
_llm_client: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    """Get global LLM client instance"""
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client
