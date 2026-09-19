import datetime
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc)


class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utc_now)

    documents = relationship('Document', back_populates='owner', cascade='all, delete-orphan')


class Document(Base):
    __tablename__ = 'documents'

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    storage_path = Column(String(512), nullable=False)
    file_size = Column(Integer, nullable=False)
    mime_type = Column(String(100), nullable=False)
    file_hash = Column(String(64), nullable=False, index=True)
    page_count = Column(Integer, default=0)
    status = Column(String(50), default='PENDING', index=True)  # PENDING, PROCESSING, COMPLETED, FAILED
    error_message = Column(Text, nullable=True)
    document_type = Column(String(50), default='question_paper')  # question_paper, answer_key, mixed
    meta_info = Column(JSON, default=dict)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    owner = relationship('User', back_populates='documents')
    questions = relationship('Question', back_populates='document', cascade='all, delete-orphan', order_by='Question.id')
    answer_keys = relationship('AnswerKeyItem', back_populates='document', cascade='all, delete-orphan')
    
    relations_as_parent = relationship(
        'DocumentRelation',
        foreign_keys='DocumentRelation.parent_document_id',
        back_populates='parent_document',
        cascade='all, delete-orphan',
    )
    relations_as_related = relationship(
        'DocumentRelation',
        foreign_keys='DocumentRelation.related_document_id',
        back_populates='related_document',
        cascade='all, delete-orphan',
    )


class DocumentRelation(Base):
    __tablename__ = 'document_relations'

    id = Column(Integer, primary_key=True, index=True)
    parent_document_id = Column(Integer, ForeignKey('documents.id', ondelete='CASCADE'), nullable=False, index=True)
    related_document_id = Column(Integer, ForeignKey('documents.id', ondelete='CASCADE'), nullable=False, index=True)
    relation_type = Column(String(50), default='answer_key')  # answer_key, continuation, appendix
    created_at = Column(DateTime, default=utc_now)

    parent_document = relationship('Document', foreign_keys=[parent_document_id], back_populates='relations_as_parent')
    related_document = relationship('Document', foreign_keys=[related_document_id], back_populates='relations_as_related')


class Question(Base):
    __tablename__ = 'questions'

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey('documents.id', ondelete='CASCADE'), nullable=False, index=True)
    question_number = Column(String(50), nullable=False)
    question_text = Column(Text, nullable=False)
    question_type = Column(String(50), default='multiple_choice')  # multiple_choice, single_choice, true_false, fill_in_the_blank, descriptive
    options = Column(JSON, default=list)  # [{"key": "A", "text": "Option text"}]
    answer = Column(String(255), nullable=True)
    answer_source = Column(String(50), nullable=True)  # inline, end_key, linked_key, manual_review
    answer_status = Column(String(50), default='unmatched')  # matched, unmatched, uncertain
    answer_confidence = Column(Float, default=0.0)
    explanation = Column(Text, nullable=True)
    source_pages = Column(JSON, default=list)  # [1, 2]
    raw_text = Column(Text, nullable=True)
    bounding_boxes = Column(JSON, nullable=True)
    confidence = Column(Float, default=1.0)
    needs_review = Column(Boolean, default=False, index=True)
    review_reasons = Column(JSON, default=list)  # ["low_ocr_confidence", "split_across_pages"]
    status = Column(String(50), default='auto_extracted')  # auto_extracted, verified, flagged, rejected
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    document = relationship('Document', back_populates='questions')


class AnswerKeyItem(Base):
    __tablename__ = 'answer_key_items'

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey('documents.id', ondelete='CASCADE'), nullable=False, index=True)
    question_number = Column(String(50), nullable=False)
    answer = Column(String(255), nullable=False)
    explanation = Column(Text, nullable=True)
    page_number = Column(Integer, nullable=True)
    raw_text = Column(Text, nullable=True)
    confidence = Column(Float, default=1.0)
    created_at = Column(DateTime, default=utc_now)

    document = relationship('Document', back_populates='answer_keys')
