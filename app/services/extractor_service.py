import re
from typing import Any, Dict, List, Optional, Tuple

from app.services.answer_matcher import match_answers_with_questions
from app.services.ocr_service import PageContent

# Regex patterns for question detection
QUESTION_START_PATTERNS = [
    # Q1., Q.1, Q 1., Q1:, Q.1:
    re.compile(r'^(?:Q(?:uestion)?\.?\s*(?:No\.?)?\s*(\d+[a-zA-Z]?))[\.\:\)\-\s]+(.*)$', re.IGNORECASE),
    # 1., 12., 101. (at start of line, followed by space or capital letter)
    re.compile(r'^(\d+[a-zA-Z]?)\.\s+(.*)$'),
    # 1), 12)
    re.compile(r'^(\d+[a-zA-Z]?)\)\s+(.*)$'),
    # [1], (1)
    re.compile(r'^[\[\(](\d+[a-zA-Z]?)[\]\)]\s+(.*)$'),
    # 1 - Question text
    re.compile(r'^(\d+[a-zA-Z]?)\s*\-\s+(.*)$'),
]

# Regex patterns for option detection
OPTION_PATTERNS = [
    # (A) text, (a) text, [A] text
    re.compile(r'(?:^|\s+)(?:\(|\[)([A-Da-d1-4])(?:\)|\])\s+([^\(\)\[\]\n]+)'),
    # A. text, A) text
    re.compile(r'(?:^|\s+)([A-Da-d1-4])[\.\)]\s+([^\n\(\)\[\]]+)'),
]

# Patterns for inline answers
INLINE_ANSWER_PATTERNS = [
    re.compile(r'(?:Ans(?:wer)?\.?|Correct\s*Option|Correct\s*Ans(?:wer)?)\s*[:\-]?\s*(?:\(|\[)?([A-Da-d1-4]|True|False|[A-Za-z0-9\s]+)(?:\)|\])?', re.IGNORECASE),
]

# Patterns for inline explanations
INLINE_EXPLANATION_PATTERNS = [
    re.compile(r'(?:Explanation|Solution|Reason)\s*[:\-]\s*(.*)$', re.IGNORECASE | re.DOTALL),
]

# Answer key section header pattern
ANSWER_KEY_SECTION_PATTERN = re.compile(
    r'(?:^|\n)\s*(?:[-=*#_\s]*)\s*(?:ANSWER\s*KEY|ANSWERS|SOLUTIONS\s*KEY|KEY\s*ANSWERS)\s*(?:[-=*#_\s]*)\s*(?:\n|$)',
    re.IGNORECASE,
)


class RawQuestion:
    def __init__(
        self,
        number: str,
        stem_lines: List[str],
        pages: List[int],
        bounding_boxes: Optional[List[Dict[str, Any]]] = None,
        is_ocr: bool = False,
        ocr_confidence: float = 1.0,
        page_warnings: Optional[List[str]] = None,
    ):
        self.number = number
        self.stem_lines = stem_lines
        self.pages = pages
        self.bounding_boxes = bounding_boxes or []
        self.is_ocr = is_ocr
        self.ocr_confidence = ocr_confidence
        self.page_warnings = page_warnings or []


def split_text_into_exam_and_answer_key(pages: List[PageContent]) -> Tuple[List[PageContent], List[Dict[str, Any]]]:
    """
    Checks if a page or section contains an Answer Key header.
    Splits pages into question content and answer key raw items.
    """
    exam_pages: List[PageContent] = []
    answer_key_raw_items: List[Dict[str, Any]] = []

    for page in pages:
        match = ANSWER_KEY_SECTION_PATTERN.search(page.text)
        if match:
            # Document has answer key section on this page
            split_pos = match.start()
            exam_text = page.text[:split_pos].strip()
            ans_text = page.text[match.end():].strip()

            if exam_text:
                exam_pages.append(
                    PageContent(
                        page_number=page.page_number,
                        text=exam_text,
                        blocks=[b for b in page.blocks if b.get('bbox', [0, 0, 0, 0])[1] < 400],
                        is_ocr=page.is_ocr,
                        ocr_confidence=page.ocr_confidence,
                        warnings=page.warnings,
                    )
                )

            # Parse answer key entries from ans_text
            parsed_answers = parse_answer_key_text(ans_text, page.page_number)
            answer_key_raw_items.extend(parsed_answers)
        else:
            # Check if this entire page is purely an answer key (e.g. table of answers)
            if is_pure_answer_key_page(page.text):
                parsed_answers = parse_answer_key_text(page.text, page.page_number)
                answer_key_raw_items.extend(parsed_answers)
            else:
                exam_pages.append(page)

    return exam_pages, answer_key_raw_items


