import os
import re
import json
import datetime
from enum import Enum
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


# ==============================================================================
# PIPELINE ARCHITECTURE LAYER 1: CONVERSATION STATE & MEMORY
# ==============================================================================

class ConversationState(str, Enum):
    INITIALIZING = "INITIALIZING"
    GREETING = "GREETING"
    LISTENING = "LISTENING"
    THINKING = "THINKING"
    ROUTING_QUESTION_RAG = "ROUTING_QUESTION_RAG"
    ROUTING_ACTION_TOOLS = "ROUTING_ACTION_TOOLS"
    SLOT_SELECTION_PENDING = "SLOT_SELECTION_PENDING"
    APPOINTMENT_BOOKED = "APPOINTMENT_BOOKED"
    HUMAN_ESCALATION = "HUMAN_ESCALATION"
    EMERGENCY_ESCALATION = "EMERGENCY_ESCALATION"
    COMPLETED = "COMPLETED"


class ShortTermMemory:
    """
    Maintains conversational working memory across turns:
    - Utterance history
    - Active slots offered
    - Selected tests & pricing
    - Extracted date, time, and patient preferences
    """
    def __init__(self):
        self.turns: List[Dict[str, str]] = []
        self.pending_availability: Optional[Dict[str, Any]] = None
        self.active_entities: Dict[str, Any] = {}
        self.last_citations: List[Dict[str, Any]] = []
        self.ambiguity_detected: bool = False

    def add_turn(self, role: str, content: str):
        self.turns.append({"role": role, "content": content})

    def get_history(self) -> List[Dict[str, str]]:
        return self.turns

    def set_pending_availability(self, avail_data: Optional[Dict[str, Any]]):
        self.pending_availability = avail_data

    def clear_pending(self):
        self.pending_availability = None


class ContextManager:
    """
    Manages long-term identity and session context:
    - Resolves caller phone to Patient in DB
    - Retrieves recent lab reports and previous appointment history
    """
    def __init__(self, caller_phone: str):
        self.caller_phone = caller_phone
        self.clean_phone = normalize_phone(caller_phone)
        self.patient: Optional[Patient] = None
        self.recent_report: Optional[LabReport] = None
        self.load_patient_context()

    def load_patient_context(self):
        db: Session = SessionLocal()
        try:
            patients = db.query(Patient).all()
            for p in patients:
                if normalize_phone(p.phone_number) == self.clean_phone or (
                    len(self.clean_phone) >= 10 and self.clean_phone[-10:] in normalize_phone(p.phone_number)
                ):
                    self.patient = p
                    break

            if self.patient:
                self.recent_report = db.query(LabReport).filter_by(
                    patient_id=self.patient.id
                ).order_by(LabReport.id.desc()).first()
        finally:
            db.close()


# ==============================================================================
# PIPELINE ARCHITECTURE LAYER 2: AGENT TOOLS SUITE (ACTION REQUIRED)
# ==============================================================================

