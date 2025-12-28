# LLM Evaluation & Optimization Pipeline

An automated system to evaluate LLM performance on medical tasks, optimize prompts based on identified weaknesses, and deploy intelligent routing in production.

---
## Overview

This repository contains three integrated systems for improving LLM performance on domain-specific tasks (medical/healthcare):

1. **autoeval** - Automatically evaluate LLM against golden references, identify weaknesses
2. **optimizer** - Convert weaknesses into improved prompts using hierarchical RAG
3. **router** - Production API with intelligent routing based on LLM weaknesses

**Use Case:** Identify where your LLM fails on medical questions, automatically generate better prompts, and deploy smart routing that knows when to use RAG vs direct LLM.

---
## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ 1. autoeval/                                                │
│    • Samples entities from golden medical references        │
│    • Generates test questions (GPT-5.1)                     │
│    • Gets answers from target LLM (e.g., DeepSeek)          │
│    • Evaluates quality (GPT-5.1 + direct golden-ref lookup) │
│    • Outputs: weakness patterns, evaluation reports         │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. optimizer/                                               │
│    • Analyzes error patterns from autoeval                  │
│    • Stores patterns with hierarchical RAG                  │
│    • Generates improved prompts (v1.0 → v1.1 → v1.2...)     │
│    • Scales to 1000s of patterns without prompt bloat       │
│    • Outputs: optimized prompts, weakness catalog           │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. router/                                                  │
│    • Serves OpenAI-compatible API                           │
│    • Routes requests based on weakness patterns             │
│    • Decides: use LLM directly, use RAG, or hybrid          │
│    • Hot-reloads when weakness catalog updates              │
│    • Outputs: production API with intelligent routing       │
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
│   ├── config/        # Weakness catalog
│   ├── core/          # Pattern analysis, storage, optimization
│   ├── rag/           # Hierarchical RAG for pattern storage
│   └── scripts/       # optimize.py (main entry point)
│
├── router/            # Smart routing system
│   ├── api/           # FastAPI application
│   ├── config/        # Router settings
│   ├── core/          # Decision engine, weakness matcher
│   ├── scripts/       # serve_router.py (main entry point)
│   └── services/      # LLM client integrations
│
└── refs/              # Golden reference data (medical CSVs)
    └── golden-refs/   # 5,730+ medical entities
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
#   POE_API_KEY=...        # For GPT-5.1 (question generation & evaluation)
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
    --questions-per-entity=5 \
    --rag-k=8

# Compare baseline vs optimized
python autoeval/scripts/evaluate.py --compare-mode
```

**What happens:**
1. Samples 10 medical entities from `refs/golden-refs/`
2. Generates 30 questions using GPT-5.1
3. Gets 30 answers from DeepSeek
4. Evaluates each answer by direct lookup of golden reference (GPT-5.1 as judge)
5. Identifies error patterns and knowledge gaps

**Outputs:**
- `outputs/reports/{eval_id}/report.json` - Detailed evaluation
- `outputs/reports/{eval_id}/report.md` - Human-readable report

---

### 2. Optimizer

**Purpose:** Convert evaluation results into improved prompts using hierarchical RAG.

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
3. Stores patterns in hierarchical RAG (FAISS + embeddings)
4. Generates improved prompt version (v1.0 → v1.1)
5. Uses RAG to retrieve relevant patterns per question (scales infinitely)

**Outputs:**
- `outputs/prompts/deepseek_system_v1.1.yaml` - Improved prompt
- `outputs/cache/error_patterns/patterns.json` - Pattern database
- `outputs/cache/error_patterns/patterns.index` - FAISS index

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

**Key Innovation:** Hierarchical RAG
- Base prompt stays small (~500 tokens)
- Retrieves top-5 relevant patterns per question
- Scales to 1000s of patterns without prompt bloat
- Total: ~800 tokens per request (efficient!)

---

### 3. Router

**Purpose:** Production API that routes requests intelligently based on LLM weaknesses.

```bash
# Start router API
python router/scripts/serve_router.py --port=8000

# Generate router configuration
python router/scripts/generate_router_config.py

# Test router
python router/scripts/test_router_llm_api.py
```

**What happens:**
1. Loads optimized prompts and weakness patterns
2. Serves OpenAI-compatible API at `http://localhost:8000`
3. For each request:
   - Matches question against weakness patterns
   - Decides: use LLM directly, use RAG, or use both
   - Injects relevant prompt improvements
   - Returns response + routing metadata

**API Endpoints:**
- `POST /v1/chat/completions` - OpenAI-compatible endpoint
- `POST /api/v1/route` - Get routing decision
- `POST /api/v1/prompt` - Get optimized prompt
- `GET /api/v1/stats` - Router statistics
- `POST /api/v1/reload` - Hot-reload weakness catalog

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
# - Detected this is about chronic disease
# - Injected relevant weakness reminders
# - Ensured prevention measures are included
```

**Routing Logic:**
```
Tier 1: Weakness pattern match (HIGHEST PRIORITY)
  → Question hits known DeepSeek weakness
  → Use updated prompt with inline reminders + bad case examples

Tier 2: RAG supplemental info (if no weakness match)
  → Retrieve golden-ref content or similar bad cases
  → Add as context to base prompt

Tier 3: Baseline only (if neither applies)
  → Use base improved prompt without augmentation
```

---

## Workflow Example

```bash
# Week 1: Baseline evaluation
python autoeval/scripts/evaluate.py --sample-size=100 --baseline-only
# Result: Average score 3.2/5.0

# Week 1: Generate optimized prompt
python optimizer/scripts/optimize.py
# Output: deepseek_system_v1.1.yaml (23 weakness patterns)

# Week 2: Re-evaluate with v1.1
python autoeval/scripts/evaluate.py --sample-size=100 --prompt-version=1.1
# Result: Average score 4.1/5.0 (+28% improvement!)

# Week 2: Deploy router
python router/scripts/serve_router.py
# Production API with smart routing

# Week 3: Monitor and iterate
python optimizer/scripts/optimize.py --stats
# Track prompt versions and pattern growth
```

---

## Data Sources

The repository includes golden reference data:

- 疾病.csv - 5,351 diseases
- 检查.csv - 215 examinations
- 手术操作.csv - 140 surgical procedures
- 疫苗.csv - 24 vaccines

**Total:** 5,730 medical entities with detailed information (symptoms, causes, treatments, prevention, etc.)
