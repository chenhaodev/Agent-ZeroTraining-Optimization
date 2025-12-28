#!/usr/bin/env python3
"""
A/B Test: Baseline DeepSeek API vs Smart Router

Compares:
- Baseline: Direct DeepSeek calls (no routing, no RAG)
- Router: Weakness-aware routing with RAG patterns

Test set: Partial questions from auto-eval + OOD questions
"""

import sys
import json
from pathlib import Path
from datetime import datetime
from loguru import logger
import time

# Add repo root to path
repo_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(repo_root))

from autoeval.services.api_client import get_api_client
from router.core.decision_engine import get_decision_engine
from optimizer.core.pattern_storage import PatternStorage


# Test Questions (mix of in-distribution and OOD)
TEST_QUESTIONS = [
    # In-distribution (from auto-eval)
    {
        "question": "膝关节半月板损伤是什么病，会有什么影响？",
        "entity_type": "disease",
        "source": "auto-eval",
        "expected_weaknesses": ["conservative_treatment_details"]
    },
    {
        "question": "破伤风针和破伤风疫苗有什么区别？",
        "entity_type": "vaccine",
        "source": "auto-eval",
        "expected_weaknesses": ["specific_dosage", "administration"]
    },
    {
        "question": "妇科超声检查是做什么的？检查的时候会疼吗？",
        "entity_type": "examination",
        "source": "auto-eval",
        "expected_weaknesses": ["preparation_requirements"]
    },

    # OOD (out-of-distribution - new questions)
    {
        "question": "糖尿病患者平时要注意什么饮食禁忌？",
        "entity_type": "disease",
        "source": "OOD",
        "expected_weaknesses": ["lifestyle_details"]
    },
    {
        "question": "做CT检查前需要注意什么？要空腹吗？",
        "entity_type": "examination",
        "source": "OOD",
        "expected_weaknesses": ["preparation_requirements"]
    },
    {
        "question": "阑尾炎手术后多久可以正常饮食？",
        "entity_type": "surgery",
        "source": "OOD",
        "expected_weaknesses": ["postoperative_care"]
    },
    {
        "question": "HPV疫苗打几针？间隔多久？",
        "entity_type": "vaccine",
        "source": "OOD",
        "expected_weaknesses": ["vaccination_schedule"]
    },
]


def call_baseline(question: str, api_client) -> dict:
    """
    Baseline: Direct DeepSeek API call without routing or RAG

    Returns:
        dict with answer, latency, tokens
    """
    logger.info(f"[BASELINE] Calling DeepSeek directly...")

    # Simple medical assistant prompt (v1.0 baseline)
    messages = [
        {
            "role": "system",
            "content": "你是一位专业的医疗健康助手。请用通俗易懂的语言回答患者的健康问题。"
        },
        {
            "role": "user",
            "content": question
        }
    ]

    start_time = time.time()
    response = api_client.call_deepseek(messages)
    latency = time.time() - start_time

    return {
        "answer": response,
        "latency": latency,
        "method": "baseline",
        "augmentation": None
    }


