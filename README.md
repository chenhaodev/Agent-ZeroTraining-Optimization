# LLM Self-Improvement via Dynamic Prompts

Learn from LLM mistakes and automatically generate context-aware prompts that inject relevant error reminders, improving response quality without retraining.

---
## Overview

This repository contains three integrated systems for improving LLM performance through **dynamic prompt engineering**:

1. **autoeval** - Evaluate LLM against golden references, identify weaknesses
2. **optimizer** - Extract error patterns and build searchable pattern database
3. **router** - Production API with dynamic prompts tailored per question

**Core Idea:** Learn from past mistakes → Store error patterns → Dynamically inject relevant reminders into prompts → LLM avoids repeating the same errors.

---
## Performance

| Metric | Baseline (v1.0) | Router-Optimized | Improvement |
|--------|-----------------|------------------|-------------|
| **Overall Score** | 4.13/5.0 | ~4.4-4.5/5.0 | **+6-9%** ✨ |
| **Completeness** | 3.86/5.0 | ~4.3/5.0 | **+11%** (biggest gain) |
| **Accuracy** | 4.21/5.0 | ~4.5/5.0 | **+7%** |
| **Error Rate** | 41 errors/14 Q&A | ~25-30 errors/14 Q&A | **-27-39%** |

**How Router Improves Quality:**
- **534 learned error patterns** automatically retrieved per question
- **Tiered routing:** Weakness matching → Pattern retrieval → Category rules
- **Runtime cost:** +1-2% (pattern retrieval is fast, FAISS vector search)
- **ROI:** 3-4.5x improvement per unit cost

**Key Insight:** Completeness (missing information) is the #1 issue. Router specifically targets this by injecting reminders about commonly-missed details from past errors.

---
## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ 1. autoeval/                                                │
│    • Samples entities from golden medical references        │
│    • Generates test questions (OpenAI)                      │
│    • Gets answers from target LLM (e.g., DeepSeek)          │
│    • Evaluates quality (LLM judge + golden-ref lookup)      │
│    • Outputs: evaluation reports with scores & errors       │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. optimizer/                                               │
│    • Extracts error patterns from evaluation reports        │
│    • Generates improved prompts (v1.0 → v1.1 → v1.2...)     │
│    • Retrieves relevant patterns per question dynamically   │
│    • Outputs: versioned prompts, pattern vector store       │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. router/                                                  │
│    • Serves OpenAI-compatible API                           │
│    • Matches questions to known weakness patterns           │
│    • Injects relevant error reminders into prompts          │
│    • Routes to DeepSeek with enhanced system prompt         │
│    • Outputs: streaming responses + routing metadata        │
└─────────────────────────────────────────────────────────────┘
```

### Repository Structure

```
.
├── autoeval/          # Auto-evaluation system
│   ├── config/        # Settings, prompts, presets
│   ├── core/          # Data models, loading, sampling
│   ├── scripts/       # evaluate.py (main entry point)
│   ├── services/      # Question/answer/evaluation services
│   └── utils/         # JSON parser, reporting
│
├── optimizer/         # Prompt optimization system
│   ├── core/          # Pattern analysis, storage, optimization
│   ├── pattern_db/    # Vector database for pattern storage & retrieval
│   └── scripts/       # optimize.py (main entry point)
│
├── router/            # Smart routing system
│   ├── api/           # FastAPI application
│   ├── core/          # Decision engine, weakness matcher
│   ├── scripts/       # serve_router.py, testing scripts
│   └── services/      # LLM client integrations
│
├── tools/             # Standalone utilities
│   ├── analyze_patterns.py
│   ├── build_weakness_patterns.py
│   ├── monitor_performance.py
│   ├── optimize_threshold.py
│   ├── list_reports.py
│   └── cleanup_repo.sh
│
├── refs/              # Golden reference data (medical CSVs)
│   └── golden-refs/   # 5,730+ medical entities
│
└── outputs/           # Generated reports, prompts, cache
```

---

## Quick Start

### Prerequisites

```bash
# Install dependencies
pip install -r autoeval/requirements.txt
pip install -r optimizer/requirements.txt
pip install -r router/requirements.txt

# Configure API keys
cp .env.example .env
# Edit .env and add:
#   OPENAI_API_KEY=...     # For question generation & evaluation
#   DEEPSEEK_API_KEY=...   # For target LLM testing
```

---

### 1. Auto-Evaluation

**Purpose:** Evaluate your LLM against golden medical references and identify weaknesses.

```bash
# Run evaluation (10 entities, 3 questions each = 30 Q&A pairs)
python autoeval/scripts/evaluate.py --sample-size=10

# Custom configuration
python autoeval/scripts/evaluate.py \
    --sample-size=50 \
    --questions-per-entity=5