def is_pure_answer_key_page(text: str) -> bool:
    """Detects if a page consists mostly of question-answer pairs like '1. A 2. B 3. C'"""
    lines = [ln.strip() for ln in text.split('\n') if ln.strip()]
    if not lines:
        return False
        
    first_few = ' '.join(lines[:3]).lower()
    if 'answer key' in first_few or 'solutions key' in first_few:
        return True

    # Check pair density: if many items look like "1: A" or "1 - B"
    pairs = re.findall(r'(?:Q\.?\s*)?(\d+)\s*[\.\:\-\)]\s*([A-Da-d])\b', text)
    if len(pairs) >= 5 and len(pairs) / max(len(lines), 1) > 0.4:
        return True

    return False


def parse_answer_key_text(text: str, page_number: int) -> List[Dict[str, Any]]:
    """Parses text into question-number -> answer mapping."""
    results: List[Dict[str, Any]] = []

    # Format 1: Table or sequence like "1. A   2. B   3. C" or "Q1. A, Q2. B"
    pairs = re.findall(
        r'(?:Q(?:uestion)?\.?\s*(?:No\.?)?\s*)?(\d+[a-zA-Z]?)\s*[\.\:\-\)]\s*(?:\(|\[)?([A-Da-d]|True|False|[A-Za-z0-9]+)(?:\)|\])?',
        text,
        re.IGNORECASE,
    )
    for q_num, ans in pairs:
        results.append({
            'question_number': str(q_num).strip(),
            'answer': str(ans).strip().upper(),
            'explanation': None,
            'page_number': page_number,
            'raw_text': f'{q_num}. {ans}',
            'confidence': 1.0,
        })

    # Deduplicate keeping last or first occurrence
    seen = set()
    deduped = []
    for item in results:
        if item['question_number'] not in seen:
            seen.add(item['question_number'])
            deduped.append(item)

    return deduped


def match_question_start(line: str) -> Tuple[Optional[str], Optional[str]]:
    """Checks if a line marks the beginning of a new question."""
    cleaned = line.strip()
    for pattern in QUESTION_START_PATTERNS:
        m = pattern.match(cleaned)
        if m:
            q_num = m.group(1).strip()
            rest = m.group(2).strip()
            # Avoid false positives on options like "A." or roman numerals if captured
            if q_num.isdigit() or re.match(r'^\d+[a-zA-Z]?$', q_num):
                return q_num, rest
    return None, None


def extract_raw_questions(pages: List[PageContent]) -> List[RawQuestion]:
    """
    Iterates through pages, tracks question starts and continuations across pages.
    """
    raw_questions: List[RawQuestion] = []
    current_q: Optional[RawQuestion] = None

    for page in pages:
        lines = page.text.split('\n')
        for line in lines:
            trimmed = line.strip()
            if not trimmed:
                continue

            q_num, stem_part = match_question_start(trimmed)
            if q_num:
                # If we were already tracking a question, save it
                if current_q:
                    raw_questions.append(current_q)

                # Start new question
                current_q = RawQuestion(
                    number=q_num,
                    stem_lines=[stem_part] if stem_part else [],
                    pages=[page.page_number],
                    is_ocr=page.is_ocr,
                    ocr_confidence=page.ocr_confidence,
                    page_warnings=list(page.warnings),
                )
            else:
                # Continuation of current question
                if current_q:
                    current_q.stem_lines.append(trimmed)
                    if page.page_number not in current_q.pages:
                        current_q.pages.append(page.page_number)
                    if page.is_ocr:
                        current_q.is_ocr = True
                        current_q.ocr_confidence = min(current_q.ocr_confidence, page.ocr_confidence)
                    for w in page.warnings:
                        if w not in current_q.page_warnings:
                            current_q.page_warnings.append(w)
                else:
                    # Header/preamble before Question 1 - ignore or keep if needed
                    pass

    if current_q:
        raw_questions.append(current_q)

    return raw_questions