def call_router(question: str, entity_type: str, api_client, decision_engine, pattern_storage) -> dict:
    """
    Router: Smart routing with weakness detection + RAG patterns

    Returns:
        dict with answer, latency, routing_decision, patterns_used
    """
    logger.info(f"[ROUTER] Using smart routing...")

    # Get routing decision (checks weakness patterns first, then RAG)
    decision = decision_engine.get_routing_decision(
        question=question,
        entity_type=entity_type,
        min_confidence=0.7,
        auto_reload=False
    )

    logger.info(f"  Routing tier: {decision.get('routing_tier', 'unknown')}")
    logger.info(f"  Use RAG: {decision['use_rag']}")
    logger.info(f"  Weakness patterns: {len(decision.get('weakness_patterns', []))}")

    # Build enhanced prompt
    base_prompt = "你是一位专业的医疗健康助手。请用通俗易懂的语言回答患者的健康问题。"

    augmentation = []

    # Add weakness pattern reminders
    if decision.get('has_weaknesses'):
        weakness_reminders = []
        for wp in decision.get('weakness_patterns', [])[:2]:  # Top 2
            weakness_reminders.append(f"- {wp.get('description', '')}")

        if weakness_reminders:
            weakness_section = "\n\n⚠️ 特别注意（常见遗漏点）：\n" + "\n".join(weakness_reminders)
            augmentation.append(("weakness", weakness_section))

    # Add RAG patterns if needed
    if decision['use_rag']:
        # Map singular entity_type to plural category names used in pattern storage
        category_map = {
            'disease': 'diseases',
            'examination': 'examinations',
            'surgery': 'surgeries',
            'vaccine': 'vaccines'
        }
        category = category_map.get(entity_type, entity_type)

        # Retrieve relevant error patterns from vector DB with category filtering
        relevant_patterns = pattern_storage.retrieve_relevant(
            question=question,
            category=category,  # ✅ Use plural category name for filtering
            k=3,
            threshold=0.5  # ✅ Lowered from 0.7 - patterns are error descriptions, not direct Q&A matches
        )

        if relevant_patterns:
            # Log retrieved patterns for debugging
            logger.info(f"  Retrieved {len(relevant_patterns)} RAG patterns:")
            for i, p in enumerate(relevant_patterns, 1):
                logger.info(f"    {i}. [{p['category']:12s}] {p['description'][:80]}...")

            pattern_reminders = []
            for pattern in relevant_patterns:
                pattern_reminders.append(f"- {pattern['description']}")

            pattern_section = "\n\n📋 相关知识点补充：\n" + "\n".join(pattern_reminders)
            augmentation.append(("rag_patterns", pattern_section))
        else:
            logger.info(f"  No RAG patterns found above threshold 0.5")

    # Construct final prompt
    augmented_prompt = base_prompt
    for aug_type, aug_content in augmentation:
        augmented_prompt += aug_content

    messages = [
        {
            "role": "system",
            "content": augmented_prompt
        },
        {
            "role": "user",
            "content": question
        }
    ]

    start_time = time.time()
    response = api_client.call_deepseek(messages)
    latency = time.time() - start_time

    return {
        "answer": response,
        "latency": latency,
        "method": "router",
        "routing_decision": decision,
        "augmentation": augmentation
    }


def compare_answers(question_data: dict, baseline_result: dict, router_result: dict) -> dict:
    """
    Compare baseline vs router answers

    Returns comparison metrics
    """
    return {
        "question": question_data["question"],
        "entity_type": question_data["entity_type"],
        "source": question_data["source"],
        "expected_weaknesses": question_data.get("expected_weaknesses", []),
        "baseline": {
            "answer": baseline_result["answer"],
            "latency": baseline_result["latency"],
            "answer_length": len(baseline_result["answer"])
        },
        "router": {
            "answer": router_result["answer"],
            "latency": router_result["latency"],
            "answer_length": len(router_result["answer"]),
            "routing_tier": router_result["routing_decision"].get("routing_tier"),
            "weakness_count": len(router_result["routing_decision"].get("weakness_patterns", [])),
            "augmentation_types": [a[0] for a in router_result.get("augmentation", [])]
        },
        "comparison": {
            "length_diff": len(router_result["answer"]) - len(baseline_result["answer"]),
            "latency_diff": router_result["latency"] - baseline_result["latency"]
        }
    }


