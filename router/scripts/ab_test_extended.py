#!/usr/bin/env python3
"""
Extended A/B Test: Baseline vs Router with 20+ questions
Tests across all categories with varying difficulty levels
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


# Extended test set with 20+ questions across all categories
EXTENDED_TEST_QUESTIONS = [
    # ========== DISEASES (8 questions) ==========
    {
        "question": "膝关节半月板损伤是什么病，会有什么影响？",
        "entity_type": "disease",
        "difficulty": "medium",
        "expected_weaknesses": ["conservative_treatment_details", "concurrent_injuries"]
    },
    {
        "question": "糖尿病患者平时要注意什么饮食禁忌？",
        "entity_type": "disease",
        "difficulty": "easy",
        "expected_weaknesses": ["lifestyle_details", "specific_recommendations"]
    },
    {
        "question": "高血压病人可以运动吗？什么运动比较合适？",
        "entity_type": "disease",
        "difficulty": "medium",
        "expected_weaknesses": ["exercise_contraindications", "intensity_guidelines"]
    },
    {
        "question": "类风湿关节炎能治好吗？需要长期吃药吗？",
        "entity_type": "disease",
        "difficulty": "hard",
        "expected_weaknesses": ["prognosis_details", "medication_duration"]
    },
    {
        "question": "痛风发作时应该怎么办？",
        "entity_type": "disease",
        "difficulty": "medium",
        "expected_weaknesses": ["acute_management", "medication_specifics"]
    },
    {
        "question": "脂肪肝需要治疗吗？会不会发展成肝癌？",
        "entity_type": "disease",
        "difficulty": "medium",
        "expected_weaknesses": ["progression_risk", "treatment_necessity"]
    },
    {
        "question": "甲状腺结节是癌症吗？需要手术吗？",
        "entity_type": "disease",
        "difficulty": "hard",
        "expected_weaknesses": ["malignancy_criteria", "treatment_indications"]
    },
    {
        "question": "过敏性鼻炎可以根治吗？",
        "entity_type": "disease",
        "difficulty": "easy",
        "expected_weaknesses": ["cure_possibility", "long_term_management"]
    },

    # ========== EXAMINATIONS (6 questions) ==========
    {
        "question": "妇科超声检查是做什么的？检查的时候会疼吗？",
        "entity_type": "examination",
        "difficulty": "easy",
        "expected_weaknesses": ["preparation_requirements", "procedure_details"]
    },
    {
        "question": "做CT检查前需要注意什么？要空腹吗？",
        "entity_type": "examination",
        "difficulty": "medium",
        "expected_weaknesses": ["preparation_requirements", "contrast_contraindications"]
    },
    {
        "question": "胃镜检查痛苦吗？可以做无痛胃镜吗？",
        "entity_type": "examination",
        "difficulty": "medium",
        "expected_weaknesses": ["anesthesia_options", "procedure_experience"]
    },
    {
        "question": "心电图能查出什么问题？",
        "entity_type": "examination",
        "difficulty": "easy",
        "expected_weaknesses": ["diagnostic_scope", "limitations"]
    },
    {
        "question": "血常规检查前需要空腹吗？",
        "entity_type": "examination",
        "difficulty": "easy",
        "expected_weaknesses": ["preparation_requirements", "timing"]
    },
    {
        "question": "核磁共振（MRI）检查有辐射吗？",
        "entity_type": "examination",
        "difficulty": "medium",
        "expected_weaknesses": ["safety_profile", "contraindications"]
    },

    # ========== SURGERIES (4 questions) ==========
    {
        "question": "阑尾炎手术后多久可以正常饮食？",
        "entity_type": "surgery",
        "difficulty": "medium",
        "expected_weaknesses": ["postoperative_care", "recovery_timeline"]
    },
    {
        "question": "痔疮手术后会复发吗？",
        "entity_type": "surgery",
        "difficulty": "medium",
        "expected_weaknesses": ["recurrence_rate", "prevention_measures"]
    },
    {
        "question": "白内障手术风险大吗？需要住院吗？",
        "entity_type": "surgery",
        "difficulty": "medium",
        "expected_weaknesses": ["surgical_risks", "hospitalization_requirements"]
    },
    {
        "question": "剖腹产后多久可以再怀孕？",
        "entity_type": "surgery",
        "difficulty": "hard",
        "expected_weaknesses": ["postoperative_timeline", "safety_considerations"]
    },

    # ========== VACCINES (4 questions) ==========
    {
        "question": "破伤风针和破伤风疫苗有什么区别？",
        "entity_type": "vaccine",
        "difficulty": "medium",
        "expected_weaknesses": ["specific_dosage", "administration", "terminology"]
    },
    {
        "question": "HPV疫苗打几针？间隔多久？",
        "entity_type": "vaccine",
        "difficulty": "easy",
        "expected_weaknesses": ["vaccination_schedule", "dosage_intervals"]
    },
    {
        "question": "流感疫苗每年都要打吗？",
        "entity_type": "vaccine",
        "difficulty": "easy",
        "expected_weaknesses": ["frequency", "necessity_rationale"]
    },
    {
        "question": "乙肝疫苗打了没有抗体怎么办？",
        "entity_type": "vaccine",
        "difficulty": "hard",
        "expected_weaknesses": ["non_responder_management", "booster_strategy"]
    },
]


def call_baseline(question: str, api_client) -> dict:
    """Baseline: Direct DeepSeek API call"""
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
        "method": "baseline"
    }


def call_router(question: str, entity_type: str, api_client, decision_engine, pattern_storage) -> dict:
    """Router: Smart routing with weakness detection + pattern retrieval patterns"""
    # Get routing decision
    decision = decision_engine.get_routing_decision(
        question=question,
        entity_type=entity_type,
        min_confidence=0.7,
        auto_reload=False
    )

    # Build enhanced prompt
    base_prompt = "你是一位专业的医疗健康助手。请用通俗易懂的语言回答患者的健康问题。"
    augmentation = []

    # Add weakness pattern reminders
    if decision.get('has_weaknesses'):
        weakness_reminders = []
        for wp in decision.get('weakness_patterns', [])[:2]:
            weakness_reminders.append(f"- {wp.get('description', '')}")

        if weakness_reminders:
            weakness_section = "\n\n⚠️ 特别注意（常见遗漏点）：\n" + "\n".join(weakness_reminders)
            augmentation.append(("weakness", weakness_section))

    # Add pattern retrieval patterns if needed
    if decision['use_patterns']:
        # Map singular to plural
        category_map = {
            'disease': 'diseases',
            'examination': 'examinations',
            'surgery': 'surgeries',
            'vaccine': 'vaccines'
        }
        category = category_map.get(entity_type, entity_type)

        relevant_patterns = pattern_storage.retrieve_relevant(
            question=question,
            category=category,
            k=3,
            threshold=0.5
        )

        if relevant_patterns:
            pattern_reminders = []
            for pattern in relevant_patterns:
                pattern_reminders.append(f"- {pattern['description']}")

            pattern_section = "\n\n📋 相关知识点补充：\n" + "\n".join(pattern_reminders)
            augmentation.append(("rag_patterns", pattern_section))

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


def main():
    """Run extended A/B comparison"""
    logger.info("=" * 80)
    logger.info("Extended A/B Test: Baseline vs Router (20+ questions)")
    logger.info("=" * 80)

    # Initialize components
    logger.info("\n[Setup] Initializing components...")
    api_client = get_api_client()
    decision_engine = get_decision_engine()
    pattern_storage = PatternStorage()

    pattern_count = len(pattern_storage.patterns)
    logger.info(f"✓ Loaded {pattern_count} patterns from vector DB")

    # Run comparison
    results = []

    for i, q_data in enumerate(EXTENDED_TEST_QUESTIONS, 1):
        logger.info(f"\n{'=' * 80}")
        logger.info(f"Question {i}/{len(EXTENDED_TEST_QUESTIONS)} [{q_data['difficulty']}]")
        logger.info(f"{'=' * 80}")
        logger.info(f"Q: {q_data['question']}")
        logger.info(f"Entity Type: {q_data['entity_type']}")
        logger.info(f"Expected Weaknesses: {', '.join(q_data.get('expected_weaknesses', []))}")

        # Call baseline
        logger.info("\n--- Baseline ---")
        baseline_result = call_baseline(q_data["question"], api_client)
        logger.info(f"✓ Complete ({baseline_result['latency']:.2f}s, {len(baseline_result['answer'])} chars)")

        # Call router
        logger.info("\n--- Router ---")
        router_result = call_router(
            q_data["question"],
            q_data["entity_type"],
            api_client,
            decision_engine,
            pattern_storage
        )
        logger.info(f"✓ Complete ({router_result['latency']:.2f}s, {len(router_result['answer'])} chars)")
        logger.info(f"Augmentation: {[a[0] for a in router_result.get('augmentation', [])]}")

        # Compare
        comparison = {
            "question": q_data["question"],
            "entity_type": q_data["entity_type"],
            "difficulty": q_data["difficulty"],
            "expected_weaknesses": q_data.get("expected_weaknesses", []),
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
        results.append(comparison)

    # Save results
    output_dir = Path("outputs/comparisons")
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / f"ab_test_extended_{timestamp}.json"

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            "metadata": {
                "timestamp": timestamp,
                "total_questions": len(EXTENDED_TEST_QUESTIONS),
                "pattern_count": pattern_count,
                "categories": {
                    "diseases": sum(1 for q in EXTENDED_TEST_QUESTIONS if q["entity_type"] == "disease"),
                    "examinations": sum(1 for q in EXTENDED_TEST_QUESTIONS if q["entity_type"] == "examination"),
                    "surgeries": sum(1 for q in EXTENDED_TEST_QUESTIONS if q["entity_type"] == "surgery"),
                    "vaccines": sum(1 for q in EXTENDED_TEST_QUESTIONS if q["entity_type"] == "vaccine"),
                }
            },
            "results": results
        }, f, ensure_ascii=False, indent=2)

    logger.info(f"\n{'=' * 80}")
    logger.info(f"✓ Extended A/B test complete! Results saved to:")
    logger.info(f"  {output_file}")
    logger.info(f"{'=' * 80}")

    # Print summary
    print("\n📊 SUMMARY\n")
    print(f"Total Questions: {len(EXTENDED_TEST_QUESTIONS)}")
    print(f"  - Diseases: {sum(1 for q in EXTENDED_TEST_QUESTIONS if q['entity_type'] == 'disease')}")
    print(f"  - Examinations: {sum(1 for q in EXTENDED_TEST_QUESTIONS if q['entity_type'] == 'examination')}")
    print(f"  - Surgeries: {sum(1 for q in EXTENDED_TEST_QUESTIONS if q['entity_type'] == 'surgery')}")
    print(f"  - Vaccines: {sum(1 for q in EXTENDED_TEST_QUESTIONS if q['entity_type'] == 'vaccine')}")

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
    print(f"  - Used pattern retrieval patterns: {rag_used}/{len(results)} questions ({rag_used/len(results)*100:.1f}%)")


if __name__ == "__main__":
    main()
