"""
Pydantic models for medical entities from DXY golden references.
"""

from pydantic import BaseModel, Field
from typing import Optional, Literal


class MedicalEntity(BaseModel):
    """Base class for all medical entities"""

    def to_text(self) -> str:
        """Convert to searchable text for embedding"""
        raise NotImplementedError

    def get_metadata(self) -> dict:
        """Get metadata for pattern retrieval"""
        raise NotImplementedError


class Disease(MedicalEntity):
    """疾病 (Disease) model"""
    disease_id: int
    url: str
    name: str
    introduction: Optional[str] = ""
    symptoms: Optional[str] = ""
    causes: Optional[str] = ""
    diagnosis: Optional[str] = ""
    treatments: Optional[str] = ""
    lifestyle: Optional[str] = ""
    prevention: Optional[str] = ""
    dept: Optional[str] = ""
    desc: Optional[str] = ""

    def to_text(self) -> str:
        """Convert to searchable text for embedding"""
        parts = []

        if self.name:
            parts.append(f"疾病名称: {self.name}")

        if self.introduction and self.introduction not in ["[]", ""]:
            parts.append(f"简介: {self.introduction}")

        if self.symptoms and self.symptoms not in ["[]", ""]:
            parts.append(f"症状: {self.symptoms}")

        if self.causes and self.causes not in ["[]", ""]:
            parts.append(f"病因: {self.causes}")

        if self.diagnosis and self.diagnosis not in ["[]", ""]:
            parts.append(f"诊断: {self.diagnosis}")

        if self.treatments and self.treatments not in ["[]", ""]:
            parts.append(f"治疗: {self.treatments}")

        if self.lifestyle and self.lifestyle not in ["[]", ""]:
            parts.append(f"生活方式: {self.lifestyle}")

        if self.prevention and self.prevention not in ["[]", ""]:
            parts.append(f"预防: {self.prevention}")

        if self.desc and self.desc not in ["[]", ""]:
            parts.append(f"描述: {self.desc}")

        return "\n\n".join(parts)

    def get_metadata(self) -> dict:
        """Get metadata for pattern retrieval"""
        return {
            'entity_type': 'disease',
            'entity_id': self.disease_id,
            'name': self.name,
            'url': self.url,
            'dept': self.dept or "未知科室"
        }

    model_config = {
        "str_strip_whitespace": True
    }


class Examination(MedicalEntity):
    """检查 (Medical Examination) model"""
    jc_id: int
    url: str
    name: str
    dept: Optional[str] = ""
    desc: Optional[str] = ""
    reference: Optional[str] = ""
    简介: Optional[str] = Field(default="", alias="简介")
    适应证: Optional[str] = Field(default="", alias="适应证")
    禁忌证: Optional[str] = Field(default="", alias="禁忌证")
    注意事项: Optional[str] = Field(default="", alias="注意事项")
    并发症: Optional[str] = Field(default="", alias="并发症")
    结果解读: Optional[str] = Field(default="", alias="结果解读")
    更多信息: Optional[str] = Field(default="", alias="更多信息")

    def to_text(self) -> str:
        """Convert to searchable text for embedding"""
        parts = []

        if self.name:
            parts.append(f"检查名称: {self.name}")

        if self.简介 and self.简介 not in ["[]", ""]:
            parts.append(f"简介: {self.简介}")

        if self.适应证 and self.适应证 not in ["[]", ""]:
            parts.append(f"适应证: {self.适应证}")

        if self.禁忌证 and self.禁忌证 not in ["[]", ""]:
            parts.append(f"禁忌证: {self.禁忌证}")

        if self.注意事项 and self.注意事项 not in ["[]", ""]:
            parts.append(f"注意事项: {self.注意事项}")

        if self.并发症 and self.并发症 not in ["[]", ""]:
            parts.append(f"并发症: {self.并发症}")

        if self.结果解读 and self.结果解读 not in ["[]", ""]:
            parts.append(f"结果解读: {self.结果解读}")

        if self.desc and self.desc not in ["[]", ""]:
            parts.append(f"描述: {self.desc}")

        return "\n\n".join(parts)

    def get_metadata(self) -> dict:
        """Get metadata for pattern retrieval"""
        return {
            'entity_type': 'examination',
            'entity_id': self.jc_id,
            'name': self.name,
            'url': self.url,
            'dept': self.dept or "未知科室"
        }

    model_config = {
        "str_strip_whitespace": True,
        "populate_by_name": True
    }


