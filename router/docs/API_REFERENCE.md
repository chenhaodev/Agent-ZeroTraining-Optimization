# Smart Router API Reference

**Version:** 1.0.0
**Base URL:** `http://localhost:8000`

---

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements/router.txt

# 2. Start server
python scripts/serve_router.py

# 3. Test API
curl http://localhost:8000/api/v1/health
```

---

## Endpoints

### 📍 POST `/api/v1/route`

Get routing decision for a question.

**Request:**
```json
{
  "question": "糖尿病有哪些症状？",
  "entity_type": "diseases",      // Optional: diseases, examinations, surgeries, vaccines
  "min_confidence": 0.70           // Optional: 0.0-1.0
}
```

**Response:**
```json
{
  "use_rag": true,
  "rag_reason": "Exact match: '糖尿病'",
  "rag_confidence": 0.95,
  "weakness_patterns": [
    {
      "weakness_id": "incomplete_symptoms_001",
      "category": "completeness",
      "subcategory": "disease_symptoms",
      "description": "Often omits progression stages...",
      "severity": "medium",
      "frequency": 0.50,
      "prompt_addition": "【症状描述重点】\n- 区分急性期和慢性期症状...",
      "match_score": 0.44
    }
  ],
  "has_weaknesses": true,
  "last_reload_check": "2025-12-27T10:30:00"
}
```

**Example (curl):**
```bash
curl -X POST http://localhost:8000/api/v1/route \
  -H "Content-Type: application/json" \
  -d '{
    "question": "糖尿病有哪些症状？",
    "entity_type": "diseases"
  }'
```

**Example (Python):**
```python
import requests

response = requests.post("http://localhost:8000/api/v1/route", json={
    "question": "糖尿病有哪些症状？",
    "entity_type": "diseases"
})

decision = response.json()
if decision['use_rag']:
    print(f"Use RAG! Confidence: {decision['rag_confidence']}")
    print(f"Weaknesses found: {len(decision['weakness_patterns'])}")
```

---

### 📍 POST `/api/v1/prompt`

Get enhanced prompt with weakness patterns injected.

**Request:**
```json
{
  "question": "糖尿病有哪些症状？",
  "entity_type": "diseases",       // Optional
  "base_prompt": "你是..."         // Optional: custom base prompt
}
```

**Response:**
```json
{
  "enhanced_prompt": "你是一位专业、耐心、友善的医疗健康助手...\n\n## ⚠️ 针对该问题类型的特别提醒\n\n【症状描述重点】\n- 区分急性期和慢性期症状...",
  "use_rag": true,
  "weakness_patterns_applied": 2,
  "routing_decision": { /* Same as /route response */ }
}
```

**Example (Python):**
```python
response = requests.post("http://localhost:8000/api/v1/prompt", json={
    "question": "糖尿病有哪些症状？",
    "entity_type": "diseases"
})

data = response.json()
enhanced_prompt = data['enhanced_prompt']

# Use with your LLM
messages = [
    {"role": "system", "content": enhanced_prompt},
    {"role": "user", "content": "糖尿病有哪些症状？"}
]
answer = call_llm(messages)
```

---

### 📍 GET `/api/v1/health`

Health check endpoint.

**Response:**
```json
{
  "status": "healthy",             // healthy, degraded, unhealthy
  "version": "1.0.0",
  "entities_loaded": 5721,
  "weaknesses_loaded": 10,
  "hot_reload_enabled": true,
  "last_reload_check": "2025-12-27T10:30:00"
}
```

**Example:**
```bash
curl http://localhost:8000/api/v1/health
```

---

### 📍 GET `/api/v1/stats`

Get detailed router statistics.

**Response:**
```json
{
  "total_entities": 5721,
  "diseases": 5351,
  "examinations": 215,
  "surgeries": 140,
  "vaccines": 24,
  "category_keywords": 45,
  "ood_keywords": 13,
  "weakness_patterns": 10,
  "weakness_categories": {
    "completeness": 3,
    "factual_precision": 2,
    "context_awareness": 2,
    "safety": 1
  },
  "last_reload_check": "2025-12-27T10:30:00",
  "entity_file_mtime": "2025-12-20T15:45:00",
  "weakness_file_mtime": "2025-12-27T10:15:00"
}
```

**Example:**
```bash
curl http://localhost:8000/api/v1/stats
```

---

### 📍 POST `/api/v1/reload`

Force reload of router data.

**Response:**
```json
{
  "reloaded": true,
  "message": "Data reloaded successfully",
  "entities_loaded": 5721,
  "weaknesses_loaded": 10,
  "timestamp": "2025-12-27T10:35:00"
}
```

**Example:**
```bash
# After running evaluation that generates new weaknesses
python scripts/evaluate.py

