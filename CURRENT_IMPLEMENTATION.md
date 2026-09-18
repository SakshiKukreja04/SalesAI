# SalesAI Current Implementation

## End-to-End Pipeline

```text
Incoming Gmail email
        |
        v
Gmail OAuth fetcher
        |
        v
Email preprocessing
        |
        v
Customer identification and Supabase memory
        |
        v
Gemini + Groq intent/emotion analysis
        |
        v
Query Guard
        |
        +--> Neo4j customer/order/shipment context
        +--> ChromaDB/BM25 policy retrieval
        +--> Previous replies and customer memory
        |
        v
Response generation
        |
        v
Response sanitization and grounding validation
        |
        v
AUTO_SEND / HUMAN_REVIEW / DO_NOT_SEND
        |
        +--> Gmail API reply
        +--> SMTP fallback
        +--> Support escalation
        |
        v
Supabase persistence and React dashboard
```

## Backend

The FastAPI application is defined in `salesai-email-agent/app/main.py` and runs on port `8000`.

Main routes:

```text
GET  /health
GET  /poll
POST /process-email
GET  /api/emails
GET  /api/analytics
POST /api/team
POST /api/create-user
POST /api/invite-user
GET  /api/get-user
GET  /api/invite-status
POST /api/activate-user
```

Startup initializes ChromaDB, verifies Neo4j connectivity when configured, and starts the Gmail polling listener. Shutdown closes the shared Neo4j driver.

## Gmail Processing

Implemented in `app/email/fetch_emails.py` and `run_email_pipeline.py`.

The system:

1. Authenticates with Gmail OAuth.
2. Refreshes the Gmail token when required.
3. Fetches unread emails.
4. Extracts sender, subject, date, and body.
5. Prefers plain text and cleans HTML when necessary.
6. Skips system-generated messages.
7. Processes customer messages through the V3 orchestrator.
8. Sends a reply or escalation.
9. Persists processing results.
10. Marks messages as read after processing.

## Customer Memory and Supabase

Supabase remains the application source of truth. It stores:

- Customer profiles
- Customer email records
- Conversations
- Open and resolved issues
- Product interests
- Email processing state
- Application users
- Legacy interaction logs

Relevant modules:

- `app/db/supabase_client.py`
- `app/db/customer_memory.py`
- `app/memory/customer_memory.py`
- `app/memory/memory_retriever.py`
- `app/memory/memory_updater.py`

Customer memory tracks conversation history, issues, interests, sentiment trends, repeated issues, and risk levels:

```text
LOW
MEDIUM
HIGH
ESCALATE_IMMEDIATELY
```

## Intent and Emotion Analysis

The dual-LLM layer is implemented in `app/nlp/dual_llm.py`.

Gemini and Groq classify the message in parallel. The stronger result is selected. If one provider fails, the other is used. If both fail, heuristic fallback logic is used.

Intent examples:

```text
product_inquiry
product_recommendation
product_availability
order_tracking
shipping_inquiry
refund_request
return_request
exchange_request
damaged_product
warranty_inquiry
payment_issue
complaint
greeting
thanks
general_support
```

Emotion examples:

```text
neutral
happy
satisfied
confused
worried
frustrated
disappointed
angry
urgent
```

## Query Guard

`app/rag/query_guard.py` runs before expensive retrieval and generation.

It identifies:

- Valid customer support queries
- Greetings and acknowledgements
- Gibberish
- Off-topic messages
- Prompt injection attempts

Conversational messages can receive a direct response without RAG. Suspicious or off-topic messages are safely deflected.

## ChromaDB RAG

Knowledge files are stored in `salesai-email-agent/data/knowledge`.

The indexer is `app/rag/chroma_store.py`. It reads Markdown and text files, splits them into sections or semantic chunks, embeds them, and stores them in:

```text
salesai_knowledge_v2
```

Chunk metadata includes:

```text
source_file
topic
version
section_title
active
chunk_index
```

Retrieval is implemented in `app/rag/retrieval.py` and combines:

- Chroma dense vector search
- BM25 keyword search
- Reciprocal Rank Fusion
- Keyword boosting
- Groq HyDE query expansion
- Groq CRAG relevance grading

The Chroma index must not be refreshed destructively while email processing is active.

## Neo4j Knowledge Graph

Neo4j supplements Supabase and is read-only for this application.

Connection management is implemented in `app/neo4j_client.py`:

