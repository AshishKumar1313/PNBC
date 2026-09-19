from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import AnswerKeyItem, Document, DocumentRelation, Question, User
from app.schemas import (
    AnswerKeyItemResponse,
    DocumentDetailResponse,
    DocumentExportResponse,
    DocumentLinkRequest,
    DocumentRelationResponse,
    DocumentResponse,
    DocumentStatusResponse,
    QuestionResponse,
)
from app.security import get_current_user
from app.services.document_processor import process_document_async
from app.services.file_service import validate_and_save_upload
from app.services.ocr_service import extract_document_pages
from app.services.queue_service import enqueue_document_processing

router = APIRouter(prefix='/documents', tags=['Documents'])


@router.post('', response_model=DocumentResponse)
@router.post('/upload', response_model=DocumentResponse)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    document_type: str = Form('question_paper'),
    parent_document_id: Optional[int] = Form(None),
    relation_type: str = Form('answer_key'),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Uploads a PDF or Image file (PNG, JPG, JPEG).
    Validates file headers (magic bytes), stores securely, and queues asynchronous extraction.
    """
    file_path, filename, file_size, mime_type, file_hash = await validate_and_save_upload(file)

    # Check parent document if linking on upload
    if parent_document_id:
        parent_stmt = select(Document).where(Document.id == parent_document_id, Document.user_id == current_user.id)
        parent_res = await db.execute(parent_stmt)
        if not parent_res.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f'Parent document {parent_document_id} not found or not owned by user',
            )

    doc = Document(
        user_id=current_user.id,
        filename=filename,
        storage_path=file_path,
        file_size=file_size,
        mime_type=mime_type,
        file_hash=file_hash,
        page_count=0,
        status='PENDING',
        document_type=document_type,
        meta_info={'original_name': file.filename},
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    if parent_document_id:
        rel = DocumentRelation(
            parent_document_id=parent_document_id,
            related_document_id=doc.id,
            relation_type=relation_type,
        )
        db.add(rel)
        await db.commit()

    # Enqueue async processing
    await enqueue_document_processing(doc.id, background_tasks)

    return doc


@router.post('/{document_id}/extract')
async def extract_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Extract page text from a stored PDF/image document for immediate inspection."""
    stmt = select(Document).where(Document.id == document_id, Document.user_id == current_user.id)
    result = await db.execute(stmt)
    doc = result.scalar_one_or_none()

    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Document not found')

    try:
        pages = extract_document_pages(doc.storage_path, doc.mime_type)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    doc.status = 'COMPLETED'
    doc.page_count = len(pages)
    await db.commit()

    return {
        'document_id': doc.id,
        'page_count': len(pages),
        'pages': [page.to_dict() for page in pages],
    }