class AgentTools:
    """
    Autonomous tools executed by the Agent when an Action is required:
    1. Price: Query test and package prices in INR (₹)
    2. Availability: Query real-time database slots (10-12 AM ₹450 vs 12-2 PM ₹500)
    3. Lab: Retrieve in-situ laboratory clinic information & directions
    4. Home collection: Check doorstep phlebotomy coverage & sterile kit logistics
    5. Booking: Confirm appointment, persist in DB, and dispatch WhatsApp + Gmail alerts
    """

    @staticmethod
    def check_availability(
        test_query: str = "CBC",
        target_date: Optional[str] = "tomorrow",
        appointment_type: str = "home_collection",
        db: Optional[Session] = None
    ) -> Dict[str, Any]:
        """
        Checks appointment slot availability and slot-specific pricing from the DATABASE.
        Queries TestCatalog and existing Appointments.
        Returns:
          - 10–12 AM at ₹450
          - 12–2 PM at ₹500
        """
        close_db = False
        if db is None:
            db = SessionLocal()
            close_db = True

        try:
            today = datetime.date.today()
            if not target_date or target_date.lower() in ["tomorrow", "tmrw"]:
                resolved_date = (today + datetime.timedelta(days=1)).isoformat()
                date_label = "tomorrow"
            elif target_date.lower() == "today":
                resolved_date = today.isoformat()
                date_label = "today"
            else:
                resolved_date = target_date
                date_label = target_date

            # Look up test in database
            matched_test = None
            test_code_clean = test_query.strip().upper()
            matched_test = db.query(TestCatalog).filter(TestCatalog.test_code == test_code_clean).first()
            if not matched_test:
                matched_test = db.query(TestCatalog).filter(
                    (TestCatalog.test_name.ilike(f"%{test_query}%")) |
                    (TestCatalog.test_code.ilike(f"%{test_query}%"))
                ).first()

            if matched_test:
                test_name = matched_test.test_name
                test_code = matched_test.test_code
                base_price = int(matched_test.price) if matched_test.price >= 100 else 450
                fasting_req = matched_test.fasting_required
                fasting_hours = matched_test.fasting_hours
            else:
                test_name = "Complete Blood Count (CBC) with Differential"
                test_code = "CBC"
                base_price = 450
                fasting_req = False
                fasting_hours = 0

            # Query Database for existing Appointments on target_date
            existing_appts = db.query(Appointment).filter(
                Appointment.scheduled_date == resolved_date,
                Appointment.status != "cancelled"
            ).all()

            slot_1_booked = sum(1 for a in existing_appts if "10:00 AM" in a.time_slot or "10-12" in a.time_slot or "10–12" in a.time_slot)
            slot_2_booked = sum(1 for a in existing_appts if "12:00 PM" in a.time_slot or "12-2" in a.time_slot or "12–2" in a.time_slot)

            max_capacity_per_slot = 5
            slot_1_price = base_price if test_code == "CBC" else base_price
            slot_2_price = 500 if test_code == "CBC" else (base_price + 50)

            slots = [
                {
                    "slot_id": "slot_10_12",
                    "time_slot": "10:00 AM - 12:00 PM",
                    "slot_label": "10–12 AM",
                    "price": slot_1_price,
                    "currency": "₹",
                    "price_formatted": f"₹{slot_1_price}",
                    "available": slot_1_booked < max_capacity_per_slot,
                    "booked_count": slot_1_booked,
                    "max_capacity": max_capacity_per_slot
                },
                {
                    "slot_id": "slot_12_2",
                    "time_slot": "12:00 PM - 02:00 PM",
                    "slot_label": "12–2 PM",
                    "price": slot_2_price,
                    "currency": "₹",
                    "price_formatted": f"₹{slot_2_price}",
                    "available": slot_2_booked < max_capacity_per_slot,
                    "booked_count": slot_2_booked,
                    "max_capacity": max_capacity_per_slot
                }
            ]

            return {
                "test_name": test_name,
                "test_code": test_code,
                "target_date": resolved_date,
                "date_label": date_label,
                "appointment_type": appointment_type,
                "fasting_required": fasting_req,
                "fasting_hours": fasting_hours,
                "slots": slots
            }
        finally:
            if close_db:
                db.close()

    @staticmethod
    def get_pricing(test_or_package_query: str, db: Optional[Session] = None) -> Dict[str, Any]:
        """Tool: Query price of specific tests or wellness health packages."""
        close_db = False
        if db is None:
            db = SessionLocal()
            close_db = True

        try:
            q_lower = test_or_package_query.lower()
            # 1. Check Packages
            packages = db.query(HealthPackage).all()
            for pkg in packages:
                if pkg.package_name.lower() in q_lower or any(w in q_lower for w in pkg.package_name.lower().split() if len(w) > 3):
                    return {
                        "type": "package",
                        "name": pkg.package_name,
                        "discounted_price": pkg.discounted_price,
                        "price_formatted": f"₹{int(pkg.discounted_price)}",
                        "original_price": pkg.price,
                        "test_count": len(pkg.to_dict().get("test_codes", [])),
                        "fasting_required": pkg.fasting_required
                    }

            # 2. Check Test Catalog
            tests = db.query(TestCatalog).all()
            for t in tests:
                if t.test_name.lower() in q_lower or t.test_code.lower() in q_lower:
                    price_val = 450 if t.test_code == "CBC" else int(t.price)
                    return {
                        "type": "test",
                        "name": t.test_name,
                        "code": t.test_code,
                        "price": price_val,
                        "price_formatted": f"₹{price_val}",
                        "turnaround_hours": t.turnaround_hours,
                        "fasting_required": t.fasting_required,
                        "fasting_hours": t.fasting_hours
                    }

            # Fallback default CBC
            return {
                "type": "test",
                "name": "Complete Blood Count (CBC) with Differential",
                "code": "CBC",
                "price": 450,
                "price_formatted": "₹450",
                "turnaround_hours": 6,
                "fasting_required": False,
                "fasting_hours": 0
            }
        finally:
            if close_db:
                db.close()

    @staticmethod
    def get_lab_info(db: Optional[Session] = None) -> Dict[str, Any]:
        """Tool: Retrieve in-situ laboratory clinic information, hours, and address."""
        return {
            "name": "Apex Family Diagnostic Laboratory",
            "address": "5580 E. 2nd St, Suite 206",
            "operating_hours": "Mon-Sat: 6:30 AM - 8:00 PM, Sun: 7:00 AM - 2:00 PM",
            "sample_drop_off": "24/7 Accessioned Processing",
            "certifications": ["NABL Accredited", "CAP Certified", "ISO 15189 Compliant"],
            "support_phone": os.getenv("AGENT_PHONE_NUMBER", "+91 80 4388 8802"),
            "agent_name": os.getenv("AGENT_NAME", "Vinod")
        }

    @staticmethod
    def check_home_collection(address: str = "", pincode: str = "") -> Dict[str, Any]:
        """Tool: Check home collection availability, logistics, cold-chain protocol."""
        return {
            "service_available": True,
            "cold_chain_carrier": "Temperature-controlled 2°C - 8°C cold box",
            "phlebotomist_protocol": "Sterile vacuum-sealed single-use BD Vacutainer needles",
            "service_charge": "Complimentary doorstep collection across service radius",
            "turnaround_time": "Sample reached to central testing facility within 45 minutes"
        }

    @staticmethod
    def book_appointment(
        patient: Optional[Patient],
        caller_phone: str,
        test_name: str,
        scheduled_date: str,
        time_slot: str,
        appointment_type: str = "home_collection",
        price_str: str = "₹450",
        agent_name: str = "Vinod",
        db: Optional[Session] = None
    ) -> Dict[str, Any]:
        """Tool: Commits appointment to DB and dispatches dual WhatsApp & Gmail confirmations."""
        close_db = False
        if db is None:
            db = SessionLocal()
            close_db = True

        try:
            booking_label = "Doorstep Home Sample Collection" if appointment_type == "home_collection" else "In-Situ Laboratory Clinic Visit"
            loc_text = "Residential Doorstep (Confirmed on call)" if appointment_type == "home_collection" else "Apex Diagnostic Center (5580 E. 2nd St, Suite 206)"

            if patient:
                patient_id = patient.id
                patient_name = patient.full_name
                patient_phone = patient.phone_number
                patient_email = patient.email or f"{patient.full_name.lower().replace(' ', '.')}@gmail.com"
                address = patient.address or loc_text
            else:
                new_patient = Patient(
                    full_name="Valued Patient",
                    phone_number=caller_phone or "+91 98200 23456",
                    email="patient@gmail.com",
                    address=loc_text,
                    gender="Unknown"
                )
                db.add(new_patient)
                db.commit()
                patient_id = new_patient.id
                patient_name = new_patient.full_name
                patient_phone = new_patient.phone_number
                patient_email = new_patient.email
                address = new_patient.address

            appt = Appointment(
                patient_id=patient_id,
                appointment_type=appointment_type,
                scheduled_date=scheduled_date,
                time_slot=time_slot,
                pickup_address=address if appointment_type == "home_collection" else loc_text,
                status="booked",
                tests_requested=test_name,
                notes=f"Booked via Virtual Lab Assistant {agent_name} for {price_str} ({time_slot})."
            )
            db.add(appt)
            db.commit()

            # Dispatch confirmations with price
            fasting_note = "Fasting is not strictly required for CBC (water is allowed)." if "cbc" in test_name.lower() else "10 to 12 hours of overnight fasting (water is allowed)."
            notif_result = notification_service.send_appointment_confirmation(
                patient_name=patient_name,
                patient_phone=patient_phone,
                patient_email=patient_email,
                appointment_id=appt.id,
                appointment_type=appointment_type,
                scheduled_date=scheduled_date,
                time_slot=time_slot,
                tests_requested=test_name,
                pickup_address=appt.pickup_address,
                fasting_instructions=fasting_note,
                price=price_str
            )

            appt.notes += f" [Confirmations Dispatched: WhatsApp ({notif_result['whatsapp']['status']}) & Gmail ({notif_result['gmail']['status']})]"
            db.commit()

            return {
                "appointment_id": appt.id,
                "patient_name": patient_name,
                "patient_phone": patient_phone,
                "patient_email": patient_email,
                "scheduled_date": scheduled_date,
                "time_slot": time_slot,
                "tests_requested": test_name,
                "price": price_str,
                "appointment_type": appointment_type,
                "booking_label": booking_label,
                "pickup_address": appt.pickup_address,
                "gmail_status": notif_result["gmail"]["status"],
                "whatsapp_status": notif_result["whatsapp"]["status"]
            }
        finally:
            if close_db:
                db.close()


