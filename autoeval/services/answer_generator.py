"""
Answer generation service using DeepSeek with dynamic RAG-based prompt optimization.
"""

import yaml
import uuid
from typing import List, Optional
from loguru import logger
from concurrent.futures import ThreadPoolExecutor, as_completed

from autoeval.services.api_client import get_api_client
from autoeval.core.models import Question, Answer
from optimizer.core.prompt_optimizer import PromptOptimizer
from autoeval.config.settings import get_settings

# Optional: Import router only if smart routing is needed
# This avoids circular dependencies and allows autoeval to work standalone
try:
    from router.core.decision_engine import DecisionEngine
    ROUTER_AVAILABLE = True
except ImportError:
    ROUTER_AVAILABLE = False


class AnswerGenerator:
    """Generate answers using DeepSeek with dynamic prompts"""

    def __init__(
        self,
        prompt_version: str = "1.0",
        use_dynamic_prompts: bool = True,
        rag_k: int = 5,
        use_category_rules: bool = True,
        use_smart_routing: bool = False
    ):
        """
        Initialize answer generator.

        Args:
            prompt_version: Prompt version to use (only if not using dynamic prompts)
            use_dynamic_prompts: Whether to use RAG-based dynamic prompts
            rag_k: Number of patterns to retrieve for dynamic prompts
            use_category_rules: Whether to use Tier 2 category-specific rules
            use_smart_routing: Whether to use smart routing to skip RAG for OOD questions
        """
        self.settings = get_settings()
        self.api_client = get_api_client()
        self.prompt_version = prompt_version
        self.use_dynamic_prompts = use_dynamic_prompts
        self.rag_k = rag_k
        self.use_category_rules = use_category_rules
        self.use_smart_routing = use_smart_routing

        # Initialize smart router if enabled
        if use_smart_routing:
            if not ROUTER_AVAILABLE:
                logger.warning("Smart routing requested but router module not available - disabling")
                self.use_smart_routing = False
            else:
                self.router = DecisionEngine()
                logger.info(f"Smart routing enabled - will skip RAG for predicted OOD questions")

        # Initialize prompt optimizer for dynamic prompts
        if use_dynamic_prompts:
            self.prompt_optimizer = PromptOptimizer()
            logger.info(f"Using dynamic prompts with RAG (k={rag_k}, category_rules={use_category_rules})")
        else:
            # Load static prompt
            prompt_path = self.settings.get_prompt_path("deepseek_system")
            with open(prompt_path, 'r', encoding='utf-8') as f:
                self.prompt_config = yaml.safe_load(f)
            logger.info(f"Using static prompt version {prompt_version}")

    def generate(self, question: Question) -> Answer:
        """
        Generate answer for a question using DeepSeek.

        Args:
            question: Question object

        Returns:
            Answer object
        """
        # Smart routing: Get complete routing decision (weakness-first priority)
        should_use_rag = True  # Default to using RAG
        routing_reason = "No routing applied"
        has_weakness = False

        if self.use_smart_routing and self.use_dynamic_prompts:
            # Use get_routing_decision() which checks weakness FIRST, then RAG
            decision = self.router.get_routing_decision(
                question=question.question,
                entity_type=None,  # Will be inferred from question
                min_confidence=0.70,
                auto_reload=False  # Avoid repeated reloads during batch processing
            )
            should_use_rag = decision['use_rag']
            routing_reason = decision['rag_reason']
            has_weakness = decision['has_weaknesses']

            logger.info(
                f"Smart routing: tier={decision.get('routing_tier', 'unknown')}, "
                f"use_rag={should_use_rag}, has_weakness={has_weakness}, "
                f"reason='{routing_reason}'"
            )

        # Build system prompt (static or dynamic)
        if self.use_dynamic_prompts:
            # Get entity type from question (source_entity_type field)
            # Map source_entity_type to category names for RAG retrieval
            entity_type_map = {
                'disease': 'diseases',
                'examination': 'examinations',
                'surgery': 'surgeries',
                'vaccine': 'vaccines'
            }
            entity_type = entity_type_map.get(question.source_entity_type, 'general')

            # Build dynamic prompt with RAG-retrieved patterns
            # Smart routing decision: skip RAG if router says so
            system_prompt = self.prompt_optimizer.build_dynamic_prompt(
                question=question.question,
                entity_type=entity_type,
                use_rag=should_use_rag,  # Router decision!
                rag_k=self.rag_k,
                use_category_rules=self.use_category_rules
            )
        else:
            # Use static prompt
            system_prompt = self.prompt_config['system_prompt']

            # Add memory/guidelines if present
            memory = self.prompt_config.get('memory', {})
            if memory.get('improvement_guidelines'):
                system_prompt += "\n\n## 改进指南\n"
                system_prompt += "\n".join(f"- {g}" for g in memory['improvement_guidelines'])

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question.question}
        ]

        # Call DeepSeek API
        logger.info(f"Generating answer for: {question.question[:50]}...")

        try:
            response = self.api_client.call_deepseek(
                messages=messages,
                temperature=0.7
            )

            # Create Answer object
            answer = Answer(
                question_id=str(uuid.uuid4()),
                answer=response,
                model=self.settings.ANSWER_GEN_MODEL,
                prompt_version=self.prompt_version
            )

            logger.info(f"Answer generated (length={len(response)})")
            return answer

        except Exception as e:
            logger.error(f"Answer generation failed: {e}")
            # Return empty answer on error
            return Answer(
                question_id=str(uuid.uuid4()),
                answer=f"[ERROR: {str(e)}]",
                model=self.settings.ANSWER_GEN_MODEL,
                prompt_version=self.prompt_version
            )

    def generate_batch(self, questions: List[Question], max_workers: int = 5) -> List[Answer]:
        """
        Generate answers for multiple questions in parallel.

        Args:
            questions: List of Question objects
            max_workers: Maximum number of parallel workers (default: 5)

        Returns:
            List of Answer objects (in same order as input questions)
        """
        logger.info(f"Generating {len(questions)} answers with {max_workers} parallel workers...")

        # Create a mapping to preserve order
        answers_dict = {}

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_idx = {
                executor.submit(self.generate, question): idx
                for idx, question in enumerate(questions)
            }

            # Collect results as they complete
            completed = 0
            for future in as_completed(future_to_idx):
                idx = future_to_idx[future]
                completed += 1
                try:
                    answer = future.result()
                    answers_dict[idx] = answer
                    logger.info(f"✓ Generated answer {completed}/{len(questions)}")
                except Exception as e:
                    logger.error(f"Answer generation failed for question {idx}: {e}")
                    # Create error answer
                    answers_dict[idx] = Answer(
                        question_id=str(uuid.uuid4()),
                        answer=f"[ERROR: {str(e)}]",
                        model=self.settings.ANSWER_GEN_MODEL,
                        prompt_version=self.prompt_version
                    )

        # Return answers in original order
        return [answers_dict[i] for i in range(len(questions))]
