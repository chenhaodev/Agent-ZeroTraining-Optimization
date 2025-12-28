# Contributing Guide

## Development Workflow

### Prerequisites

```bash
# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env and add your API keys
```

### Running Tests

```bash
# Run auto-evaluation
python autoeval/scripts/evaluate.py --sample-size 10

# Run optimizer
python optimizer/scripts/optimize.py

# Run router tests
python router/scripts/test_router_llm_api.py

# Run A/B comparison
python router/scripts/compare_baseline_vs_router.py
```

### Tools

Utility scripts in `tools/`:
- `optimize_threshold.py` - Find optimal RAG retrieval threshold
- `analyze_patterns.py` - Analyze pattern quality and find duplicates
- `monitor_performance.py` - Monitor system performance metrics
- `build_weakness_patterns.py` - Build entity-specific weakness patterns

### Cleanup Before Commit

```bash
# Run cleanup script
./cleanup_repo.sh
```

This removes:
- Python cache files (`__pycache__`, `*.pyc`)
- macOS files (`.DS_Store`)
- Temporary log files
- Old evaluation reports (keeps latest)

## Project Structure

```
.
├── autoeval/          # Auto-evaluation module
│   ├── config/        # Settings and configuration
│   ├── core/          # Data models, loaders, samplers
│   ├── scripts/       # Evaluation scripts
│   ├── services/      # API clients, generators, evaluators
│   └── utils/         # Utilities (JSON parser, reporting)
│
├── optimizer/         # Prompt optimization module
│   ├── core/          # Pattern analysis, storage, optimization
│   ├── rag/           # RAG infrastructure (embeddings, vector store)
│   ├── scripts/       # Optimization scripts
│   └── services/      # Optimizer services
│
├── router/            # Smart routing module
│   ├── api/           # FastAPI service endpoints
│   ├── core/          # Decision engine, weakness matcher
│   ├── scripts/       # Router test scripts
│   └── services/      # LLM client
│
├── tools/             # Utility tools
├── config/            # Global configuration
│   └── prompts/       # Prompt templates (YAML)
├── outputs/           # Generated outputs (cached, reported)
├── docs/              # Documentation
└── refs/              # Reference data (golden-refs)
```

## Code Style

- Follow PEP 8
- Use type hints
- Document classes and functions with docstrings
- Use loguru for logging

## Key Configuration Files

- `.env` - API keys and environment variables (not committed)
- `.env.example` - Template for environment variables
- `config/prompts/*.yaml` - Prompt templates
- `outputs/cache/error_patterns/patterns.json` - Error pattern database

## Performance Monitoring

Check system health:
```bash
python tools/monitor_performance.py
```

Metrics tracked:
- Retrieval latency (P50, P95, P99)
- Cache hit rates
- Pattern quality scores
- System health score

## Common Issues

### "No patterns retrieved"
- Check RAG threshold (should be 0.4)
- Verify pattern cache exists: `outputs/cache/error_patterns/patterns.json`
- Check embedding cache: `outputs/cache/embeddings/embedding_cache.pkl`

### "API key not found"
- Ensure `.env` file exists with `DEEPSEEK_API_KEY` and `POE_API_KEY`
- Check environment variables are loaded

### "Reference entity not found"
- Check entity name matches exactly in golden-refs
- Consider adding entity aliases for common variations

## Commit Guidelines

Before committing:
1. Run `./cleanup_repo.sh` to remove temp files
2. Ensure tests pass
3. Update documentation if needed
4. Use clear, descriptive commit messages

Commit message format:
```
<type>: <description>

[optional body]

[optional footer]
```

Types: `feat`, `fix`, `docs`, `test`, `refactor`, `perf`, `chore`

Example:
```
feat: Add threshold optimization for RAG retrieval

- Implemented threshold testing across 0.3-0.7 range
- Found optimal threshold of 0.4 (100% retrieval rate)
- Updated router to use optimized threshold
```