def extract_options_from_lines(lines: List[str]) -> Tuple[List[Dict[str, str]], List[str], Optional[str], Optional[str]]:
    """
    Separates stem lines, options, inline answer, and inline explanation.
    Returns: (options, remaining_stem_lines, inline_answer, explanation)
    """
    options: List[Dict[str, str]] = []
    stem_lines: List[str] = []
    inline_answer: Optional[str] = None
    explanation: Optional[str] = None

    option_keys_seen = set()
    in_explanation = False
    explanation_lines = []

    for line in lines:
        trimmed = line.strip()
        if not trimmed:
            continue

        # Check inline explanation
        if in_explanation:
            explanation_lines.append(trimmed)
            continue

        for exp_pat in INLINE_EXPLANATION_PATTERNS:
            exp_match = exp_pat.search(trimmed)
            if exp_match:
                in_explanation = True
                explanation_lines.append(exp_match.group(1).strip())
                trimmed = trimmed[:exp_match.start()].strip()
                break

        if not trimmed:
            continue

        # Check inline answer
        for ans_pat in INLINE_ANSWER_PATTERNS:
            ans_match = ans_pat.search(trimmed)
            if ans_match:
                inline_answer = ans_match.group(1).strip().upper()
                trimmed = trimmed[:ans_match.start()].strip()
                break

        if not trimmed:
            continue

        # Check options on this line
        # Single line might contain multiple options: "(A) Apple (B) Banana"
        # Try finding all matches
        line_options = []
        # Pattern 1: (A) or [A]
        matches1 = list(re.finditer(r'(?:^|\s+)(?:\(|\[)([A-Da-d1-4])(?:\)|\])\s+([^\(\)\[\]\n]+)', trimmed))
        if matches1:
            for m in matches1:
                key = m.group(1).upper()
                text = m.group(2).strip()
                if key not in option_keys_seen:
                    line_options.append({'key': key, 'text': text})
                    option_keys_seen.add(key)
        else:
            # Pattern 2: A. or A)
            matches2 = list(re.finditer(r'(?:^|\s+)([A-Da-d1-4])[\.\)]\s+([^\n\(\)\[\]]+)', trimmed))
            if matches2:
                for m in matches2:
                    key = m.group(1).upper()
                    text = m.group(2).strip()
                    if key not in option_keys_seen:
                        line_options.append({'key': key, 'text': text})
                        option_keys_seen.add(key)

        if line_options:
            options.extend(line_options)
        else:
            if not options:
                stem_lines.append(trimmed)
            else:
                # Continuation of last option
                if options:
                    options[-1]['text'] += f' {trimmed}'

    full_explanation = ' '.join(explanation_lines).strip() if explanation_lines else None
    return options, stem_lines, inline_answer, full_explanation


def classify_question_type(stem: str, options: List[Dict[str, str]]) -> str:
    """Classifies question type based on stem text and options."""
    if len(options) >= 2:
        # Check if multiple choice or single choice
        stem_lower = stem.lower()
        if 'select all that apply' in stem_lower or 'which of the following are' in stem_lower:
            return 'multiple_choice'
        return 'single_choice'

    lower = stem.lower()
    if 'true or false' in lower or 'state whether true or false' in lower or 'true/false' in lower:
        return 'true_false'
    
    if '____' in stem or 'fill in the blank' in lower or '.........' in stem:
        return 'fill_in_the_blank'

    return 'descriptive'


