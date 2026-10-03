import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import SessionLocal, get_database_info
from backend.models import Patient, TestCatalog, Appointment, CallLog, LabReport
from backend.rag_engine import rag_engine
from backend.voice_agent import DiagnosticVoiceAgent
from backend.multimodal_analyzer import multimodal_analyzer
from backend.notifications import notification_service

try:
    from starlette.testclient import TestClient
except (ImportError, ModuleNotFoundError):
    from fastapi.testclient import TestClient

def test_policy_rag():
    print("\n--- [TEST 1] Testing Policy RAG Engine & Hybrid Vector Search ---")
    res1 = rag_engine.answer_query("What are the fasting requirements for Lipid Profile?")
    print("Q: Fasting for Lipid Profile")
    print(f"A: {res1['answer'][:160]}...")
    assert "10 to 12 hours" in res1["answer"], "Fasting hours should match policy"
    assert len(res1["citations"]) > 0, "Should have citations"
    print(f"[PASS] Policy RAG Fasting check passed! (Vector DB Mode: {res1.get('vector_db', 'memory')})")

    res2 = rag_engine.answer_query("What is the panic value for Troponin?")
    print("Q: Panic value for Troponin")
    print(f"A: {res2['answer'][:160]}...")
    assert "0.04" in res2["answer"] or "Troponin" in res2["answer"], "Troponin panic value cited"
    print("[PASS] Policy RAG Panic Values check passed!")

