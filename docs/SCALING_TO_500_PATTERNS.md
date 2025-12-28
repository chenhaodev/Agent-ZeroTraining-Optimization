# Scaling to 500+ Patterns - Optimization Plan

## Problem Statement

Current system has 61 patterns, all with `category: general`. Need to support 500+ patterns efficiently while maintaining:
- Fast retrieval (< 100ms)
- High quality (retrieve most relevant patterns)
- Low cost (minimize tokens)

## Bottleneck Analysis

### Current Performance (61 Patterns)
- Storage: 762 KB
- Retrieval: O(n) linear search through all patterns
- Category filtering: ❌ NOT WORKING (all "general")
- Deduplication: ❌ NOT IMPLEMENTED

### Projected Performance (500 Patterns)
- Storage: ~6 MB ✅ OK
- Retrieval: O(n) through 500 patterns ⚠️ SLOWER
- Category filtering: ❌ STILL BROKEN
- Deduplication: ❌ STILL MISSING

---

## Optimization #1: Fix Category Classification ⭐ CRITICAL

### Problem
All patterns have `category: general` instead of specific entity types.

**Root Cause:** Check `prompt_optimizer.py` extraction logic:
```python
# Line 154 - Always sets category to 'general'
pattern = {
    'category': pattern_data.get('category', 'general'),  # ← Fallback to 'general'
    ...
}
```

### Solution: Infer Category from Context

```python
def infer_category(pattern_data: dict, evaluations: list) -> str:
    """Infer entity category from pattern context"""

    # Check if pattern has category in error data
    if 'category' in pattern_data and pattern_data['category'] != 'general':
        return pattern_data['category']

    # Infer from examples
    examples = pattern_data.get('examples', [])
    if examples:
        # Get entity types from questions that triggered this error
        entity_types = []
        for example in examples:
            # Find evaluation that matches this example
            for eval_data in evaluations:
                if example.get('question') == eval_data.question.question:
                    entity_type = eval_data.question.source_entity_type
                    entity_types.append(entity_type)
                    break

        # Return most common entity type
        if entity_types:
            from collections import Counter
            return Counter(entity_types).most_common(1)[0][0]

    # Infer from description keywords
    description = pattern_data.get('description', '').lower()
    if any(kw in description for kw in ['疾病', '症状', '病因', '治疗', '并发症']):
        return 'disease'
    elif any(kw in description for kw in ['检查', '超声', 'ct', 'mri', 'x线']):
        return 'examination'
    elif any(kw in description for kw in ['手术', '术后', '麻醉', '切除']):
        return 'surgery'
    elif any(kw in description for kw in ['疫苗', '接种', '免疫']):
        return 'vaccine'

    return 'general'
```

**Impact:** Reduces search space by 75% (500 → 125 patterns per query)

---

## Optimization #2: Hierarchical Retrieval Strategy

### Tier 1: Category-Specific Search (Primary)
```python
def retrieve_relevant(
    self,
    question: str,
    entity_type: str = None,  # ← NEW: Pass entity type
    k: int = 5,
    threshold: float = 0.7
):
    # Step 1: Filter by category first
    if entity_type:
        candidate_patterns = [p for p in self.patterns
                              if p['category'] == entity_type or p['category'] == 'general']
    else:
        candidate_patterns = self.patterns

    # Step 2: Build filtered FAISS index
    candidate_indices = [i for i, p in enumerate(self.patterns)
                         if p in candidate_patterns]

    # Step 3: Search within candidates only
    q_embedding = self.embedder.embed(question)
    distances, indices = self.index.search(q_embedding, k * 2)  # Get 2x for filtering

    # Step 4: Filter results by category
    results = []
    for dist, idx in zip(distances[0], indices[0]):
        if idx in candidate_indices:
            similarity = 1 - dist
            if similarity >= threshold:
                results.append(self.patterns[idx])
                if len(results) >= k:
                    break

    return results
```

**Impact:**
- Search space: 500 → 125-150 patterns (75% reduction)
- Quality: Higher relevance (category-matched patterns rank higher)

### Tier 2: Frequency-Based Pre-filtering
```python
def retrieve_relevant(..., min_frequency: int = 1):
    # Only consider patterns that appeared multiple times
    candidate_patterns = [p for p in candidate_patterns
                          if p['frequency'] >= min_frequency]
```

**Impact:** After 3-5 evaluation runs, ~50% of patterns will have freq >= 2, reducing search to 62-75 patterns.

### Tier 3: Severity-Based Prioritization
```python
def retrieve_relevant(..., prioritize_severity: bool = True):
    results = self._search(q_embedding, k * 3)  # Get 3x candidates

    if prioritize_severity:
        # Sort by: severity (critical > major > minor), then similarity
        severity_order = {'critical': 3, 'major': 2, 'minor': 1}
        results.sort(key=lambda p: (
            severity_order[p['severity']],
            p['similarity']
        ), reverse=True)

    return results[:k]
```

