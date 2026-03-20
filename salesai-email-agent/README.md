# SalesAI - Email-Based Multi-Agent AI Customer Support System

A production-ready Python project skeleton for an email support assistant using:
- FastAPI (backend API)
- Gmail API (email fetching)
- SMTP (email sending)
- spaCy + Transformers (NLP stack foundation)
- Gemini API (placeholder stubs for intent/emotion/reply)
- ChromaDB (RAG knowledge retrieval)
- Supabase PostgreSQL (interaction logging)

## Project Structure

```text
salesai-email-agent/
|
|-- app/
|   |-- main.py
|   |-- config.py
|   |
|   |-- email/
|   |   |-- fetch_emails.py
|   |   |-- send_email.py
|   |
|   |-- nlp/
|   |   |-- preprocess.py
|   |   |-- intent.py
|   |   |-- emotion.py
|   |
|   |-- rag/
|   |   |-- chroma_store.py
|   |   |-- retrieval.py
|   |
|   |-- agents/
|   |   |-- orchestrator.py
|   |   |-- strategy.py
|   |   |-- generator.py
|   |
|   |-- db/
|       |-- supabase_client.py
|
|-- data/
|   |-- knowledge/
|       |-- shipping.txt
|       |-- refund.txt
|
|-- requirements.txt
|-- .env
|-- README.md
```

## Quick Start

1. Create and activate virtual environment.

```bash
python -m venv .venv
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
```

2. Install dependencies.

```bash
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

3. Fill `.env` with your credentials (optional for mock mode).

4. Run the API.

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

5. Test endpoints:
- `GET /health`
- `GET /poll`
- `POST /process-email`

Example request body for `POST /process-email`:

```json
{
  "customer_email": "customer@example.com",
  "subject": "Need refund for wrong item",
  "body": "Hi, I received the wrong item and want a refund."
}
```

## Architecture Overview

1. Email Intake Layer (`app/email`)
- `fetch_emails.py`: polls Gmail (or returns mock messages).
- `send_email.py`: sends response over SMTP (or mock print).

2. NLP Layer (`app/nlp`)
- `preprocess.py`: lightweight text cleaning.
- `intent.py`: intent classification with Gemini placeholder + fallback heuristics.
- `emotion.py`: emotion detection with Gemini placeholder + fallback heuristics.

3. RAG Layer (`app/rag`)
- `chroma_store.py`: initializes Chroma collection and indexes policy docs.
- `retrieval.py`: fetches top-k relevant policy snippets.

4. Agent Layer (`app/agents`)
- `orchestrator.py`: full pipeline coordination.
- `strategy.py`: selects response strategy from intent/emotion.
- `generator.py`: builds final reply (Gemini placeholder).

5. Storage Layer (`app/db`)
- `supabase_client.py`: Supabase logging stub with safe mock fallback.

## End-to-End Flow

1. Customer email arrives (or API payload is posted).
2. Text is preprocessed.
3. Intent and emotion are derived.
4. RAG pulls relevant policy context from ChromaDB.
5. Strategy is selected.
6. Reply is generated.
7. Interaction is logged to Supabase (or stdout fallback).
8. Reply is sent with SMTP (or mock print).

## Notes for Production Hardening

- Replace Gemini placeholder functions with actual API integration.
- Add OAuth refresh logic and MIME parsing for Gmail.
- Add authentication, retries, and structured logging.
- Add unit/integration tests and CI pipeline.
- Add queue/worker system if inbox volume grows.