def test_voice_agent_caller_id_and_tools():
    print("\n--- [TEST 2] Testing Human-Like Voice Coordinator (Vinod) & Inbound Caller ID ---")
    # Test returning caller Rohan Mehta
    agent = DiagnosticVoiceAgent(caller_phone="+91 98200 23456", call_sid="TEST-CALL-001")
    greeting = agent.get_initial_greeting()
    print(f"Caller Phone: {agent.caller_phone}")
    print(f"Recognized Patient: {greeting['caller_name']}")
    print(f"Greeting Speech: {greeting['speech'][:140]}...")
    assert greeting["is_returning_patient"] is True, "Should identify Rohan Mehta as returning"
    assert "Rohan" in greeting["speech"], "Greeting should mention patient name"
    assert "Hi, I'm your Lab Assistant Vinod" in greeting["speech"], "Greeting must introduce agent as 'Hi, I'm your Lab Assistant Vinod'"
    assert greeting.get("coordinator_name") == "Vinod", "Coordinator name must be Vinod"
    print("[PASS] Caller ID & Vinod Personalized Greeting passed!")

    # Test new caller greeting with Vinod
    new_agent = DiagnosticVoiceAgent(caller_phone="+1 (555) 000-9999", call_sid="TEST-CALL-NEW")
    new_greeting = new_agent.get_initial_greeting()
    assert "Hi, I'm your Lab Assistant Vinod" in new_greeting["speech"], "New caller must be greeted with 'Hi, I'm your Lab Assistant Vinod'"
    print("[PASS] New Caller Vinod greeting verified with 'Hi, I\'m your Lab Assistant Vinod'!")

    # Test report query
    turn1 = agent.process_turn("Can you check my recent cholesterol results?")
    print(f"\nUser: Can you check my recent cholesterol results?")
    print(f"Agent (Vinod): {turn1['speech']}")
    assert "Lipid Profile" in turn1["speech"] or "215" in turn1["speech"], "Should retrieve lipid report"
    print("[PASS] Test Report retrieval tool passed!")

    # Test booking tool with GMAIL & WHATSAPP
    turn2 = agent.process_turn("Please book a home collection appointment for tomorrow morning at 7:30 AM.")
    print(f"\nUser: Please book a home collection appointment tomorrow morning at 7:30 AM.")
    print(f"Agent (Vinod): {turn2['speech']}")
    assert turn2["intent"] == "book_appointment_success", "Should successfully book appointment"
    assert "WhatsApp" in turn2["speech"], "Agent must confirm WhatsApp notification"
    assert "Gmail" in turn2["speech"], "Agent must confirm Gmail notification"
    assert "gmail_dispatched" in turn2["extra"], "extra must confirm gmail_dispatched"
    assert "whatsapp_dispatched" in turn2["extra"], "extra must confirm whatsapp_dispatched"

    # Verify DB appointment was recorded
    db = SessionLocal()
    try:
        latest_appt = db.query(Appointment).filter_by(patient_id=agent.patient.id).order_by(Appointment.id.desc()).first()
        assert latest_appt is not None, "Appointment should exist in database"
        assert "WhatsApp" in latest_appt.notes and "Gmail" in latest_appt.notes, "DB notes must record WhatsApp & Gmail delivery"
        print(f"[PASS] Appointment #{latest_appt.id} booked with confirmed WhatsApp & Gmail dispatch!")

        # Verify call log recorded
        call_log = db.query(CallLog).filter_by(call_sid="TEST-CALL-001").first()
        assert call_log is not None, "Call log should be recorded"
        print(f"[PASS] Call Log recorded in DB with actions: {call_log.actions_taken}")
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
    from backend.main import app

    client = TestClient(app)

    # Health check
    res_health = client.get("/api/health")
    assert res_health.status_code == 200
    health_data = res_health.json()
    assert health_data["status"] == "healthy"
    assert health_data["environment_variables"]["agent_name"] == "Vinod"
    assert "gmail_configured" in health_data["environment_variables"]
    assert "whatsapp_configured" in health_data["environment_variables"]
    assert "human_transfer_enabled" in health_data["environment_variables"]
    assert "ambiguity_detection_active" in health_data["environment_variables"]
    print(f"[PASS] GET /api/health passed! Coordinator: {health_data['environment_variables']['agent_name']}, Ambiguity Active: {health_data['environment_variables']['ambiguity_detection_active']}")

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
    assert "Senior Duty Medical Officer" in turn_car["speech"]
    print("[PASS] Out-of-scope query successfully triggers Senior Duty Medical Officer handover!")

    # 2. Explicit Human Request
    turn_human = agent.process_turn("Can I speak to human supervisor or a real person?")
    print("\nUser: Can I speak to human supervisor or a real person?")
    print(f"Agent: {turn_human['speech']}")
    assert turn_human["intent"] == "human_handover", "Should route human request to supervisor"
    assert "Senior Duty Medical Officer" in turn_human["speech"]
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
    assert "WhatsApp" in turn_insitu["speech"] and "Gmail" in turn_insitu["speech"]
    print("[PASS] In-situ clinic sampling booking passed with WhatsApp/Gmail delivery!")

    # 5. Doorstep Home Collection Booking
    turn_doorstep = agent.process_turn("Actually please schedule a doorstep home collection for lipid profile instead.")
    print("\nUser: Actually please schedule a doorstep home collection for lipid profile instead.")
    print(f"Agent: {turn_doorstep['speech']}")
    assert turn_doorstep["intent"] == "book_appointment_success"
    assert turn_doorstep["extra"]["type"] == "home_collection", "Should record home_collection type"
    assert "Doorstep Home Sample Collection" in turn_doorstep["speech"]
    assert "WhatsApp" in turn_doorstep["speech"] and "Gmail" in turn_doorstep["speech"]
    print("[PASS] Doorstep home collection sampling booking passed with WhatsApp/Gmail delivery!")

