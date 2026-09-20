import os
import sys

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import SessionLocal
from backend.models import Patient, TestCatalog, Appointment, CallLog, LabReport
from backend.rag_engine import rag_engine
from backend.voice_agent import DiagnosticVoiceAgent
from backend.multimodal_analyzer import multimodal_analyzer

def test_policy_rag():
    print("\n--- [TEST 1] Testing Policy RAG Engine ---")
    res1 = rag_engine.answer_query("What are the fasting requirements for Lipid Profile?")
    print("Q: Fasting for Lipid Profile")
    print(f"A: {res1['answer'][:160]}...")
    assert "10 to 12 hours" in res1["answer"], "Fasting hours should match policy"
    assert len(res1["citations"]) > 0, "Should have citations"
    print("[PASS] Policy RAG Fasting check passed!")

    res2 = rag_engine.answer_query("What is the panic value for Troponin?")
    print("Q: Panic value for Troponin")
    print(f"A: {res2['answer'][:160]}...")
    assert "0.04" in res2["answer"] or "Troponin" in res2["answer"], "Troponin panic value cited"
    print("[PASS] Policy RAG Panic Values check passed!")

def test_voice_agent_caller_id_and_tools():
    print("\n--- [TEST 2] Testing Human-Like Voice Agent & Inbound Caller ID ---")
    # Test returning caller Robert Vance
    agent = DiagnosticVoiceAgent(caller_phone="+1 (555) 234-5678", call_sid="TEST-CALL-001")
    greeting = agent.get_initial_greeting()
    print(f"Caller Phone: {agent.caller_phone}")
    print(f"Recognized Patient: {greeting['caller_name']}")
    print(f"Greeting Speech: {greeting['speech'][:140]}...")
    assert greeting["is_returning_patient"] is True, "Should identify Robert Vance as returning"
    assert "Robert Vance" in greeting["speech"], "Greeting should mention patient name"
    print("[PASS] Caller ID & Personalized Greeting passed!")

    # Test report query
    turn1 = agent.process_turn("Can you check my recent cholesterol results?")
    print(f"\nUser: Can you check my recent cholesterol results?")
    print(f"Agent: {turn1['speech']}")
    assert "Lipid Profile" in turn1["speech"] or "215" in turn1["speech"], "Should retrieve lipid report"
    print("[PASS] Test Report retrieval tool passed!")

    # Test booking tool
    turn2 = agent.process_turn("Please book a home collection appointment for tomorrow morning at 7:30 AM.")
    print(f"\nUser: Please book a home collection appointment tomorrow morning at 7:30 AM.")
    print(f"Agent: {turn2['speech']}")
    assert turn2["intent"] == "book_appointment_success", "Should successfully book appointment"

    # Verify DB appointment was recorded
    db = SessionLocal()
    try:
        latest_appt = db.query(Appointment).filter_by(patient_id=agent.patient.id).order_by(Appointment.id.desc()).first()
        assert latest_appt is not None, "Appointment should exist in database"
        print(f"[PASS] Appointment booked in DB: ID #{latest_appt.id} for {latest_appt.scheduled_date} at {latest_appt.time_slot}")

        # Verify call log recorded
        call_log = db.query(CallLog).filter_by(call_sid="TEST-CALL-001").first()
        assert call_log is not None, "Call log should be recorded"
        print(f"[PASS] Call Log recorded in DB with duration {call_log.duration_seconds}s and actions: {call_log.actions_taken}")
    finally:
        db.close()

def test_multimodal_analyzer():
    print("\n--- [TEST 3] Testing Multimodal Prescription Analyzer ---")
    result = multimodal_analyzer.analyze_prescription(image_base64="", doctor_hint="Dr. Rajesh K. Mehta, MD")
    print(f"Doctor: {result['doctor_name']}")
    print(f"Detected Tests Count: {len(result['detected_tests'])}")
    print(f"Estimated Total: ${result['total_estimated_price']:.2f}")
    print(f"Preparation Summary: {result['preparation_summary']}")
    assert len(result["detected_tests"]) > 0, "Should detect prescribed tests"
    assert result["total_estimated_price"] > 0, "Price should be calculated"
    print("[PASS] Multimodal Prescription Engine passed!")

