# Pattern Clustering & LLM Abstraction

## Overview

The clustering + abstraction system addresses the **representativeness problem** in pattern selection for the base prompt. Instead of selecting patterns by frequency alone (which creates bias), we use:

1. **K-means clustering** on pattern embeddings for diversity
2. **LLM abstraction** to generate general reminders from pattern clusters
3. **Three-tier architecture** for comprehensive coverage

---

## The Problem

**Before (Frequency-Based Selection):**
```
722 total patterns
├─ 713 patterns (freq=1) → IGNORED ❌
├─ 6 patterns (freq=5-12) → Maybe included
└─ 3 patterns (freq=149) → Always included ⚠️ All about SAME entity!

Result: Base prompt contains only 9 patterns, heavily biased toward one entity
```

**Issues:**
- 98.8% of patterns (freq=1) are never used in base prompt
- No diversity across medical domains
- Over-representation of repeated errors
- Under-representation of unique knowledge gaps

---

## The Solution

### Three-Tier Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ Tier 1: General Reminders (10 reminders)                   │
│  - LLM-abstracted from pattern clusters                    │
│  - Broad, generalizable guidelines                         │
│  - Example: "关于半月板损伤，要提到血液供应分区及其临床意义"    │
├─────────────────────────────────────────────────────────────┤
│ Tier 2: Representative Patterns (15 patterns)              │
│  - K-means clustered, 1 per cluster                        │
│  - Diverse across medical domains                          │
│  - Specific, actionable reminders                          │
├─────────────────────────────────────────────────────────────┤
│ Tier 3: All Patterns in FAISS (722 patterns)               │
│  - Runtime retrieval via semantic search                   │
│  - Question-specific pattern matching                      │
│  - Dynamic prompt enhancement                              │
└─────────────────────────────────────────────────────────────┘
```

---

## How It Works

### Step 1: Pattern Clustering

```python
from optimizer.core.pattern_clustering import PatternClusterer

# Initialize
clusterer = PatternClusterer(embedder, pattern_storage)

# Cluster patterns using k-means
clusters = clusterer.cluster_patterns(
    n_clusters=20,        # Create 20 clusters
    min_cluster_size=3    # Merge small clusters
)

# Result: 20 diverse clusters
# Cluster 0: 半月板损伤 related patterns (45 patterns)
# Cluster 1: 糖尿病 related patterns (38 patterns)
# Cluster 2: 疫苗 related patterns (22 patterns)
# ...
```

**Benefits:**
- Groups similar patterns together
- Ensures diversity in selection
- Uses existing embeddings (no extra API calls)

### Step 2: Representative Selection

```python
# Select 1 representative per cluster
representatives = clusterer.select_representatives(
    clusters,
    per_cluster=1,
    strategy="balanced"  # Mix of frequency + severity
)

# Result: 20 diverse patterns (1 from each cluster)
# - Pattern from 半月板损伤 cluster (highest freq in that cluster)
# - Pattern from 糖尿病 cluster
# - Pattern from 疫苗 cluster
# ...
```

**Strategies:**
- `highest_frequency`: Pick most common in cluster
- `highest_severity`: Pick most critical in cluster
- `balanced`: Combine frequency + severity

### Step 3: LLM Abstraction

```python
from optimizer.core.pattern_abstractor import PatternAbstractor

abstractor = PatternAbstractor(api_client)

# Abstract each cluster into general reminder
abstractions = abstractor.abstract_all_clusters(
    clusters,
    min_cluster_size=5  # Only abstract large clusters
)

# Example input (Cluster with 45 patterns about 半月板损伤):
# 1. [incomplete] AI回答未提及半月板损伤的血液供应分区（红-红区、红-白区、白-白区）...
# 2. [incomplete] AI回答未提及半月板损伤可能合并其他膝关节结构损伤...
# 3. [incomplete] AI回答未提及半月板损伤的慢性症状表现...
# ...

# Example output (LLM-generated general reminder):
# "关于半月板损伤，需要系统阐述：(1)血液供应分区及其对愈合的影响；(2)可能的合并损伤；
#  (3)急性与慢性症状的差异；(4)诊断与治疗方案的选择依据。"
```

**LLM Prompt:**
```
你是医疗AI系统的提示词优化专家。分析这些错误模式的共同点，
生成简洁、通用、可操作的指导原则。

要求：
1. 简洁：1-2句话，不超过100字
2. 通用：提取共性，而非重复具体细节
3. 可操作：明确告诉AI应该做什么
4. 医疗专业：使用准确的医疗术语
```

---

## Generated Prompt Structure

```yaml
version: '1.9'
last_updated: '2025-12-28'

system_prompt: |
  你是一位专业、耐心、友善的医疗健康助手...