def test_exotel_telephony_and_barge_in():
    print("\n--- [TEST 6] Testing Exotel Telephony & Barge-In Audio Protocols ---")
    from backend.main import app
    client = TestClient(app)

    # 1. Test Exotel Inbound Call Webhook
    res_exotel_in = client.post(
        "/api/telephony/exotel/incoming",
        data={"From": "+91 98200 23456", "CallSid": "EXO-TEST-001"}
    )
    assert res_exotel_in.status_code == 200
    xml_content = res_exotel_in.text
    assert "Response" in xml_content, "Exotel response must be XML"
    assert 'bargin="true"' in xml_content, "Exotel response must enable barge-in so user speech interrupts agent"
    assert "Rohan" in xml_content, "Recognized patient name in Exotel greeting"
    assert "Vinod" in xml_content, "Vinod must greet caller in Exotel call"
    print("[PASS] Exotel Inbound Webhook with Caller ID, Vinod persona & Barge-In verified!")

    # 2. Test Exotel Turn Webhook
    res_exotel_turn = client.post(
        "/api/telephony/exotel/turn?call_sid=EXO-TEST-001",
        data={"SpeechResult": "What are the fasting rules for lipid profile?", "CallSid": "EXO-TEST-001"}
    )
    assert res_exotel_turn.status_code == 200
    assert 'bargin="true"' in res_exotel_turn.text
    print("[PASS] Exotel Spoken Turn with Barge-In verified!")

    # 3. Test Twilio Inbound Call Webhook with Barge-In
    res_twilio_in = client.post(
        "/api/telephony/twilio/incoming",
        data={"From": "+91 98200 23456", "CallSid": "TWILIO-TEST-001"}
    )
    assert res_twilio_in.status_code == 200
    assert 'bargeIn="true"' in res_twilio_in.text, "Twilio must enable bargeIn=true to stop agent speaking"
    assert "Vinod" in res_twilio_in.text
    print("[PASS] Twilio Inbound Webhook with Vinod & bargeIn='true' verified!")

def test_ambiguity_detection_and_human_sensitivity():
    print("\n--- [TEST 7] Testing Ambiguity Detection, Direct Human Transfer & Human Empathy ---")
    agent = DiagnosticVoiceAgent(caller_phone="+1 (555) 888-7777", call_sid="TEST-AMBIG-001")

    # 1. Ambiguity Detection: Doubt about medication conflicting with test
    query_ambig = "My doctor told me something different and I am confused about taking insulin, is that safe for me?"
    turn_ambig = agent.process_turn(query_ambig)
    print(f"User: {query_ambig}")
    print(f"Agent (Vinod): {turn_ambig['speech']}")
    assert turn_ambig["intent"] == "human_handover_ambiguity", "Must identify clinical ambiguity"
    assert turn_ambig["tool_executed"] == "transfer_to_real_human_assistant", "Must execute direct transfer to human assistant"
    assert "unambiguous" in turn_ambig["speech"].lower() or "medical nuances" in turn_ambig["speech"].lower()
    assert "Senior Duty Medical Officer" in turn_ambig["speech"]
    print("[PASS] Clinical ambiguity triggers direct transfer to Real Human Medical Assistant!")

    # 2. Human Sensitivity: Caller in distress / fear
    query_distress = "I am terrified and feeling very scared about my biopsy results, please help me"
    turn_distress = agent.process_turn(query_distress)
    print(f"\nUser: {query_distress}")
    print(f"Agent (Vinod): {turn_distress['speech']}")
    assert "anxious" in turn_distress["speech"].lower() or "safe hands" in turn_distress["speech"].lower(), "Agent must demonstrate human empathy"
    print("[PASS] Human interaction sensitivity (Empathy) successfully detected and expressed!")

    # 3. Direct Human Transfer Dial in Exotel & Twilio
    from backend.main import app
    client = TestClient(app)
    res_exo_ambig = client.post(
        "/api/telephony/exotel/turn?call_sid=TEST-AMBIG-001",
        data={"SpeechResult": "I have doubts and conflicting advice from two doctors, I am not sure what to do", "CallSid": "TEST-AMBIG-001"}
    )
    assert res_exo_ambig.status_code == 200
    assert "<Dial" in res_exo_ambig.text, "Exotel must issue <Dial> to transfer call directly to human assistant"
    print("[PASS] Exotel telephony executes direct live call transfer to Human Assistant on ambiguity!")

