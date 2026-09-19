import os
import uuid
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


@pytest.fixture
def auth_header():
    unique_id = uuid.uuid4().hex[:8]
    email = f'tester_{unique_id}@pragati.edu'
    password = 'SecurePassword123!'

    reg_resp = client.post('/auth/register', json={'email': email, 'password': password})
    assert reg_resp.status_code in [200, 201]

    login_resp = client.post('/auth/login', json={'email': email, 'password': password})
    assert login_resp.status_code == 200
    token = login_resp.json()['access_token']
    return {'Authorization': f'Bearer {token}'}


@pytest.fixture
def second_auth_header():
    unique_id = uuid.uuid4().hex[:8]
    email = f'unauth_{unique_id}@pragati.edu'
    password = 'SecurePassword123!'

    client.post('/auth/register', json={'email': email, 'password': password})
    login_resp = client.post('/auth/login', json={'email': email, 'password': password})
    token = login_resp.json()['access_token']
    return {'Authorization': f'Bearer {token}'}


# =========================================================================
# Demonstration Scenario 1: Uploading a PDF
# =========================================================================
def test_scenario_01_upload_pdf(auth_header):
    pdf_path = os.path.join('sample_documents', 'sample_1_standard_mcq.pdf')
    with open(pdf_path, 'rb') as f:
        resp = client.post(
            '/documents/upload',
            files={'file': ('sample_1_standard_mcq.pdf', f, 'application/pdf')},
            headers=auth_header,
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data['filename'] == 'sample_1_standard_mcq.pdf'
    assert data['mime_type'] == 'application/pdf'
    assert data['file_size'] > 0
    assert 'id' in data


# =========================================================================
# Demonstration Scenario 2: Uploading an Image (PNG/JPEG)
# =========================================================================
def test_scenario_02_upload_image(auth_header):
    img_path = os.path.join('sample_documents', 'sample_5_scanned_image.png')
    with open(img_path, 'rb') as f:
        resp = client.post(
            '/documents/upload',
            files={'file': ('sample_5_scanned_image.png', f, 'image/png')},
            headers=auth_header,
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data['filename'] == 'sample_5_scanned_image.png'
    assert data['mime_type'] == 'image/png'


# =========================================================================
# Demonstration Scenario 3: Processing a Scanned / Low-Quality Document
# =========================================================================
def test_scenario_03_process_scanned_or_image(auth_header):
    img_path = os.path.join('sample_documents', 'sample_5_scanned_image.png')
    with open(img_path, 'rb') as f:
        up_resp = client.post(
            '/documents/upload',
            files={'file': ('sample_5_scanned_image.png', f, 'image/png')},
            headers=auth_header,
        )
    doc_id = up_resp.json()['id']

    ext_resp = client.post(f'/documents/{doc_id}/extract', headers=auth_header)
    assert ext_resp.status_code == 200
    res_data = ext_resp.json()
    assert res_data['page_count'] == 1
    assert len(res_data['pages']) == 1
    # Page must be marked as OCR or processed
    assert res_data['pages'][0]['page_number'] == 1


# =========================================================================
# Demonstration Scenario 4: Extracting Multiple Questions
# =========================================================================
def test_scenario_04_extract_multiple_questions(auth_header):
    pdf_path = os.path.join('sample_documents', 'sample_1_standard_mcq.pdf')
    with open(pdf_path, 'rb') as f:
        up_resp = client.post(
            '/documents/upload',
            files={'file': ('sample_1_standard_mcq.pdf', f, 'application/pdf')},
            headers=auth_header,
        )
    doc_id = up_resp.json()['id']

    # Execute extraction
    ext_resp = client.post(f'/documents/{doc_id}/extract', headers=auth_header)
    assert ext_resp.status_code == 200

    q_resp = client.get(f'/documents/{doc_id}/questions', headers=auth_header)
    assert q_resp.status_code == 200
    questions = q_resp.json()
    assert len(questions) == 3

    # Check question numbers
    q_nums = [q['question_number'] for q in questions]
    assert q_nums == ['1', '2', '3']


# =========================================================================
# Demonstration Scenario 5: Handling a Question Spanning Multiple Pages
# =========================================================================
def test_scenario_05_multipage_spanning_question(auth_header):
    pdf_path = os.path.join('sample_documents', 'sample_2_multipage_spanning.pdf')
    with open(pdf_path, 'rb') as f:
        up_resp = client.post(
            '/documents/upload',
            files={'file': ('sample_2_multipage_spanning.pdf', f, 'application/pdf')},
            headers=auth_header,
        )
    doc_id = up_resp.json()['id']

    ext_resp = client.post(f'/documents/{doc_id}/extract', headers=auth_header)
    assert ext_resp.status_code == 200

    q_resp = client.get(f'/documents/{doc_id}/questions', headers=auth_header)
    assert q_resp.status_code == 200
    questions = q_resp.json()
    assert len(questions) == 3

    # Question 2 spans across page 1 and page 2
    q2 = next(q for q in questions if q['question_number'] == '2')
    assert 1 in q2['source_pages']
    assert 2 in q2['source_pages']
    assert len(q2['options']) == 4
    assert q2['answer'] == 'B'


# =========================================================================
# Demonstration Scenario 6: Extracting Question Options
# =========================================================================
def test_scenario_06_extract_question_options(auth_header):
    pdf_path = os.path.join('sample_documents', 'sample_1_standard_mcq.pdf')
    with open(pdf_path, 'rb') as f:
        up_resp = client.post(
            '/documents/upload',
            files={'file': ('sample_1_standard_mcq.pdf', f, 'application/pdf')},
            headers=auth_header,
        )
    doc_id = up_resp.json()['id']

    client.post(f'/documents/{doc_id}/extract', headers=auth_header)

    q_resp = client.get(f'/documents/{doc_id}/questions', headers=auth_header)
    questions = q_resp.json()
    q1 = questions[0]

    assert len(q1['options']) == 4
    assert [opt['key'] for opt in q1['options']] == ['A', 'B', 'C', 'D']
    assert q1['options'][0]['text'] == 'Queue'
    assert q1['options'][1]['text'] == 'Stack'


# =========================================================================
# Demonstration Scenario 7: Detecting and Associating an Answer Key
# =========================================================================
def test_scenario_07_detect_and_associate_answer_key(auth_header):
    pdf_path = os.path.join('sample_documents', 'sample_3_with_end_answer_key.pdf')
    with open(pdf_path, 'rb') as f:
        up_resp = client.post(
            '/documents/upload',
            files={'file': ('sample_3_with_end_answer_key.pdf', f, 'application/pdf')},
            headers=auth_header,
        )
    doc_id = up_resp.json()['id']

    client.post(f'/documents/{doc_id}/extract', headers=auth_header)

    # 1. Verify answer key items parsed
    ak_resp = client.get(f'/documents/{doc_id}/answer-key', headers=auth_header)
    assert ak_resp.status_code == 200
    answer_keys = ak_resp.json()
    assert len(answer_keys) == 5

    # 2. Verify questions received answers from key
    q_resp = client.get(f'/documents/{doc_id}/questions', headers=auth_header)
    questions = q_resp.json()
    assert len(questions) == 5

    q1 = next(q for q in questions if q['question_number'] == '1')
    assert q1['answer'] == 'B'
    assert q1['answer_source'] == 'document_answer_key'
    assert q1['answer_status'] == 'matched'

    q2 = next(q for q in questions if q['question_number'] == '2')
    assert q2['answer'] == 'C'
    assert q2['answer_source'] == 'document_answer_key'
    assert q2['answer_status'] == 'matched'


# =========================================================================
# Demonstration Scenario 8: Showing Uncertain / Low-Confidence Extraction
# =========================================================================
def test_scenario_08_uncertain_low_confidence_review(auth_header):
    pdf_path = os.path.join('sample_documents', 'sample_6_noisy_low_confidence.pdf')
    with open(pdf_path, 'rb') as f:
        up_resp = client.post(
            '/documents/upload',
            files={'file': ('sample_6_noisy_low_confidence.pdf', f, 'application/pdf')},
            headers=auth_header,
        )
    doc_id = up_resp.json()['id']

    client.post(f'/documents/{doc_id}/extract', headers=auth_header)

    # Retrieve review items
    rev_resp = client.get(f'/documents/{doc_id}/review-items', headers=auth_header)
    assert rev_resp.status_code == 200
    review_items = rev_resp.json()
    assert len(review_items) >= 1

    # Verify review flags & reasons
    q1 = next(q for q in review_items if q['question_number'] == '1')
    assert q1['needs_review'] is True
    assert q1['confidence'] < 0.75
    assert len(q1['review_reasons']) > 0
    assert 'very_short_question_stem' in q1['review_reasons']
    assert 'discontinuous_option_keys' in q1['review_reasons']


# =========================================================================
# Demonstration Scenario 9: Retrieving Final Structured Question Data
# =========================================================================
def test_scenario_09_retrieve_structured_export(auth_header):
    pdf_path = os.path.join('sample_documents', 'sample_1_standard_mcq.pdf')
    with open(pdf_path, 'rb') as f:
        up_resp = client.post(
            '/documents/upload',
            files={'file': ('sample_1_standard_mcq.pdf', f, 'application/pdf')},
            headers=auth_header,
        )
    doc_id = up_resp.json()['id']

    client.post(f'/documents/{doc_id}/extract', headers=auth_header)

    export_resp = client.get(f'/documents/{doc_id}/export', headers=auth_header)
    assert export_resp.status_code == 200
    data = export_resp.json()

    assert data['document_id'] == doc_id
    assert data['filename'] == 'sample_1_standard_mcq.pdf'
    assert data['total_questions'] == 3
    assert len(data['questions']) == 3

    first_q = data['questions'][0]
    assert 'question_text' in first_q
    assert 'options' in first_q
    assert 'answer' in first_q
    assert 'source_pages' in first_q
    assert 'confidence' in first_q


# =========================================================================
# Demonstration Scenario 10: Handling Invalid or Unsupported Document
# =========================================================================
def test_scenario_10_reject_invalid_or_malformed_document(auth_header):
    invalid_path = os.path.join('sample_documents', 'sample_invalid.pdf')
    with open(invalid_path, 'rb') as f:
        resp = client.post(
            '/documents/upload',
            files={'file': ('sample_invalid.pdf', f, 'application/pdf')},
            headers=auth_header,
        )
    assert resp.status_code == 400
    detail = resp.json()['detail']
    assert 'Invalid or corrupted file' in detail or 'header signature' in detail


# =========================================================================
# Security & Authorization Tests: Multi-Tenant Isolation
# =========================================================================
def test_security_multi_tenant_isolation(auth_header, second_auth_header):
    pdf_path = os.path.join('sample_documents', 'sample_1_standard_mcq.pdf')
    with open(pdf_path, 'rb') as f:
        up_resp = client.post(
            '/documents/upload',
            files={'file': ('sample_1_standard_mcq.pdf', f, 'application/pdf')},
            headers=auth_header,
        )
    doc_id = up_resp.json()['id']

    # User B must NOT be able to view User A's document
    get_resp = client.get(f'/documents/{doc_id}', headers=second_auth_header)
    assert get_resp.status_code == 404

    # Unauthenticated request must be rejected
    unauth_resp = client.get(f'/documents/{doc_id}')
    assert unauth_resp.status_code in [401, 403]


# =========================================================================
# Document Linking Test: Associating External Answer Key Document
# =========================================================================
def test_linking_external_answer_key_document(auth_header):
    # 1. Upload Question Paper
    qp_path = os.path.join('sample_documents', 'sample_1_standard_mcq.pdf')
    with open(qp_path, 'rb') as f:
        qp_resp = client.post(
            '/documents/upload',
            files={'file': ('qp.pdf', f, 'application/pdf')},
            headers=auth_header,
        )
    qp_id = qp_resp.json()['id']
    client.post(f'/documents/{qp_id}/extract', headers=auth_header)

    # 2. Upload Standalone Answer Key
    ak_path = os.path.join('sample_documents', 'sample_4_separate_answer_key.pdf')
    with open(ak_path, 'rb') as f:
        ak_resp = client.post(
            '/documents/upload',
            files={'file': ('ak.pdf', f, 'application/pdf')},
            headers=auth_header,
        )
    ak_id = ak_resp.json()['id']
    client.post(f'/documents/{ak_id}/extract', headers=auth_header)

    # 3. Link them
    link_resp = client.post(
        f'/documents/{qp_id}/link',
        json={'related_document_id': ak_id, 'relation_type': 'answer_key'},
        headers=auth_header,
    )
    assert link_resp.status_code == 201

    # Verify link relation was established
    doc_detail = client.get(f'/documents/{qp_id}', headers=auth_header).json()
    assert len(doc_detail['relations_as_parent']) == 1
    assert doc_detail['relations_as_parent'][0]['related_document_id'] == ak_id


# =========================================================================
# Human-in-the-Loop Review Test: PATCH /questions/{id}
# =========================================================================
def test_human_in_the_loop_question_review(auth_header):
    pdf_path = os.path.join('sample_documents', 'sample_6_noisy_low_confidence.pdf')
    with open(pdf_path, 'rb') as f:
        up_resp = client.post(
            '/documents/upload',
            files={'file': ('sample_6_noisy_low_confidence.pdf', f, 'application/pdf')},
            headers=auth_header,
        )
    doc_id = up_resp.json()['id']
    client.post(f'/documents/{doc_id}/extract', headers=auth_header)

    q_resp = client.get(f'/documents/{doc_id}/questions', headers=auth_header)
    questions = q_resp.json()
    target_q = questions[0]
    assert target_q['needs_review'] is True

    # Reviewer corrects the question stem and options, verifies it
    patch_resp = client.patch(
        f'/questions/{target_q["id"]}',
        json={
            'question_text': 'Who is considered the father of modern computing?',
            'answer': 'A',
            'status': 'verified',
        },
        headers=auth_header,
    )
    assert patch_resp.status_code == 200
    updated = patch_resp.json()
    assert updated['question_text'] == 'Who is considered the father of modern computing?'
    assert updated['answer'] == 'A'
    assert updated['status'] == 'verified'
    assert updated['needs_review'] is False
    assert updated['confidence'] == 1.0