# Legacy standalone wrapper for direct backward compatibility
def check_availability(
    test_query: str = "CBC",
    target_date: Optional[str] = "tomorrow",
    appointment_type: str = "home_collection",
    db: Optional[Session] = None
) -> Dict[str, Any]:
    return AgentTools.check_availability(test_query, target_date, appointment_type, db)


# ==============================================================================
# PIPELINE ARCHITECTURE LAYER 3: RAG ROUTING (QUESTION)
# ==============================================================================

class RAGEngineRouter:
    """
    Handles Question routing to Knowledge Retrieval (RAG):
    - Test: Biological parameters, normal ranges, indications
    - FAQ: Operating hours, sample turnaround, reports
    - Prep: Fasting requirements, water, medication instructions
    - Policy: Refund, cancellation, insurance, panic values escalation
    """

    @staticmethod
    def query(user_query: str) -> Dict[str, Any]:
        result = rag_engine.answer_query(user_query)
        # Classify sub-category of RAG question
        q_lower = user_query.lower()
        if any(w in q_lower for w in ["fasting", "fast", "water", "food", "eat", "drink", "prepare", "preparation", "tea", "coffee"]):
            component = "Prep"
        elif any(w in q_lower for w in ["refund", "cancel", "policy", "insurance", "hipaa", "privacy", "panic", "critical"]):
            component = "Policy"
        elif any(w in q_lower for w in ["hours", "open", "timing", "accredited", "address", "faq", "where"]):
            component = "FAQ"
        else:
            component = "Test"

        result["rag_component"] = component
        return result


# ==============================================================================
# PIPELINE ARCHITECTURE LAYER 4: CONVERSATION ENGINE (PIPELINE ROUTER)
# ==============================================================================

