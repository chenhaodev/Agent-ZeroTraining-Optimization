# Router as OpenAI-Compatible LLM API

The Smart Router can be used as a **drop-in replacement** for OpenAI's API (or any OpenAI-compatible API like DeepSeek). Just change the `base_url` and you get intelligent routing + weakness pattern enhancement!

---

## Quick Start

### Before: Direct LLM API Call

```python
from openai import OpenAI

client = OpenAI(
    api_key="your-deepseek-key",
    base_url="https://api.deepseek.com"  # Direct API
)

response = client.chat.completions.create(
    model="deepseek-chat",
    messages=[
        {"role": "user", "content": "什么是糖尿病？"}
    ]
)

print(response.choices[0].message.content)
```

### After: With Smart Router

```python
from openai import OpenAI

client = OpenAI(
    api_key="your-deepseek-key",
    base_url="http://localhost:8000"  # ⭐ Point to router!
)

response = client.chat.completions.create(
    model="deepseek-chat",
    messages=[
        {"role": "user", "content": "什么是糖尿病？"}
    ]
)

print(response.choices[0].message.content)
# Same interface, but now with:
# - RAG decision making
# - Weakness pattern enhancement
# - Automatic prompt optimization
```

**That's it!** No code changes needed besides the URL.

---

## What the Router Does Automatically

When you send a chat completion request through the router, it:

1. **Analyzes the question** - Extracts user intent from messages
2. **Makes routing decision** - Should this use RAG retrieval? (based on entity matching, confidence scoring)
3. **Finds weakness patterns** - Matches question against known DeepSeek weaknesses
4. **Enhances the prompt** - Injects weakness reminders into system message
5. **Calls the LLM** - Forwards to actual LLM API (DeepSeek, OpenAI, etc.)
6. **Returns enhanced response** - With routing metadata included

All of this happens transparently - your code sees the same OpenAI-compatible response!

---

## Routing Metadata

The router adds custom fields to the response (prefixed with `x_`):

```python
response = client.chat.completions.create(...)

# Standard OpenAI fields
print(response.choices[0].message.content)
print(response.usage.total_tokens)

# Router-specific metadata
if hasattr(response, 'x_routing_decision'):
    decision = response.x_routing_decision
    print(f"Use RAG: {decision['use_rag']}")
    print(f"Confidence: {decision['rag_confidence']}")
    print(f"Weaknesses found: {len(decision['weakness_patterns'])}")

if hasattr(response, 'x_enhanced_prompt_used'):
    print(f"Prompt enhanced: {response.x_enhanced_prompt_used}")
```

---

## Router-Specific Parameters

You can control router behavior using custom parameters (prefixed with `x_`):

### 1. Entity Type Hint (`x_entity_type`)

Helps router match weaknesses more accurately:

```python
response = client.chat.completions.create(
    model="deepseek-chat",
    messages=[{"role": "user", "content": "什么是糖尿病？"}],
    extra_body={"x_entity_type": "diseases"}  # Hint: this is about a disease
)
```

Valid values: `diseases`, `examinations`, `surgeries`, `vaccines`

### 2. Minimum Confidence (`x_min_confidence`)

Set RAG confidence threshold:

```python
response = client.chat.completions.create(
    model="deepseek-chat",
    messages=[{"role": "user", "content": "什么是糖尿病？"}],
    extra_body={"x_min_confidence": 0.80}  # Require 80% confidence for RAG
)
```

Default: `0.70`

### 3. Disable Routing (`x_disable_routing`)

Skip routing entirely, call LLM directly:

```python
response = client.chat.completions.create(
    model="deepseek-chat",
    messages=[{"role": "user", "content": "什么是糖尿病？"}],
    extra_body={"x_disable_routing": True}  # Direct LLM call
)
```

Useful for A/B testing or debugging.

### 4. Disable Weaknesses (`x_disable_weaknesses`)

Keep routing decision, but don't inject weakness patterns:

```python
response = client.chat.completions.create(
    model="deepseek-chat",
    messages=[{"role": "user", "content": "什么是糖尿病？"}],
    extra_body={"x_disable_weaknesses": True}  # Routing only, no patterns
)
```

---

## Streaming Support

The router fully supports streaming:

```python
stream = client.chat.completions.create(
    model="deepseek-chat",
    messages=[{"role": "user", "content": "什么是糖尿病？"}],
    stream=True
)

for chunk in stream:
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="")
```

**Note:** Routing metadata appears in the first chunk only.

---

## A/B Testing: Router vs Baseline

Easy to compare router against baseline:

```python
from openai import OpenAI

# Setup two clients
baseline = OpenAI(api_key=key, base_url="https://api.deepseek.com")
router = OpenAI(api_key=key, base_url="http://localhost:8000")

questions = ["什么是糖尿病？", "高血压有哪些症状？"]

for q in questions:
    # Call both
    baseline_resp = baseline.chat.completions.create(model="deepseek-chat", messages=[{"role": "user", "content": q}])
    router_resp = router.chat.completions.create(model="deepseek-chat", messages=[{"role": "user", "content": q}])

    # Compare
    print(f"Question: {q}")
    print(f"Baseline: {baseline_resp.choices[0].message.content[:100]}...")
    print(f"Router: {router_resp.choices[0].message.content[:100]}...")
    print(f"Router used RAG: {router_resp.x_routing_decision['use_rag']}")
    print(f"Weaknesses applied: {len(router_resp.x_routing_decision['weakness_patterns'])}")
    print("-" * 80)
```

---

## Supported Models

