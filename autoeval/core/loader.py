"""
CSV data loader with optimized encoding handling for medical reference data.
"""

import pandas as pd
from pathlib import Path
from typing import List, Dict
from loguru import logger

from .models import Disease, Examination, Surgery, Vaccine


class DataLoader:
    """Load medical reference data from CSV files"""

    # Known encodings for each file (eliminates slow chardet auto-detection)
    KNOWN_ENCODINGS = {
        '疾病.csv': 'utf-8',
        '检查.csv': 'utf-8',
        '手术操作.csv': 'utf-8',
        '疫苗.csv': 'gbk'  # Vaccines file uses GBK encoding
    }

    def __init__(self, data_dir: str = "refs/golden-refs/dxys"):
        self.data_dir = Path(data_dir)
        if not self.data_dir.exists():
            raise FileNotFoundError(f"Data directory not found: {self.data_dir}")

    def load_csv_safe(self, file_path: Path) -> pd.DataFrame:
        """Load CSV with known encoding (optimized - no auto-detection)"""
        # Use known encoding first
        primary_encoding = self.KNOWN_ENCODINGS.get(file_path.name, 'utf-8')

        try:
            df = pd.read_csv(file_path, encoding=primary_encoding)
            logger.info(f"Loaded {len(df)} rows from {file_path.name} (encoding: {primary_encoding})")
            return df
        except Exception as e:
            logger.info(f"Primary encoding {primary_encoding} failed for {file_path.name}, trying fallbacks...")
            # Fallback to common encodings
            for fallback_enc in ['utf-8', 'gbk', 'gb18030', 'latin1']:
                if fallback_enc == primary_encoding:
                    continue  # Skip already-tried encoding
                try:
                    df = pd.read_csv(file_path, encoding=fallback_enc)
                    logger.info(f"✓ Successfully loaded {file_path.name} with {fallback_enc}")
                    return df
                except Exception:
                    continue
            raise RuntimeError(f"Failed to load {file_path.name} with any encoding")

    def _load_entities(self, file_name: str, entity_class: type, entity_type_name: str) -> List:
        """
        Generic method to load entities from CSV file.

        Args:
            file_name: Name of CSV file
            entity_class: Pydantic model class to instantiate
            entity_type_name: Human-readable name for logging (e.g., "diseases")

        Returns:
            List of entity instances
        """
        file_path = self.data_dir / file_name
        df = self.load_csv_safe(file_path)
        df = df.fillna("")

        entities = []
        for _, row in df.iterrows():
            try:
                entity = entity_class(**row.to_dict())
                entities.append(entity)
            except Exception as e:
                logger.warning(f"Failed to parse {entity_type_name} row: {e}")
                continue

        logger.info(f"Successfully loaded {len(entities)} {entity_type_name}")
        return entities

    def load_diseases(self) -> List[Disease]:
        """Load disease data from 疾病.csv"""
        return self._load_entities("疾病.csv", Disease, "diseases")

    def load_examinations(self) -> List[Examination]:
        """Load examination data from 检查.csv"""
        return self._load_entities("检查.csv", Examination, "examinations")

    def load_surgeries(self) -> List[Surgery]:
        """Load surgical procedure data from 手术操作.csv"""
        return self._load_entities("手术操作.csv", Surgery, "surgeries")

    def load_vaccines(self) -> List[Vaccine]:
        """Load vaccine data from 疫苗.csv"""
        return self._load_entities("疫苗.csv", Vaccine, "vaccines")

    def load_all(self) -> Dict[str, List]:
        """Load all medical reference data"""
        logger.info("Loading all medical reference data...")

        data = {
            'diseases': self.load_diseases(),
            'examinations': self.load_examinations(),
            'surgeries': self.load_surgeries(),
            'vaccines': self.load_vaccines()
        }

        total = sum(len(v) for v in data.values())
        logger.info(f"Total entities loaded: {total}")
        logger.info(f"  - Diseases: {len(data['diseases'])}")
        logger.info(f"  - Examinations: {len(data['examinations'])}")
        logger.info(f"  - Surgeries: {len(data['surgeries'])}")
        logger.info(f"  - Vaccines: {len(data['vaccines'])}")

        return data

    def get_stats(self) -> Dict[str, int]:
        """Get statistics about the loaded data"""
        data = self.load_all()
        return {
            'diseases': len(data['diseases']),
            'examinations': len(data['examinations']),
            'surgeries': len(data['surgeries']),
            'vaccines': len(data['vaccines']),
            'total': sum(len(v) for v in data.values())
        }