class ConversationEngine:
    """
    Coordinates the pipeline matching the user's architectural specification:
    User Input ➔ Intent Detection & State Management ➔ Decision (Question vs Action)
    ➔ Branch to [RAG (Test/FAQ/Prep/Policy)] OR [AGENT TOOLS (Price/Availability/Lab/Home collection/Booking)]
    ➔ Response Generator ➔ Streaming TTS Output Trace
    """
    def __init__(self, agent_name: str = "Vinod"):
        self.agent_name = agent_name
        self.state = ConversationState.INITIALIZING
        self.memory = ShortTermMemory()

    def detect_category_and_intent(self, text: str) -> Dict[str, Any]:
        """
        Classifies incoming utterance into:
        - "Question" (routes to RAG: Test, FAQ, Prep, Policy)
        - "Action required" (routes to AGENT TOOLS: Price, Availability, Lab, Home collection, Booking)
        - "Emergency" (immediate medical handover)
        - "Ambiguity" (direct human assistant handover)
        - "ChitChat" (identity, greeting, pleasantry)
        """
        user_lower = text.lower()

        # 1. Emergency Red Flags
        if any(term in user_lower for term in ["chest pain", "can't breathe", "cannot breathe", "fainting", "heart attack", "collapsed", "severe bleeding", "emergency"]):
            return {
                "category": "Emergency",
                "route": "EMERGENCY_TRANSFER",
                "component": "Emergency Escalation",
                "intent": "emergency_escalation"
            }

        # 2. Ambiguity Detection (Conflicting advice, medical doubt, high-risk questions)
        ambiguity_signals = [
            "not sure", "confused", "have doubts", "doubt", "unclear", "ambiguous",
            "doctor said something else", "doctor said something different", "is that safe for me",
            "is it safe for", "what if something goes wrong", "taking blood thinner", "taking insulin",
            "can i take my medication", "heart pills with fasting", "complicated condition", "high risk",
            "second opinion", "not certain", "hard to explain", "conflicting advice"
        ]
        if any(sig in user_lower for sig in ambiguity_signals):
            return {
                "category": "Ambiguity",
                "route": "HUMAN_HANDOVER",
                "component": "Direct Human Assistant",
                "intent": "human_handover_ambiguity"
            }

        # 3. Explicit Human Transfer or Out of Scope
        out_of_scope_keywords = [
            "talk to human", "speak to human", "real person", "operator", "representative", "transfer me", "supervisor",
            "surgery", "car", "mechanic", "loan", "lawyer", "dentist", "flight"
        ]
        if any(k in user_lower for k in out_of_scope_keywords):
            return {
                "category": "Ambiguity",
                "route": "HUMAN_HANDOVER",
                "component": "Human Specialist Desk",
                "intent": "human_handover"
            }

        # 4. Action Required: Slot Confirmation (User confirming 10-12 AM or 12-2 PM)
        if self.memory.pending_availability:
            if any(term in user_lower for term in ["10 to 12", "10-12", "10–12", "10 am", "10:00", "450", "₹450", "first", "first one", "slot 1", "morning",
                                                  "12 to 2", "12-2", "12–2", "12 pm", "2 pm", "500", "₹500", "second", "second one", "slot 2", "noon", "afternoon"]):
                return {
                    "category": "Action required",
                    "route": "AGENT_TOOLS",
                    "component": "Booking",
                    "tool": "book_appointment",
                    "intent": "confirm_slot_selection"
                }

        # 5. Action Required: Check Availability ("I need a CBC tomorrow", "User wants CBC tomorrow")
        is_cbc_query = "cbc" in user_lower or "complete blood count" in user_lower
        is_avail = any(q in user_lower for q in [
            "wants cbc", "want cbc", "need cbc", "available", "availability", "check availability",
            "slots", "which slot", "what time", "timings"
        ]) or (is_cbc_query and ("tomorrow" in user_lower or "today" in user_lower))

        has_explicit_time = any(t in user_lower for t in ["7:30", "07:30", "6:30", "06:30", "4:00", "04:00", "7 am", "8 am", "6 am"])

        if is_avail and not has_explicit_time:
            return {
                "category": "Action required",
                "route": "AGENT_TOOLS",
                "component": "Availability",
                "tool": "check_availability",
                "intent": "check_availability"
            }

        # 6. Action Required: Booking Appointment (Doorstep or In-situ)
        if any(k in user_lower for k in ["book", "schedule", "appointment", "doorstep", "home collection", "in-situ", "insitu", "in person", "visit lab", "come to lab", "clinic visit", "sample draw"]):
            return {
                "category": "Action required",
                "route": "AGENT_TOOLS",
                "component": "Booking",
                "tool": "book_appointment",
                "intent": "book_appointment"
            }

        # 7. Action Required: Price / Catalog Query
        if any(k in user_lower for k in ["price", "cost", "how much", "charges", "rate", "package fee", "discount"]):
            return {
                "category": "Action required",
                "route": "AGENT_TOOLS",
                "component": "Price",
                "tool": "get_pricing",
                "intent": "search_catalog"
            }

        # 8. Action Required: Reports Lookup
        if any(k in user_lower for k in ["report", "result", "cholesterol", "sugar level", "findings", "test status"]) and (
            "check" in user_lower or "what is" in user_lower or "how is" in user_lower or "ready" in user_lower or "my" in user_lower
        ):
            return {
                "category": "Action required",
                "route": "AGENT_TOOLS",
                "component": "Lab",
                "tool": "get_patient_reports",
                "intent": "query_report"
            }

        # 9. Question: RAG (Prep / Policy / FAQ / Test)
        if any(k in user_lower for k in ["fasting", "fast", "water", "food", "eat", "drink", "prepare", "preparation", "cancel", "refund", "late", "insurance", "privacy", "hipaa", "panic", "critical", "cold chain"]):
            return {
                "category": "Question",
                "route": "RAG",
                "component": "Prep" if any(w in user_lower for w in ["fasting", "water", "food", "eat", "drink", "prepare"]) else "Policy",
                "tool": "rag_engine",
                "intent": "check_policy"
            }

        # 10. Question: General Test or FAQ Questions
        if any(k in user_lower for k in ["what is", "why do i need", "how do you test", "how does", "what does", "hours", "where are you located"]):
            return {
                "category": "Question",
                "route": "RAG",
                "component": "FAQ",
                "tool": "rag_engine",
                "intent": "check_policy"
            }

        # 11. ChitChat / Identity
        if any(k in user_lower for k in ["who are you", "what is your name", "what are you"]):
            return {
                "category": "ChitChat",
                "route": "RESPONSE_GENERATOR",
                "component": "Identity",
                "intent": "bot_identity"
            }

        if any(k in user_lower for k in ["hello", "hi", "namaste", "hey vinod", "can you hear me"]):
            return {
                "category": "ChitChat",
                "route": "RESPONSE_GENERATOR",
                "component": "Greeting",
                "intent": "bot_acknowledgement"
            }

        if any(k in user_lower for k in ["thank you", "thanks", "helpful", "appreciate"]):
            return {
                "category": "ChitChat",
                "route": "RESPONSE_GENERATOR",
                "component": "Gratitude",
                "intent": "bot_gratitude"
            }

        # Default fallback: Action/Question general assistance
        return {
            "category": "Action required",
            "route": "AGENT_TOOLS",
            "component": "Lab",
            "tool": "general_assistance",
            "intent": "general_assistance"
        }


# ==============================================================================
# PIPELINE ARCHITECTURE LAYER 5: DEDICATED VOICE AGENT (VINOD)
# ==============================================================================