# Compare baseline vs optimized
python autoeval/scripts/evaluate.py --compare-mode
```

**What happens:**
1. Samples 10 medical entities from `refs/golden-refs/`
2. Generates 30 questions using OpenAI API
3. Gets 30 answers from DeepSeek
4. Evaluates each answer by direct lookup of golden reference
5. Identifies error patterns and knowledge gaps

**Outputs:**
- `outputs/reports/{eval_id}/report.json` - Detailed evaluation
- `outputs/reports/{eval_id}/report.md` - Human-readable report

---

### 2. Optimizer

**Purpose:** Extract error patterns and build a searchable database for dynamic prompt assembly.

```bash
# Optimize using latest evaluation
python optimizer/scripts/optimize.py

# Optimize using specific evaluation
python optimizer/scripts/optimize.py --eval-report=eval_20251228_001

# Show statistics
python optimizer/scripts/optimize.py --stats

# List all stored patterns
python optimizer/scripts/optimize.py --list-patterns
```

**What happens:**
1. Loads evaluation report from autoeval
2. Analyzes error patterns (PatternAnalyzer)
3. Stores patterns in vector database (FAISS + embeddings)
4. Generates improved prompt version (v1.0 → v1.1)
5. Enables retrieval of relevant patterns per question at runtime

**Outputs:**
- `outputs/prompts/deepseek_system_v1.1.yaml` - Improved prompt
- `outputs/cache/error_patterns/` - Pattern storage (JSON + FAISS index)

**Example Output:**
```
Optimization Summary:
  Previous version: 1.0
  New version: 1.1
  Total patterns in RAG: 23
  Pattern categories: 4

Top Improvements:
  1. When answering about chronic diseases, include prevention measures
  2. For dietary questions, provide specific food examples
  3. Explain testing procedures step-by-step
```

**Key Innovation:** Dynamic Prompt Engineering (Not Traditional RAG)
- **Not RAG**: Doesn't retrieve external knowledge documents
- **Not Fine-tuning**: Doesn't retrain model weights
- **Dynamic Prompts**: Selects & combines relevant error reminders per question
- **How**: Base prompt + retrieved error patterns = customized prompt per request
- **Benefit**: Scales to 1000s of learned patterns without prompt bloat

---

### 3. Router

**Purpose:** Production API that dynamically customizes prompts per question using learned error patterns.

```bash
# Start router API
python router/scripts/serve_router.py --port=8000

# Test and compare
python router/scripts/test_router_llm_api.py
python router/scripts/compare_baseline_vs_router.py
python router/scripts/ab_test_extended.py
```

**What happens:**
1. Loads optimized prompts and weakness pattern database
2. Serves OpenAI-compatible API at `http://localhost:8000`
3. For each incoming question:
   - Searches for similar past error patterns
   - Injects relevant reminders into system prompt
   - Forwards enhanced request to DeepSeek API
   - Returns response with routing metadata

**Example Usage:**

```python
from openai import OpenAI

# Just change the base_url - that's it!
client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="your-llm-api-key"
)

response = client.chat.completions.create(
    model="deepseek-chat",
    messages=[
        {"role": "user", "content": "What is diabetes?"}
    ]
)

print(response.choices[0].message.content)
# Router automatically:
# - Searched: "What is diabetes?" → found past errors on chronic diseases
# - Injected: "Remember to include prevention measures" into system prompt
# - Result: More complete answer than baseline DeepSeek
```

**How it works:**
```
For each question:
1. Search pattern database for similar past errors
2. If matches found → inject error reminders into system prompt
3. If no matches → use base optimized prompt
4. Forward to DeepSeek with enhanced prompt
5. Return response with metadata (patterns used, routing decision)
```

---

## Workflow Example

```bash
# Step 1: Run initial evaluation
python autoeval/scripts/evaluate.py --sample-size=100
# Output: Report shows errors and weaknesses

# Step 2: Generate optimized prompt from errors
python optimizer/scripts/optimize.py
# Output: deepseek_system_v1.1.yaml with pattern database

# Step 3: Test improvement with A/B comparison
python router/scripts/compare_baseline_vs_router.py
# Compares baseline vs router-enhanced responses

# Step 4: Deploy production API
python router/scripts/serve_router.py
# Router serves requests with pattern-based enhancements

# Step 5: Continue learning (iterate steps 1-2)
python autoeval/scripts/evaluate.py --sample-size=50
python optimizer/scripts/optimize.py
# Accumulates more patterns over time
```

---

## Utilities

Additional tools for monitoring and analysis:

```bash
# Analyze pattern quality and find duplicates
python tools/analyze_patterns.py

# Build entity-specific weakness mappings
python tools/build_weakness_patterns.py

# Monitor performance and track metrics
python tools/monitor_performance.py

# Optimize retrieval thresholds
python tools/optimize_threshold.py

# List all evaluation reports
python tools/list_reports.py

# Clean up repository
bash tools/cleanup_repo.sh
```

---

## Data Sources

The repository includes golden reference data:

- 疾病.csv - 5,351 diseases
- 检查.csv - 215 examinations
- 手术操作.csv - 140 surgical procedures
- 疫苗.csv - 24 vaccines

**Total:** 5,730 medical entities with detailed information (symptoms, causes, treatments, prevention, etc.)
