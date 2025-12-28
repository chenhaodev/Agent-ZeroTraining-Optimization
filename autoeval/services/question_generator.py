"""
Question generation service using OpenAI GPT-4.1.
"""

import yaml
from typing import List
from loguru import logger

from autoeval.services.api_client import get_api_client
from autoeval.core.models import Question, MedicalEntity
from autoeval.config.settings import get_settings
from autoeval.utils.json_parser import extract_json_from_markdown, safe_log_response


class QuestionGenerator:
    """Generate questions from medical entities using OpenAI GPT-4.1"""

    def __init__(self):
        self.settings = get_settings()
        self.api_client = get_api_client()

        # Load prompt template
        prompt_path = self.settings.get_prompt_path("question_generation")
        with open(prompt_path, 'r', encoding='utf-8') as f:
            self.prompt_config = yaml.safe_load(f)

    def generate(self, entity: MedicalEntity, num_questions: int = None) -> List[Question]:
        """
        Generate questions for a medical entity.

        Args:
            entity: Medical entity (Disease, Examination, etc.)
            num_questions: Number of questions to generate (defaults to config)

        Returns:
            List of Question objects
        """
        if num_questions is None:
            num_questions = self.prompt_config.get('num_questions', 5)

        metadata = entity.get_metadata()
        content = entity.to_text()

        # Build prompt
        system_prompt = self.prompt_config['system_prompt']
        user_prompt = self.prompt_config['user_prompt_template'].format(
            num_questions=num_questions,
            entity_type=metadata['entity_type'],
            name=metadata['name'],
            content=content[:2000]  # Limit content length
        )

        # Call API
        logger.info(f"Generating {num_questions} questions for {metadata['name']}")

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        response = None
        try:
            response = self.api_client.call_openai(
                model=self.settings.QUESTION_GEN_MODEL,
                messages=messages,
                temperature=0.7
            )

            # Parse JSON response (handles markdown code blocks)
            data = extract_json_from_markdown(response)

            # Convert to Question objects
            questions = []
            for q_data in data.get('questions', []):
                # Validate required fields
                if 'question' not in q_data:
                    logger.warning(f"Skipping question without 'question' field: {q_data}")
                    continue

                question = Question(
                    question=q_data['question'],
                    category=q_data.get('category', 'other'),
                    difficulty=q_data.get('difficulty', 'medium'),
                    source_entity_type=metadata.get('entity_type', 'unknown'),
                    source_entity_id=metadata.get('entity_id', 0),
                    source_entity_name=metadata.get('name', 'unknown')
                )
                questions.append(question)

            logger.info(f"Generated {len(questions)} questions")
            return questions

        except Exception as e:
            logger.error(f"Question generation failed: {e}")
            safe_log_response(response, "Failed generation")
            return []
