import re
from pathlib import Path

import fitz


def extract_pages_from_pdf(file_path: str):
    doc = fitz.open(file_path)
    pages = []

    for page_no in range(doc.page_count):
        page = doc[page_no]
        text = page.get_text("text")
        pages.append({
            'page_no': page_no + 1,
            'text': text.strip(),
            'char_count': len(text.strip()),
        })

    return {
        'page_count': doc.page_count,
        'pages': pages,
    }


def extract_question_candidates(text: str):
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    question_lines = []
    for line in lines:
        if re.search(r'Q\d+|\b\d+\.', line, flags=re.I):
            question_lines.append(line)
    return question_lines