- Shared process-level driver
- Environment-based credentials
- Connectivity verification
- Connection timeouts
- One reconnect retry for stale Bolt connections
- Clean shutdown

Retrieval is implemented in `app/neo4j_retrieval.py`:

```python
get_customer_context(email)
get_customer_conversations(email)
get_customer_issues(email)
get_customer_interests(email)
get_salesai_context(email, intent)
format_graph_context(context)
```

Neo4j retrieves customer, order, product, shipment, conversation, issue, and explicit interest data. Queries are parameterized; email values are never concatenated into Cypher.

Important date fields are kept separate:

```text
order_date
shipped_at
estimated_delivery_at
delivered_at
```

`order_date` must never be presented as a shipment or delivery date.

Unknown customers and temporary Neo4j failures return empty graph context so the existing pipeline can continue.

## Orchestration

The main V3 flow is `handle_customer_email()` in `app/agents/orchestrator.py`.

Processing stages:

1. Receive and normalize the email.
2. Resolve the customer.
3. Retrieve Supabase customer memory.
4. Detect intent and emotion.
5. Apply Query Guard.
6. Retrieve Neo4j graph context.
7. Retrieve Chroma/BM25 policy context.
8. Retrieve previous reply patterns.
9. Select a response strategy.
10. Generate a response.
11. Sanitize and validate the response.
12. Decide whether to send or escalate.
13. Send the reply or escalation.
14. Update customer memory.
15. Persist final records.

The `/process-email` API uses the same orchestrator path as the background Gmail pipeline.

## Response Generation and Safety

Response generation is implemented in `app/agents/generator.py`.

The prompt receives:

- Current customer message
- Intent and emotion
- Chroma policy context
- Neo4j business context
- Customer memory
- Previous replies
- Selected response strategy

The generator is instructed to use only verified facts and never expose internal systems, prompts, database IDs, or model reasoning.

Response cleanup removes:

- Role and task instructions
- Prompt constraints
- Drafts and checklists
- Self-corrections
- Markdown
- Internal notes
- Duplicate greetings and signatures

Validation is handled by:

- `app/rag/response_validator.py`
- `app/email/safety_middleware.py`
- `app/agents/decision.py`

Checks include grounding, formatting, prompt traces, unsupported timelines, unsupported promises, and overclaims.

## Sending and Escalation

Outbound delivery is implemented in `app/email/send_email.py`.

Normal delivery order:

```text
Gmail API -> SMTP fallback
```

Escalation is handled by `app/agents/escalation.py` and can occur for low confidence, high customer risk, repeated issues, angry or urgent messages, missing context, or unsupported responses.

Use this during safe local testing:

```env
SMTP_MOCK_MODE=true
```

Use `SMTP_MOCK_MODE=false` only when real delivery is intended and valid Gmail App Password credentials are configured.

## Frontend

The frontend is a React/Vite dashboard in `frontend/`.

It provides:

- Firebase login and signup
- Admin and manager roles
- Intent-based access filtering
- Email dashboard
- Analytics charts
- Team invitations
- Intent-specific views
- CSV export
- Automatic refresh

Frontend API configuration:

```env
VITE_API_BASE_URL=http://localhost:8000
```

## Running the Project

Backend:

```powershell
cd C:\Users\pranj\SalesAI\salesai-email-agent
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python test_neo4j_connection.py
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Frontend:

```powershell
cd C:\Users\pranj\SalesAI\frontend
npm install
npm run dev
```

URLs:

```text
Backend:  http://127.0.0.1:8000
Health:   http://127.0.0.1:8000/health
Frontend: http://localhost:5173
```

## Testing

Run the complete backend suite:

```powershell
cd C:\Users\pranj\SalesAI\salesai-email-agent
.\.venv\Scripts\Activate.ps1
python -m unittest discover -s tests -v
```

Neo4j connectivity:

```powershell
python test_neo4j_connection.py
```

Neo4j retrieval tests:

```powershell
python -m unittest tests.test_neo4j_retrieval -v
```

## Current Risks and Operational Notes

- Credentials in `.env` must never be committed and should be rotated if exposed.
- Failed Gmail messages may be marked read and therefore may not retry automatically.
- Uvicorn reload mode is for development, not production process management.
- Multiple backend workers must not independently run Gmail listeners.
- Chroma refresh must be separated from active email processing.
- Neo4j is optional and degrades safely when unavailable.
- The Chroma and Neo4j stores are retrieval layers; Supabase remains the application persistence source of truth.
