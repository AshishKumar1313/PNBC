# Pragati Bharati — Document Intelligence & Question Extraction Service

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688.svg?logo=fastapi)](https://fastapi.tiangolo.com)
[![Python](https://img.shields.io/badge/Python-3.12-blue.svg?logo=python)](https://python.org)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791.svg?logo=postgresql)](https://www.postgresql.org/)
[![Redis](https://img.shields.io/badge/Redis-7-red.svg?logo=redis)](https://redis.io/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED.svg?logo=docker)](https://www.docker.com/)

An asynchronous, production-grade document intelligence and question extraction service built for **Pragati Bharati**. The platform ingests diverse, unstructured examination materials (digital PDFs, scanned PDFs, JPG, and PNG images) and extracts structured, machine-readable questions and associated answer keys with provenance tracking and confidence scoring.

---

## 🚀 Key Features

- **Multi-Format Ingestion**: Supports digital PDFs, scanned PDFs, JPG, JPEG, and PNG images.
- **Security & Integrity**: Magic-byte signature verification (`%PDF`, `\x89PNG`, `\xff\xd8\xff`), file size enforcement, and UUID-based isolated file storage.
- **Intelligent Question Extraction**:
  - Automatically identifies varied numbering styles (`Q1.`, `1.`, `Question 1:`, `[1]`, `1)`).
  - Handles questions spanning across page boundaries without breaking continuity.
  - Extracts options (`(A)`, `(B)`, `(C)`, `(D)`) and separates question stems.
  - Classifies question types (`multiple_choice`, `single_choice`, `true_false`, `fill_in_the_blank`, `descriptive`).
- **Answer Key Association**:
  - Extracts inline answers (`Ans: B`, `Answer: Option C`).
  - Detects dedicated answer key sections at the end of documents or on dedicated pages.
  - Supports linking external, standalone answer key documents to question papers.
  - Handles conflicts and marks unverified or ambiguous answers as `uncertain` or `unmatched`.
- **Confidence Scoring & Human-in-the-Loop Review**:
  - Multi-factor scoring rubric based on OCR readability, stem completeness, option continuity, sequence order, and answer correlation.
  - Automatic `needs_review` flag with explicit human-readable reasons (e.g. `split_across_pages`, `discontinuous_option_keys`, `low_ocr_confidence`).
  - Dedicated human review workflow (`PATCH /questions/{id}`) to verify, edit, or reject flagged extractions.
- **Dual-Mode Asynchronous Architecture**:
  - Distributed background job queue using **ARQ + Redis** for production clustering.
  - Seamless in-process fallback using **FastAPI BackgroundTasks** for zero-dependency standalone operation and rapid unit testing.
- **Multi-Tenant Security**: Stateless JWT bearer authentication (`/auth/register`, `/auth/login`, `/auth/me`) ensuring strict tenant isolation.

---

## 🏗️ System Architecture

```
Client / Assessment Platform
       │  (REST API with JWT Auth)
       ▼
┌─────────────────────────────────────────────────────────────┐
│                      FastAPI Gateway                        │
│   ├── Auth Guard & Tenant Isolation                         │
│   ├── Magic-Byte File Validation & SHA256 Hashing           │
│   └── Dual-Mode Queue Dispatcher (Redis ARQ / In-Process)   │
└──────────────────────────────┬──────────────────────────────┘
                               │
                ┌──────────────┴──────────────┐
                ▼                             ▼
   ┌────────────────────────┐    ┌───────────────────────────┐
   │    Worker Tier (ARQ)   │    │ BackgroundTasks (Local)   │
   └────────────┬───────────┘    └─────────────┬─────────────┘
                └──────────────┬───────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                 Document Intelligence Pipeline              │
│   ├── 1. Text & Layout Engine (PyMuPDF & PIL / Tesseract)  │
│   ├── 2. Question Segmentation & Multi-Page Stitching       │
│   ├── 3. Option Parser & Type Classifier                    │
│   ├── 4. Answer Key Matcher & Conflict Detector             │
│   └── 5. Confidence Scoring & Review Engine                 │
└──────────────────────────────┬──────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                       Persistence Tier                      │
│   ├── PostgreSQL 16 / SQLite (SQLAlchemy 2.0 Async ORM)    │
│   └── Alembic Database Migrations                           │
└─────────────────────────────────────────────────────────────┘
```

For detailed architecture diagrams and design rationale, see [ARCHITECTURE.md](file:///c:/Users/SA/Desktop/PNBC/ARCHITECTURE.md).

---

## 📦 Project Structure

```
├── app/
│   ├── config.py                 # Pydantic environment configuration
│   ├── database.py               # Async SQLAlchemy engine & session maker
│   ├── models.py                 # ORM models (User, Document, Question, etc.)
│   ├── schemas.py                # Pydantic v2 validation schemas
│   ├── security.py               # JWT tokens & bcrypt password hashing
│   ├── main.py                   # FastAPI app factory, CORS, error handlers
│   ├── routes/
│   │   ├── auth.py               # /auth/register, /auth/login, /auth/me
│   │   ├── documents.py          # Document upload, status, questions, export
│   │   └── questions.py          # Question detail & human review (PATCH)
│   ├── services/
│   │   ├── file_service.py       # Magic-byte validation & secure storage
│   │   ├── ocr_service.py        # PyMuPDF & Tesseract OCR pipeline
│   │   ├── extractor_service.py  # Regex & heuristic question parser
│   │   ├── answer_matcher.py     # Answer key association & conflict detection
│   │   ├── document_processor.py # Async pipeline orchestrator
│   │   └── queue_service.py      # Dual-mode Redis ARQ & BackgroundTasks
│   └── workers/
│       └── arq_worker.py         # ARQ Redis background worker settings
├── alembic/                      # Alembic database migration environment
├── sample_documents/             # 7 realistic sample input documents
├── sample_outputs/               # Structured JSON extraction outputs
├── tests/
│   ├── test_basic.py             # Basic functionality tests
│   └── test_full_suite.py        # Comprehensive suite covering all 10 scenarios
├── scripts/
│   ├── generate_sample_documents.py
│   ├── generate_sample_outputs.py
│   ├── export_openapi.py
│   └── verify_all_scenarios.py
├── ARCHITECTURE.md               # Detailed architectural specification
├── DEMO_EVIDENCE.md              # Evidence report for all 10 scenarios
├── postman_collection.json       # Complete Postman API collection
├── openapi.json                  # Exported OpenAPI 3.1 specification
├── Dockerfile                    # Production Docker container with Tesseract
└── docker-compose.yml            # Multi-service stack (API, DB, Redis, Worker)
```

---

## ⚡ Quickstart & Local Setup

### Option 1: Run Locally with Python Virtualenv (Zero External Dependencies)

1. **Activate Virtual Environment**:
   ```powershell
   .venv\Scripts\activate
   ```

2. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Run Database Migrations**:
   ```bash
   alembic upgrade head
   ```

4. **Start the API Server**:
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```

5. **Access Interactive Docs**:
   - Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs)
   - ReDoc: [http://localhost:8000/redoc](http://localhost:8000/redoc)

---

### Option 2: Run with Docker Compose (Full Production Stack)

To run the complete stack including **PostgreSQL 16**, **Redis 7**, the **FastAPI Gateway**, and the **ARQ Distributed Worker**:

```bash
docker compose up --build
```

- API Endpoint: `http://localhost:8000`
- PostgreSQL: Port `5432`
- Redis: Port `6379`

### Live Deployment

The API is deployed on Render and is available for demonstration:

- API: [https://pnbc-33vb.onrender.com](https://pnbc-33vb.onrender.com)
- Swagger UI: [https://pnbc-33vb.onrender.com/docs](https://pnbc-33vb.onrender.com/docs)
- ReDoc: [https://pnbc-33vb.onrender.com/redoc](https://pnbc-33vb.onrender.com/redoc)
- Health check: [https://pnbc-33vb.onrender.com/health](https://pnbc-33vb.onrender.com/health)

Use the Swagger UI to register a user, log in, authorize with the returned bearer token, upload an exam document, and view the extracted questions.

---

## 🧪 Running Automated Tests

Run the complete test suite covering all 10 demonstration scenarios, security isolation, document linking, and human review:

```bash
python -m pytest -v tests/test_full_suite.py
```

All 13 test cases execute and validate:
- ✅ Scenario 1: Uploading a PDF
- ✅ Scenario 2: Uploading an image (PNG/JPEG)
- ✅ Scenario 3: Scanned / image document processing
- ✅ Scenario 4: Multiple questions extraction
- ✅ Scenario 5: Multi-page spanning question stitching (`source_pages: [1, 2]`)
- ✅ Scenario 6: Question options extraction (`A`, `B`, `C`, `D`)
- ✅ Scenario 7: Answer key detection & association
- ✅ Scenario 8: Uncertain / low-confidence extraction & review item retrieval
- ✅ Scenario 9: System-independent structured JSON retrieval
- ✅ Scenario 10: Rejection of corrupted / invalid files with HTTP 400
- ✅ Multi-tenant authorization isolation
- ✅ Separate answer key document linking (`POST /documents/{id}/link`)
- ✅ Human-in-the-loop review workflow (`PATCH /questions/{id}`)

---

## 🔍 API Surface Reference

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/auth/register` | Register a new user account |
| `POST` | `/auth/login` | Authenticate and obtain JWT Bearer access token |
| `GET` | `/auth/me` | Retrieve authenticated user profile |
| `POST` | `/documents/upload` | Upload PDF or image for asynchronous processing |
| `GET` | `/documents` | List user's documents with pagination and status filters |
| `GET` | `/documents/{id}` | Get document details including questions and relations |
| `GET` | `/documents/{id}/status` | Fast polling endpoint for document status & counts |
| `POST` | `/documents/{id}/process` | Trigger or re-trigger document extraction |
| `GET` | `/documents/{id}/questions`| Retrieve extracted questions (`needs_review`, `min_confidence`) |
| `GET` | `/documents/{id}/answer-key`| Retrieve parsed answer key items |
| `GET` | `/documents/{id}/review-items`| Retrieve questions flagged for human review |
| `POST` | `/documents/{id}/link` | Link a related document (e.g. external Answer Key) |
| `GET` | `/documents/{id}/export` | Export structured questions in downstream-independent JSON |
| `DELETE`| `/documents/{id}` | Delete document and cascade delete related records |
| `GET` | `/questions/{id}` | Retrieve individual question details with full provenance |
| `PATCH` | `/questions/{id}` | Human-in-the-loop review/update stem, options, or answer |

---

## 📑 Postman Collection

Import `postman_collection.json` into Postman:
- Contains pre-configured requests for every workflow.
- Pre-request script automatically captures `access_token` on login and attaches it to subsequent requests.
- Collection variables `{{baseUrl}}`, `{{token}}`, `{{documentId}}`, and `{{questionId}}` are automatically managed.

---

## 📊 Evaluation Deliverables Checklist

- [x] **Complete Source Code**: Fully modular FastAPI codebase under `app/`.
- [x] **Database Migrations / Schema**: Alembic migrations under `alembic/versions/`.
- [x] **Sample Input Documents**: 7 realistic sample files in `sample_documents/`.
- [x] **Sample Extracted Output**: 5 structured JSON output files in `sample_outputs/`.
- [x] **Setup & Configuration Instructions**: Provided in `README.md`.
- [x] **Architecture & Design Documentation**: Comprehensive specification in `ARCHITECTURE.md`.
- [x] **Automated Tests**: Complete test suite in `tests/test_full_suite.py`.
- [x] **Postman Collection**: Exported to `postman_collection.json`.
- [x] **Swagger UI / OpenAPI Documentation**: Served live at `/docs` and exported to `openapi.json`.
- [x] **Demonstration Evidence**: Detailed execution report in `DEMO_EVIDENCE.md`.