@router.get('', response_model=List[DocumentResponse])
async def list_documents(
    status_filter: Optional[str] = Query(None, alias='status'),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all documents owned by the authenticated user."""
    stmt = select(Document).where(Document.user_id == current_user.id)
    if status_filter:
        stmt = stmt.where(Document.status == status_filter.upper())
    stmt = stmt.offset(skip).limit(limit).order_by(Document.id.desc())

    result = await db.execute(stmt)
    return result.scalars().all()


@router.get('/{document_id}', response_model=DocumentDetailResponse)
async def get_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve full document details, including questions, answer keys, and related documents."""
    stmt = (
        select(Document)
        .options(
            selectinload(Document.questions),
            selectinload(Document.answer_keys),
            selectinload(Document.relations_as_parent),
            selectinload(Document.relations_as_related),
        )
        .where(Document.id == document_id, Document.user_id == current_user.id)
    )
    result = await db.execute(stmt)
    doc = result.scalar_one_or_none()

    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Document not found')

    return doc


@router.get('/{document_id}/status', response_model=DocumentStatusResponse)
async def get_document_status(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Quick status check endpoint to poll processing progress."""
    stmt = select(Document).where(Document.id == document_id, Document.user_id == current_user.id)
    result = await db.execute(stmt)
    doc = result.scalar_one_or_none()

    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Document not found')

    # Count questions and review items
    q_count_res = await db.execute(
        select(func.count(Question.id)).where(Question.document_id == document_id)
    )
    question_count = q_count_res.scalar() or 0

    review_count_res = await db.execute(
        select(func.count(Question.id)).where(
            Question.document_id == document_id, Question.needs_review.is_(True)
        )
    )
    needs_review_count = review_count_res.scalar() or 0

    return DocumentStatusResponse(
        id=doc.id,
        filename=doc.filename,
        status=doc.status,
        page_count=doc.page_count,
        question_count=question_count,
        needs_review_count=needs_review_count,
        error_message=doc.error_message,
        updated_at=doc.updated_at,
    )


@router.post('/{document_id}/process', response_model=DocumentStatusResponse)
async def trigger_process_document(
    document_id: int,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Re-triggers asynchronous processing for a document."""
    stmt = select(Document).where(Document.id == document_id, Document.user_id == current_user.id)
    result = await db.execute(stmt)
    doc = result.scalar_one_or_none()

    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Document not found')

    doc.status = 'PENDING'
    doc.error_message = None
    await db.commit()

    await enqueue_document_processing(doc.id, background_tasks)

    return DocumentStatusResponse(
        id=doc.id,
        filename=doc.filename,
        status=doc.status,
        page_count=doc.page_count,
        question_count=0,
        needs_review_count=0,
        error_message=None,
        updated_at=doc.updated_at,
    )


@router.post('/{document_id}/extract')
async def extract_document_sync(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Synchronous document extraction returning pages and extracted data."""
    stmt = select(Document).where(Document.id == document_id, Document.user_id == current_user.id)
    result = await db.execute(stmt)
    doc = result.scalar_one_or_none()

    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Document not found')

    # Execute extraction
    await process_document_async(document_id)
    pages = extract_document_pages(doc.storage_path, doc.mime_type)

    return {
        'document_id': doc.id,
        'status': 'completed',
        'page_count': len(pages),
        'pages': [p.to_dict() for p in pages],
    }


@router.get('/{document_id}/questions', response_model=List[QuestionResponse])
async def get_document_questions(
    document_id: int,
    needs_review: Optional[bool] = Query(None),
    min_confidence: Optional[float] = Query(None, ge=0.0, le=1.0),
    page: Optional[int] = Query(None, ge=1),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve extracted questions for a document with optional filtering."""
    # Verify ownership
    doc_stmt = select(Document).where(Document.id == document_id, Document.user_id == current_user.id)
    doc_res = await db.execute(doc_stmt)
    if not doc_res.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Document not found')

    stmt = select(Question).where(Question.document_id == document_id)

    if needs_review is not None:
        stmt = stmt.where(Question.needs_review == needs_review)

    if min_confidence is not None:
        stmt = stmt.where(Question.confidence >= min_confidence)

    stmt = stmt.order_by(Question.id.asc())
    res = await db.execute(stmt)
    questions = res.scalars().all()

    if page is not None:
        questions = [q for q in questions if page in (q.source_pages or [])]

    return questions


@router.get('/{document_id}/answer-key', response_model=List[AnswerKeyItemResponse])
async def get_document_answer_key(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve answer key items parsed from the document."""
    doc_stmt = select(Document).where(Document.id == document_id, Document.user_id == current_user.id)
    doc_res = await db.execute(doc_stmt)
    if not doc_res.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Document not found')

    stmt = select(AnswerKeyItem).where(AnswerKeyItem.document_id == document_id).order_by(AnswerKeyItem.id.asc())
    res = await db.execute(stmt)
    return res.scalars().all()


@router.get('/{document_id}/review-items', response_model=List[QuestionResponse])
async def get_document_review_items(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve questions requiring human review and verification."""
    doc_stmt = select(Document).where(Document.id == document_id, Document.user_id == current_user.id)
    doc_res = await db.execute(doc_stmt)
    if not doc_res.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Document not found')

    stmt = (
        select(Question)
        .where(Question.document_id == document_id, Question.needs_review.is_(True))
        .order_by(Question.id.asc())
    )
    res = await db.execute(stmt)
    return res.scalars().all()


@router.post('/{document_id}/link', response_model=DocumentRelationResponse, status_code=status.HTTP_201_CREATED)
async def link_related_document(
    document_id: int,
    payload: DocumentLinkRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Links another document (e.g. an external Answer Key) to this document.
    Triggers re-processing to integrate answers into questions.
    """
    # Verify both documents exist and belong to user
    d1 = await db.execute(select(Document).where(Document.id == document_id, Document.user_id == current_user.id))
    if not d1.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Parent document not found')

    d2 = await db.execute(
        select(Document).where(Document.id == payload.related_document_id, Document.user_id == current_user.id)
    )
    if not d2.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Related document not found')

    # Check if relation already exists
    rel_stmt = select(DocumentRelation).where(
        DocumentRelation.parent_document_id == document_id,
        DocumentRelation.related_document_id == payload.related_document_id,
    )
    rel_res = await db.execute(rel_stmt)
    existing_rel = rel_res.scalar_one_or_none()

    if existing_rel:
        return existing_rel

    relation = DocumentRelation(
        parent_document_id=document_id,
        related_document_id=payload.related_document_id,
        relation_type=payload.relation_type,
    )
    db.add(relation)
    await db.commit()
    await db.refresh(relation)

    # Re-process parent document to integrate linked answers
    await enqueue_document_processing(document_id, background_tasks)

    return relation


@router.get('/{document_id}/export', response_model=DocumentExportResponse)
async def export_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Exports structured question data in a clean, system-independent JSON format."""
    stmt = (
        select(Document)
        .options(
            selectinload(Document.questions),
            selectinload(Document.answer_keys),
        )
        .where(Document.id == document_id, Document.user_id == current_user.id)
    )
    res = await db.execute(stmt)
    doc = res.scalar_one_or_none()

    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Document not found')

    return DocumentExportResponse(
        document_id=doc.id,
        filename=doc.filename,
        total_questions=len(doc.questions),
        questions=doc.questions,
        answer_keys=doc.answer_keys,
        extracted_at=datetime.now(timezone.utc),
    )


@router.delete('/{document_id}', status_code=status.HTTP_200_OK)
async def delete_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Deletes a document and all related questions and answer keys."""
    stmt = select(Document).where(Document.id == document_id, Document.user_id == current_user.id)
    res = await db.execute(stmt)
    doc = res.scalar_one_or_none()

    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Document not found')

    await db.delete(doc)
    await db.commit()

    return {'message': f'Document {document_id} deleted successfully'}