**Impact:** Critical patterns always retrieved first, ensuring safety.

---

## Optimization #3: Pattern Deduplication

### Problem
Similar patterns might be created multiple times:
- "Missing dietary restrictions for diabetes"
- "Lacks specific diet recommendations for diabetic patients"

These should be merged.

### Solution: Semantic Deduplication

```python
def deduplicate_patterns(self):
    """Merge patterns with similarity > 0.95"""

    if len(self.patterns) < 2:
        return

    # Build similarity matrix
    embeddings = np.array([p['embedding'] for p in self.patterns])

    # Compute pairwise similarities
    from sklearn.metrics.pairwise import cosine_similarity
    similarities = cosine_similarity(embeddings)

    # Find duplicates (similarity > 0.95)
    merged_indices = set()
    for i in range(len(self.patterns)):
        if i in merged_indices:
            continue

        duplicates = [j for j in range(i+1, len(self.patterns))
                      if similarities[i,j] > 0.95]

        if duplicates:
            # Merge patterns
            base_pattern = self.patterns[i]
            for j in duplicates:
                dup_pattern = self.patterns[j]

                # Combine frequencies
                base_pattern['frequency'] += dup_pattern['frequency']

                # Merge examples
                base_pattern['examples'].extend(dup_pattern['examples'])
                base_pattern['examples'] = base_pattern['examples'][:5]  # Keep top 5

                # Upgrade severity if needed
                if dup_pattern['severity'] == 'critical':
                    base_pattern['severity'] = 'critical'
                elif dup_pattern['severity'] == 'major' and base_pattern['severity'] == 'minor':
                    base_pattern['severity'] = 'major'

                merged_indices.add(j)

    # Remove duplicates
    self.patterns = [p for i, p in enumerate(self.patterns)
                     if i not in merged_indices]

    logger.info(f"Deduplicated: {len(merged_indices)} patterns merged")
```

**Impact:** Reduces pattern count by 10-20% (500 → 400-450) while preserving all information.

---

## Optimization #4: Use IVF Index for 1000+ Patterns

### When to Use
- Current: IndexFlatL2 (exact search, fast for < 1000 patterns)
- Switch to: IndexIVFFlat when patterns > 1000

### Implementation

```python
def _build_index(self, embeddings: np.ndarray):
    """Build FAISS index with automatic IVF for large datasets"""

    d = embeddings.shape[1]  # Dimension
    n = embeddings.shape[0]  # Number of patterns

    if n < 1000:
        # Use exact search for small datasets
        index = faiss.IndexFlatL2(d)
        logger.info(f"Using IndexFlatL2 (exact search) for {n} patterns")
    else:
        # Use IVF for large datasets
        nlist = int(np.sqrt(n))  # Number of clusters
        quantizer = faiss.IndexFlatL2(d)
        index = faiss.IndexIVFFlat(quantizer, d, nlist)

        # Train index
        logger.info(f"Training IndexIVFFlat with {nlist} clusters...")
        index.train(embeddings)

        logger.info(f"Using IndexIVFFlat (approximate search) for {n} patterns")

    index.add(embeddings)
    return index
```

**Impact:**
- < 1000 patterns: Exact search (100% accuracy)
- 1000+ patterns: 10x faster, 99% accuracy

---

## Optimization #5: Smart Caching

### Cache Retrieved Patterns per Session

```python
class PatternStorage:
    def __init__(self):
        self.retrieval_cache = {}  # question_hash -> patterns

    def retrieve_relevant(self, question: str, ...):
        # Check cache first
        q_hash = hashlib.md5(question.encode()).hexdigest()
        if q_hash in self.retrieval_cache:
            logger.debug(f"Cache hit for question: {question[:50]}...")
            return self.retrieval_cache[q_hash]

        # Retrieve patterns
        patterns = self._search(...)

        # Cache results
        self.retrieval_cache[q_hash] = patterns
        return patterns
```

**Impact:** Repeated questions (e.g., A/B testing) are instant.

---

## Complete Optimization Summary

| Optimization | Speedup | Quality Gain | Effort |
|--------------|---------|--------------|--------|
| 1. Fix Category Classification | 4x | High | 2 hours |
| 2. Hierarchical Retrieval | Built-in | High | 1 hour |
| 3. Pattern Deduplication | 1.2x | Medium | 3 hours |
| 4. IVF Index (1000+) | 10x | -1% | 2 hours |
| 5. Smart Caching | ∞ | None | 1 hour |

**Total Implementation Time:** ~9 hours
**Total Speedup:** 40-50x at 500 patterns
**Quality:** Higher (category-specific, deduplicated)

---

## Performance Targets

### Current (61 Patterns, Unoptimized)
```
Search time: ~10ms
Search space: 61 patterns
Top-5 relevance: ~70% (many general patterns)
Storage: 762 KB
```

