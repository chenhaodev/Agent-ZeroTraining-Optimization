# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an **LLM self-improvement system** using dynamic prompt engineering. It learns from LLM mistakes, extracts error patterns into a searchable database, then dynamically injects relevant reminders into prompts to avoid repeating errors.

**Core Innovation:** This is NOT traditional RAG (doesn't retrieve external knowledge documents) and NOT fine-tuning (doesn't retrain model weights). Instead, it performs **dynamic prompt engineering** by selecting and combining relevant error pattern reminders per question.

## Architecture - Three Integrated Systems

```
[autoeval] → Identify errors → [optimizer] → Build pattern DB → [router] → Serve enhanced API
```

1. **autoeval/** - Auto-evaluation system
   - Samples medical entities from golden references (5,730+ entities in `refs/golden-refs/dxys/`)
   - Generates questions using OpenAI GPT-4.1
   - Gets answers from DeepSeek
   - Evaluates with direct golden reference lookup (NOT RAG-based evaluation)
   - Outputs detailed evaluation reports

2. **optimizer/** - Prompt optimization system
   - Analyzes evaluation reports to extract error patterns
   - Stores patterns in FAISS vector database with embeddings
   - Generates versioned prompts (v1.0 → v1.1 → v1.2...)
   - Enables semantic search for relevant patterns

3. **router/** - Production API gateway
   - FastAPI server with OpenAI-compatible `/v1/chat/completions` endpoint
   - Tiered routing: Weakness matching (Tier 1) → Pattern retrieval (Tier 2) → Category rules (Tier 3)
   - Dynamic prompt enhancement by retrieving relevant error patterns
   - Hot-reload capability when pattern database updates

## Common Commands

### Development Workflow

```bash
# 1. Run evaluation (small sample for testing)
python autoeval/scripts/evaluate.py --sample-size=10

# 2. Generate optimized prompts from evaluation
python optimizer/scripts/optimize.py

# 3. Test router API
python router/scripts/serve_router.py --reload  # Development mode
python router/scripts/test_router_llm_api.py   # Test endpoint

# 4. Compare baseline vs optimized
python router/scripts/compare_baseline_vs_router.py
```

### Full Evaluation

```bash
# Standard evaluation (100 entities, 5 questions each = 500 Q&A pairs)
python autoeval/scripts/evaluate.py --sample-size=100

# Custom configuration
python autoeval/scripts/evaluate.py \
    --sample-size=50 \
    --questions-per-entity=3 \
    --max-workers=10

# A/B comparison mode
python autoeval/scripts/evaluate.py --compare-mode

# Use preset configurations
python autoeval/scripts/evaluate.py --preset=balanced
# Available presets: baseline, cost_optimized, balanced, high_accuracy, maximum_quality, fast_iteration
```

### Optimization

```bash
# Optimize using latest evaluation
python optimizer/scripts/optimize.py

# Optimize specific evaluation report
python optimizer/scripts/optimize.py --eval-report=eval_20251228_001

# Show statistics
python optimizer/scripts/optimize.py --stats

# List all stored patterns
python optimizer/scripts/optimize.py --list-patterns
```

### Router Server

```bash
# Development mode (auto-reload on file changes)
python router/scripts/serve_router.py --reload

# Production mode (multiple workers)
python router/scripts/serve_router.py --workers=4

# Custom host/port
python router/scripts/serve_router.py --host=0.0.0.0 --port=8080
```

### Utilities

```bash
# Analyze pattern quality and find duplicates
python tools/analyze_patterns.py

# Build entity-specific weakness mappings
python tools/build_weakness_patterns.py

# Monitor performance metrics
python tools/monitor_performance.py

# Optimize retrieval thresholds
python tools/optimize_threshold.py

# List all evaluation reports
python tools/list_reports.py

# Clean up repository before commit
bash tools/cleanup_repo.sh
```

## Key Technical Concepts

### Direct Lookup vs Pattern Retrieval

This is a common source of confusion:

- **Evaluation uses direct lookup** (autoeval/services/evaluator.py)
  - Questions contain `source_entity_name` field
  - Evaluator uses direct lookup to find exact golden reference
  - No RAG/vector search needed during evaluation

- **Answer generation uses pattern retrieval** (autoeval/services/answer_generator.py)
  - Retrieves similar error patterns to inject into prompts
  - Uses FAISS vector search for semantic similarity
  - This is intentional: evaluation needs exact reference, answering benefits from similar patterns

### Tiered Routing Strategy

The router uses a 3-tier priority system:

1. **Tier 1 (Highest):** Weakness pattern matching
   - Checks known weakness categories from `router/config/deepseek_weaknesses.json`
   - Matches using keywords, question patterns, entity types
   - Injects targeted reminders for known weak areas

2. **Tier 2:** Pattern retrieval
   - Semantic search for relevant error patterns in vector database
   - Uses cosine similarity with configurable threshold
   - Retrieves top-k patterns (default: 5)

3. **Tier 3:** Category-specific rules
   - Hard-coded rules for diseases, vaccines, examinations, surgeries
   - Ensures minimum quality standards

### Prompt Versioning

- Versions increment: `v1.0` → `v1.1` → `v1.2`
- Stored in: `outputs/prompts/deepseek_system_v{version}.yaml`
- Each version includes:
  - Metadata: version, updated_at, changes
  - Memory sections: pattern reminders organized by category
  - Base instructions: core LLM behavior guidelines

### Configuration Management

- Single `.env` file shared across all modules
- Module-specific prefixes (e.g., `ROUTER_*` for router settings)
- Pydantic Settings for type-safe configuration
- Singleton pattern: `get_settings()` returns global instance

Example `.env` structure:
```bash
# API Keys
OPENAI_API_KEY=...      # For GPT-4.1 (question generation) and embeddings
DEEPSEEK_API_KEY=...    # For answer generation and evaluation

# Pattern Retrieval Configuration
RETRIEVAL_TOP_K=5                    # Number of patterns to retrieve per question
PATTERN_RELEVANCE_THRESHOLD=0.65     # Minimum similarity score (0.0=disabled, 0.65=recommended)
USE_SMART_ROUTING=false              # Skip pattern retrieval for predicted OOD questions

# Embedding Configuration
EMBEDDING_MODEL=text-embedding-3-large
EMBEDDING_DIMENSION=3072
USE_EMBEDDING_CACHE=true
```

## Code Organization Patterns

### Singleton Pattern

Many core components use singletons accessed via `get_*()` functions:

```python
from autoeval.config.settings import get_settings
from optimizer.pattern_db.vector_store import get_vector_store
from optimizer.pattern_db.retriever import get_retriever
from router.core.decision_engine import get_decision_engine
```

### Service Classes

Reusable service classes for API interactions:
- `OpenAIClient` - OpenAI API wrapper
- `DeepSeekClient` - DeepSeek API wrapper
- `QuestionGenerator` - Question generation service
- `AnswerGenerator` - Answer generation service
- `Evaluator` - Evaluation service

### Pydantic Models

Type-safe data models throughout:
- `MedicalEntity` (base): `Disease`, `Examination`, `Surgery`, `Vaccine`
- `Question` - Generated test questions
- `Answer` - LLM responses
- `Evaluation` - Evaluation results with scores and errors
- `Error` - Individual error details

### Parallel Processing

Uses `ThreadPoolExecutor` for concurrent API calls:

```python
# In autoeval/scripts/evaluate.py
with ThreadPoolExecutor(max_workers=max_workers) as executor:
    # Process multiple questions in parallel
    futures = [executor.submit(generator.generate, entity) for entity in entities]
```

Default `max_workers=5` to avoid rate limits.

## Data Flow

```
1. Load golden references (refs/golden-refs/dxys/*.csv)
   → MedicalEntity objects

2. Sample entities (stratified sampling)
   → Build FAISS index for pattern retrieval

3. Generate questions (OpenAI GPT-4.1)
   → Question objects

4. Generate answers (DeepSeek with dynamic prompts)
   → Optional pattern retrieval for prompt enhancement
   → Answer objects

5. Evaluate (direct golden-ref lookup + LLM judge)
   → Parallel processing with ThreadPoolExecutor
   → Evaluation objects with scores and errors

6. Extract patterns (PatternAnalyzer)
   → Error patterns + Knowledge gaps

7. Store patterns (PatternStorage + FAISS)
   → JSON storage + Vector embeddings

8. Generate optimized prompt (PromptOptimizer)
   → Versioned YAML prompt files

9. Serve via router (FastAPI)
   → Weakness matching → Pattern retrieval → Enhanced prompts
```

## File Locations

### Configuration
- `.env` - Environment variables (not committed)
- `.env.example` - Template with all required variables
- `autoeval/config/settings.py` - Pydantic settings class

### Data
- `refs/golden-refs/dxys/*.csv` - Golden medical references (5,730 entities)
- `outputs/cache/vector_store/` - FAISS index (index.faiss, metadata.pkl, texts.pkl)
- `outputs/cache/error_patterns/` - Error pattern storage (patterns.json, patterns.index)
- `outputs/cache/embeddings/` - Embedding cache (embedding_cache.pkl)

### Outputs
- `outputs/reports/eval_*/` - Evaluation reports (report.json, report.md)
- `outputs/prompts/` - Versioned prompt files (deepseek_system_v*.yaml)
- `outputs/logs/` - Log files (evaluation.log, router.log)

### Router Configuration
- `router/config/deepseek_weaknesses.json` - Known weakness patterns
- `router/refs/entity_names.json` - Entity-specific weakness mappings

## Hot-Reload Capability

The router can reload configuration without restart:

1. Automatic reload when files change:
   - `router/config/deepseek_weaknesses.json`
   - `router/refs/entity_names.json`

2. Manual reload via API:
   ```bash
   curl -X POST http://localhost:8000/api/v1/reload
   ```

3. Enable via environment variable:
   ```bash
   ROUTER_ENABLE_HOT_RELOAD=true
   ```

## Testing Strategy

This project uses **real-world evaluation** rather than unit tests:

1. **Integration Testing via Evaluation**
   ```bash
   python autoeval/scripts/evaluate.py --sample-size=10  # Fast smoke test
   ```

2. **A/B Comparison Testing**
   ```bash
   python router/scripts/compare_baseline_vs_router.py
   ```

3. **Extended A/B Tests**
   ```bash
   python router/scripts/ab_test_extended.py
   ```

**Evaluation Metrics:**
- 5-dimensional scoring: accuracy, completeness, relevance, clarity, safety
- Acceptance rate (boolean threshold)
- Error categorization: factual_error, incomplete, misleading, irrelevant, unsafe, unclear
- Error severity: critical, major, minor

## Common Issues

### "No patterns retrieved"
- Check `PATTERN_RELEVANCE_THRESHOLD` in `.env` (recommended: 0.65)
- Verify pattern cache exists: `outputs/cache/error_patterns/patterns.json`
- Check vector store: `outputs/cache/vector_store/index.faiss`
- Run: `python optimizer/scripts/optimize.py --stats`

### "Vector store not built"
- Run optimizer first: `python optimizer/scripts/optimize.py`
- Or set `REBUILD_VECTOR_INDEX=true` in `.env`

### "Reference entity not found"
- Questions must have valid `source_entity_name` field
- Check entity name matches exactly in `refs/golden-refs/dxys/*.csv`
- Use case-sensitive matching

### API rate limits
- Reduce `max_workers` in evaluation script
- Default is 5, try `--max-workers=3`
- Add delays via `API_RETRY_WAIT_MIN/MAX` in settings

### Import errors after refactoring
- This codebase was recently refactored from "RAG" to "pattern_db" terminology
- Check for any remaining `from optimizer.rag.` imports (should be `optimizer.pattern_db.`)
- Verify settings use `PATTERN_RELEVANCE_THRESHOLD` not `RAG_RELEVANCE_THRESHOLD`

## Cleanup Before Commit

```bash
bash tools/cleanup_repo.sh
```

This removes:
- Python cache files (`__pycache__`, `*.pyc`)
- macOS files (`.DS_Store`)
- Temporary log files
- Old evaluation reports (keeps latest 5)
- Backup files (`*.bak`, `*.tmp`)

## Router API Usage

The router serves an OpenAI-compatible API:

```python
from openai import OpenAI

# Just change the base_url - that's it!
client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="your-deepseek-api-key"
)

response = client.chat.completions.create(
    model="deepseek-chat",
    messages=[
        {"role": "user", "content": "What is diabetes?"}
    ],
    stream=True  # Streaming supported
)

for chunk in response:
    print(chunk.choices[0].delta.content, end='')
```

**How it works:**
1. Router searches pattern database for similar past errors
2. If matches found → injects error reminders into system prompt
3. Forwards enhanced request to DeepSeek API
4. Returns response with routing metadata

**Endpoints:**
- `POST /v1/chat/completions` - OpenAI-compatible chat endpoint
- `POST /api/v1/reload` - Manual reload of configuration
- `GET /docs` - Swagger UI documentation

## Iterative Improvement Workflow

```bash
# Step 1: Run evaluation to find errors
python autoeval/scripts/evaluate.py --sample-size=100

# Step 2: Extract patterns and optimize prompts
python optimizer/scripts/optimize.py

# Step 3: Test improvement
python router/scripts/compare_baseline_vs_router.py

# Step 4: Deploy router (if improvement confirmed)
python router/scripts/serve_router.py --workers=4

# Step 5: Iterate - run more evaluations and accumulate patterns
python autoeval/scripts/evaluate.py --sample-size=50
python optimizer/scripts/optimize.py
# Pattern database grows over time
```

## Key Files to Understand

### Core Data Models
- `autoeval/core/models.py` - All Pydantic models (MedicalEntity, Question, Answer, Evaluation, Error)

### Main Entry Points
- `autoeval/scripts/evaluate.py` - Main evaluation script (400+ lines)
- `optimizer/scripts/optimize.py` - Main optimization script
- `router/scripts/serve_router.py` - Router server startup

### Critical Components
- `autoeval/services/evaluator.py` - Direct lookup evaluation logic (NOT RAG-based)
- `optimizer/pattern_db/vector_store.py` - FAISS vector store implementation
- `router/core/decision_engine.py` - Tiered routing logic
- `router/core/weakness_matcher.py` - Weakness pattern matching (Tier 1)
- `optimizer/pattern_db/retriever.py` - Pattern retrieval (Tier 2)

### Configuration
- `autoeval/config/settings.py` - All settings with defaults and env var mapping
- `.env.example` - Complete list of available environment variables
