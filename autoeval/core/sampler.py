"""
Stratified sampling for medical entity data.
"""

import random
from typing import Dict, List
from loguru import logger

from .models import Disease, Examination, Surgery, Vaccine, MedicalEntity


class MedicalDataSampler:
    """Stratified random sampler for medical entities"""

    def __init__(self, sample_size: int = 100, random_seed: int = 42):
        self.sample_size = sample_size
        self.random_seed = random_seed
        random.seed(random_seed)

    def stratified_sample(self, data_dict: Dict[str, List[MedicalEntity]]) -> Dict[str, List[MedicalEntity]]:
        """
        Perform stratified random sampling across entity types.

        Args:
            data_dict: Dictionary with entity types as keys and lists of entities as values
                      {'diseases': [...], 'examinations': [...], 'surgeries': [...], 'vaccines': [...]}

        Returns:
            Dictionary with sampled entities for each type
        """
        # Calculate total entities
        total = sum(len(v) for v in data_dict.values())

        if total == 0:
            logger.warning("No data to sample from")
            return {k: [] for k in data_dict.keys()}

        logger.info(f"Performing stratified sampling (sample_size={self.sample_size}, total={total})")

        samples = {}
        allocated_total = 0

        # Proportional allocation based on dataset size
        for entity_type, entities in data_dict.items():
            if len(entities) == 0:
                samples[entity_type] = []
                logger.info(f"  - {entity_type}: 0 samples (no data)")
                continue

            # Calculate proportional sample size
            proportion = len(entities) / total
            n_samples = max(1, int(self.sample_size * proportion))  # At least 1 sample

            # Don't sample more than available
            n_samples = min(n_samples, len(entities))

            # Perform random sampling
            sampled = random.sample(entities, n_samples)
            samples[entity_type] = sampled
            allocated_total += n_samples

            logger.info(f"  - {entity_type}: {n_samples} samples ({proportion * 100:.1f}% of total)")

        # Adjust if we haven't reached target sample_size due to rounding
        shortfall = self.sample_size - allocated_total

        if shortfall > 0:
            logger.info(f"Allocating {shortfall} additional samples to largest category")
            # Add extra samples to the largest category
            largest_type = max(data_dict.items(), key=lambda x: len(x[1]))[0]
            current_samples = set(e.get_metadata()['entity_id'] for e in samples[largest_type])
            available = [e for e in data_dict[largest_type]
                        if e.get_metadata()['entity_id'] not in current_samples]

            if available:
                extra_samples = random.sample(available, min(shortfall, len(available)))
                samples[largest_type].extend(extra_samples)
                logger.info(f"  - Added {len(extra_samples)} to {largest_type}")

        # Log final counts
        final_total = sum(len(v) for v in samples.values())
        logger.info(f"Final sample size: {final_total}")

        return samples

    def sample_by_department(self, entities: List[MedicalEntity], top_n_depts: int = 10) -> Dict[str, List[MedicalEntity]]:
        """
        Sample entities grouped by medical department.

        Args:
            entities: List of medical entities (Disease, Examination, etc.)
            top_n_depts: Number of top departments to sample from

        Returns:
            Dictionary with department names as keys and sampled entities as values
        """
        # Group by department
        by_dept = {}
        for entity in entities:
            metadata = entity.get_metadata()
            dept = metadata.get('dept', '未知科室')

            # Clean up department field (e.g., "就诊科室：内分泌科" -> "内分泌科")
            if '：' in dept:
                dept = dept.split('：', 1)[1]
            elif ':' in dept:
                dept = dept.split(':', 1)[1]

            if dept not in by_dept:
                by_dept[dept] = []
            by_dept[dept].append(entity)

        # Sort by count and get top N departments
        sorted_depts = sorted(by_dept.items(), key=lambda x: len(x[1]), reverse=True)
        top_depts = sorted_depts[:top_n_depts]

        logger.info(f"Top {top_n_depts} departments by entity count:")
        for dept, ents in top_depts:
            logger.info(f"  - {dept}: {len(ents)} entities")

        return dict(top_depts)

    def balanced_sample(
        self,
        data_dict: Dict[str, List[MedicalEntity]],
        samples_per_type: int
    ) -> Dict[str, List[MedicalEntity]]:
        """
        Sample equal number of entities from each type.

        Args:
            data_dict: Dictionary with entity types as keys
            samples_per_type: Number of samples to take from each type

        Returns:
            Dictionary with balanced samples
        """
        logger.info(f"Performing balanced sampling ({samples_per_type} per type)")

        samples = {}
        for entity_type, entities in data_dict.items():
            if len(entities) == 0:
                samples[entity_type] = []
                continue

            n = min(samples_per_type, len(entities))
            samples[entity_type] = random.sample(entities, n)
            logger.info(f"  - {entity_type}: {n} samples")

        return samples


# Convenience function
def sample_data(
    data_dict: Dict[str, List],
    sample_size: int = 100,
    method: str = "stratified",
    random_seed: int = 42
) -> Dict[str, List]:
    """
    Sample medical data using specified method.

    Args:
        data_dict: Data dictionary from DataLoader
        sample_size: Target number of samples
        method: "stratified" or "balanced"
        random_seed: Random seed for reproducibility

    Returns:
        Sampled data dictionary
    """
    sampler = MedicalDataSampler(sample_size=sample_size, random_seed=random_seed)

    if method == "stratified":
        return sampler.stratified_sample(data_dict)
    elif method == "balanced":
        # For balanced, divide sample_size by number of types
        n_types = len([v for v in data_dict.values() if len(v) > 0])
        samples_per_type = max(1, sample_size // n_types)
        return sampler.balanced_sample(data_dict, samples_per_type)
    else:
        raise ValueError(f"Unknown sampling method: {method}")