def main():
    """Run A/B comparison"""
    logger.info("=" * 80)
    logger.info("A/B Test: Baseline DeepSeek vs Smart Router")
    logger.info("=" * 80)

    # Initialize components
    logger.info("\n[Setup] Initializing components...")
    api_client = get_api_client()
    decision_engine = get_decision_engine()
    pattern_storage = PatternStorage()

    # Check pattern count
    pattern_count = len(pattern_storage.patterns)
    logger.info(f"✓ Loaded {pattern_count} patterns from vector DB")

    # Run comparison
    results = []

    for i, q_data in enumerate(TEST_QUESTIONS, 1):
        logger.info(f"\n{'=' * 80}")
        logger.info(f"Question {i}/{len(TEST_QUESTIONS)} [{q_data['source']}]")
        logger.info(f"{'=' * 80}")
        logger.info(f"Q: {q_data['question']}")
        logger.info(f"Entity Type: {q_data['entity_type']}")
        logger.info(f"Expected Weaknesses: {', '.join(q_data.get('expected_weaknesses', []))}")

        # Call baseline
        logger.info("\n--- Baseline API Call ---")
        baseline_result = call_baseline(q_data["question"], api_client)
        logger.info(f"✓ Baseline complete ({baseline_result['latency']:.2f}s, {len(baseline_result['answer'])} chars)")

        # Call router
        logger.info("\n--- Router API Call ---")
        router_result = call_router(
            q_data["question"],
            q_data["entity_type"],
            api_client,
            decision_engine,
            pattern_storage
        )
        logger.info(f"✓ Router complete ({router_result['latency']:.2f}s, {len(router_result['answer'])} chars)")

        # Compare
        comparison = compare_answers(q_data, baseline_result, router_result)
        results.append(comparison)

        logger.info(f"\n--- Quick Comparison ---")
        logger.info(f"Length: Baseline {comparison['baseline']['answer_length']} vs Router {comparison['router']['answer_length']} ({comparison['comparison']['length_diff']:+d} chars)")
        logger.info(f"Latency: Baseline {comparison['baseline']['latency']:.2f}s vs Router {comparison['router']['latency']:.2f}s ({comparison['comparison']['latency_diff']:+.2f}s)")
        logger.info(f"Router used: {comparison['router']['routing_tier']} tier, {comparison['router']['weakness_count']} weakness patterns")

    # Save results
    output_dir = Path("outputs/comparisons")
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / f"baseline_vs_router_{timestamp}.json"

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            "metadata": {
                "timestamp": timestamp,
                "total_questions": len(TEST_QUESTIONS),
                "in_distribution": sum(1 for q in TEST_QUESTIONS if q["source"] == "auto-eval"),
                "ood": sum(1 for q in TEST_QUESTIONS if q["source"] == "OOD"),
                "pattern_count": pattern_count
            },
            "results": results
        }, f, ensure_ascii=False, indent=2)

    logger.info(f"\n{'=' * 80}")
    logger.info(f"✓ Comparison complete! Results saved to:")
    logger.info(f"  {output_file}")
    logger.info(f"{'=' * 80}")

    # Print summary
    print("\n📊 SUMMARY\n")
    print(f"Total Questions: {len(TEST_QUESTIONS)}")
    print(f"  - In-Distribution (auto-eval): {sum(1 for q in TEST_QUESTIONS if q['source'] == 'auto-eval')}")
    print(f"  - OOD (new questions): {sum(1 for q in TEST_QUESTIONS if q['source'] == 'OOD')}")
    print(f"\nPatterns Used: {pattern_count} patterns in vector DB")

    avg_baseline_len = sum(r['baseline']['answer_length'] for r in results) / len(results)
    avg_router_len = sum(r['router']['answer_length'] for r in results) / len(results)

    print(f"\nAverage Answer Length:")
    print(f"  - Baseline: {avg_baseline_len:.0f} chars")
    print(f"  - Router:   {avg_router_len:.0f} chars ({avg_router_len - avg_baseline_len:+.0f} chars)")

    weakness_used = sum(1 for r in results if r['router']['weakness_count'] > 0)
    rag_used = sum(1 for r in results if 'rag_patterns' in r['router']['augmentation_types'])

    print(f"\nRouter Behavior:")
    print(f"  - Used weakness patterns: {weakness_used}/{len(results)} questions")
    print(f"  - Used RAG patterns: {rag_used}/{len(results)} questions")

    print(f"\n💡 Next Step: Manually review answers in {output_file}")
    print(f"   Compare quality, completeness, and accuracy")


if __name__ == "__main__":
    main()
