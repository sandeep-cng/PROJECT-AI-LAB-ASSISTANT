# Apex MediLab - Multimodal AI-Enabled Diagnostic Lab & Human-Like Voice Agent

An enterprise-grade, Multimodal AI Diagnostic Laboratory system built to automate pathology and radiology workflows. Any patient calling from their personal phone number is attended in real-time by a human-like, empathetic conversational AI agent that identifies the caller, checks preparation/fasting guidelines via an integrated Policy RAG engine, schedules home sample collections, queries diagnostic reports, and extracts ordered tests from doctor prescriptions using Multimodal Vision.

---

## Key Highlights & Capabilities

### 1. Inbound Telephone Voice Agent & Caller ID Lookup
- **Personal Number Recognition**: Automatically extracts caller ID (`+91 98200-23456` for Vinod or `+91 98765-43210` for Ananya), looks up registered patient records, and provides warm, personalized greetings.
- **Empathetic Turn-Taking**: Handles natural pauses, polite medical communication, and active listening.
- **Autonomous Task Execution ("Do The Job")**:
  - Checks test pricing and turnaround times.
  - Schedules home sample collection appointments in the database.
  - Cites fasting and sample collection guidelines via Policy RAG.
  - Retrieves and summarizes previous laboratory test reports.
  - Escalates immediately to human medical supervisors upon detecting chest pain or emergency red-flag symptoms.
- **Dual Telephony Modes**:
  - **Live Carrier Webhooks**: Twilio Inbound Voice Webhook (`/api/telephony/twilio/incoming`) & LiveKit SIP dispatch (`/api/telephony/livekit/token`).
  - **Interactive Browser Phone Call Studio**: Complete in-browser phone dialer with WebSocket audio streaming, real-time waveform visualizer, and microphone input.

### 2. Policy RAG Engine (Diagnostic SOPs & Panic Thresholds)
- Embedded retrieval engine operating over official laboratory standard operating procedures:
  - `policies/sample_collection_guidelines.md` (Fasting rules: 10-12 hrs for Lipids/FBS, water permitted, medication protocols)
  - `policies/critical_values_escalation.md` (Panic thresholds: Troponin >0.04, Glucose <50 or >400 mg/dL, Potassium alerts)
  - `policies/cancellation_and_refund.md` (Cancellation windows, 100% refund SLA, rescheduling policy)
  - `policies/home_collection_sop.md` (Cold chain 2°C-8°C preservation, sterile vacuum needles, phlebotomist hygiene)
  - `policies/insurance_and_billing.md` (TPA cashless claims, itemized diagnostic receipts)
  - `policies/patient_privacy_hipaa.md` (HIPAA data security, telephone disclosure restrictions)

### 3. Multimodal Vision AI: Prescription Scanner & Report Explainer
- **Prescription OCR & Extraction**: Upload handwritten or printed doctor prescriptions (JPG, PNG, PDF) to automatically extract prescribing clinician, clinical notes, and ordered diagnostic tests.
- **Auto-Matching with Lab Catalog**: Calculates estimated costs, specimen tubes required, and preparation instructions with 1-click home collection booking.
- **Patient-Friendly Biomarker Explainer**: Translates technical lab parameters into plain-English health insights with proper medical safety disclaimers.

### 4. Production Database Schema (PostgreSQL & SQLite)
- Built with SQLAlchemy ORM, fully compatible with both SQLite and PostgreSQL:
  - `patients`: Personal demographics, caller ID phone numbers, medical history.
  - `doctors`: Referring clinicians, hospital affiliations, license numbers.
  - `test_catalog`: Diagnostic parameters, specimen types, fasting hours, normal ranges, prices.
  - `health_packages`: Curated wellness packages (Executive Full Body, Diabetic Guard, Senior Screen).
  - `appointments`: Scheduled home visits or clinic visits, status tracking, requested tests.
  - `prescriptions`: Uploaded image scans, OCR text, detected tests, clinical indications.
  - `orders` & `order_items`: Invoices, discounts, payment status.
  - `lab_reports`: Biomarker values, reference ranges, normal/high/critical flags, pathologist signatures, AI summaries.
  - `call_logs`: Telephony Call SIDs, transcripts, detected intentions, duration, actions executed.
  - `policy_documents`: Policy content and semantic chunk metadata.

### 5. Zero-Configuration & Blank Environment Variables
- All environment variables in `.env` and `.env.example` are strictly **BLANK** as instructed.
- The system includes intelligent local fallback and simulation engines so the entire platform can be run, dialed, and tested immediately without requiring external API keys.
- Once API keys (Gemini, OpenAI, Twilio, LiveKit, ElevenLabs) are added, the system seamlessly activates cloud models.