memory:
  # Tier 1: General Reminders (LLM-abstracted)
  general_reminders:
    - "关于半月板损伤，需要系统阐述血液供应分区、合并损伤、症状差异及治疗选择依据"
    - "回答糖尿病相关问题时，要区分1型和2型的病因、症状和治疗差异"
    - "对于疫苗类问题，应明确接种时机、禁忌症、接种后注意事项和不良反应"
    - ...

  # Tier 2: Representative Patterns (diverse, specific)
  representative_patterns:
    mistakes:
      - "避免incomplete错误：关于半月板损伤要提到血液供应分区"
      - "避免incomplete错误：糖尿病并发症要分类阐述（急性、感染性、慢性）"
      - ...
    guidelines:
      - "避免factual_error：洗澡水温应为32-37℃，不是37-40℃"
      - "避免misleading：推荐润肤油时要警告避免橄榄油等植物油"
      - ...

  metadata:
    clustering_used: true
    n_clusters: 20
    n_representatives: 15
    n_general_reminders: 10
    total_patterns_in_storage: 722

changes:
  from_version: '1.8'
  patterns_added: 0
  total_patterns_in_storage: 722
  improvements:
    - "Generated 10 general reminders via LLM abstraction"
    - "Selected 15 representative patterns from 20 clusters"
    - "Improved diversity and coverage across medical domains"
  clustering_stats:
    n_clusters: 20
    avg_cluster_size: 36.1
    abstractions_generated: 12
```

---

## Usage

### Option 1: Test with Existing Patterns

```bash
# Run clustering-based optimization on latest evaluation
python optimizer/scripts/optimize_with_clustering.py

# This will:
# 1. Load evaluation report
# 2. Cluster existing 722 patterns
# 3. Generate general reminders via LLM
# 4. Create new prompt version with clustering
```

### Option 2: Integrate into Main Optimizer

```bash
# Modify optimizer/scripts/optimize.py to use clustering
python optimizer/scripts/optimize.py --use-clustering
```

---

## Benefits

### 1. **Diversity**
- Covers all medical domains (diseases, vaccines, exams, surgeries)
- No over-representation of single entities
- Balanced across error types

### 2. **Generalizability**
- LLM abstracts specific patterns into broader guidelines
- Applies to entities not seen in training
- Better OOD (out-of-distribution) performance

### 3. **Efficiency**
- Base prompt stays compact (10 reminders + 15 patterns)
- All 722 patterns available for runtime retrieval
- Faster inference, same coverage

### 4. **Interpretability**
- General reminders are human-readable
- Clustering metadata shows pattern organization
- Easier to audit and improve

---

## Comparison

| Metric | Frequency-Based | Clustering + Abstraction |
|--------|-----------------|--------------------------|
| **Patterns in base prompt** | 9 | 10 reminders + 15 patterns |
| **Diversity** | Low (3 from same entity) | High (20 clusters) |
| **Coverage** | 1.2% of patterns | 100% via 3 tiers |
| **Generalizability** | Low | High (LLM-abstracted) |
| **OOD performance** | Poor | Good |
| **Interpretability** | Medium | High |

---

## Configuration

### Clustering Parameters

```python
optimizer.generate_updated_prompt_with_clustering(
    analysis,
    n_clusters=20,           # Number of clusters (adjust based on pattern count)
    n_representatives=15,    # Representatives for base prompt
    n_general_reminders=10,  # General reminders to generate
    incremental=True         # Build on previous version
)
```

**Guidelines:**
- `n_clusters`: ~10-30 depending on total patterns (rule of thumb: total_patterns / 20)
- `n_representatives`: ~10-20 for base prompt (balance coverage vs. size)
- `n_general_reminders`: ~5-15 (broader is better, but LLM cost increases)

### Clustering Strategy

```python
representatives = clusterer.select_representatives(
    clusters,
    per_cluster=1,
    strategy="balanced"  # or "highest_frequency" or "highest_severity"
)
```

---

## Output Files

After running clustering-based optimization:

```
outputs/prompts/
├── deepseek_system_v1.9.yaml           # New prompt with clustering
└── clustering_metadata_v1.9.json       # Detailed clustering info

outputs/cache/error_patterns/
├── patterns.json                        # All 722 patterns
└── patterns.index                       # FAISS index (unchanged)
```

**clustering_metadata_v1.9.json** contains:
- All cluster assignments
- Abstraction results for each cluster
- Representative pattern selections
- Clustering statistics

---

## Future Improvements

1. **Hierarchical Clustering**
   - Multi-level clustering (medical domain → entity type → specific issue)
   - Better organization of knowledge

2. **Adaptive Clustering**
   - Automatically determine optimal `n_clusters`
   - Use silhouette score or elbow method

3. **Category-Aware Clustering**
   - Enforce diversity across categories
   - Ensure each category has representation

4. **Iterative Refinement**
   - Use LLM to evaluate abstraction quality
   - Regenerate poor abstractions

5. **Prompt A/B Testing**
   - Compare frequency-based vs clustering-based prompts
   - Measure OOD generalization improvement
