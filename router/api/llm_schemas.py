"""
OpenAI-compatible chat completion schemas for router API.
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Literal, Union
from datetime import datetime


class ChatMessage(BaseModel):
    """Single message in a chat conversation"""
    role: Literal["system", "user", "assistant"] = Field(..., description="Message role")
    content: str = Field(..., description="Message content")
    name: Optional[str] = Field(None, description="Optional name of the message author")


class ChatCompletionRequest(BaseModel):
    """OpenAI-compatible chat completion request"""
    model: str = Field(..., description="Model to use (e.g., 'deepseek-chat', 'gpt-4')")
    messages: List[ChatMessage] = Field(..., min_length=1, description="List of messages")

    # Optional parameters (OpenAI-compatible)
    temperature: Optional[float] = Field(1.0, ge=0.0, le=2.0, description="Sampling temperature")
    top_p: Optional[float] = Field(1.0, ge=0.0, le=1.0, description="Nucleus sampling")
    n: Optional[int] = Field(1, ge=1, description="Number of completions to generate")
    stream: Optional[bool] = Field(False, description="Whether to stream responses")
    stop: Optional[Union[str, List[str]]] = Field(None, description="Stop sequences")
    max_tokens: Optional[int] = Field(None, ge=1, description="Maximum tokens to generate")
    presence_penalty: Optional[float] = Field(0.0, ge=-2.0, le=2.0)
    frequency_penalty: Optional[float] = Field(0.0, ge=-2.0, le=2.0)
    logit_bias: Optional[Dict[str, float]] = Field(None)
    user: Optional[str] = Field(None, description="User identifier")

    # Router-specific extensions (optional, prefixed with 'x_')
    x_entity_type: Optional[str] = Field(None, description="Entity type hint for routing")
    x_min_confidence: Optional[float] = Field(0.70, description="Minimum pattern retrieval confidence")
    x_disable_routing: Optional[bool] = Field(False, description="Disable smart routing")
    x_disable_weaknesses: Optional[bool] = Field(False, description="Disable weakness patterns")


class ChatCompletionChoice(BaseModel):
    """Single completion choice"""
    index: int = Field(..., description="Choice index")
    message: ChatMessage = Field(..., description="Generated message")
    finish_reason: Optional[Literal["stop", "length", "content_filter", "null"]] = Field(None)


class ChatCompletionUsage(BaseModel):
    """Token usage statistics"""
    prompt_tokens: int = Field(..., description="Tokens in prompt")
    completion_tokens: int = Field(..., description="Tokens in completion")
    total_tokens: int = Field(..., description="Total tokens used")


class ChatCompletionResponse(BaseModel):
    """OpenAI-compatible chat completion response"""
    id: str = Field(..., description="Unique completion ID")
    object: Literal["chat.completion"] = Field("chat.completion")
    created: int = Field(..., description="Unix timestamp")
    model: str = Field(..., description="Model used")
    choices: List[ChatCompletionChoice] = Field(..., description="Generated completions")
    usage: ChatCompletionUsage = Field(..., description="Token usage")

    # Router-specific extensions
    x_routing_decision: Optional[Dict[str, Any]] = Field(None, description="Smart routing decision")
    x_enhanced_prompt_used: Optional[bool] = Field(None, description="Whether prompt was enhanced")


class ChatCompletionChunk(BaseModel):
    """Streaming chunk for chat completion"""
    id: str = Field(..., description="Unique completion ID")
    object: Literal["chat.completion.chunk"] = Field("chat.completion.chunk")
    created: int = Field(..., description="Unix timestamp")
    model: str = Field(..., description="Model used")
    choices: List[Dict[str, Any]] = Field(..., description="Streaming choices")

    # Router-specific extensions (only in first chunk)
    x_routing_decision: Optional[Dict[str, Any]] = Field(None)


class ErrorResponse(BaseModel):
    """Error response"""
    error: Dict[str, Any] = Field(..., description="Error details")

    @classmethod
    def create(cls, message: str, type: str = "invalid_request_error", code: Optional[str] = None):
        """Create error response"""
        return cls(error={
            "message": message,
            "type": type,
            "code": code
        })
