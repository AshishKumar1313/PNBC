from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Document, Question, User
from app.schemas import QuestionDetailResponse, QuestionReviewUpdate
from app.security import get_current_user

router = APIRouter(prefix='/questions', tags=['Questions'])


@router.get('/{question_id}', response_model=QuestionDetailResponse)
async def get_question(
    question_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve complete question details including raw text, page sources, and review metadata."""
    stmt = (
        select(Question)
        .join(Document, Question.document_id == Document.id)
        .where(Question.id == question_id, Document.user_id == current_user.id)
    )
    result = await db.execute(stmt)
    question = result.scalar_one_or_none()

    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Question not found or unauthorized access',
        )

    return question


@router.patch('/{question_id}', response_model=QuestionDetailResponse)
async def review_and_update_question(
    question_id: int,
    payload: QuestionReviewUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Human-in-the-loop endpoint allowing reviewers to verify, edit, or reject extracted questions.
    Clears needs_review flag upon manual verification.
    """
    stmt = (
        select(Question)
        .join(Document, Question.document_id == Document.id)
        .where(Question.id == question_id, Document.user_id == current_user.id)
    )
    result = await db.execute(stmt)
    question = result.scalar_one_or_none()

    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Question not found or unauthorized access',
        )

    # Apply updates
    if payload.question_text is not None:
        question.question_text = payload.question_text

    if payload.question_type is not None:
        question.question_type = payload.question_type

    if payload.options is not None:
        question.options = [opt.model_dump() for opt in payload.options]

    if payload.answer is not None:
        question.answer = payload.answer
        question.answer_source = 'manual_review'
        question.answer_status = 'matched'
        question.answer_confidence = 1.0

    if payload.explanation is not None:
        question.explanation = payload.explanation

    if payload.status is not None:
        question.status = payload.status
        if payload.status == 'verified':
            question.needs_review = False
            question.confidence = 1.0

    if payload.needs_review is not None:
        question.needs_review = payload.needs_review

    question.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(question)

    return question
