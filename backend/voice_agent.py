import os
import re
import json
import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from backend.database import SessionLocal
from backend.models import Patient, TestCatalog, HealthPackage, Appointment, LabReport, CallLog, Order
from backend.rag_engine import rag_engine
from backend.notifications import notification_service

def normalize_phone(phone: str) -> str:
    """Normalize phone numbers by stripping formatting characters for reliable matching."""
    if not phone:
        return ""
    digits = re.sub(r'[^0-9+]', '', phone.strip())
    return digits

class DiagnosticVoiceAgent:
    """
    Dedicated Human-Like Care Coordinator (Riya) for Apex Family Diagnostic Lab.
    Attends inbound telephone calls from personal phone numbers, recognizes returning
    patients, checks preparation/fasting SOPs using RAG, schedules doorstep sampling
    or in-situ clinic visits with automated WhatsApp & Gmail confirmations, detects
    any clinical or diagnostic ambiguity and directly transfers to a real human assistant,
    and exhibits high emotional sensitivity and empathy in all human interactions.
    """
    def __init__(self, caller_phone: str, call_sid: Optional[str] = None):
        self.caller_phone = caller_phone
        self.clean_phone = normalize_phone(caller_phone)
        self.call_sid = call_sid or f"CALL-{int(datetime.datetime.utcnow().timestamp())}"
        self.patient: Optional[Patient] = None
        self.history: List[Dict[str, str]] = []
        self.actions_taken: List[str] = []
        self.detected_intent: str = "general_inquiry"

        # Initialize session and lookup caller
        self._lookup_caller()

    def _lookup_caller(self):
        db: Session = SessionLocal()
        try:
            patients = db.query(Patient).all()
            for p in patients:
                if normalize_phone(p.phone_number) == self.clean_phone or (
                    len(self.clean_phone) >= 10 and self.clean_phone[-10:] in normalize_phone(p.phone_number)
                ):
                    self.patient = p
                    break
        finally:
            db.close()

    def get_initial_greeting(self) -> Dict[str, Any]:
        """
        Generates immediate, warm, compassionate greeting upon phone pickup from Riya.
        """
        if self.patient:
            db: Session = SessionLocal()
            recent_report = None
            try:
                recent_report = db.query(LabReport).filter_by(patient_id=self.patient.id).order_by(LabReport.id.desc()).first()
            finally:
                db.close()

            if recent_report:
                greeting = (
                    f"Hello {self.patient.full_name}, thank you for calling Apex Family Diagnostic Lab! "
                    f"My name is Riya, your care coordinator. I see you recently had tests with us. "
                    f"Are you calling to review your recent results, or would you like to schedule a new test today? "
                    f"We offer both doorstep home sample collection and in-situ clinic appointments."
                )
            else:
                greeting = (
                    f"Hello {self.patient.full_name}, thank you for calling Apex Family Diagnostic Lab! "
                    f"My name is Riya, your care coordinator. It is wonderful to hear from you again. "
                    f"How can I assist you today? Would you like to book a doorstep sample draw or an in-situ laboratory clinic visit?"
                )
            caller_name = self.patient.full_name
        else:
            greeting = (
                "Thank you for calling Apex Family Diagnostic Lab! My name is Riya, your dedicated care coordinator. "
                "I can help you schedule a doorstep home collection, reserve an in-situ lab clinic appointment, "
                "or explain pre-test fasting guidelines. How may I assist you today?"
            )
            caller_name = "New Caller"

        self.history.append({"role": "assistant", "content": greeting})
        return {
            "speech": greeting,
            "caller_name": caller_name,
            "caller_phone": self.caller_phone,
            "is_returning_patient": bool(self.patient),
            "call_sid": self.call_sid,
            "action": "greeting",
            "coordinator_name": "Riya"
        }

    def _detect_human_empathy_prefix(self, user_lower: str) -> str:
        """
        Evaluates emotional cues and sentiment to provide sensitive, empathetic human interaction.
        """
        # 1. Distress / Anxiety / Fear
        if any(w in user_lower for w in ["scared", "worried", "nervous", "anxious", "terrified", "panic", "stress", "crying", "please help me", "pain is bad", "feeling bad"]):
            return "I hear how anxious you are feeling, and I want to assure you that you are in caring and safe hands with our clinical team. "
        
        # 2. Frustration / Complaints
        if any(w in user_lower for w in ["bad service", "frustrated", "irritated", "why so slow", "taking forever", "terrible", "unacceptable", "complaint"]):
            return "I completely understand your frustration and apologize for any inconvenience. Your peace of mind and health are my top priority. "
        
        # 3. Elderly / Confusion
        if any(w in user_lower for w in ["elderly", "old person", "hard of hearing", "speak slowly", "don't understand computers"]):
            return "Take all the time you need, I am right here with you. "
        
        return ""

    def process_turn(self, user_transcript: str) -> Dict[str, Any]:
        """
        Processes a spoken or typed turn from the user, applies human interaction sensitivity,
        detects clinical/policy ambiguities to direct calls to real human assistants,
        and executes diagnostic laboratory workflows.
        """
        self.history.append({"role": "user", "content": user_transcript})
        user_lower = user_transcript.lower()
        db: Session = SessionLocal()

        # Human Interaction Sensitivity (Empathy Prefix)
        empathy_prefix = self._detect_human_empathy_prefix(user_lower)

        try:
            # 1. Emergency red-flag symptom detection -> Immediate Human Medical Handover
            if any(term in user_lower for term in ["chest pain", "can't breathe", "cannot breathe", "fainting", "heart attack", "collapsed", "severe bleeding", "emergency"]):
                self.detected_intent = "emergency_escalation"
                self.actions_taken.append("Emergency Red-Flag Symptoms -> Transferred to Duty Medical Officer & Emergency Protocol")
                response = (
                    "I hear that you are experiencing urgent symptoms. Please hold the line — let me connect you "
                    "immediately to our Senior Duty Medical Officer and our clinical emergency team. "
                    "If you are in immediate distress, please also dial 911 or 112 right away. Connecting you now..."
                )
                return self._finalize_turn(
                    response,
                    intent="emergency_transfer",
                    tool_executed="transfer_to_duty_medical_officer",
                    extra={"transfer_target": "Senior Duty Medical Officer", "priority": "CRITICAL"}
                )

            # 2. AMBIGUITY DETECTION & DIRECT ESCALATION TO REAL HUMAN ASSISTANT
            # Triggers when:
            # a) User expresses doubt, uncertainty, or confusion
            # b) Conflicting medications/medical history with fasting or tests
            # c) Complex clinical queries where automated answers could carry risk
            ambiguity_signals = [
                "not sure", "confused", "have doubts", "doubt", "unclear", "ambiguous",
                "doctor said something else", "doctor said something different", "is that safe for me",
                "is it safe for", "what if something goes wrong", "taking blood thinner", "taking insulin",
                "can i take my medication", "heart pills with fasting", "complicated condition", "high risk",
                "second opinion", "not certain", "hard to explain", "conflicting advice"
            ]
            if any(sig in user_lower for sig in ambiguity_signals):
                self.detected_intent = "human_handover_ambiguity"
                self.actions_taken.append("Clinical / Procedural Ambiguity Detected -> Directed Call to Real Human Assistant Desk")
                human_desk_phone = os.getenv("HUMAN_ASSISTANT_PHONE_NUMBER", "(562) 438-8802")
                response = (
                    f"{empathy_prefix}Because your health, safety, and comfort are our absolute priority, "
                    f"and that situation involves important medical nuances, I want to make sure you receive completely "
                    f"unambiguous, verified clinical guidance. "
                    f"Please hold the line for just a moment — I am directly transferring your call to our Senior Duty Medical Officer "
                    f"and Human Clinical Care Desk at {human_desk_phone} right now so you can speak directly with a doctor. "
                    f"Connecting you now..."
                )
                return self._finalize_turn(
                    response,
                    intent="human_handover_ambiguity",
                    tool_executed="transfer_to_real_human_assistant",
                    extra={
                        "transfer_destination": "Senior Duty Medical Officer & Human Care Desk",
                        "phone": human_desk_phone,
                        "ambiguity_detected": True,
                        "status": "direct_human_transfer"
                    }
                )

            # 3. Out-of-Scope / Explicit Human Request -> Graceful Human Handover Protocol
            out_of_scope_keywords = [
                "surgery", "car", "mechanic", "loan", "lawyer", "attorney", "dentist", "dental",
                "crypto", "flight", "hotel", "house rent", "prescription for antibiotics", "give me pills",
                "talk to human", "speak to human", "real person", "operator", "representative", "transfer me", "supervisor"
            ]
            if any(k in user_lower for k in out_of_scope_keywords):
                self.detected_intent = "out_of_scope_transfer"
                self.actions_taken.append("Out of Scope Query -> Transferred call to Senior Human Clinical Desk")
                response = (
                    f"{empathy_prefix}Let me connect you right now to our Senior Duty Medical Officer / Clinical Supervisor "
                    "who can assist you directly with that request. Please hold on for just a moment while I transfer your call..."
                )
                return self._finalize_turn(response, intent="human_handover", tool_executed="transfer_to_human_specialist")

            # 4. Check Lab Reports / Test Results Intent
            if any(k in user_lower for k in ["report", "result", "cholesterol", "sugar level", "findings", "test status"]) and (
                "check" in user_lower or "what is" in user_lower or "how is" in user_lower or "ready" in user_lower or "my" in user_lower
            ):
                self.detected_intent = "query_report"
                if not self.patient:
                    response = (
                        f"{empathy_prefix}I would be glad to look up your laboratory findings. Since you are calling from a new number, "
                        "could you please share your full name and registered 10-digit telephone number so I can access your records securely?"
                    )
                    return self._finalize_turn(response, intent="query_report_auth_needed")

                reports = db.query(LabReport).filter_by(patient_id=self.patient.id).order_by(LabReport.id.desc()).limit(3).all()
                if not reports:
                    response = (
                        f"{empathy_prefix}Mr./Ms. {self.patient.full_name}, I checked our laboratory records, but there are no completed reports on file right now. "
                        "If you gave a sample earlier today, our standard turnaround is 6 to 8 hours. "
                        "Let me connect you directly to our Pathology Accessioning Desk if you need an expedited status check."
                    )
                    return self._finalize_turn(response, intent="query_report_empty")

                report_summaries = []
                for r in reports:
                    flag_note = f" (Flagged as {r.flag.upper()})" if r.flag != "normal" else " (Optimal / Normal)"
                    summary_line = f"{r.test.test_name}: Result is {r.result_value}{flag_note}."
                    if r.ai_summary:
                        summary_line += f" Clinical note: {r.ai_summary}"
                    report_summaries.append(summary_line)

                self.actions_taken.append(f"Retrieved {len(reports)} lab reports for {self.patient.full_name}")
                response = (
                    f"{empathy_prefix}Here are your latest laboratory results, {self.patient.full_name}:\n"
                    + " ".join(report_summaries)
                    + "\nWould you like me to send the official signed PDF report to your WhatsApp and Gmail, or would you like to schedule any follow-up tests?"
                )
                return self._finalize_turn(response, intent="query_report_success", tool_executed="get_patient_reports")

            # 5. Fasting & Pre-test Preparation / Lab Policy (RAG Tool with Ambiguity Guard)
            if any(k in user_lower for k in ["fasting", "fast", "water", "food", "eat", "drink", "prepare", "preparation", "cancel", "refund", "late", "insurance", "privacy", "hipaa", "panic", "critical", "cold chain"]):
                self.detected_intent = "check_policy"
                rag_result = rag_engine.answer_query(user_transcript)
                citations = rag_result.get("citations", [])

                # Check if RAG result has low confidence / ambiguity
                ambiguity_threshold = float(os.getenv("AMBIGUITY_THRESHOLD", "0.30"))
                if not citations or (citations and citations[0].get("score", 1.0) < ambiguity_threshold):
                    # Ambiguity in policy match -> Escalate to human assistant
                    self.detected_intent = "human_handover_ambiguity"
                    self.actions_taken.append("RAG Policy Ambiguity (< threshold) -> Escalated to Human Care Desk")
                    response = (
                        f"{empathy_prefix}Our Standard Operating Procedures have specific protocols for that, but to ensure "
                        "zero ambiguity for your exact situation, let me directly connect you to our Senior Duty Medical Officer. "
                        "Please hold the line for a moment while I transfer you..."
                    )
                    return self._finalize_turn(response, intent="human_handover_ambiguity", tool_executed="transfer_to_real_human_assistant")

                answer_body = rag_result["answer"]
                spoken_answer = re.sub(r'#+\s*', '', answer_body)
                spoken_answer = re.sub(r'\*\*', '', spoken_answer)

                top_clause = citations[0]["section"] if citations else "Standard Operating Procedures"
                self.actions_taken.append(f"Queried Policy RAG: '{user_transcript}' -> Cited {top_clause}")
                response = (
                    f"{empathy_prefix}Here is our official laboratory guidance on that:\n{spoken_answer}\n"
                    "Would you like to book a doorstep sample collection at your home, or would you prefer an in-situ clinic appointment at our laboratory?"
                )
                return self._finalize_turn(
                    response,
                    intent="check_policy",
                    tool_executed="query_policy_rag",
                    extra={"citations": citations}
                )

            # 6. Book Appointment: Distinguishes Doorstep vs. In-Situ & Dispatches GMAIL + WHATSAPP
            if any(k in user_lower for k in ["book", "schedule", "appointment", "doorstep", "home collection", "in-situ", "insitu", "in person", "visit lab", "come to lab", "clinic visit", "sample draw", "tomorrow", "slot"]):
                self.detected_intent = "book_appointment"

                tomorrow = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
                time_slot = "07:30 AM - 08:30 AM"
                if "morning" in user_lower or "early" in user_lower:
                    time_slot = "06:30 AM - 07:30 AM"
                elif "evening" in user_lower or "afternoon" in user_lower:
                    time_slot = "04:00 PM - 05:00 PM"

                # Detect booking type preference
                if any(m in user_lower for m in ["insitu", "in-situ", "clinic", "in person", "come to clinic", "walk in", "lab visit"]):
                    appointment_type = "insitu_lab_visit"
                    booking_label = "In-Situ Laboratory Clinic Visit"
                    loc_text = "Apex Diagnostic Center (5580 E. 2nd St, Suite 206)"
                else:
                    appointment_type = "home_collection"
                    booking_label = "Doorstep Home Sample Collection"
                    loc_text = "at your residence"

                # Extract tests requested
                test_names = "Complete Blood Count (CBC) & Fasting Profile"
                fasting_rules = "10 to 12 hours of overnight fasting (water is allowed)."
                if "lipid" in user_lower:
                    test_names = "Comprehensive Lipid Profile"
                    fasting_rules = "12 hours strict fasting. Water is permitted."
                elif "full body" in user_lower or "package" in user_lower:
                    test_names = "Apex Complete Executive Wellness Package"
                    fasting_rules = "10 to 12 hours fasting. Avoid morning tea/coffee."
                elif "thyroid" in user_lower:
                    test_names = "Thyroid Profile (TSH)"
                    fasting_rules = "Fasting is not strictly mandatory, but morning draws before medications are recommended."

                if self.patient:
                    patient_id = self.patient.id
                    patient_name = self.patient.full_name
                    patient_phone = self.patient.phone_number
                    patient_email = self.patient.email or f"{self.patient.full_name.lower().replace(' ', '.')}@gmail.com"
                    address = self.patient.address or "Address on file"
                else:
                    new_patient = Patient(
                        full_name="Valued Patient",
                        phone_number=self.caller_phone or "+1 (555) 000-1111",
                        email="patient@gmail.com",
                        address="Residential Doorstep (Confirmed on call)",
                        gender="Unknown"
                    )
                    db.add(new_patient)
                    db.commit()
                    self.patient = new_patient
                    patient_id = new_patient.id
                    patient_name = new_patient.full_name
                    patient_phone = new_patient.phone_number
                    patient_email = new_patient.email
                    address = new_patient.address

                # Record appointment
                appt = Appointment(
                    patient_id=patient_id,
                    appointment_type=appointment_type,
                    scheduled_date=tomorrow,
                    time_slot=time_slot,
                    pickup_address=address if appointment_type == "home_collection" else "Apex Diagnostic Center (5580 E. 2nd St, Suite 206)",
                    status="booked",
                    tests_requested=test_names,
                    notes=f"Booked via Care Coordinator Riya for {booking_label}."
                )
                db.add(appt)
                db.commit()

                # Dispatch automated booking confirmations on GMAIL & WHATSAPP
                notif_result = notification_service.send_appointment_confirmation(
                    patient_name=patient_name,
                    patient_phone=patient_phone,
                    patient_email=patient_email,
                    appointment_id=appt.id,
                    appointment_type=appointment_type,
                    scheduled_date=tomorrow,
                    time_slot=time_slot,
                    tests_requested=test_names,
                    pickup_address=appt.pickup_address,
                    fasting_instructions=fasting_rules
                )

                self.actions_taken.append(
                    f"Booked {booking_label} #{appt.id} for {patient_name} on {tomorrow} ({time_slot}); "
                    f"Dispatched confirmation on GMAIL ({notif_result['gmail']['status']}) & WhatsApp ({notif_result['whatsapp']['status']})"
                )

                appt.notes += f" [Confirmations Dispatched: WhatsApp ({notif_result['whatsapp']['status']}) & Gmail ({notif_result['gmail']['status']})]"
                db.commit()

                if appointment_type == "home_collection":
                    response = (
                        f"{empathy_prefix}Wonderful! I have scheduled your Doorstep Home Sample Collection for tomorrow, {tomorrow}, "
                        f"during the slot {time_slot} for {test_names}. "
                        f"Our phlebotomist will arrive equipped with a sterile collection kit and temperature-controlled cold box. "
                        f"I have also instantly dispatched your booking confirmation and pre-test fasting instructions to your WhatsApp ({patient_phone}) "
                        f"and your Gmail inbox ({patient_email})! Is there anything else I can assist you with today?"
                    )
                else:
                    response = (
                        f"{empathy_prefix}Perfect! I have reserved your In-Situ Laboratory Clinic Appointment for tomorrow, {tomorrow}, "
                        f"at {time_slot} for {test_names} at our facility on 5580 E. 2nd St. "
                        f"Your slot is priority fast-tracked with zero waiting time. "
                        f"I have also sent your complete booking confirmation and clinic directions to your WhatsApp ({patient_phone}) "
                        f"and your Gmail inbox ({patient_email})! How else may I assist you today?"
                    )

                return self._finalize_turn(
                    response,
                    intent="book_appointment_success",
                    tool_executed="book_appointment",
                    extra={
                        "appointment_id": appt.id,
                        "date": tomorrow,
                        "slot": time_slot,
                        "type": appointment_type,
                        "gmail_dispatched": notif_result["gmail"]["status"],
                        "whatsapp_dispatched": notif_result["whatsapp"]["status"]
                    }
                )

            # 7. Search Tests / Pricing / Packages
            if any(k in user_lower for k in ["price", "cost", "how much", "package", "full body", "cbc", "lipid", "thyroid", "sugar", "vitamin", "kft", "lft", "tests available"]):
                self.detected_intent = "search_catalog"
                matched_tests = []
                for test in db.query(TestCatalog).all():
                    if test.test_name.lower() in user_lower or test.test_code.lower() in user_lower or any(word in user_lower for word in test.test_name.lower().split() if len(word) > 3):
                        matched_tests.append(test)

                matched_packages = []
                for pkg in db.query(HealthPackage).all():
                    if any(word in user_lower for word in pkg.package_name.lower().split() if len(word) > 3) or "package" in user_lower:
                        matched_packages.append(pkg)

                if matched_packages and ("package" in user_lower or "full body" in user_lower or "wellness" in user_lower):
                    pkg = matched_packages[0]
                    self.actions_taken.append(f"Retrieved Package: {pkg.package_name}")
                    response = (
                        f"{empathy_prefix}Our featured comprehensive checkup is the '{pkg.package_name}'. "
                        f"It covers {len(pkg.to_dict()['test_codes'])} essential parameters. "
                        f"The special package fee is ${pkg.discounted_price:.2f} (normally ${pkg.price:.2f}). "
                        f"We can conduct this either as a doorstep home collection or as an in-situ clinic visit. Which would you prefer?"
                    )
                    return self._finalize_turn(response, intent="search_catalog_package", tool_executed="search_packages")

                if matched_tests:
                    t = matched_tests[0]
                    fasting_text = f"It requires {t.fasting_hours} hours of fasting." if t.fasting_required else "No fasting is required."
                    self.actions_taken.append(f"Retrieved Test: {t.test_name}")
                    response = (
                        f"{empathy_prefix}The {t.test_name} ({t.test_code}) is ${t.price:.2f}. "
                        f"Results are ready within {t.turnaround_hours} hours. {fasting_text} "
                        f"Would you prefer our complimentary doorstep home collection, or would you like to visit our in-situ laboratory clinic?"
                    )
                    return self._finalize_turn(response, intent="search_catalog_test", tool_executed="search_test_catalog")

            # 8. Default / Fallback Support
            self.detected_intent = "conversational_support"
            response = (
                f"{empathy_prefix}I am here to take care of all your diagnostic requirements. "
                "I can schedule a doorstep sample draw at your home, book an in-situ laboratory clinic visit, "
                "or explain fasting and preparation rules. Which would you prefer today?"
            )
            return self._finalize_turn(response, intent="general_assistance")

        finally:
            db.close()

    def _finalize_turn(self, response_text: str, intent: str, tool_executed: Optional[str] = None, extra: Optional[Dict] = None) -> Dict[str, Any]:
        self.history.append({"role": "assistant", "content": response_text})

        db: Session = SessionLocal()
        try:
            call_log = db.query(CallLog).filter_by(call_sid=self.call_sid).first()
            transcript_text = "\n".join([f"{h['role'].upper()}: {h['content']}" for h in self.history])
            actions_text = "; ".join(self.actions_taken)

            if not call_log:
                call_log = CallLog(
                    caller_phone=self.caller_phone,
                    caller_name=self.patient.full_name if self.patient else "Guest Caller",
                    call_sid=self.call_sid,
                    call_type="inbound",
                    duration_seconds=len(self.history) * 12,
                    full_transcript=transcript_text,
                    detected_intent=self.detected_intent,
                    actions_taken=actions_text,
                    satisfaction_score=5.0
                )
                db.add(call_log)
            else:
                call_log.full_transcript = transcript_text
                call_log.detected_intent = self.detected_intent
                call_log.actions_taken = actions_text
                call_log.duration_seconds = len(self.history) * 12
            db.commit()
        except Exception as e:
            print(f"[VoiceAgent] Error updating call log: {e}")
            db.rollback()
        finally:
            db.close()

        payload = {
            "speech": response_text,
            "call_sid": self.call_sid,
            "intent": intent,
            "tool_executed": tool_executed,
            "actions_taken": self.actions_taken,
            "caller_phone": self.caller_phone,
            "patient_name": self.patient.full_name if self.patient else "Guest Caller",
            "coordinator_name": "Riya"
        }
        if extra:
            payload["extra"] = extra
            payload.update(extra)
        return payload