def compute_confidence_and_review(
    stem: str,
    options: List[Dict[str, str]],
    source_pages: List[int],
    ocr_confidence: float,
    page_warnings: List[str],
    has_answer: bool,
    expected_number: Optional[int],
    actual_number: str,
) -> Tuple[float, bool, List[str]]:
    """
    Computes a reliability confidence score (0.0 - 1.0) and review requirements.
    """
    confidence = 1.0
    reasons = []

    # Factor 1: OCR quality
    if ocr_confidence < 0.7:
        confidence -= 0.25
        reasons.append('low_ocr_confidence')
    elif ocr_confidence < 0.85:
        confidence -= 0.1

    # Factor 2: Question stem length & clarity
    if len(stem.strip()) < 15:
        confidence -= 0.3
        reasons.append('very_short_question_stem')

    # Factor 3: Option continuity
    if options:
        opt_keys = [o['key'] for o in options]
        # Standard A, B, C, D check
        if opt_keys == ['A', 'B', 'C', 'D']:
            pass
        elif opt_keys in [['A', 'B'], ['A', 'B', 'C']]:
            confidence -= 0.15
            reasons.append(f'partial_options_count_{len(options)}')
        else:
            # Check missing middle options
            expected_keys = ['A', 'B', 'C', 'D'][:len(opt_keys)]
            if opt_keys != expected_keys:
                confidence -= 0.2
                reasons.append('discontinuous_option_keys')

    # Factor 4: Spanning multiple pages
    if len(source_pages) > 1:
        reasons.append('split_across_pages')
        confidence -= 0.05

    # Factor 5: Page warnings
    for w in page_warnings:
        if w not in reasons:
            reasons.append(w)
            if 'low_resolution' in w:
                confidence -= 0.1

    # Factor 6: Sequence order
    if expected_number is not None and actual_number.isdigit():
        act_num = int(actual_number)
        if act_num != expected_number:
            reasons.append(f'non_sequential_number_expected_{expected_number}_got_{act_num}')
            confidence -= 0.1

    # Factor 7: Answer association
    if not has_answer:
        reasons.append('unmatched_answer_key')
        confidence -= 0.05

    confidence = round(max(0.1, min(1.0, confidence)), 2)
    needs_review = (
        confidence < 0.75
        or 'very_short_question_stem' in reasons
        or 'discontinuous_option_keys' in reasons
        or 'low_ocr_confidence' in reasons
        or 'split_across_pages' in reasons
    )

    return confidence, needs_review, reasons


def extract_structured_questions(
    pages: List[PageContent],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Main extraction orchestrator:
    1. Splits pages into exam pages and answer key items
    2. Identifies question boundaries across pages
    3. Parses options, stem, inline answers, explanations
    4. Computes confidence scores and review reasons
    Returns: (structured_questions, answer_key_items)
    """
    exam_pages, answer_key_items = split_text_into_exam_and_answer_key(pages)
    raw_questions = extract_raw_questions(exam_pages)

    structured_questions: List[Dict[str, Any]] = []
    expected_num = 1

    for raw_q in raw_questions:
        options, stem_lines, inline_ans, explanation = extract_options_from_lines(raw_q.stem_lines)
        question_text = ' '.join(stem_lines).strip()

        q_type = classify_question_type(question_text, options)
        raw_full_text = '\n'.join(raw_q.stem_lines)

        has_answer = inline_ans is not None

        confidence, needs_review, review_reasons = compute_confidence_and_review(
            stem=question_text,
            options=options,
            source_pages=raw_q.pages,
            ocr_confidence=raw_q.ocr_confidence,
            page_warnings=raw_q.page_warnings,
            has_answer=has_answer,
            expected_number=expected_num if raw_q.number.isdigit() else None,
            actual_number=raw_q.number,
        )

        if raw_q.number.isdigit():
            expected_num = int(raw_q.number) + 1

        structured_questions.append({
            'question_number': raw_q.number,
            'question_text': question_text,
            'question_type': q_type,
            'options': options,
            'answer': inline_ans,
            'answer_source': 'inline' if inline_ans else None,
            'answer_status': 'matched' if inline_ans else 'unmatched',
            'answer_confidence': 1.0 if inline_ans else 0.0,
            'explanation': explanation,
            'source_pages': raw_q.pages,
            'raw_text': raw_full_text,
            'bounding_boxes': raw_q.bounding_boxes,
            'confidence': confidence,
            'needs_review': needs_review,
            'review_reasons': review_reasons,
            'status': 'auto_extracted',
        })

    matched_questions = match_answers_with_questions(structured_questions, answer_key_items, source_label='document_answer_key')
    return matched_questions, answer_key_items