class Surgery(MedicalEntity):
    """手术操作 (Surgical Procedure) model"""
    jc_id: int
    url: str
    name: str
    dept: Optional[str] = ""
    desc: Optional[str] = ""
    简介: Optional[str] = Field(default="", alias="简介")
    适应证: Optional[str] = Field(default="", alias="适应证")
    禁忌证: Optional[str] = Field(default="", alias="禁忌证")
    风险和并发症: Optional[str] = Field(default="", alias="风险和并发症")
    术前注意事项: Optional[str] = Field(default="", alias="术前注意事项")
    术中注意事项: Optional[str] = Field(default="", alias="术中注意事项")
    术后注意事项: Optional[str] = Field(default="", alias="术后注意事项")
    更多信息: Optional[str] = Field(default="", alias="更多信息")
    reference: Optional[str] = ""
    注意事项: Optional[str] = Field(default="", alias="注意事项")
    并发症: Optional[str] = Field(default="", alias="并发症")
    结果解读: Optional[str] = Field(default="", alias="结果解读")

    def to_text(self) -> str:
        """Convert to searchable text for embedding"""
        parts = []

        if self.name:
            parts.append(f"手术名称: {self.name}")

        if self.简介 and self.简介 not in ["[]", ""]:
            parts.append(f"简介: {self.简介}")

        if self.适应证 and self.适应证 not in ["[]", ""]:
            parts.append(f"适应证: {self.适应证}")

        if self.禁忌证 and self.禁忌证 not in ["[]", ""]:
            parts.append(f"禁忌证: {self.禁忌证}")

        if self.风险和并发症 and self.风险和并发症 not in ["[]", ""]:
            parts.append(f"风险和并发症: {self.风险和并发症}")

        if self.术前注意事项 and self.术前注意事项 not in ["[]", ""]:
            parts.append(f"术前注意事项: {self.术前注意事项}")

        if self.术中注意事项 and self.术中注意事项 not in ["[]", ""]:
            parts.append(f"术中注意事项: {self.术中注意事项}")

        if self.术后注意事项 and self.术后注意事项 not in ["[]", ""]:
            parts.append(f"术后注意事项: {self.术后注意事项}")

        if self.desc and self.desc not in ["[]", ""]:
            parts.append(f"描述: {self.desc}")

        return "\n\n".join(parts)

    def get_metadata(self) -> dict:
        """Get metadata for pattern retrieval"""
        return {
            'entity_type': 'surgery',
            'entity_id': self.jc_id,
            'name': self.name,
            'url': self.url,
            'dept': self.dept or "未知科室"
        }

    model_config = {
        "str_strip_whitespace": True,
        "populate_by_name": True
    }


class Vaccine(MedicalEntity):
    """疫苗 (Vaccine) model"""
    ym_id: int
    url: str
    name: str
    type: Optional[str] = ""  # 一类疫苗/二类疫苗/被动免疫制剂
    desc: Optional[str] = ""
    reference: Optional[str] = ""
    功效作用: Optional[str] = Field(default="", alias="功效作用")
    用药禁忌: Optional[str] = Field(default="", alias="用药禁忌")
    用法用量: Optional[str] = Field(default="", alias="用法用量")
    不良反应: Optional[str] = Field(default="", alias="不良反应")
    更多信息: Optional[str] = Field(default="", alias="更多信息")

    def to_text(self) -> str:
        """Convert to searchable text for embedding"""
        parts = []

        if self.name:
            parts.append(f"疫苗名称: {self.name}")

        if self.type and self.type not in ["[]", ""]:
            parts.append(f"类型: {self.type}")

        if self.功效作用 and self.功效作用 not in ["[]", ""]:
            parts.append(f"功效作用: {self.功效作用}")

        if self.用法用量 and self.用法用量 not in ["[]", ""]:
            parts.append(f"用法用量: {self.用法用量}")

        if self.用药禁忌 and self.用药禁忌 not in ["[]", ""]:
            parts.append(f"用药禁忌: {self.用药禁忌}")

        if self.不良反应 and self.不良反应 not in ["[]", ""]:
            parts.append(f"不良反应: {self.不良反应}")

        if self.desc and self.desc not in ["[]", ""]:
            parts.append(f"描述: {self.desc}")

        return "\n\n".join(parts)

    def get_metadata(self) -> dict:
        """Get metadata for pattern retrieval"""
        return {
            'entity_type': 'vaccine',
            'entity_id': self.ym_id,
            'name': self.name,
            'url': self.url,
            'type': self.type or "未知类型"
        }

    model_config = {
        "str_strip_whitespace": True,
        "populate_by_name": True
    }


# Question and Answer models for evaluation

class Question(BaseModel):
    """Generated question model"""
    question: str
    category: Literal["definition", "symptoms", "causes", "diagnosis", "treatment", "prevention", "lifestyle", "other"]
    difficulty: Literal["easy", "medium", "hard"]
    source_entity_type: str
    source_entity_id: int
    source_entity_name: str


class Answer(BaseModel):
    """Answer from DeepSeek"""
    question_id: str
    answer: str
    model: str = "deepseek-chat"
    prompt_version: str = "1.0"


# Evaluation models
# Note: Error types: factual_error, incomplete, misleading, irrelevant, unsafe, unclear
# Note: Error severities: critical, major, minor

class Error(BaseModel):
    """Detected error in answer"""
    type: str  # ErrorType
    severity: str  # ErrorSeverity
    description: str
    quote_from_answer: str
    correct_info_from_reference: str


class Evaluation(BaseModel):
    """Evaluation result for a Q&A pair"""
    question: Question
    answer: Answer
    scores: dict[str, float]  # accuracy, completeness, relevance, clarity, safety, overall
    errors: list[Error]
    knowledge_gaps: list[str]
    suggestions: str
    is_acceptable: bool
    # rag_context removed - we use direct golden-ref lookup instead