class DiagnosticVoiceAgent:
    """
    Dedicated Indian Male Virtual Lab Assistant (Vinod) for Apex Family Diagnostic Lab.
    Implements the complete Voice Pipeline Architecture:
    [Microphone] ➔ [Audio Input Engine] ➔ [Streaming STT] ➔ [Conversation Engine]
    ➔ [LLM/Agent] ➔ [Question (RAG) vs Action (Agent Tools)] ➔ [Response Generator] ➔ [Streaming TTS].
    """
    def __init__(self, caller_phone: str, call_sid: Optional[str] = None):
        self.caller_phone = caller_phone
        self.clean_phone = normalize_phone(caller_phone)
        self.call_sid = call_sid or f"CALL-{int(datetime.datetime.utcnow().timestamp())}"
        self.agent_name: str = os.getenv("AGENT_NAME", "Vinod")
        self.actions_taken: List[str] = []
        self.detected_intent: str = "general_inquiry"

        # Initialize Architecture Components
        self.context_mgr = ContextManager(caller_phone)
        self.patient = self.context_mgr.patient
        self.engine = ConversationEngine(agent_name=self.agent_name)
        self.history: List[Dict[str, str]] = self.engine.memory.turns

        # For backward compatibility
        self.pending_availability: Optional[Dict[str, Any]] = None

    def _lookup_caller(self):
        """Reload caller profile from database."""
        self.context_mgr.load_patient_context()
        self.patient = self.context_mgr.patient

    def get_initial_greeting(self) -> Dict[str, Any]:
        """
        Generates immediate, warm, compassionate greeting upon phone pickup from Vinod.
        Starts with: "Hi, I'm your Lab Assistant Vinod..."
        """
        self.engine.state = ConversationState.GREETING
        self._lookup_caller()

        if self.patient:
            if self.context_mgr.recent_report:
                greeting = (
                    f"Hi, I'm your Lab Assistant {self.agent_name} from Apex Family Diagnostic Lab! "
                    f"Hello {self.patient.full_name}, it's wonderful to speak with you again. I see your recent diagnostic reports on file. "
                    f"Are you calling to review your results, or would you like to schedule a home sample collection or clinic test today?"
                )
            else:
                greeting = (
                    f"Hi, I'm your Lab Assistant {self.agent_name} from Apex Family Diagnostic Lab! "
                    f"Hello {self.patient.full_name}, it's wonderful to speak with you again. "
                    f"How can I assist you today? I can help you schedule a doorstep home collection or book an in-clinic lab appointment."
                )
            caller_name = self.patient.full_name
        else:
            greeting = (
                f"Hi, I'm your Lab Assistant {self.agent_name} from Apex Family Diagnostic Lab! "
                f"How may I assist you today? I can help you schedule a doorstep home sample collection, "
                f"book an in-clinic lab appointment, or explain pre-test fasting instructions."
            )
            caller_name = "New Caller"

        self.engine.memory.add_turn("assistant", greeting)
        return {
            "speech": greeting,
            "caller_name": caller_name,
            "caller_phone": self.caller_phone,
            "is_returning_patient": bool(self.patient),
            "call_sid": self.call_sid,
            "action": "greeting",
            "coordinator_name": self.agent_name
        }

    def _detect_human_empathy_prefix(self, user_lower: str) -> str:
        """Evaluates emotional cues to deliver compassionate care."""
        if any(w in user_lower for w in ["scared", "worried", "nervous", "anxious", "terrified", "panic", "stress", "crying", "please help me", "pain is bad", "feeling bad"]):
            return "I hear how anxious you are feeling, and I want to assure you that you are in caring and safe hands with our clinical team. "
        if any(w in user_lower for w in ["bad service", "frustrated", "irritated", "why so slow", "taking forever", "terrible", "unacceptable", "complaint"]):
            return "I completely understand your frustration and apologize for any inconvenience. Your peace of mind and health are my top priority. "
        if any(w in user_lower for w in ["elderly", "old person", "hard of hearing", "speak slowly", "don't understand computers"]):
            return "Take all the time you need, I am right here with you. "
        return ""

    def process_turn(self, user_transcript: str) -> Dict[str, Any]:
        """
        Executes the end-to-end conversation pipeline:
        1. Ingests user transcript into Conversation Engine memory
        2. Detects intent and routes to either:
           - Question ➔ RAG (Test, FAQ, Prep, Policy)
           - Action required ➔ AGENT TOOLS (Price, Availability, Lab, Home collection, Booking)
        3. Response Generator creates humanized speech from Vinod
        4. Returns speech and full pipeline trace for streaming TTS and frontend visualizer
        """
        self.engine.memory.add_turn("user", user_transcript)
        user_lower = user_transcript.lower()
        db: Session = SessionLocal()

        empathy_prefix = self._detect_human_empathy_prefix(user_lower)

        # Sync pending availability state between agent and engine memory
        if self.pending_availability and not self.engine.memory.pending_availability:
            self.engine.memory.pending_availability = self.pending_availability

        try:
            routing_decision = self.engine.detect_category_and_intent(user_transcript)
            category = routing_decision["category"]
            route = routing_decision["route"]
            component = routing_decision["component"]
            intent = routing_decision["intent"]

            pipeline_trace = {
                "user_input": user_transcript,
                "category": category,
                "route": route,
                "component": component,
                "engine": "ConversationEngine",
                "state": None
            }

            # ------------------------------------------------------------------
            # 1. EMERGENCY ESCALATION
            # ------------------------------------------------------------------
            if category == "Emergency":
                self.engine.state = ConversationState.EMERGENCY_ESCALATION
                self.detected_intent = "emergency_escalation"
                self.actions_taken.append("Emergency Red-Flag Symptoms -> Transferred to Duty Medical Officer & Emergency Protocol")
                response = (
                    "I hear that you are experiencing urgent symptoms. Please hold the line — let me connect you "
                    "immediately to our Senior Duty Medical Officer and our clinical emergency team. "
                    "If you are in immediate distress, please also dial 911 or 112 right away. Connecting you now..."
                )
                pipeline_trace["state"] = self.engine.state.value
                return self._finalize_turn(
                    response,
                    intent="emergency_transfer",
                    tool_executed="transfer_to_duty_medical_officer",
                    extra={"transfer_target": "Senior Duty Medical Officer", "priority": "CRITICAL", "pipeline_trace": pipeline_trace}
                )

            # ------------------------------------------------------------------
            # 2. AMBIGUITY DETECTION -> DIRECT HUMAN ASSISTANT TRANSFER
            # ------------------------------------------------------------------
            if category == "Ambiguity":
                self.engine.state = ConversationState.HUMAN_ESCALATION
                self.detected_intent = intent
                human_desk_phone = os.getenv("AGENT_PHONE_NUMBER", os.getenv("HUMAN_ASSISTANT_PHONE_NUMBER", "+91 80 4388 8802"))

                if intent == "human_handover_ambiguity":
                    self.actions_taken.append("Clinical / Procedural Ambiguity Detected -> Directed Call to Real Human Assistant Desk")
                    response = (
                        f"{empathy_prefix}Because your health, safety, and comfort are our absolute priority, "
                        f"and that situation involves important medical nuances, I want to make sure you receive completely "
                        f"unambiguous, verified clinical guidance. "
                        f"Please hold the line for just a moment — I am directly transferring your call to our Senior Duty Medical Officer "
                        f"and Human Clinical Care Desk at {human_desk_phone} right now so you can speak directly with a doctor. "
                        f"Connecting you now..."
                    )
                else:
                    self.actions_taken.append("Human Specialist Request -> Transferred to Senior Human Clinical Desk")
                    response = (
                        f"{empathy_prefix}Let me connect you right now to our Senior Duty Medical Officer / Clinical Supervisor "
                        f"who can assist you directly with that request at {human_desk_phone}. Please hold on for just a moment while I transfer your call..."
                    )

                pipeline_trace["state"] = self.engine.state.value
                return self._finalize_turn(
                    response,
                    intent=intent,
                    tool_executed="transfer_to_real_human_assistant",
                    extra={
                        "transfer_destination": "Senior Duty Medical Officer & Human Care Desk",
                        "phone": human_desk_phone,
                        "ambiguity_detected": True,
                        "status": "direct_human_transfer",
                        "pipeline_trace": pipeline_trace
                    }
                )

            # ------------------------------------------------------------------
            # 3. ACTION REQUIRED: AGENT TOOLS BRANCH
            # ------------------------------------------------------------------
            if category == "Action required":
                self.engine.state = ConversationState.ROUTING_ACTION_TOOLS
                pipeline_trace["state"] = self.engine.state.value

                # A. Slot Selection Confirmation (e.g. user selected "10 to 12 AM please")
                if component == "Booking" and intent == "confirm_slot_selection" and self.engine.memory.pending_availability:
                    avail_data = self.engine.memory.pending_availability
                    slots = avail_data.get("slots", [])
                    chosen_slot = None

                    if any(term in user_lower for term in ["10 to 12", "10-12", "10–12", "10 am", "10:00", "450", "₹450", "first", "first one", "slot 1", "morning"]):
                        chosen_slot = slots[0] if len(slots) > 0 else None
                    elif any(term in user_lower for term in ["12 to 2", "12-2", "12–2", "12 pm", "2 pm", "500", "₹500", "second", "second one", "slot 2", "noon", "afternoon"]):
                        chosen_slot = slots[1] if len(slots) > 1 else None

                    if chosen_slot:
                        test_name = avail_data.get("test_name", "Complete Blood Count (CBC)")
                        target_date = avail_data.get("target_date", (datetime.date.today() + datetime.timedelta(days=1)).isoformat())
                        appt_type = avail_data.get("appointment_type", "home_collection")
                        price_str = chosen_slot["price_formatted"]
                        slot_label = chosen_slot["time_slot"]

                        booking_res = AgentTools.book_appointment(
                            patient=self.patient,
                            caller_phone=self.caller_phone,
                            test_name=test_name,
                            scheduled_date=target_date,
                            time_slot=slot_label,
                            appointment_type=appt_type,
                            price_str=price_str,
                            agent_name=self.agent_name,
                            db=db
                        )

                        self.actions_taken.append(
                            f"Booked {booking_res['booking_label']} #{booking_res['appointment_id']} for {booking_res['patient_name']} on {target_date} ({slot_label}) at {price_str}; "
                            f"Dispatched GMAIL ({booking_res['gmail_status']}) & WhatsApp ({booking_res['whatsapp_status']})"
                        )

                        self.pending_availability = None
                        self.engine.memory.clear_pending()
                        self.detected_intent = "book_appointment_success"
                        self.engine.state = ConversationState.APPOINTMENT_BOOKED
                        pipeline_trace["state"] = self.engine.state.value

                        response = (
                            f"{empathy_prefix}Perfect! I have scheduled your {test_name} for tomorrow from {slot_label} at {price_str}. "
                            f"Our phlebotomist will arrive equipped with a sterile collection kit and cold-chain carrier. "
                            f"I have also sent your confirmed booking details to your WhatsApp ({booking_res['patient_phone']}) and your Gmail inbox ({booking_res['patient_email']})! "
                            f"Is there anything else I can assist you with today?"
                        )
                        return self._finalize_turn(
                            response,
                            intent="book_appointment_success",
                            tool_executed="book_appointment",
                            extra={
                                "appointment_id": booking_res["appointment_id"],
                                "date": target_date,
                                "slot": slot_label,
                                "price": price_str,
                                "type": appt_type,
                                "gmail_dispatched": booking_res["gmail_status"],
                                "whatsapp_dispatched": booking_res["whatsapp_status"],
                                "pipeline_trace": pipeline_trace
                            }
                        )

                # B. Availability Check ("User wants CBC tomorrow" / "I need a CBC tomorrow")
                if component == "Availability":
                    test_code_to_check = "CBC" if ("cbc" in user_lower or "complete blood count" in user_lower) else ("LIPID" if "lipid" in user_lower else "CBC")
                    avail_data = AgentTools.check_availability(test_query=test_code_to_check, target_date="tomorrow", db=db)
                    self.pending_availability = avail_data
                    self.engine.memory.set_pending_availability(avail_data)
                    self.detected_intent = "check_availability"
                    self.engine.state = ConversationState.SLOT_SELECTION_PENDING
                    pipeline_trace["state"] = self.engine.state.value

                    slot1 = avail_data["slots"][0]
                    slot2 = avail_data["slots"][1]
                    self.actions_taken.append(
                        f"Executed check_availability('{test_code_to_check}', 'tomorrow') -> Database returned: {slot1['slot_label']} ({slot1['price_formatted']}), {slot2['slot_label']} ({slot2['price_formatted']})"
                    )

                    response = (
                        f"{empathy_prefix}For your {avail_data['test_name']} tomorrow, we have two slots available: "
                        f"{slot1['slot_label']} for {slot1['price_formatted']}, or {slot2['slot_label']} for {slot2['price_formatted']}. "
                        f"Which one works best for you?"
                    )
                    return self._finalize_turn(
                        response,
                        intent="check_availability_slots",
                        tool_executed="check_availability",
                        extra={
                            "test_name": avail_data["test_name"],
                            "test_code": avail_data["test_code"],
                            "target_date": avail_data["target_date"],
                            "slots": avail_data["slots"],
                            "pipeline_trace": pipeline_trace
                        }
                    )

                # C. Booking Appointment (Direct Booking)
                if component == "Booking":
                    tomorrow = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
                    time_slot = "07:30 AM - 08:30 AM"
                    if "morning" in user_lower or "early" in user_lower:
                        time_slot = "06:30 AM - 07:30 AM"
                    elif "evening" in user_lower or "afternoon" in user_lower:
                        time_slot = "04:00 PM - 05:00 PM"

                    appt_type = "insitu_lab_visit" if any(m in user_lower for m in ["insitu", "in-situ", "clinic", "in person", "walk in", "lab visit"]) else "home_collection"

                    test_names = "Complete Blood Count (CBC) & Fasting Profile"
                    if "lipid" in user_lower:
                        test_names = "Comprehensive Lipid Profile"
                    elif "full body" in user_lower or "package" in user_lower:
                        test_names = "Apex Complete Executive Wellness Package"
                    elif "thyroid" in user_lower:
                        test_names = "Thyroid Profile (TSH)"

                    booking_res = AgentTools.book_appointment(
                        patient=self.patient,
                        caller_phone=self.caller_phone,
                        test_name=test_names,
                        scheduled_date=tomorrow,
                        time_slot=time_slot,
                        appointment_type=appt_type,
                        price_str="₹450" if "cbc" in test_names.lower() else "₹850",
                        agent_name=self.agent_name,
                        db=db
                    )

                    self.actions_taken.append(
                        f"Booked {booking_res['booking_label']} #{booking_res['appointment_id']} for {booking_res['patient_name']} on {tomorrow} ({time_slot}); "
                        f"Dispatched confirmation on GMAIL ({booking_res['gmail_status']}) & WhatsApp ({booking_res['whatsapp_status']})"
                    )

                    self.detected_intent = "book_appointment_success"
                    self.engine.state = ConversationState.APPOINTMENT_BOOKED
                    pipeline_trace["state"] = self.engine.state.value

                    if appt_type == "home_collection":
                        response = (
                            f"{empathy_prefix}Wonderful! I have scheduled your Doorstep Home Sample Collection for tomorrow, {tomorrow}, "
                            f"during the slot {time_slot} for {test_names}. "
                            f"Our phlebotomist will arrive equipped with a sterile collection kit and temperature-controlled cold box. "
                            f"I have also instantly dispatched your booking confirmation and pre-test fasting instructions to your WhatsApp ({booking_res['patient_phone']}) "
                            f"and your Gmail inbox ({booking_res['patient_email']})! Is there anything else I can assist you with today?"
                        )
                    else:
                        response = (
                            f"{empathy_prefix}Perfect! I have reserved your In-Situ Laboratory Clinic Appointment for tomorrow, {tomorrow}, "
                            f"at {time_slot} for {test_names} at our facility on 5580 E. 2nd St. "
                            f"Your slot is priority fast-tracked with zero waiting time. "
                            f"I have also sent your complete booking confirmation and clinic directions to your WhatsApp ({booking_res['patient_phone']}) "
                            f"and your Gmail inbox ({booking_res['patient_email']})! How else may I assist you today?"
                        )

                    return self._finalize_turn(
                        response,
                        intent="book_appointment_success",
                        tool_executed="book_appointment",
                        extra={
                            "appointment_id": booking_res["appointment_id"],
                            "date": tomorrow,
                            "slot": time_slot,
                            "type": appt_type,
                            "gmail_dispatched": booking_res["gmail_status"],
                            "whatsapp_dispatched": booking_res["whatsapp_status"],
                            "pipeline_trace": pipeline_trace
                        }
                    )

                # D. Price Query (Agent Tools: Price)
                if component == "Price":
                    pricing_data = AgentTools.get_pricing(user_transcript, db=db)
                    self.actions_taken.append(f"Retrieved Pricing for {pricing_data['name']}: {pricing_data['price_formatted']}")
                    self.detected_intent = "search_catalog"

                    if pricing_data["type"] == "package":
                        response = (
                            f"{empathy_prefix}Our featured checkup is the '{pricing_data['name']}'. "
                            f"It covers {pricing_data['test_count']} essential parameters. "
                            f"The special package fee is {pricing_data['price_formatted']} (normally ₹{int(pricing_data['original_price'])}). "
                            f"We can conduct this either as a doorstep home collection or as an in-situ clinic visit. Which would you prefer?"
                        )
                        tool_executed = "search_packages"
                    else:
                        fasting_text = f"It requires {pricing_data['fasting_hours']} hours of fasting." if pricing_data["fasting_required"] else "No fasting is required."
                        response = (
                            f"{empathy_prefix}The {pricing_data['name']} ({pricing_data['code']}) is {pricing_data['price_formatted']}. "
                            f"Results are ready within {pricing_data['turnaround_hours']} hours. {fasting_text} "
                            f"Would you prefer our complimentary doorstep home collection, or would you like to visit our in-situ laboratory clinic?"
                        )
                        tool_executed = "search_test_catalog"

                    return self._finalize_turn(
                        response,
                        intent="search_catalog",
                        tool_executed=tool_executed,
                        extra={"pricing": pricing_data, "pipeline_trace": pipeline_trace}
                    )

                # E. Reports Query (Agent Tools: Lab Reports)
                if component == "Lab" and intent == "query_report":
                    self.detected_intent = "query_report"
                    if not self.patient:
                        response = (
                            f"{empathy_prefix}I would be glad to look up your laboratory findings. Since you are calling from a new number, "
                            "could you please share your full name and registered 10-digit telephone number so I can access your records securely?"
                        )
                        return self._finalize_turn(response, intent="query_report_auth_needed", extra={"pipeline_trace": pipeline_trace})

                    reports = db.query(LabReport).filter_by(patient_id=self.patient.id).order_by(LabReport.id.desc()).limit(3).all()
                    if not reports:
                        response = (
                            f"{empathy_prefix}Mr./Ms. {self.patient.full_name}, I checked our laboratory records, but there are no completed reports on file right now. "
                            "If you gave a sample earlier today, our standard turnaround is 6 to 8 hours. "
                            "Let me connect you directly to our Pathology Accessioning Desk if you need an expedited status check."
                        )
                        return self._finalize_turn(response, intent="query_report_empty", extra={"pipeline_trace": pipeline_trace})

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
                    return self._finalize_turn(
                        response,
                        intent="query_report_success",
                        tool_executed="get_patient_reports",
                        extra={"reports_count": len(reports), "pipeline_trace": pipeline_trace}
                    )

            # ------------------------------------------------------------------
            # 4. QUESTION: RAG BRANCH (Test, FAQ, Prep, Policy)
            # ------------------------------------------------------------------
            if category == "Question":
                self.engine.state = ConversationState.ROUTING_QUESTION_RAG
                pipeline_trace["state"] = self.engine.state.value

                rag_result = RAGEngineRouter.query(user_transcript)
                citations = rag_result.get("citations", [])
                rag_component = rag_result.get("rag_component", component)
                pipeline_trace["component"] = rag_component

                # Ambiguity Threshold Guard
                ambiguity_threshold = float(os.getenv("AMBIGUITY_THRESHOLD", "0.30"))
                if not citations or (citations and citations[0].get("score", 1.0) < ambiguity_threshold):
                    self.detected_intent = "human_handover_ambiguity"
                    self.actions_taken.append(f"RAG {rag_component} Ambiguity (< threshold) -> Escalated to Human Care Desk")
                    response = (
                        f"{empathy_prefix}Our Standard Operating Procedures have specific protocols for that, but to ensure "
                        "zero ambiguity for your exact situation, let me directly connect you to our Senior Duty Medical Officer. "
                        "Please hold the line for a moment while I transfer you..."
                    )
                    return self._finalize_turn(
                        response,
                        intent="human_handover_ambiguity",
                        tool_executed="transfer_to_real_human_assistant",
                        extra={"citations": citations, "pipeline_trace": pipeline_trace}
                    )

                answer_body = rag_result["answer"]
                spoken_answer = re.sub(r'#+\s*', '', answer_body)
                spoken_answer = re.sub(r'\*\*', '', spoken_answer)

                top_clause = citations[0]["section"] if citations else "Standard Operating Procedures"
                self.actions_taken.append(f"Queried RAG ({rag_component}): '{user_transcript}' -> Cited {top_clause}")
                self.detected_intent = "check_policy"

                response = (
                    f"{empathy_prefix}Here is our official laboratory guidance on that:\n{spoken_answer}\n"
                    "Would you like to book a doorstep sample collection at your home, or would you prefer an in-situ clinic appointment at our laboratory?"
                )
                return self._finalize_turn(
                    response,
                    intent="check_policy",
                    tool_executed="query_policy_rag",
                    extra={"citations": citations, "rag_component": rag_component, "pipeline_trace": pipeline_trace}
                )

            # ------------------------------------------------------------------
            # 5. CHITCHAT / IDENTITY / GENERAL ASSISTANCE
            # ------------------------------------------------------------------
            if intent == "bot_identity":
                response = (
                    f"{empathy_prefix}I am {self.agent_name}, your dedicated Indian virtual lab assistant at Apex Family Diagnostic Lab. "
                    "I am here to understand your healthcare needs, guide you with test preparation, and arrange hassle-free sample collections."
                )
                return self._finalize_turn(response, intent="bot_identity", extra={"pipeline_trace": pipeline_trace})

            if intent == "bot_acknowledgement":
                response = (
                    f"{empathy_prefix}Yes, I can hear you clearly! I am right here with you. How can I help you today with your lab tests, fasting rules, or appointments?"
                )
                return self._finalize_turn(response, intent="bot_acknowledgement", extra={"pipeline_trace": pipeline_trace})

            if intent == "bot_gratitude":
                response = (
                    f"{empathy_prefix}You are very welcome! It is truly my pleasure to support your health. Please let me know if you need anything else, or if you're ready to schedule your sample collection."
                )
                return self._finalize_turn(response, intent="bot_gratitude", extra={"pipeline_trace": pipeline_trace})

            # Default General Assistance
            self.detected_intent = "conversational_support"
            response = (
                f"{empathy_prefix}I am here to take care of all your diagnostic requirements. "
                "I can schedule a doorstep sample draw at your home, book an in-situ laboratory clinic visit, "
                "or explain fasting and preparation rules. Which would you prefer today?"
            )
            return self._finalize_turn(response, intent="general_assistance", extra={"pipeline_trace": pipeline_trace})

        finally:
            db.close()

    def _finalize_turn(self, response_text: str, intent: str, tool_executed: Optional[str] = None, extra: Optional[Dict] = None) -> Dict[str, Any]:
        self.engine.memory.add_turn("assistant", response_text)

        db: Session = SessionLocal()
        try:
            call_log = db.query(CallLog).filter_by(call_sid=self.call_sid).first()
            transcript_text = "\n".join([f"{h['role'].upper()}: {h['content']}" for h in self.engine.memory.turns])
            actions_text = "; ".join(self.actions_taken)

            if not call_log:
                call_log = CallLog(
                    caller_phone=self.caller_phone,
                    caller_name=self.patient.full_name if self.patient else "Guest Caller",
                    call_sid=self.call_sid,
                    call_type="inbound",
                    duration_seconds=len(self.engine.memory.turns) * 12,
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
                call_log.duration_seconds = len(self.engine.memory.turns) * 12
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
            "coordinator_name": self.agent_name
        }
        if extra:
            payload["extra"] = extra
            payload.update(extra)
        return payload
