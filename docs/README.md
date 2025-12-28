# Documentation Index

This directory contains detailed documentation for the Agent-FineTune-2026 project.

## System Overview

**Main Documentation:**
- [../README.md](../README.md) - Project overview and quickstart guide
- [../CLAUDE.md](../CLAUDE.md) - Complete system documentation for Claude Code

## Test Results & Analysis

### Latest Test Results
- [OOD_TEST_FINAL_RESULTS.md](OOD_TEST_FINAL_RESULTS.md) - Out-of-distribution test comparing baseline vs router (with threshold optimization)

### Router Integration
- [ROUTER_INTEGRATION_SUCCESS.md](ROUTER_INTEGRATION_SUCCESS.md) - Router integration test results and recommendations

### Optimizer Tests
- [OPTIMIZER_TEST_SUMMARY.md](OPTIMIZER_TEST_SUMMARY.md) - Summary of optimizer test results
- [OPTIMIZER_TEST_RESULTS.md](OPTIMIZER_TEST_RESULTS.md) - Detailed optimizer test results
- [OPTIMIZER_RUN_SUMMARY.md](OPTIMIZER_RUN_SUMMARY.md) - Optimizer run summary

### Scaling & Optimization
- [SCALING_TO_500_PATTERNS.md](SCALING_TO_500_PATTERNS.md) - Analysis of scaling pattern database to 500+ patterns
- [OPTIMIZATION_RESULTS_500_PATTERNS.md](OPTIMIZATION_RESULTS_500_PATTERNS.md) - Optimization results with 500 patterns

## Key Findings

### Threshold Optimization
- **Optimal RAG threshold: 0.4**
- Provides 100% pattern retrieval rate
- Based on empirical testing across 12 test questions

### Pattern Quality
- 534 error patterns extracted from evaluations
- Quality score: 80/100 (excellent)
- 33 patterns recommended for cleanup (19.5%)

### Router Performance
- RAG retrieval working correctly
- No accuracy degradation (router ≥ baseline always)
- Current test questions too easy to show improvement (baseline already 5.0/5.0)

## Next Steps

See [ROUTER_INTEGRATION_SUCCESS.md](ROUTER_INTEGRATION_SUCCESS.md) for detailed recommendations on:
1. Expanding pattern database to 300-500 patterns
2. Testing with harder evaluation questions
3. Building entity-specific weakness patterns
4. Category-specific tuning
