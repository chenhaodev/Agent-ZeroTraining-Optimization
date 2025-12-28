"""
Evaluation service using DeepSeek as judge with direct golden-ref lookup.
"""

import yaml
from typing import List, Dict
from loguru import logger
from concurrent.futures import ThreadPoolExecutor, as_completed

from autoeval.services.api_client import get_api_client
from autoeval.core.models import Question, Answer, Evaluation, Error, MedicalEntity
from autoeval.core.loader import DataLoader
from autoeval.config.settings import get_settings
from autoeval.utils.json_parser import extract_json_from_markdown, safe_log_response


class Evaluator:
    """Evaluate answers using DeepSeek with direct golden-ref lookup"""

    def __init__(self):
        self.settings = get_settings()
        self.api_client = get_api_client()

        # Load golden-refs for direct lookup (no RAG needed!)
        self.golden_refs = self._load_golden_refs()
        logger.info(f"Loaded {sum(len(v) for v in self.golden_refs.values())} golden-ref entities for evaluation")

        # Load prompt template
        prompt_path = self.settings.get_prompt_path("evaluation_criteria")
        with open(prompt_path, 'r', encoding='utf-8') as f:
            self.prompt_config = yaml.safe_load(f)

    def _load_golden_refs(self) -> Dict[str, Dict[str, MedicalEntity]]:
        """
        Load all golden-ref entities for direct lookup.

        Returns:
            Dict with structure: {'diseases': {'糖尿病': entity, ...}, ...}
        """
        loader = DataLoader(self.settings.DATA_DIR)  # Use settings path
        data = loader.load_all()

        # Create lookup index by entity name
        return {
            'diseases': {e.name: e for e in data['diseases']},
            'examinations': {e.name: e for e in data['examinations']},
            'surgeries': {e.name: e for e in data['surgeries']},
            'vaccines': {e.name: e for e in data['vaccines']}
        }

    def _get_reference_context(self, question: Question) -> str:
        """
        Get reference context via direct lookup (no RAG/embedding needed).

        Since questions are generated from sampled entities, we already know
        which entity to compare against - just look it up directly!
        """
        # Map entity type to category
        type_map = {
            'disease': 'diseases',
            'examination': 'examinations',
            'surgery': 'surgeries',
            'vaccine': 'vaccines'
        }

        category = type_map.get(question.source_entity_type)

        if not category:
            logger.warning(f"Unknown entity type: {question.source_entity_type}")
            return "参考资料未找到"

        if question.source_entity_name not in self.golden_refs[category]:
            logger.warning(f"Entity not found: {question.source_entity_name} in {category}")
            return "参考资料未找到"

        # Direct lookup - instant, no embedding/search needed!
        entity = self.golden_refs[category][question.source_entity_name]

        # Map category to Chinese display name
        category_names = {
            'diseases': '疾病',
            'examinations': '检查',
            'surgeries': '手术',
            'vaccines': '疫苗'
        }
        entity_type_display = category_names.get(category, category)

        # Format as reference context
        return f"""## 权威医学参考资料

来源: {entity_type_display} - {entity.name}
网址: {entity.url}

{entity.to_text()}
"""

    def evaluate(self, question: Question, answer: Answer) -> Evaluation:
        """
        Evaluate an answer using DeepSeek with direct golden-ref lookup.

        Args:
            question: Question object (contains source_entity_name)
            answer: Answer object

        Returns:
            Evaluation object
        """
        logger.info(f"Evaluating answer for: {question.question[:50]}...")

        # Get reference context via direct lookup (no RAG!)
        reference_context = self._get_reference_context(question)

        # Build evaluation prompt
        system_prompt = self.prompt_config['system_prompt']
        user_prompt = self.prompt_config['evaluation_prompt_template'].format(
            question=question.question,
            ai_answer=answer.answer,
            reference_context=reference_context
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        # Call DeepSeek for evaluation
        response = None
        try:
            response = self.api_client.call_deepseek(
                messages=messages,
                temperature=0.3  # Lower temperature for consistent evaluation
            )

            # Parse JSON response (handles markdown code blocks)
            data = extract_json_from_markdown(response)

            # Convert errors to Error objects
            errors = []
            for err_data in data.get('errors', []):
                # Validate required fields
                if not all(k in err_data for k in ['type', 'severity', 'description']):
                    logger.warning(f"Skipping error with missing fields: {err_data}")
                    continue

                error = Error(
                    type=err_data['type'],
                    severity=err_data['severity'],
                    description=err_data['description'],
                    quote_from_answer=err_data.get('quote_from_answer', ''),
                    correct_info_from_reference=err_data.get('correct_info_from_reference', '')
                )
                errors.append(error)

            # Create Evaluation object (no rag_context field needed)
            evaluation = Evaluation(
                question=question,
                answer=answer,
                scores=data.get('scores', {}),
                errors=errors,
                knowledge_gaps=data.get('knowledge_gaps', []),
                suggestions=data.get('suggestions', ''),
                is_acceptable=data.get('is_acceptable', False)
            )

            logger.info(f"Evaluation complete (overall score: {evaluation.scores.get('overall', 0)})")
            return evaluation

        except Exception as e:
            logger.error(f"Evaluation failed: {e}")
            safe_log_response(response, "Failed evaluation")
            return self._create_default_evaluation(question, answer, error_msg=str(e))

    def _create_default_evaluation(self, question: Question, answer: Answer, error_msg: str = "") -> Evaluation:
        """Create a default evaluation when parsing fails"""
        return Evaluation(
            question=question,
            answer=answer,
            scores={
                'accuracy': 0,
                'completeness': 0,
                'relevance': 0,
                'clarity': 0,
                'safety': 0,
                'overall': 0
            },
            errors=[Error(
                type='unclear',
                severity='major',
                description=f'评估失败: {error_msg}',
                quote_from_answer='',
                correct_info_from_reference=''
            )],
            knowledge_gaps=[],
            suggestions=f'评估过程出错: {error_msg}',
            is_acceptable=False
        )

    def evaluate_batch(self, qa_pairs: List[tuple], max_workers: int = 5) -> List[Evaluation]:
        """
        Evaluate multiple Q&A pairs in parallel.

        Args:
            qa_pairs: List of (Question, Answer) tuples
            max_workers: Maximum number of parallel workers (default: 5)

        Returns:
            List of Evaluation objects (in same order as input)
        """
        logger.info(f"Evaluating {len(qa_pairs)} Q&A pairs with {max_workers} parallel workers...")

        # Create a mapping to preserve order
        evaluations_dict = {}

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_idx = {
                executor.submit(self.evaluate, question, answer): idx
                for idx, (question, answer) in enumerate(qa_pairs)
            }

            # Collect results as they complete
            completed = 0
            for future in as_completed(future_to_idx):
                idx = future_to_idx[future]
                completed += 1
                try:
                    evaluation = future.result()
                    evaluations_dict[idx] = evaluation
                    logger.info(f"✓ Evaluated {completed}/{len(qa_pairs)}")
                except Exception as e:
                    logger.error(f"Evaluation failed for Q&A pair {idx}: {e}")
                    # Create error evaluation
                    evaluations_dict[idx] = Evaluation(
                        question=qa_pairs[idx][0],
                        answer=qa_pairs[idx][1],
                        scores={'overall': 0.0, 'accuracy': 0.0, 'completeness': 0.0, 'relevance': 0.0, 'clarity': 0.0, 'safety': 0.0},
                        errors=[Error(
                            type="evaluation_error",
                            description=str(e),
                            severity="critical",
                            quote_from_answer="",
                            correct_info_from_reference=""
                        )],
                        knowledge_gaps=[],
                        suggestions=f"Evaluation failed: {str(e)}",
                        is_acceptable=False
                    )

        # Return evaluations in original order
        return [evaluations_dict[i] for i in range(len(qa_pairs))]
