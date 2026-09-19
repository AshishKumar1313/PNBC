import datetime
import logging
from typing import Optional

from sqlalchemy import delete, select
from sqlalchemy.orm import selectinload

from app.database import AsyncSessionLocal
from app.models import AnswerKeyItem, Document, DocumentRelation, Question
from app.services.answer_matcher import match_answers_with_questions
from app.services.extractor_service import extract_structured_questions
from app.services.ocr_service import extract_document_pages

logger = logging.getLogger('document_processor')


async def process_document_async(document_id: int) -> None:
    """
    Main asynchronous pipeline for processing an uploaded document.
    Executes text/OCR extraction, question parsing, answer matching, and persistence.
    """
    async with AsyncSessionLocal() as db:
        stmt = (
            select(Document)
            .options(
                selectinload(Document.relations_as_parent),
                selectinload(Document.relations_as_related),
            )
            .where(Document.id == document_id)
        )
        result = await db.execute(stmt)
        document = result.scalar_one_or_none()

        if not document:
            logger.error(f'Document {document_id} not found for processing')
            return

        try:
            document.status = 'PROCESSING'
            document.error_message = None
            await db.commit()

            # Step 1: Extract pages and text/OCR
            pages = extract_document_pages(document.storage_path, document.mime_type)
            document.page_count = len(pages)

            # Step 2: Extract structured questions and internal answer keys
            extracted_questions, answer_key_items = extract_structured_questions(pages)

            # Step 3: Check for linked external answer key documents
            linked_answer_key_items = []
            stmt_relations = (
                select(DocumentRelation)
                .where(
                    DocumentRelation.parent_document_id == document.id,
                    DocumentRelation.relation_type == 'answer_key',
                )
            )
            res_relations = await db.execute(stmt_relations)
            relations = res_relations.scalars().all()

            for rel in relations:
                stmt_linked_keys = select(AnswerKeyItem).where(AnswerKeyItem.document_id == rel.related_document_id)
                res_linked = await db.execute(stmt_linked_keys)
                for item in res_linked.scalars().all():
                    linked_answer_key_items.append({
                        'question_number': item.question_number,
                        'answer': item.answer,
                        'explanation': item.explanation,
                        'page_number': item.page_number,
                        'raw_text': item.raw_text,
                        'confidence': item.confidence,
                    })

            # Step 4: Match internal answers first, then external linked answers
            if answer_key_items:
                extracted_questions = match_answers_with_questions(
                    extracted_questions,
                    answer_key_items,
                    source_label='document_answer_key',
                )
            
            if linked_answer_key_items:
                extracted_questions = match_answers_with_questions(
                    extracted_questions,
                    linked_answer_key_items,
                    source_label='linked_answer_key_doc',
                )

            # Step 5: Clean up any prior questions & answer keys for this doc (if re-processing)
            await db.execute(delete(Question).where(Question.document_id == document.id))
            await db.execute(delete(AnswerKeyItem).where(AnswerKeyItem.document_id == document.id))

            # Step 6: Persist AnswerKeyItems
            for ak in answer_key_items:
                ak_record = AnswerKeyItem(
                    document_id=document.id,
                    question_number=ak['question_number'],
                    answer=ak['answer'],
                    explanation=ak.get('explanation'),
                    page_number=ak.get('page_number'),
                    raw_text=ak.get('raw_text'),
                    confidence=ak.get('confidence', 1.0),
                )
                db.add(ak_record)

            # Step 7: Persist Questions
            for q_data in extracted_questions:
                q_record = Question(
                    document_id=document.id,
                    question_number=q_data['question_number'],
                    question_text=q_data['question_text'],
                    question_type=q_data['question_type'],
                    options=q_data['options'],
                    answer=q_data.get('answer'),
                    answer_source=q_data.get('answer_source'),
                    answer_status=q_data.get('answer_status', 'unmatched'),
                    answer_confidence=q_data.get('answer_confidence', 0.0),
                    explanation=q_data.get('explanation'),
                    source_pages=q_data.get('source_pages', []),
                    raw_text=q_data.get('raw_text'),
                    bounding_boxes=q_data.get('bounding_boxes'),
                    confidence=q_data.get('confidence', 1.0),
                    needs_review=q_data.get('needs_review', False),
                    review_reasons=q_data.get('review_reasons', []),
                    status=q_data.get('status', 'auto_extracted'),
                )
                db.add(q_record)

            # Step 8: If this document is an Answer Key linked to a parent question document,
            # update the parent document's questions with these answers!
            stmt_parent_rel = (
                select(DocumentRelation)
                .where(
                    DocumentRelation.related_document_id == document.id,
                    DocumentRelation.relation_type == 'answer_key',
                )
            )
            res_parent_rel = await db.execute(stmt_parent_rel)
            parent_rel = res_parent_rel.scalars().first()

            if parent_rel and answer_key_items:
                parent_id = parent_rel.parent_document_id
                parent_q_stmt = select(Question).where(Question.document_id == parent_id)
                res_parent_q = await db.execute(parent_q_stmt)
                parent_questions = res_parent_q.scalars().all()

                # Convert to dicts, run matcher, update records
                parent_dicts = [
                    {
                        'id': pq.id,
                        'question_number': pq.question_number,
                        'options': pq.options,
                        'answer': pq.answer,
                        'review_reasons': list(pq.review_reasons or []),
                        'needs_review': pq.needs_review,
                    }
                    for pq in parent_questions
                ]
                matched_parents = match_answers_with_questions(
                    parent_dicts, answer_key_items, source_label='linked_answer_key_doc'
                )
                
                # Update parent question entities
                parent_map = {pq.id: pq for pq in parent_questions}
                for mp in matched_parents:
                    pq_entity = parent_map.get(mp['id'])
                    if pq_entity:
                        pq_entity.answer = mp.get('answer')
                        pq_entity.answer_source = mp.get('answer_source')
                        pq_entity.answer_status = mp.get('answer_status')
                        pq_entity.answer_confidence = mp.get('answer_confidence')
                        pq_entity.needs_review = mp.get('needs_review')
                        pq_entity.review_reasons = mp.get('review_reasons')

            document.status = 'COMPLETED'
            document.updated_at = datetime.datetime.now(datetime.timezone.utc)
            await db.commit()
            logger.info(f'Document {document_id} processed successfully: {len(extracted_questions)} questions extracted')

        except Exception as exc:
            logger.exception(f'Error processing document {document_id}: {exc}')
            document.status = 'FAILED'
            document.error_message = str(exc)
            document.updated_at = datetime.datetime.now(datetime.timezone.utc)
            await db.commit()