---

## Quickstart Guide

### 1. Install Dependencies & Run
Using Python 3.12 (or `uv`):
```bash
# Install dependencies
uv pip install -r requirements.txt

# Launch the platform (database and RAG auto-seed on startup)
python run.py
```

### 2. Access the Platform
- **Web Portal**: [http://localhost:8000](http://localhost:8000)
- **Interactive Phone Call Studio**: [http://localhost:8000/#voice-studio](http://localhost:8000/#voice-studio)
- **API Documentation (Swagger)**: [http://localhost:8000/docs](http://localhost:8000/docs)

---

### 6. Instant Barge-In (Interruption Engine)
- **Natural Human Conversations**: Whenever the user begins speaking into the microphone, types in the input box, or clicks an action button, the agent **immediately halts speech playback** (`window.speechSynthesis.cancel()` / WebSockets interrupt / `bargin="true"`).
- **Multi-Layer Detection**:
  - **Hardware VAD**: Web Audio API volume energy analysis triggers interruption in < 40ms.
  - **SpeechRecognition Events**: `onspeechstart` and `onsoundstart` cut off agent voice instantly.
  - **Telephony Carrier Barge-In**: Twilio (`bargeIn="true"`) and Exotel (`bargin="true"`) markups ensure live phone callers can interrupt the AI at any word.
  - **Manual Interruption**: One-click `✋ Interrupt` button in the UI.

---

## Environment Variables Configuration

The `.env` file provides full configuration keys for all supported services:

### 1. PostgreSQL
```ini
# Complete URL or individual parameters
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/diagnostic_lab
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=diagnostic_lab
POSTGRES_SSLMODE=prefer
```
*(If left blank or if PostgreSQL is unreachable, the system automatically runs on local SQLite without crashing).*

### 2. Vector Databases (Hybrid RAG)
```ini
VECTOR_DB_TYPE=memory        # 'memory', 'pgvector', 'chroma', 'pinecone', 'qdrant'
EMBEDDING_PROVIDER=gemini    # 'gemini', 'openai', 'local_bm25'
EMBEDDING_MODEL=text-embedding-004
VECTOR_SEARCH_TOP_K=3

# pgvector
PGVECTOR_ENABLED=false
PGVECTOR_TABLE=diagnostic_policy_vectors

# ChromaDB
CHROMA_PERSIST_DIRECTORY=./chroma_db
CHROMA_COLLECTION_NAME=diagnostic_policies

# Pinecone
PINECONE_API_KEY=
PINECONE_ENVIRONMENT=
PINECONE_INDEX_NAME=diagnostic-lab-rag

# Qdrant
QDRANT_URL=
QDRANT_API_KEY=
QDRANT_COLLECTION=diagnostic_policies
```

### 3. Exotel Telephony (India & Global)
```ini
EXOTEL_ACCOUNT_SID=
EXOTEL_API_KEY=
EXOTEL_API_TOKEN=
EXOTEL_SUBDOMAIN=api.exotel.com
EXOTEL_VIRTUAL_NUMBER=
EXOTEL_APP_ID=
EXOTEL_WEBHOOK_SECRET=
```
- Inbound Webhook: `POST /api/telephony/exotel/incoming`
- Spoken Turn Webhook: `POST /api/telephony/exotel/turn`
- Status Callback: `POST /api/telephony/exotel/status`
- Outbound Call: `POST /api/telephony/exotel/call`

---

## Testing Scenarios

1. **Inbound Call Simulation & Barge-In**:
   - Click the **+91 80 4388 8802** telephone badge in the top right header to connect to Riya.
   - Click **"Do I need to fast for Lipid test?"**
   - While Riya is speaking, start talking into your microphone or click the **✋ Interrupt** button.
   - Notice Riya stops speaking immediately!
2. **Lab Report Query**:
   - Ask: *"Can you check my recent cholesterol results?"*
   - The agent reads out the latest values (Total Chol: 215 mg/dL) and offers to SMS the signed report.
3. **Appointment Booking (Doorstep vs. In-Situ)**:
   - Ask: *"Please book a home blood sample collection for tomorrow morning at 7:30 AM."* or *"I want to visit the laboratory clinic in-situ tomorrow."*
   - The agent books the appointment in the database and dispatches a confirmation.
4. **Multimodal Prescription OCR**:
   - Send prescription scans to `/api/prescriptions/upload`.
5. **Automated Test Suite**:
   - Run `.venv\Scripts\python.exe tests/test_system.py` to run all 6 test suites covering RAG, Voice Agent, Caller ID, Handover, Exotel Webhooks, and Barge-In.

