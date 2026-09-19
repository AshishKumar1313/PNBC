import io
import uuid

import fitz
from fastapi.testclient import TestClient

from app.main import app
from app.services.extractor_service import extract_structured_questions
from app.services.ocr_service import PageContent

client = TestClient(app)


def test_health_check():
    response = client.get('/health')
    assert response.status_code == 200
    assert response.json()['status'] == 'ok'


def test_register_and_login():
    email = f'student_{uuid.uuid4().hex[:8]}@example.com'
    password = 'secret123'

    register_response = client.post('/auth/register', json={'email': email, 'password': password})
    assert register_response.status_code == 200

    login_response = client.post('/auth/login', json={'email': email, 'password': password})
    assert login_response.status_code == 200
    assert 'access_token' in login_response.json()


def test_upload_valid_pdf_and_reject_fake_pdf():
    email = f'docuser_{uuid.uuid4().hex[:8]}@example.com'
    password = 'secret123'

    client.post('/auth/register', json={'email': email, 'password': password})
    login_response = client.post('/auth/login', json={'email': email, 'password': password})
    token = login_response.json()['access_token']
    headers = {'Authorization': f'Bearer {token}'}

    pdf_content = b'%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF'
    upload_response = client.post(
        '/documents',
        files={'file': ('sample.pdf', pdf_content, 'application/pdf')},
        headers=headers,
    )
    assert upload_response.status_code == 200
    assert upload_response.json()['filename'] == 'sample.pdf'

    fake_response = client.post(
        '/documents',
        files={'file': ('fake.pdf', b'not-a-real-pdf', 'application/pdf')},
        headers=headers,
    )
    assert fake_response.status_code == 400


def test_extract_pdf_pages():
    email = f'extract_{uuid.uuid4().hex[:8]}@example.com'
    password = 'secret123'
    register_response = client.post('/auth/register', json={'email': email, 'password': password})
    assert register_response.status_code == 200

    login_response = client.post('/auth/login', json={'email': email, 'password': password})
    token = login_response.json()['access_token']
    headers = {'Authorization': f'Bearer {token}'}

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), 'Q1. What is AI?')
    pdf_bytes = io.BytesIO()
    doc.save(pdf_bytes)
    pdf_bytes.seek(0)

    upload_response = client.post(
        '/documents',
        files={'file': ('exam.pdf', pdf_bytes.getvalue(), 'application/pdf')},
        headers=headers,
    )
    document_id = upload_response.json()['id']

    extraction_response = client.post(f'/documents/{document_id}/extract', headers=headers)
    assert extraction_response.status_code == 200
    payload = extraction_response.json()
    assert payload['page_count'] >= 1
    assert 'Q1. What is AI?' in payload['pages'][0]['text']


def test_question_extraction_pipeline_extracts_questions_and_answer_key():
    pages = [
        PageContent(
            page_number=1,
            text='Q1. What is AI?\nA. A machine\nB. A river\nC. A book\nD. A city\nQ2. Which is a language?\nA. Python\nB. Rock\nC. Chair\nD. Table\nANSWER KEY\n1. A\n2. B',
            blocks=[],
            is_ocr=False,
            ocr_confidence=1.0,
            warnings=[],
        )
    ]

    questions, answer_key = extract_structured_questions(pages)

    assert len(questions) == 2
    assert questions[0]['question_number'] == '1'
    assert questions[0]['question_text'] == 'What is AI?'
    assert questions[0]['options'][0]['key'] == 'A'
    assert questions[0]['answer'] == 'A'
    assert questions[1]['question_number'] == '2'
    assert answer_key[0]['question_number'] == '1'
    assert answer_key[0]['answer'] == 'A'
    assert answer_key[1]['question_number'] == '2'
    assert answer_key[1]['answer'] == 'B'