# Force router to reload
curl -X POST http://localhost:8000/api/v1/reload
```

---

## Error Responses

All endpoints return standard error responses:

**404 Not Found:**
```json
{
  "detail": "Endpoint not found"
}
```

**422 Validation Error:**
```json
{
  "detail": [
    {
      "loc": ["body", "question"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

**500 Internal Error:**
```json
{
  "detail": "Internal server error message"
}
```

---

## Configuration

Edit `config/router/settings.py` or use environment variables:

```python
# config/router/settings.py

class RouterSettings:
    # Data paths
    ENTITY_NAMES_PATH: Path = "data/entity_names.json"
    WEAKNESSES_PATH: Path = "data/deepseek_weaknesses.json"

    # Router settings
    RAG_MIN_CONFIDENCE: float = 0.70
    WEAKNESS_TOP_K: int = 2
    WEAKNESS_MIN_FREQUENCY: float = 0.15

    # Hot-reload
    ENABLE_HOT_RELOAD: bool = True
    WATCH_INTERVAL: int = 30

    # API settings
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    WORKERS: int = 4
```

**Environment Variables:**
```bash
# .env
ROUTER_HOST=0.0.0.0
ROUTER_PORT=8000
ROUTER_ENABLE_HOT_RELOAD=true
ROUTER_RAG_MIN_CONFIDENCE=0.70
```

---

## Interactive Documentation

The router API includes interactive Swagger documentation:

- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc

These provide:
- API endpoint listings
- Request/response schemas
- Try-it-out functionality
- Auto-generated examples

---

## Common Use Cases

### **1. Basic Routing Decision**

```python
def get_routing_decision(question: str):
    response = requests.post(
        "http://localhost:8000/api/v1/route",
        json={"question": question}
    )
    return response.json()

decision = get_routing_decision("糖尿病有哪些症状？")
print(f"Use RAG: {decision['use_rag']}")
print(f"Weaknesses: {len(decision['weakness_patterns'])}")
```

### **2. Build Complete LLM Prompt**

```python
def build_llm_prompt(question: str):
    response = requests.post(
        "http://localhost:8000/api/v1/prompt",
        json={"question": question, "entity_type": "diseases"}
    )
    return response.json()['enhanced_prompt']

prompt = build_llm_prompt("糖尿病有哪些症状？")
# Use with DeepSeek, GPT, or any LLM
```

### **3. Monitor Router Health**

```python
def check_router_health():
    response = requests.get("http://localhost:8000/api/v1/health")
    health = response.json()

    if health['status'] != 'healthy':
        alert("Router unhealthy!")

    return health

health = check_router_health()
print(f"Entities loaded: {health['entities_loaded']}")
print(f"Weaknesses loaded: {health['weaknesses_loaded']}")
```

### **4. Trigger Reload After Evaluation**

```python
# After running auto-evaluation
subprocess.run(["python", "scripts/evaluate.py", "--sample-size", "100"])

# Force router to reload new weaknesses
response = requests.post("http://localhost:8000/api/v1/reload")
reload_info = response.json()

print(f"Reloaded: {reload_info['reloaded']}")
print(f"New weaknesses: {reload_info['weaknesses_loaded']}")
```

---

## Performance

| Metric | Value |
|--------|-------|
| **Startup Time** | <1 second |
| **Routing Decision** | <10ms |
| **Prompt Building** | <20ms |
| **Hot-Reload Check** | <5ms |
| **Memory Usage** | 50-100MB |
| **Concurrent Requests** | 1000+ req/s (4 workers) |

---

## Security Considerations

**For Production:**

1. **Disable CORS wildcard:**
   ```python
   # router/api/app.py
   app.add_middleware(
       CORSMiddleware,
       allow_origins=["https://your-domain.com"],  # Specific domains
       ...
   )
   ```

2. **Add authentication:**
   ```python
   from fastapi.security import HTTPBearer

   security = HTTPBearer()

   @app.post("/api/v1/route")
   async def route_question(
       request: RouteRequest,
       credentials: HTTPAuthorizationCredentials = Depends(security)
   ):
       # Verify credentials
       ...
   ```

3. **Rate limiting:**
   ```python
   from slowapi import Limiter

   limiter = Limiter(key_func=get_remote_address)

   @app.post("/api/v1/route")
   @limiter.limit("100/minute")
   async def route_question(...):
       ...
   ```

---

## Troubleshooting

**Router won't start:**
```bash
# Check if port is available
lsof -i :8000

# Try different port
python scripts/serve_router.py --port 8080
```

**Hot-reload not working:**
```bash
# Check settings
python -c "from config.router.settings import get_router_settings; print(get_router_settings().ENABLE_HOT_RELOAD)"

# Force reload manually
curl -X POST http://localhost:8000/api/v1/reload
```

**Weakness patterns not loading:**
```bash
# Check if file exists
ls data/deepseek_weaknesses.json

# Check file permissions
chmod 644 data/deepseek_weaknesses.json

# Check stats endpoint
curl http://localhost:8000/api/v1/stats
```

---

For more information, see [SEPARATION_GUIDE.md](../../SEPARATION_GUIDE.md).