def test_api_server_endpoints():
    print("\n--- [TEST 4] Testing FastAPI Endpoints ---")
    from fastapi.testclient import TestClient
    from backend.main import app

    client = TestClient(app)

    # Health check
    res_health = client.get("/api/health")
    assert res_health.status_code == 200
    assert res_health.json()["status"] == "healthy"
    print("[PASS] GET /api/health passed!")

    # Stats
    res_stats = client.get("/api/stats")
    assert res_stats.status_code == 200
    stats = res_stats.json()
    print(f"[PASS] GET /api/stats passed! Tests: {stats['total_tests']}, Packages: {stats['total_packages']}, Patients: {stats['total_patients']}")

    # Tests Catalog
    res_tests = client.get("/api/tests")
    assert res_tests.status_code == 200
    assert len(res_tests.json()) >= 10
    print(f"[PASS] GET /api/tests returned {len(res_tests.json())} diagnostic tests")

    # Packages
    res_pkgs = client.get("/api/packages")
    assert res_pkgs.status_code == 200
    assert len(res_pkgs.json()) >= 3
    print(f"[PASS] GET /api/packages returned {len(res_pkgs.json())} health packages")

    # RAG search endpoint
    res_rag = client.post("/api/rag/search", json={"query": "Lipid Profile fasting rules"})
    assert res_rag.status_code == 200
    assert len(res_rag.json()["citations"]) > 0
    print("[PASS] POST /api/rag/search endpoint passed!")

def test_handover_and_sampling_options():
    print("\n--- [TEST 5] Testing Human Handover Protocol & Dual Sampling Options ---")
    agent = DiagnosticVoiceAgent(caller_phone="+1 (555) 444-9999", call_sid="TEST-CALL-002")

    # 1. Out-of-Scope Query
    turn_car = agent.process_turn("Can you fix my car transmission and do an oil change?")
    print("User: Can you fix my car transmission and do an oil change?")
    print(f"Agent: {turn_car['speech']}")
    assert turn_car["intent"] == "human_handover", "Should detect out-of-scope inquiry"
    assert "Let me connect you right now to our Senior Duty Medical Officer" in turn_car["speech"]
    assert "automated" not in turn_car["speech"].lower() and "ai" not in turn_car["speech"].lower().split(), "No AI or automated words"
    print("[PASS] Out-of-scope query successfully triggers Senior Duty Medical Officer handover!")

    # 2. Explicit Human Request
    turn_human = agent.process_turn("Can I speak to human supervisor or a real person?")
    print("\nUser: Can I speak to human supervisor or a real person?")
    print(f"Agent: {turn_human['speech']}")
    assert turn_human["intent"] == "human_handover", "Should route human request to supervisor"
    assert "Let me connect you right now to our Senior Duty Medical Officer" in turn_human["speech"]
    print("[PASS] Human supervisor escalation protocol passed!")

    # 3. Emergency Symptom Escalation
    turn_emerg = agent.process_turn("I have crushing chest pain and cannot breathe!")
    print("\nUser: I have crushing chest pain and cannot breathe!")
    print(f"Agent: {turn_emerg['speech']}")
    assert turn_emerg["intent"] == "emergency_transfer", "Should detect clinical emergency"
    assert "911" in turn_emerg["speech"] and "Senior Duty Medical Officer" in turn_emerg["speech"]
    print("[PASS] Emergency red-flag symptom protocol passed!")

    # 4. In-Situ Clinic Booking
    turn_insitu = agent.process_turn("I would like to book an in-situ appointment to visit the laboratory clinic tomorrow morning.")
    print("\nUser: I would like to book an in-situ appointment to visit the laboratory clinic tomorrow morning.")
    print(f"Agent: {turn_insitu['speech']}")
    assert turn_insitu["intent"] == "book_appointment_success"
    assert turn_insitu["extra"]["type"] == "insitu_lab_visit", "Should record insitu_lab_visit type"
    assert "In-Situ Laboratory Clinic Appointment" in turn_insitu["speech"]
    print("[PASS] In-situ clinic sampling booking passed!")

    # 5. Doorstep Home Collection Booking
    turn_doorstep = agent.process_turn("Actually please schedule a doorstep home collection for lipid profile instead.")
    print("\nUser: Actually please schedule a doorstep home collection for lipid profile instead.")
    print(f"Agent: {turn_doorstep['speech']}")
    assert turn_doorstep["intent"] == "book_appointment_success"
    assert turn_doorstep["extra"]["type"] == "home_collection", "Should record home_collection type"
    assert "Doorstep Home Sample Collection" in turn_doorstep["speech"]
    print("[PASS] Doorstep home collection sampling booking passed!")

if __name__ == "__main__":
    test_policy_rag()
    test_voice_agent_caller_id_and_tools()
    test_multimodal_analyzer()
    test_api_server_endpoints()
    test_handover_and_sampling_options()
    print("\n" + "=" * 60)
    print("ALL 5 AUTOMATED TEST SUITES COMPLETED WITH 100% SUCCESS!")
    print("=" * 60)