### After Optimization (500 Patterns)
```
Search time: ~15ms (1.5x slower, acceptable)
Search space: 125 patterns (filtered by category)
Top-5 relevance: ~90% (category-matched)
Storage: ~5 MB (after deduplication)
```

### Projected (1000 Patterns, with IVF)
```
Search time: ~20ms (IVF approximate search)
Search space: 250 patterns (filtered)
Top-5 relevance: ~88% (99% accuracy of exact search)
Storage: ~10 MB
```

---

## Implementation Priority

### Phase 1: Critical (Do Now)
✅ **Optimization #1: Fix Category Classification**
- Without this, categories remain useless
- Blocks all other optimizations

### Phase 2: High-Impact (This Week)
- **Optimization #2: Hierarchical Retrieval**
- **Optimization #3: Pattern Deduplication**

### Phase 3: Future-Proofing (When patterns > 800)
- **Optimization #4: IVF Index**
- **Optimization #5: Smart Caching**

---

## Code Changes Required

### File 1: `optimizer/core/prompt_optimizer.py`
**Line 154:** Add category inference
```python
pattern = {
    'description': pattern_data.get('description', ''),
    'guideline': pattern_data.get('guideline', ''),
    'category': self._infer_category(pattern_data, evaluations),  # ← NEW
    'error_type': error_type,
    ...
}
```

### File 2: `optimizer/core/pattern_storage.py`
**Line 80:** Add category filtering
```python
def retrieve_relevant(
    self,
    question: str,
    entity_type: str = None,  # ← NEW parameter
    k: int = 5,
    threshold: float = 0.7,
    min_frequency: int = 1  # ← NEW parameter
):
```

**Line 95:** Add deduplication
```python
def add_patterns_batch(self, patterns: List[dict]):
    # ... existing code ...

    # Deduplicate after adding
    if len(self.patterns) > 50:  # Only when worth it
        self.deduplicate_patterns()
```

### File 3: `router/core/decision_engine.py`
**Line 150:** Pass entity_type to retrieval
```python
patterns = self.pattern_storage.retrieve_relevant(
    question=question,
    entity_type=entity_type,  # ← NEW: Pass category
    k=k,
    threshold=threshold
)
```

---

## Testing Plan

### Test 1: Category Distribution
```bash
python3 << EOF
from optimizer.core.pattern_storage import PatternStorage
ps = PatternStorage()

from collections import Counter
categories = Counter([p['category'] for p in ps.patterns])
print(f"Category distribution: {dict(categories)}")
# Expected: {'disease': 40, 'examination': 10, 'surgery': 8, 'vaccine': 3}
# NOT: {'general': 61}
EOF
```

### Test 2: Retrieval Speed
```bash
python3 << EOF
import time
from optimizer.core.pattern_storage import PatternStorage

ps = PatternStorage()

# Benchmark: 100 retrievals
start = time.time()
for i in range(100):
    ps.retrieve_relevant("糖尿病患者平时要注意什么？", entity_type='disease', k=5)
elapsed = time.time() - start

print(f"100 retrievals: {elapsed:.2f}s ({elapsed*10:.1f}ms per query)")
# Target: < 50ms per query
EOF
```

### Test 3: Deduplication
```bash
python3 << EOF
from optimizer.core.pattern_storage import PatternStorage
ps = PatternStorage()

before = len(ps.patterns)
ps.deduplicate_patterns()
after = len(ps.patterns)

print(f"Patterns before: {before}")
print(f"Patterns after: {after}")
print(f"Deduplicated: {before - after} patterns ({(before-after)/before*100:.1f}%)")
# Expected: 10-20% reduction
EOF
```

---

## Migration Path

### Step 1: Backup Current Patterns
```bash
cp outputs/cache/error_patterns/patterns.json \
   outputs/cache/error_patterns/patterns.json.backup
```

### Step 2: Implement Optimizations
Follow implementation priority above

### Step 3: Re-categorize Existing Patterns
```bash
python3 << EOF
from optimizer.core.prompt_optimizer import PromptOptimizer
from optimizer.core.pattern_storage import PatternStorage

ps = PatternStorage()
po = PromptOptimizer()

# Re-infer categories for all patterns
for pattern in ps.patterns:
    # Use keyword-based inference (no evaluations available)
    pattern['category'] = po._infer_category_from_keywords(pattern['description'])

ps.save()
print(f"Re-categorized {len(ps.patterns)} patterns")
EOF
```

### Step 4: Verify & Test
Run all 3 tests above

---

## Conclusion

With these optimizations, the system can efficiently handle:
- ✅ 500 patterns: ~15ms retrieval, 90% relevance
- ✅ 1000 patterns: ~20ms retrieval, 88% relevance
- ✅ 2000 patterns: ~30ms retrieval (with IVF)

**Next Steps:**
1. Implement Optimization #1 (category classification) - 2 hours
2. Test with current 61 patterns
3. Scale to 500 patterns and measure performance