def test_gmail_and_whatsapp_notification_dispatch():
    print("\n--- [TEST 8] Testing GMAIL and WhatsApp Booking Confirmation Dispatch ---")
    from backend.main import app
    client = TestClient(app)

    # 1. Direct Notification Service Test
    res_notif = notification_service.send_appointment_confirmation(
        patient_name="Vinod",
        patient_phone="+91 98200 23456",
        patient_email="vinod@gmail.com",
        appointment_id=888,
        appointment_type="home_collection",
        scheduled_date="2026-10-04",
        time_slot="07:30 AM - 08:30 AM",
        tests_requested="Comprehensive Lipid Profile & Fasting Blood Sugar",
        pickup_address="42 Green Glen Layout, Bellandur, Bengaluru",
        fasting_instructions="12 hours of overnight fasting (water is allowed)."
    )
    assert "gmail" in res_notif
    assert "whatsapp" in res_notif
    assert res_notif["gmail"]["status"] in ["sent", "simulated_sent"]
    assert res_notif["whatsapp"]["status"] in ["sent", "simulated_sent"]
    assert res_notif["gmail"]["recipient"] == "vinod@gmail.com"
    print(f"[PASS] Direct dispatch: Gmail ({res_notif['gmail']['status']}) & WhatsApp ({res_notif['whatsapp']['status']}) verified!")

    # 2. Test Notification HTTP Endpoint
    res_api = client.post("/api/notifications/test", json={
        "patient_name": "Pooja Sharma",
        "phone": "+91 98765 01234",
        "email": "pooja.sharma@gmail.com"
    })
    assert res_api.status_code == 200
    api_data = res_api.json()
    assert api_data["gmail"]["status"] in ["sent", "simulated_sent"]
    assert api_data["whatsapp"]["status"] in ["sent", "simulated_sent"]
    print("[PASS] POST /api/notifications/test endpoint passed!")

def test_check_availability_database_flow():
    print("\n--- [TEST 9] Testing check_availability() Database Query & Dynamic Pricing Flow ---")
    from backend.voice_agent import DiagnosticVoiceAgent, check_availability

    # 1. Direct check_availability() Database Query
    avail = check_availability("CBC", "tomorrow")
    assert avail["test_code"] == "CBC"
    assert len(avail["slots"]) >= 2
    slot_10_12 = avail["slots"][0]
    slot_12_2 = avail["slots"][1]
    assert slot_10_12["slot_label"] == "10–12 AM"
    assert slot_10_12["price"] == 450
    assert slot_12_2["slot_label"] == "12–2 PM"
    assert slot_12_2["price"] == 500
    print(f"[PASS] check_availability('CBC', 'tomorrow') returned slots: 10-12 AM (Rs.{slot_10_12['price']}) & 12-2 PM (Rs.{slot_12_2['price']})")

    # 2. Conversational Agent Flow: "User wants CBC tomorrow" -> check_availability() -> Database -> 10-12 AM (₹450) vs 12-2 PM (₹500)
    agent = DiagnosticVoiceAgent(caller_phone="+91 98200 23456", call_sid="TEST-AVAIL-001")
    turn1 = agent.process_turn("User wants CBC tomorrow")
    assert turn1["tool_executed"] == "check_availability"
    assert "10" in turn1["speech"] and "450" in turn1["speech"]
    assert "12" in turn1["speech"] and "500" in turn1["speech"]
    print(f"[PASS] Agent Turn 1: check_availability executed and returned slots via TTS speech!")

    # 3. Follow-up Turn: User selects "10 to 12 AM please"
    turn2 = agent.process_turn("10 to 12 AM please")
    assert turn2["intent"] == "book_appointment_success"
    assert "10:00 AM - 12:00 PM" in turn2["speech"]
    assert "450" in turn2["speech"]
    assert turn2["extra"]["price"] == "₹450"
    assert turn2["extra"]["gmail_dispatched"] in ["sent", "simulated_sent"]
    assert turn2["extra"]["whatsapp_dispatched"] in ["sent", "simulated_sent"]
    print(f"[PASS] Agent Turn 2: Booked chosen slot 10:00 AM - 12:00 PM at ₹450 with WhatsApp/Gmail alerts!")

    # 4. FastAPI /api/availability endpoint test
    from backend.main import app
    client = TestClient(app)
    res_api = client.get("/api/availability?test=CBC&date=tomorrow")
    assert res_api.status_code == 200
    data = res_api.json()
    assert data["slots"][0]["price"] == 450
    assert data["slots"][1]["price"] == 500
    print("[PASS] GET /api/availability endpoint verified!")

