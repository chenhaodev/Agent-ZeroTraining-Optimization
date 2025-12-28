"""
Request/Response schemas for Router API.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


class RouteRequest(BaseModel):
    """Request for routing decision"""
    question: str = Field(..., description="User question", min_length=1)
    entity_type: Optional[str] = Field(None, description="Entity type hint (diseases, examinations, surgeries, vaccines)")
    min_confidence: Optional[float] = Field(0.70, description="Minimum confidence for pattern retrieval (0.0-1.0)", ge=0.0, le=1.0)

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "question": "糖尿病有哪些症状？",
                    "entity_type": "diseases",
                    "min_confidence": 0.70
                }
            ]
        }
    }


class WeaknessPattern(BaseModel):
    """Weakness pattern information"""
    weakness_id: str
    category: str
    subcategory: str
    description: str
    severity: str
    frequency: float
    prompt_addition: str
    match_score: float


class RouteResponse(BaseModel):
    """Response with routing decision"""
    use_patterns: bool = Field(..., description="Whether to use pattern retrieval retrieval")
    rag_reason: str = Field(..., description="Explanation for pattern retrieval decision")
    rag_confidence: float = Field(..., description="Confidence in pattern retrieval decision (0.0-1.0)")
    weakness_patterns: List[WeaknessPattern] = Field(default=[], description="Matched weakness patterns")
    has_weaknesses: bool = Field(..., description="Whether weakness patterns were matched")
    last_reload_check: str = Field(..., description="Last time reload was checked (ISO format)")


class PromptRequest(BaseModel):
    """Request for enhanced prompt"""
    question: str = Field(..., description="User question", min_length=1)
    entity_type: Optional[str] = Field(None, description="Entity type hint")
    base_prompt: Optional[str] = Field(None, description="Base system prompt (if not provided, uses default)")


class PromptResponse(BaseModel):
    """Response with enhanced prompt"""
    enhanced_prompt: str = Field(..., description="Prompt with weakness patterns injected")
    use_patterns: bool = Field(..., description="Whether pattern retrieval should be used")
    weakness_patterns_applied: int = Field(..., description="Number of weakness patterns applied")
    routing_decision: RouteResponse = Field(..., description="Full routing decision")


class HealthResponse(BaseModel):
    """Health check response"""
    status: str = Field(..., description="Service status (healthy, degraded, unhealthy)")
    version: str = Field(..., description="API version")
    entities_loaded: int = Field(..., description="Number of entities loaded")
    weaknesses_loaded: int = Field(..., description="Number of weakness patterns loaded")
    hot_reload_enabled: bool = Field(..., description="Whether hot-reload is enabled")
    last_reload_check: str = Field(..., description="Last time reload was checked")


class StatsResponse(BaseModel):
    """Statistics response"""
    total_entities: int
    diseases: int
    examinations: int
    surgeries: int
    vaccines: int
    category_keywords: int
    ood_keywords: int
    weakness_patterns: int
    weakness_categories: Dict[str, int]
    last_reload_check: str
    entity_file_mtime: Optional[str]
    weakness_file_mtime: Optional[str]


class ReloadResponse(BaseModel):
    """Reload response"""
    reloaded: bool = Field(..., description="Whether data was reloaded")
    message: str = Field(..., description="Reload status message")
    entities_loaded: int = Field(..., description="Number of entities after reload")
    weaknesses_loaded: int = Field(..., description="Number of weakness patterns after reload")
    timestamp: str = Field(..., description="Reload timestamp (ISO format)")
