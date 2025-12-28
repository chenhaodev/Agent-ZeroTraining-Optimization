#!/usr/bin/env python3
"""
Performance Monitoring Tool
Tracks retrieval latency, cache hit rates, and answer quality trends
"""
import sys
import json
import time
from pathlib import Path
from collections import defaultdict
from datetime import datetime

# Add repo root to path
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root))

from optimizer.core.pattern_storage import PatternStorage
from optimizer.rag.embedder import Embedder
from loguru import logger


def benchmark_retrieval_speed(pattern_storage: PatternStorage, num_queries: int = 100) -> dict:
    """Benchmark pattern retrieval speed"""
    logger.info(f"Benchmarking retrieval speed ({num_queries} queries)...")

    test_questions = [
        "糖尿病患者平时要注意什么？",
        "做CT检查前需要注意什么？",
        "阑尾炎手术后多久可以正常饮食？",
        "HPV疫苗打几针？",
        "膝关节半月板损伤是什么病？",
    ]

    latencies = []

    for i in range(num_queries):
        question = test_questions[i % len(test_questions)]
        category = ["diseases", "examinations", "surgeries", "vaccines"][i % 4]

        start = time.time()
        patterns = pattern_storage.retrieve_relevant(
            question=question,
            category=category,
            k=3,
            threshold=0.5
        )
        latency = (time.time() - start) * 1000  # Convert to ms

        latencies.append(latency)

    return {
        "num_queries": num_queries,
        "avg_latency_ms": sum(latencies) / len(latencies),
        "min_latency_ms": min(latencies),
        "max_latency_ms": max(latencies),
        "p50_latency_ms": sorted(latencies)[len(latencies) // 2],
        "p95_latency_ms": sorted(latencies)[int(len(latencies) * 0.95)],
        "p99_latency_ms": sorted(latencies)[int(len(latencies) * 0.99)],
    }


def analyze_cache_hit_rate(embedder: Embedder) -> dict:
    """Analyze embedding cache hit rate"""
    logger.info("Analyzing cache hit rate...")

    cache_file = Path("outputs/cache/embeddings/embeddings_cache.pkl")

    if not cache_file.exists():
        return {
            "cache_exists": False,
            "cached_embeddings": 0
        }

    import pickle
    with open(cache_file, 'rb') as f:
        cache = pickle.load(f)

    return {
        "cache_exists": True,
        "cached_embeddings": len(cache),
        "cache_size_mb": cache_file.stat().st_size / (1024 * 1024)
    }


def analyze_pattern_storage(pattern_storage: PatternStorage) -> dict:
    """Analyze pattern storage metrics"""
    logger.info("Analyzing pattern storage...")

    patterns = pattern_storage.patterns
    pattern_count = len(patterns)

    # Category distribution
    from collections import Counter
    category_counts = Counter([p.get('category', 'general') for p in patterns])

    # Frequency distribution
    freq_counts = Counter([p.get('frequency', 1) for p in patterns])

    # Storage size
    patterns_file = Path("outputs/cache/error_patterns/patterns.json")
    index_file = Path("outputs/cache/error_patterns/patterns.index")

    storage_size_mb = 0
    if patterns_file.exists():
        storage_size_mb += patterns_file.stat().st_size / (1024 * 1024)
    if index_file.exists():
        storage_size_mb += index_file.stat().st_size / (1024 * 1024)

    return {
        "total_patterns": pattern_count,
        "storage_size_mb": storage_size_mb,
        "category_distribution": dict(category_counts),
        "frequency_distribution": dict(freq_counts),
        "avg_patterns_per_category": pattern_count / len(category_counts) if category_counts else 0
    }


def track_quality_trends(reports_dir: Path = Path("outputs/reports")) -> dict:
    """Track answer quality trends over time"""
    logger.info("Tracking quality trends...")

    if not reports_dir.exists():
        return {"has_data": False}

    # Find all evaluation reports
    report_files = sorted(reports_dir.glob("*/summary.json"))

    if not report_files:
        return {"has_data": False}

    trends = []

    for report_file in report_files:
        try:
            with open(report_file, 'r', encoding='utf-8') as f:
                summary = json.load(f)

            # Extract key metrics
            trends.append({
                "timestamp": summary.get("timestamp", "unknown"),
                "report_id": summary.get("report_id", "unknown"),
                "overall_score": summary.get("overall_score", 0),
                "acceptance_rate": summary.get("acceptance_rate", 0),
                "total_evaluations": summary.get("total_evaluations", 0),
                "dimension_scores": summary.get("dimension_scores", {})
            })
        except Exception as e:
            logger.warning(f"Failed to load report {report_file}: {e}")
            continue

    if not trends:
        return {"has_data": False}

    # Calculate trend statistics
    overall_scores = [t["overall_score"] for t in trends]
    acceptance_rates = [t["acceptance_rate"] for t in trends]

    return {
        "has_data": True,
        "total_reports": len(trends),
        "latest_score": overall_scores[-1] if overall_scores else 0,
        "avg_score": sum(overall_scores) / len(overall_scores) if overall_scores else 0,
        "score_trend": "improving" if len(overall_scores) > 1 and overall_scores[-1] > overall_scores[0] else "stable",
        "latest_acceptance_rate": acceptance_rates[-1] if acceptance_rates else 0,
        "avg_acceptance_rate": sum(acceptance_rates) / len(acceptance_rates) if acceptance_rates else 0,
        "reports": trends
    }


def main():
    """Run performance monitoring"""
    logger.info("=" * 80)
    logger.info("Performance Monitoring Dashboard")
    logger.info("=" * 80)

    # Initialize components
    logger.info("\n[Setup] Initializing components...")
    pattern_storage = PatternStorage()
    embedder = Embedder()

    # Run benchmarks
    results = {}

    logger.info("\n[1/4] Benchmarking retrieval speed...")
    results["retrieval"] = benchmark_retrieval_speed(pattern_storage, num_queries=100)

    logger.info("\n[2/4] Analyzing cache performance...")
    results["cache"] = analyze_cache_hit_rate(embedder)

    logger.info("\n[3/4] Analyzing pattern storage...")
    results["storage"] = analyze_pattern_storage(pattern_storage)

    logger.info("\n[4/4] Tracking quality trends...")
    results["quality_trends"] = track_quality_trends()

    # Print dashboard
    print("\n" + "=" * 80)
    print("PERFORMANCE DASHBOARD")
    print("=" * 80)

    # Retrieval Performance
    print("\n⚡ Retrieval Performance:")
    print("-" * 80)
    retrieval = results["retrieval"]
    print(f"   Queries tested: {retrieval['num_queries']}")
    print(f"   Average latency: {retrieval['avg_latency_ms']:.2f} ms")
    print(f"   Min latency: {retrieval['min_latency_ms']:.2f} ms")
    print(f"   Max latency: {retrieval['max_latency_ms']:.2f} ms")
    print(f"   P50 (median): {retrieval['p50_latency_ms']:.2f} ms")
    print(f"   P95: {retrieval['p95_latency_ms']:.2f} ms")
    print(f"   P99: {retrieval['p99_latency_ms']:.2f} ms")

    # Performance rating
    if retrieval['avg_latency_ms'] < 10:
        print(f"\n   ✅ Excellent performance (<10ms)")
    elif retrieval['avg_latency_ms'] < 50:
        print(f"\n   ✅ Good performance (<50ms)")
    elif retrieval['avg_latency_ms'] < 100:
        print(f"\n   ⚠️  Acceptable performance (<100ms)")
    else:
        print(f"\n   ❌ Slow performance (>100ms) - consider optimization")

    # Cache Performance
    print("\n💾 Cache Performance:")
    print("-" * 80)
    cache = results["cache"]
    if cache["cache_exists"]:
        print(f"   Cached embeddings: {cache['cached_embeddings']}")
        print(f"   Cache size: {cache['cache_size_mb']:.2f} MB")
        print(f"   Status: ✅ Cache enabled")
    else:
        print(f"   Status: ❌ No cache found")

    # Storage Metrics
    print("\n📦 Pattern Storage:")
    print("-" * 80)
    storage = results["storage"]
    print(f"   Total patterns: {storage['total_patterns']}")
    print(f"   Storage size: {storage['storage_size_mb']:.2f} MB")
    print(f"   Avg patterns per category: {storage['avg_patterns_per_category']:.1f}")

    print(f"\n   Category Distribution:")
    for category, count in sorted(storage['category_distribution'].items(), key=lambda x: -x[1]):
        pct = count / storage['total_patterns'] * 100 if storage['total_patterns'] > 0 else 0
        print(f"      {category:15s}: {count:4d} patterns ({pct:5.1f}%)")

    print(f"\n   Frequency Distribution:")
    for freq, count in sorted(storage['frequency_distribution'].items()):
        print(f"      Frequency {freq}: {count:4d} patterns")

    # Quality Trends
    print("\n📈 Quality Trends:")
    print("-" * 80)
    quality = results["quality_trends"]

    if quality["has_data"]:
        print(f"   Total evaluation reports: {quality['total_reports']}")
        print(f"   Latest overall score: {quality['latest_score']:.2f}/5.0")
        print(f"   Average overall score: {quality['avg_score']:.2f}/5.0")
        print(f"   Latest acceptance rate: {quality['latest_acceptance_rate']*100:.1f}%")
        print(f"   Average acceptance rate: {quality['avg_acceptance_rate']*100:.1f}%")
        print(f"   Trend: {quality['score_trend'].upper()}")

        if quality['score_trend'] == "improving":
            print(f"\n   ✅ Quality is improving over time!")
        else:
            print(f"\n   ℹ️  Quality is stable")

        # Show recent reports
        if len(quality['reports']) > 0:
            print(f"\n   Recent Reports:")
            for report in quality['reports'][-3:]:
                print(f"      [{report['timestamp']}] Score: {report['overall_score']:.2f}/5.0, Acceptance: {report['acceptance_rate']*100:.0f}%")
    else:
        print(f"   No evaluation reports found")
        print(f"   Run evaluations to track quality trends")

    # System Health Score
    print("\n" + "=" * 80)
    print("🎯 SYSTEM HEALTH SCORE")
    print("=" * 80)

    health_score = 0

    # Retrieval speed (30 points)
    if retrieval['avg_latency_ms'] < 10:
        health_score += 30
    elif retrieval['avg_latency_ms'] < 50:
        health_score += 20
    elif retrieval['avg_latency_ms'] < 100:
        health_score += 10

    # Cache status (20 points)
    if cache["cache_exists"]:
        health_score += 20

    # Pattern count (30 points)
    if storage['total_patterns'] >= 300:
        health_score += 30
    elif storage['total_patterns'] >= 150:
        health_score += 20
    elif storage['total_patterns'] >= 50:
        health_score += 10

    # Quality trends (20 points)
    if quality["has_data"]:
        if quality['latest_score'] >= 4.0:
            health_score += 20
        elif quality['latest_score'] >= 3.5:
            health_score += 15
        elif quality['latest_score'] >= 3.0:
            health_score += 10

    print(f"\n   Overall Health Score: {health_score}/100")

    if health_score >= 80:
        print(f"   ✅ Excellent system health")
    elif health_score >= 60:
        print(f"   ⚠️  Good, but room for improvement")
    else:
        print(f"   ❌ Needs attention")

    # Recommendations
    print(f"\n💡 Recommendations:")

    if retrieval['avg_latency_ms'] > 50:
        print(f"   - Optimize retrieval speed (current: {retrieval['avg_latency_ms']:.2f}ms)")

    if not cache["cache_exists"]:
        print(f"   - Enable embedding cache to improve performance")

    if storage['total_patterns'] < 300:
        print(f"   - Expand pattern database (current: {storage['total_patterns']}, target: 300-500)")

    if quality["has_data"] and quality['latest_score'] < 4.0:
        print(f"   - Review and improve answer quality (current: {quality['latest_score']:.2f}/5.0)")

    # Save monitoring results
    output_file = Path("outputs/monitoring/performance_report.json")
    output_file.parent.mkdir(parents=True, exist_ok=True)

    results["timestamp"] = datetime.now().isoformat()
    results["health_score"] = health_score

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n💾 Performance report saved to: {output_file}")
    print()


if __name__ == "__main__":
    main()
