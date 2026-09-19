from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field


# Auth Schemas
class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: int
    email: str
    is_active: bool
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = 'bearer'


# Option Schema
class OptionItem(BaseModel):
    key: str  # A, B, C, D
    text: str

    model_config = ConfigDict(from_attributes=True)


# Question Schemas
class QuestionResponse(BaseModel):
    id: int
    document_id: int
    question_number: str
    question_text: str
    question_type: str
    options: List[OptionItem] = []
    answer: Optional[str] = None
    answer_source: Optional[str] = None
    answer_status: str
    answer_confidence: float = 0.0
    explanation: Optional[str] = None
    source_pages: List[int] = []
    confidence: float
    needs_review: bool
    review_reasons: List[str] = []
    status: str
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class QuestionDetailResponse(QuestionResponse):
    raw_text: Optional[str] = None
    bounding_boxes: Optional[Any] = None
    updated_at: Optional[datetime] = None


class QuestionReviewUpdate(BaseModel):
    question_text: Optional[str] = None
    question_type: Optional[str] = None
    options: Optional[List[OptionItem]] = None
    answer: Optional[str] = None
    explanation: Optional[str] = None
    status: Optional[str] = Field(None, description='verified, flagged, rejected')
    needs_review: Optional[bool] = None
    review_notes: Optional[str] = None


# Answer Key Schemas
class AnswerKeyItemResponse(BaseModel):
    id: int
    document_id: int
    question_number: str
    answer: str
    explanation: Optional[str] = None
    page_number: Optional[int] = None
    confidence: float
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# Document Relation Schemas
class DocumentLinkRequest(BaseModel):
    related_document_id: int
    relation_type: str = Field('answer_key', description='answer_key, continuation, appendix')


class DocumentRelationResponse(BaseModel):
    id: int
    parent_document_id: int
    related_document_id: int
    relation_type: str
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# Document Schemas
class DocumentResponse(BaseModel):
    id: int
    filename: str
    file_size: int
    mime_type: str
    page_count: int
    status: str
    error_message: Optional[str] = None
    document_type: str
    meta_info: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class DocumentStatusResponse(BaseModel):
    id: int
    filename: str
    status: str
    page_count: int
    question_count: int = 0
    needs_review_count: int = 0
    error_message: Optional[str] = None
    updated_at: Optional[datetime] = None


class DocumentDetailResponse(DocumentResponse):
    questions: List[QuestionResponse] = []
    answer_keys: List[AnswerKeyItemResponse] = []
    relations_as_parent: List[DocumentRelationResponse] = []
    relations_as_related: List[DocumentRelationResponse] = []


# Export Schema
class DocumentExportResponse(BaseModel):
    document_id: int
    filename: str
    total_questions: int
    questions: List[QuestionResponse]
    answer_keys: List[AnswerKeyItemResponse]
    extracted_at: datetime
