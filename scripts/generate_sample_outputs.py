import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.ocr_service import extract_document_pages
from app.services.extractor_service import extract_structured_questions
from app.services.answer_matcher import match_answers_with_questions


def generate_outputs():
    os.makedirs('sample_outputs', exist_ok=True)
    samples = [
        ('sample_1_standard_mcq.pdf', 'application/pdf', 'sample_1_standard_mcq_output.json'),
        ('sample_2_multipage_spanning.pdf', 'application/pdf', 'sample_2_multipage_spanning_output.json'),
        ('sample_3_with_end_answer_key.pdf', 'application/pdf', 'sample_3_with_end_answer_key_output.json'),
        ('sample_4_separate_answer_key.pdf', 'application/pdf', 'sample_4_separate_answer_key_output.json'),
        ('sample_6_noisy_low_confidence.pdf', 'application/pdf', 'sample_6_noisy_low_confidence_output.json'),
    ]

    for filename, mime, out_name in samples:
        path = os.path.join('sample_documents', filename)
        pages = extract_document_pages(path, mime)
        questions, answer_keys = extract_structured_questions(pages)

        if answer_keys:
            questions = match_answers_with_questions(questions, answer_keys, source_label='document_answer_key')

        result = {
            'filename': filename,
            'page_count': len(pages),
            'total_questions': len(questions),
            'questions': questions,
            'answer_key_items': answer_keys,
        }

        out_path = os.path.join('sample_outputs', out_name)
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2)

        print(f'Wrote {out_path} ({len(questions)} questions)')


if __name__ == '__main__':
    generate_outputs()
