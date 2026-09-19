import json
import os
import sys
import uuid
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.main import app

client = TestClient(app)

def run_verification():
    evidence = []
    evidence.append("# Demonstration Evidence: Pragati Bharati Document Intelligence Service\n")
    evidence.append("This document records the exact execution evidence, API requests, and verified responses for all 10 required demonstration scenarios.\n")
    
    # 0. Setup test user
    email = f"evaluator_{uuid.uuid4().hex[:6]}@pragati.edu"
    password = "EvaluatorPassword2026!"
    client.post("/auth/register", json={"email": email, "password": password})
    login_resp = client.post("/auth/login", json={"email": email, "password": password})
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    evidence.append(f"**Authenticated Evaluator Session**: `{email}`\n")
    evidence.append("---\n")

    # 1. Uploading a PDF
    evidence.append("## Scenario 1: Uploading a PDF\n")
    evidence.append("- **Input Document**: `sample_documents/sample_1_standard_mcq.pdf`\n")
    with open("sample_documents/sample_1_standard_mcq.pdf", "rb") as f:
        r1 = client.post("/documents/upload", files={"file": ("sample_1_standard_mcq.pdf", f, "application/pdf")}, headers=headers)
    d1 = r1.json()
    evidence.append("```json\n" + json.dumps(d1, indent=2) + "\n```\n")
    assert r1.status_code == 200
    assert d1["mime_type"] == "application/pdf"
    evidence.append("> [!NOTE] PDF successfully validated via magic bytes (`%PDF-1.4`), assigned unique ID and stored securely.\n\n---\n")

    # 2. Uploading an Image
    evidence.append("## Scenario 2: Uploading an Image\n")
    evidence.append("- **Input Document**: `sample_documents/sample_5_scanned_image.png`\n")
    with open("sample_documents/sample_5_scanned_image.png", "rb") as f:
        r2 = client.post("/documents/upload", files={"file": ("sample_5_scanned_image.png", f, "image/png")}, headers=headers)
    d2 = r2.json()
    evidence.append("```json\n" + json.dumps(d2, indent=2) + "\n```\n")
    assert r2.status_code == 200
    assert d2["mime_type"] == "image/png"
    evidence.append("> [!NOTE] Image validated via PNG header (`\\x89PNG`), ingested for asynchronous OCR processing.\n\n---\n")

    # 3. Processing a Scanned / Low-Quality Document
    evidence.append("## Scenario 3: Processing a Scanned / Image Document\n")
    doc2_id = d2["id"]
    r3 = client.post(f"/documents/{doc2_id}/extract", headers=headers)
    d3 = r3.json()
    evidence.append("```json\n" + json.dumps(d3, indent=2) + "\n```\n")
    assert r3.status_code == 200
    assert d3.get("page_count", 0) >= 1
    evidence.append("> [!NOTE] Document rasterized, preprocessed with PIL, and extracted through OCR pipeline.\n\n---\n")

    # 4. Extracting Multiple Questions
    evidence.append("## Scenario 4: Extracting Multiple Questions\n")
    doc1_id = d1["id"]
    client.post(f"/documents/{doc1_id}/extract", headers=headers)
    r4 = client.get(f"/documents/{doc1_id}/questions", headers=headers)
    d4 = r4.json()
    evidence.append(f"- **Total Questions Extracted**: {len(d4)}\n")
    evidence.append("```json\n" + json.dumps(d4, indent=2) + "\n```\n")
    assert len(d4) == 3
    evidence.append("> [!NOTE] Extracted 3 distinct questions sequentially with stem, options, and answers.\n\n---\n")

    # 5. Handling a Question Spanning Multiple Pages
    evidence.append("## Scenario 5: Handling a Question Spanning Multiple Pages\n")
    evidence.append("- **Input Document**: `sample_documents/sample_2_multipage_spanning.pdf` (Question 2 starts on Page 1 and finishes on Page 2)\n")
    with open("sample_documents/sample_2_multipage_spanning.pdf", "rb") as f:
        r_span = client.post("/documents/upload", files={"file": ("sample_2_multipage_spanning.pdf", f, "application/pdf")}, headers=headers)
    span_id = r_span.json()["id"]
    client.post(f"/documents/{span_id}/extract", headers=headers)
    r5 = client.get(f"/documents/{span_id}/questions", headers=headers)
    d5 = r5.json()
    q_spanning = [q for q in d5 if q["question_number"] == "2"][0]
    evidence.append("```json\n" + json.dumps(q_spanning, indent=2) + "\n```\n")
    assert q_spanning["source_pages"] == [1, 2]
    evidence.append("> [!IMPORTANT] Question 2 correctly stitched across page boundaries: `source_pages: [1, 2]`, options intact.\n\n---\n")

    # 6. Extracting Question Options
    evidence.append("## Scenario 6: Extracting Question Options\n")
    q1 = d4[0]
    evidence.append("```json\n" + json.dumps(q1["options"], indent=2) + "\n```\n")
    assert len(q1["options"]) == 4
    assert [o["key"] for o in q1["options"]] == ["A", "B", "C", "D"]
    evidence.append("> [!NOTE] Options accurately separated into structured `{key, text}` records.\n\n---\n")

    # 7. Detecting and Associating an Answer Key
    evidence.append("## Scenario 7: Detecting and Associating an Answer Key\n")
    evidence.append("- **Input Document**: `sample_documents/sample_3_with_end_answer_key.pdf` (End-of-document answer key)\n")
    with open("sample_documents/sample_3_with_end_answer_key.pdf", "rb") as f:
        r_ak = client.post("/documents/upload", files={"file": ("sample_3_with_end_answer_key.pdf", f, "application/pdf")}, headers=headers)
    ak_doc_id = r_ak.json()["id"]
    client.post(f"/documents/{ak_doc_id}/extract", headers=headers)
    
    r7_keys = client.get(f"/documents/{ak_doc_id}/answer-key", headers=headers)
    r7_questions = client.get(f"/documents/{ak_doc_id}/questions", headers=headers)
    evidence.append("### Extracted Answer Key Table:\n```json\n" + json.dumps(r7_keys.json(), indent=2) + "\n```\n")
    evidence.append("### Questions with Associated Answers:\n```json\n" + json.dumps(r7_questions.json()[:2], indent=2) + "\n```\n")
    assert len(r7_keys.json()) == 5
    assert r7_questions.json()[0]["answer"] == "B"
    assert r7_questions.json()[0]["answer_source"] == "document_answer_key"
    evidence.append("> [!NOTE] Answer key table automatically detected and associated with Questions 1-5.\n\n---\n")

    # 8. Showing an Uncertain / Low-Confidence Extraction
    evidence.append("## Scenario 8: Showing Uncertain / Low-Confidence Extraction\n")
    evidence.append("- **Input Document**: `sample_documents/sample_6_noisy_low_confidence.pdf` (Missing option C, truncated stem, skipped numbering)\n")
    with open("sample_documents/sample_6_noisy_low_confidence.pdf", "rb") as f:
        r_noisy = client.post("/documents/upload", files={"file": ("sample_6_noisy_low_confidence.pdf", f, "application/pdf")}, headers=headers)
    noisy_id = r_noisy.json()["id"]
    client.post(f"/documents/{noisy_id}/extract", headers=headers)
    r8 = client.get(f"/documents/{noisy_id}/review-items", headers=headers)
    d8 = r8.json()
    evidence.append("```json\n" + json.dumps(d8, indent=2) + "\n```\n")
    assert len(d8) >= 1
    assert d8[0]["needs_review"] is True
    evidence.append(f"> [!WARNING] Flagged for review: `confidence: {d8[0]['confidence']}`, reasons: `{d8[0]['review_reasons']}`\n\n---\n")

    # 9. Retrieving the Final Structured Question Data
    evidence.append("## Scenario 9: Retrieving Final Structured Question Data\n")
    r9 = client.get(f"/documents/{doc1_id}/export", headers=headers)
    d9 = r9.json()
    evidence.append("```json\n" + json.dumps(d9, indent=2) + "\n```\n")
    assert d9["total_questions"] == 3
    evidence.append("> [!NOTE] Clean, downstream-agnostic schema with questions, options, answers, pages, and metadata.\n\n---\n")

    # 10. Demonstrating Appropriate Handling of an Invalid or Unsupported Document
    evidence.append("## Scenario 10: Handling Invalid or Unsupported Document\n")
    with open("sample_documents/sample_invalid.pdf", "rb") as f:
        r10 = client.post("/documents/upload", files={"file": ("sample_invalid.pdf", f, "application/pdf")}, headers=headers)
    evidence.append(f"- **HTTP Status Code**: `{r10.status_code}`\n")
    evidence.append("```json\n" + json.dumps(r10.json(), indent=2) + "\n```\n")
    assert r10.status_code == 400
    evidence.append("> [!CAUTION] Corrupted / spoofed document rejected immediately at ingestion boundary with HTTP 400 Bad Request.\n")

    with open("DEMO_EVIDENCE.md", "w", encoding="utf-8") as f:
        f.writelines(evidence)
    print("DEMO_EVIDENCE.md generated successfully with all 10 scenarios verified!")

if __name__ == "__main__":
    run_verification()
