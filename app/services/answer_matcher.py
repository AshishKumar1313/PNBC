import re
from typing import Any, Dict, List, Optional


def normalize_q_num(q_num: str) -> str:
    """Normalizes 'Q1', '01', '1.' to '1'."""
    clean = re.sub(r'^[^\d]*', '', q_num)
    clean = re.sub(r'[^\d]+$', '', clean)
    return clean if clean else q_num.strip().lower()


def match_answers_with_questions(
    questions: List[Dict[str, Any]],
    answer_key_items: List[Dict[str, Any]],
    source_label: str = 'document_answer_key',
) -> List[Dict[str, Any]]:
    """
    Associates answer key items with extracted questions.
    Handles matching, conflict detection, and uncertainty.
    """
    if not answer_key_items:
        return questions

    # Build lookup map: normalized_q_num -> answer_item
    answer_map: Dict[str, Dict[str, Any]] = {}
    for item in answer_key_items:
        norm = normalize_q_num(item['question_number'])
        answer_map[norm] = item

    for q in questions:
        norm_q = normalize_q_num(q['question_number'])
        ans_item = answer_map.get(norm_q)

        if ans_item:
            target_answer = ans_item['answer'].upper()
            available_option_keys = [opt['key'].upper() for opt in q.get('options', [])]

            # Validate that if options exist, answer is among them or boolean
            if available_option_keys and target_answer not in available_option_keys and target_answer not in ['TRUE', 'FALSE']:
                # Mismatch between option set and answer key
                q['answer'] = target_answer
                q['answer_source'] = source_label
                q['answer_status'] = 'uncertain'
                q['answer_confidence'] = 0.4
                q['needs_review'] = True
                if 'answer_option_mismatch_with_options_list' not in q['review_reasons']:
                    q['review_reasons'].append('answer_option_mismatch_with_options_list')
                continue

            # If question already had an inline answer
            if q.get('answer'):
                existing_ans = q['answer'].upper()
                if existing_ans == target_answer:
                    q['answer_source'] = 'inline_and_key_verified'
                    q['answer_status'] = 'matched'
                    q['answer_confidence'] = 1.0
                else:
                    # Conflict between inline answer and answer key
                    q['answer_status'] = 'uncertain'
                    q['answer_confidence'] = 0.5
                    q['needs_review'] = True
                    conflict_msg = f'conflicting_answers_inline_{existing_ans}_vs_key_{target_answer}'
                    if conflict_msg not in q['review_reasons']:
                        q['review_reasons'].append(conflict_msg)
            else:
                # Assign answer from key
                q['answer'] = target_answer
                q['answer_source'] = source_label
                q['answer_status'] = 'matched'
                q['answer_confidence'] = 0.95
                if ans_item.get('explanation') and not q.get('explanation'):
                    q['explanation'] = ans_item['explanation']
                # Remove unmatched reason if present
                if 'unmatched_answer_key' in q['review_reasons']:
                    q['review_reasons'].remove('unmatched_answer_key')
        else:
            # Answer key was provided for the document, but this specific question was not in the key
            if not q.get('answer'):
                q['answer_status'] = 'unmatched'
                q['answer_confidence'] = 0.0
                if 'unmatched_answer_key' not in q['review_reasons']:
                    q['review_reasons'].append('unmatched_answer_key')

    return questions