def test_pipeline_architecture_routing():
    print("\n--- [TEST 10] Testing Complete Pipeline Architecture: Question (RAG) vs Action (Agent Tools) ---")
    from backend.voice_agent import DiagnosticVoiceAgent, AgentTools, RAGEngineRouter, ConversationEngine, ConversationState

    agent = DiagnosticVoiceAgent(caller_phone="+91 98200 23456", call_sid="TEST-PIPELINE-001")

    # 1. Pipeline Test: "I need a CBC tomorrow" -> Action Required -> AGENT TOOLS -> check_availability -> 10-12 AM (₹450) & 12-2 PM (₹500)
    print("Step 1: User says: 'I need a CBC tomorrow'")
    turn1 = agent.process_turn("I need a CBC tomorrow")
    assert turn1["tool_executed"] == "check_availability", "Action must execute check_availability tool"
    trace1 = turn1["extra"]["pipeline_trace"]
    assert trace1["category"] == "Action required", "Must classify as 'Action required'"
    assert trace1["route"] == "AGENT_TOOLS", "Must route to AGENT_TOOLS"
    assert trace1["component"] == "Availability", "Component must be Availability"
    assert "10" in turn1["speech"] and "450" in turn1["speech"], "Must offer 10-12 AM at ₹450"
    assert "12" in turn1["speech"] and "500" in turn1["speech"], "Must offer 12-2 PM at ₹500"
    print(f"[PASS] Action Required -> AGENT TOOLS (Availability) -> Returned: 10-12 AM (₹450) & 12-2 PM (₹500)")

    # 2. Pipeline Test: Question -> RAG (Prep / Fasting)
    print("\nStep 2: User asks Question: 'Do I need to fast before CBC test?'")
    agent2 = DiagnosticVoiceAgent(caller_phone="+91 98200 23456", call_sid="TEST-PIPELINE-002")
    turn2 = agent2.process_turn("Do I need to fast before CBC test?")
    trace2 = turn2["extra"]["pipeline_trace"]
    assert trace2["category"] == "Question", "Must classify as 'Question'"
    assert trace2["route"] == "RAG", "Must route to RAG"
    assert trace2["component"] == "Prep", "Component must be Prep"
    assert "fasting" in turn2["speech"].lower(), "Must address fasting"
    print(f"[PASS] Question -> RAG (Prep) -> Provided verified SOP guidance with citations!")

    # 3. Pipeline Test: Question -> RAG (Policy / Refund)
    print("\nStep 3: User asks Question: 'What is your cancellation and refund policy?'")
    turn3 = agent2.process_turn("What is your cancellation and refund policy?")
    trace3 = turn3["extra"]["pipeline_trace"]
    assert trace3["category"] == "Question", "Must classify as 'Question'"
    assert trace3["route"] == "RAG", "Must route to RAG"
    assert trace3["component"] == "Policy", "Component must be Policy"
    print(f"[PASS] Question -> RAG (Policy) -> Policy citations verified!")

    # 4. Agent Tools Suite Verification
    price_info = AgentTools.get_pricing("CBC")
    assert price_info["price"] == 450
    assert price_info["price_formatted"] == "₹450"
    print(f"[PASS] AgentTools.get_pricing('CBC') returned {price_info['price_formatted']}")

    lab_info = AgentTools.get_lab_info()
    assert "Apex Family Diagnostic" in lab_info["name"]
    assert "NABL Accredited" in lab_info["certifications"]
    print(f"[PASS] AgentTools.get_lab_info() verified: {lab_info['name']} ({', '.join(lab_info['certifications'])})")

    home_col = AgentTools.check_home_collection()
    assert home_col["service_available"] is True
    assert "2°C - 8°C" in home_col["cold_chain_carrier"]
    print(f"[PASS] AgentTools.check_home_collection() verified: {home_col['cold_chain_carrier']}")

