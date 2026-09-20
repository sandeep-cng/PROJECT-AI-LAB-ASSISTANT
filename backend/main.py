import os
import sys
import json
from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import get_db, engine, Base
from backend.models import (
    Patient, TestCatalog, HealthPackage, Appointment, Order,
    LabReport, CallLog, PolicyDocument, Prescription
)
from backend.rag_engine import rag_engine
from backend.multimodal_analyzer import multimodal_analyzer
from backend.telephony_router import telephony_router, handle_phone_call_websocket
from backend.seed_data import init_and_seed_db

# Initialize FastAPI App
app = FastAPI(
    title="Apex MediLab - Multimodal AI Diagnostic Lab",
    description="Multimodal AI-enabled diagnostic laboratory with human-like telephony agent, RAG policy engine, and prescription vision recognition.",
    version="2.0.0"
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Telephony Router
app.include_router(telephony_router)

# WebSocket endpoint for interactive phone call simulation
@app.websocket("/ws/phone-call")
async def websocket_call_endpoint(websocket: WebSocket):
    await handle_phone_call_websocket(websocket)

# --- Startup Event: Auto Initialize & Seed Database ---
@app.on_event("startup")
def on_startup():
    init_and_seed_db()

# --- Health & Diagnostic Stats ---
@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "service": "Apex MediLab Multimodal AI System",
        "version": "2.0.0",
        "environment_variables": {
            "gemini_configured": bool(os.getenv("GEMINI_API_KEY", "").strip()),
            "openai_configured": bool(os.getenv("OPENAI_API_KEY", "").strip()),
            "twilio_configured": bool(os.getenv("TWILIO_ACCOUNT_SID", "").strip()),
            "database": "Active (SQLite/PostgreSQL)"
        }
    }

@app.get("/api/stats")
def get_dashboard_stats(db: Session = Depends(get_db)):
    return {
        "total_tests": db.query(TestCatalog).count(),
        "total_packages": db.query(HealthPackage).count(),
        "total_patients": db.query(Patient).count(),
        "total_appointments": db.query(Appointment).count(),
        "total_call_logs": db.query(CallLog).count(),
        "total_reports": db.query(LabReport).count(),
        "total_policy_chunks": len(rag_engine.chunks)
    }

# --- Diagnostic Test Catalog & Packages ---
@app.get("/api/tests")
def get_tests(category: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(TestCatalog)
    if category:
        query = query.filter(TestCatalog.category == category)
    return [t.to_dict() for t in query.all()]

@app.get("/api/packages")
def get_packages(db: Session = Depends(get_db)):
    return [p.to_dict() for p in db.query(HealthPackage).all()]

# --- Patients & Profiles ---
@app.get("/api/patients")
def get_patients(db: Session = Depends(get_db)):
    return [p.to_dict() for p in db.query(Patient).all()]

@app.get("/api/patients/{phone}/lookup")
def lookup_patient_by_phone(phone: str, db: Session = Depends(get_db)):
    from backend.voice_agent import normalize_phone
    clean_target = normalize_phone(phone)
    for p in db.query(Patient).all():
        if normalize_phone(p.phone_number) == clean_target or (
            len(clean_target) >= 10 and clean_target[-10:] in normalize_phone(p.phone_number)
        ):
            return p.to_dict()
    raise HTTPException(status_code=404, detail="Patient profile not found")

@app.get("/api/patients/{patient_id}/reports")
def get_patient_reports(patient_id: int, db: Session = Depends(get_db)):
    reports = db.query(LabReport).filter_by(patient_id=patient_id).order_by(LabReport.id.desc()).all()
    return [r.to_dict() for r in reports]

# --- Appointments ---
@app.get("/api/appointments")
def get_appointments(db: Session = Depends(get_db)):
    appts = db.query(Appointment).order_by(Appointment.id.desc()).all()
    return [a.to_dict() for a in appts]

@app.post("/api/appointments")
def create_appointment(data: dict, db: Session = Depends(get_db)):
    patient_id = data.get("patient_id")
    if not patient_id:
        phone = data.get("phone", "+1 (555) 000-0000")
        name = data.get("full_name", "Walk-In Patient")
        p = Patient(full_name=name, phone_number=phone, address=data.get("address"))
        db.add(p)
        db.commit()
        patient_id = p.id

    appt = Appointment(
        patient_id=patient_id,
        appointment_type=data.get("appointment_type", "home_collection"),
        scheduled_date=data.get("scheduled_date"),
        time_slot=data.get("time_slot", "07:30 AM - 08:30 AM"),
        pickup_address=data.get("address"),
        tests_requested=data.get("tests_requested"),
        notes=data.get("notes")
    )
    db.add(appt)
    db.commit()
    return appt.to_dict()

# --- Multimodal Prescription & Report Analysis ---
@app.post("/api/prescriptions/upload")
async def upload_and_analyze_prescription(
    file: Optional[UploadFile] = File(None),
    doctor_hint: Optional[str] = Form(None)
):
    import base64
    image_b64 = ""
    if file:
        contents = await file.read()
        image_b64 = base64.b64encode(contents).decode("utf-8")

    result = multimodal_analyzer.analyze_prescription(image_b64, doctor_hint=doctor_hint)
    return result

@app.post("/api/reports/explain")
def explain_biomarkers(data: dict):
    biomarkers = data.get("biomarkers", [])
    return multimodal_analyzer.interpret_lab_report(biomarkers)

# --- Policy RAG Search ---
@app.post("/api/rag/search")
def search_lab_policies(data: dict):
    query = data.get("query", "").strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    return rag_engine.answer_query(query)

@app.get("/api/rag/chunks")
def get_all_policy_chunks():
    return [
        {
            "title": c.doc_title,
            "category": c.category,
            "section": c.section,
            "content": c.content,
            "file": c.file_path
        }
        for c in rag_engine.chunks
    ]

# --- Call Logs ---
@app.get("/api/call-logs")
def get_call_logs(db: Session = Depends(get_db)):
    logs = db.query(CallLog).order_by(CallLog.id.desc()).all()
    return [cl.to_dict() for cl in logs]

# --- Static Frontend Serving ---
FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")
if os.path.exists(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

    @app.get("/")
    def serve_index():
        return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))