The router automatically detects which backend to use based on model name:

| Model Name | Backend | Base URL |
|------------|---------|----------|
| `deepseek-chat`, `deepseek-*` | DeepSeek | `DEEPSEEK_BASE_URL` (env) |
| `gpt-4`, `gpt-3.5-*`, `o1-*` | OpenAI | `OPENAI_BASE_URL` or `POE_BASE_URL` (env) |
| Other | DeepSeek (default) | `DEEPSEEK_BASE_URL` |

Configure base URLs in `.env`:

```bash
# .env
DEEPSEEK_API_KEY=sk-...
DEEPSEEK_BASE_URL=https://api.deepseek.com

OPENAI_API_KEY=sk-...
OPENAI_BASE_URL=https://api.openai.com/v1
```

---

## Example: Complete Integration

```python
#!/usr/bin/env python3
"""
Example: Medical Q&A chatbot using smart router.
"""
from openai import OpenAI
import os

# Setup router client
client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="http://localhost:8000"  # Router
)

def ask_medical_question(question: str, entity_type: str = None) -> dict:
    """
    Ask a medical question with smart routing.

    Args:
        question: User's medical question
        entity_type: Optional hint (diseases, examinations, surgeries, vaccines)

    Returns:
        dict with answer and routing info
    """
    extra_body = {}
    if entity_type:
        extra_body["x_entity_type"] = entity_type

    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": "你是专业的医疗健康助手"},
            {"role": "user", "content": question}
        ],
        extra_body=extra_body,
        temperature=0.7,
        max_tokens=500
    )

    return {
        "answer": response.choices[0].message.content,
        "use_rag": response.x_routing_decision['use_rag'] if hasattr(response, 'x_routing_decision') else None,
        "confidence": response.x_routing_decision['rag_confidence'] if hasattr(response, 'x_routing_decision') else None,
        "weaknesses_applied": len(response.x_routing_decision['weakness_patterns']) if hasattr(response, 'x_routing_decision') else 0,
        "tokens_used": response.usage.total_tokens
    }

# Example usage
if __name__ == "__main__":
    result = ask_medical_question("什么是糖尿病？", entity_type="diseases")

    print(f"Question: 什么是糖尿病？")
    print(f"\nAnswer:\n{result['answer']}\n")
    print(f"Routing Info:")
    print(f"  - Use RAG: {result['use_rag']}")
    print(f"  - Confidence: {result['confidence']:.2f}")
    print(f"  - Weaknesses applied: {result['weaknesses_applied']}")
    print(f"  - Tokens used: {result['tokens_used']}")
```

---

## Performance

| Metric | Value |
|--------|-------|
| **Routing Decision Time** | <10ms |
| **Prompt Enhancement Time** | <5ms |
| **Total Overhead** | <15ms |
| **LLM Call Time** | ~2-5s (depends on LLM) |

The router adds minimal latency (~15ms) while providing significant quality improvements through weakness pattern injection.

---

## Testing

Run the test suite to verify router functionality:

```bash
# Start router first
python scripts/serve_router.py

# In another terminal, run tests
python scripts/test_router_llm_api.py
```

This will run:
- Drop-in replacement test
- A/B comparison test
- Router-specific features test
- Streaming support test

---

## Troubleshooting

### Router not responding

```bash
# Check if router is running
curl http://localhost:8000/api/v1/health

# If not, start it
python scripts/serve_router.py
```

### API key errors

```bash
# Check environment variables
echo $DEEPSEEK_API_KEY
echo $OPENAI_API_KEY

# Or add to .env file
DEEPSEEK_API_KEY=sk-...
OPENAI_API_KEY=sk-...
```

### Model not found

The router forwards model names to the backend. Make sure the model exists:
- `deepseek-chat` → DeepSeek API
- `gpt-4`, `gpt-3.5-turbo` → OpenAI API

### Routing not working

Check that data files exist:
```bash
ls data/entity_names.json
ls data/deepseek_weaknesses.json

# If missing, run evaluation first
python scripts/evaluate.py --sample-size 10
```

---

## Comparison with Direct API Calls

| Feature | Direct LLM API | Smart Router |
|---------|---------------|--------------|
| **Interface** | OpenAI-compatible | ✓ Same (drop-in) |
| **Streaming** | ✓ Supported | ✓ Supported |
| **RAG Decision** | ✗ Manual | ✓ Automatic |
| **Weakness Patterns** | ✗ None | ✓ Auto-injected |
| **Prompt Optimization** | ✗ Manual | ✓ Automatic |
| **Hot-Reload** | ✗ N/A | ✓ Auto-updates |
| **Latency Overhead** | 0ms | ~15ms |
| **Code Changes** | N/A | Just base_url |

---

## Next Steps

1. **Start the router:**
   ```bash
   python scripts/serve_router.py
   ```

2. **Update your code:**
   ```python
   # Change this
   base_url="https://api.deepseek.com"

   # To this
   base_url="http://localhost:8000"
   ```

3. **Test it:**
   ```bash
   python scripts/test_router_llm_api.py
   ```

4. **Monitor improvements:**
   - Check `x_routing_decision` in responses
   - Compare answers with/without router
   - Track token usage and quality

5. **Iterate:**
   - Run evaluation to discover new weaknesses
   - Router auto-reloads updated patterns
   - Quality improves continuously

---

For more information:
- [API Reference](API_REFERENCE.md) - Complete API documentation
- [Separation Guide](../../SEPARATION_GUIDE.md) - Architecture overview
- [Test Script](../../scripts/test_router_llm_api.py) - Example code