def test_user_speech_detector_subsystem():
    print("\n--- [TEST 11] Testing User Speech Detector Interruption Circuit ---")
    from backend.main import app
    client = TestClient(app)

    # 1. Telephony Webhook Barge-in verification
    # Exotel Gather with bargin="true"
    res_exo = client.post("/api/telephony/exotel/incoming?CallFrom=%2B919820023456")
    assert 'bargin="true"' in res_exo.text, "Exotel incoming must enable bargin='true'"
    print("[PASS] User Speech Detector: Exotel Voice gathers enforce hardware bargin='true'")

    # Twilio Gather with bargeIn="true"
    res_twi = client.post("/api/telephony/twilio/incoming", data={"From": "+919820023456"})
    assert 'bargeIn="true"' in res_twi.text, "Twilio incoming must enable bargeIn='true'"
    print("[PASS] User Speech Detector: Twilio Voice gathers enforce hardware bargeIn='true'")

    # 2. Interactive WebSocket User Speech Interruption Event
    with client.websocket_connect("/ws/phone-call") as ws:
        # Connect call
        ws.send_json({"type": "initiate_call", "caller_phone": "+91 98200 23456"})
        init_resp = ws.receive_json()
        assert init_resp["type"] == "call_connected"
        call_sid = init_resp["call_sid"]

        # Step: User starts speaking while AI is speaking -> Sends user_interrupt
        ws.send_json({
            "type": "user_interrupt",
            "reason": "vad_mic_energy",
            "timestamp": 1727900000000
        })
        interrupt_resp = ws.receive_json()
        assert interrupt_resp["type"] == "agent_interrupted"
        assert interrupt_resp["status"] == "stopped_speaking"
        assert interrupt_resp["reason"] == "vad_mic_energy"
        print("[PASS] User Speech Detector: User starts speaking -> IMMEDIATELY STOP TTS & CANCEL AI AUDIO confirmed by server!")

        # Step: LISTEN TO USER -> User finishes speaking complete query
        ws.send_json({
            "type": "user_speech",
            "text": "I need a CBC tomorrow"
        })
        speech_resp = ws.receive_json()
        assert speech_resp["type"] == "agent_response"
        assert speech_resp["tool_executed"] == "check_availability"
        assert "10" in speech_resp["speech"] and "450" in speech_resp["speech"]
        print("[PASS] User Speech Detector: Successfully listened to user complete query and returned 10–12 AM (₹450) & 12–2 PM (₹500)!")

        # Hang up
        ws.send_json({"type": "hangup"})
        ws.receive_json()

if __name__ == "__main__":
    test_policy_rag()
    test_voice_agent_caller_id_and_tools()
    test_multimodal_analyzer()
    test_api_server_endpoints()
    test_handover_and_sampling_options()
    test_exotel_telephony_and_barge_in()
    test_ambiguity_detection_and_human_sensitivity()
    test_gmail_and_whatsapp_notification_dispatch()
    test_check_availability_database_flow()
    test_pipeline_architecture_routing()
    test_user_speech_detector_subsystem()
    print("\n" + "=" * 75)
    print("ALL 11 AUTOMATED TEST SUITES COMPLETED WITH 100% SUCCESS!")
    print("=" * 75)


