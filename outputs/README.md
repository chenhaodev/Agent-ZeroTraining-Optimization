# Outputs Directory

This directory contains all generated outputs from the system.

## Directory Structure

```
outputs/
├── cache/              # Cached data (embeddings, patterns, vector stores)
│   ├── embeddings/     # Cached text embeddings
│   ├── error_patterns/ # Error pattern storage (534 patterns)
│   └── vector_store/   # FAISS vector store indexes
├── logs/               # Execution logs
├── monitoring/         # Performance monitoring reports
├── prompts/            # Generated/optimized system prompts
├── reports/            # Evaluation reports (JSON + Markdown)
└── router/             # Router configuration outputs
```

## Cache Directory (~23MB)

**Important:** The cache directory contains:
- 534 error patterns extracted from evaluations
- FAISS vector indexes for RAG retrieval
- Embedding cache (557 embeddings)

**These are essential for router operation** - do not delete unless rebuilding from scratch.

## Reports Directory

Each evaluation run creates a timestamped directory:
- `eval_YYYYMMDD_HHMMSS/report.json` - Full evaluation data
- `eval_YYYYMMDD_HHMMSS/report.md` - Human-readable report (if generated)
- `eval_YYYYMMDD_HHMMSS/summary.json` - Quick summary

## Git Ignore Rules

Most outputs are ignored by git to keep repository clean:
- Old evaluation reports (keep latest only)
- Large cache files (embeddings, vector indexes)
- Temporary logs

See `.gitignore` for full rules.
