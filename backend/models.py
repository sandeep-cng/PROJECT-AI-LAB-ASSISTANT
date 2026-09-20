import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, Text, DateTime, ForeignKey
)
from sqlalchemy.orm import relationship
from backend.database import Base

class Patient(Base):
    __tablename__ = "patients"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    full_name = Column(String(120), nullable=False)
    phone_number = Column(String(30), unique=True, index=True, nullable=False)  # Caller ID lookup key
    email = Column(String(120), nullable=True)
    dob = Column(String(20), nullable=True)
    gender = Column(String(20), nullable=True)
    blood_group = Column(String(10), nullable=True)
    address = Column(Text, nullable=True)
    emergency_contact = Column(String(30), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    appointments = relationship("Appointment", back_populates="patient", cascade="all, delete-orphan")
    orders = relationship("Order", back_populates="patient", cascade="all, delete-orphan")
    prescriptions = relationship("Prescription", back_populates="patient")
    reports = relationship("LabReport", back_populates="patient")

    def to_dict(self):
        return {
            "id": self.id,
            "full_name": self.full_name,
            "phone_number": self.phone_number,
            "email": self.email,
            "dob": self.dob,
            "gender": self.gender,
            "blood_group": self.blood_group,
            "address": self.address,
            "emergency_contact": self.emergency_contact,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class Doctor(Base):
    __tablename__ = "doctors"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(120), nullable=False)
    specialization = Column(String(100), nullable=False)
    clinic_hospital = Column(String(150), nullable=True)
    phone = Column(String(30), nullable=True)
    license_number = Column(String(50), nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "specialization": self.specialization,
            "clinic_hospital": self.clinic_hospital,
            "phone": self.phone,
            "license_number": self.license_number
        }


class TestCatalog(Base):
    __tablename__ = "test_catalog"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    test_code = Column(String(30), unique=True, index=True, nullable=False)
    test_name = Column(String(150), nullable=False, index=True)
    category = Column(String(80), nullable=False, index=True)  # Pathology, Biochemistry, Hematology, etc.
    specimen_type = Column(String(80), nullable=False)        # Serum, EDTA Whole Blood, Urine, Plasma
    fasting_required = Column(Boolean, default=False)
    fasting_hours = Column(Integer, default=0)
    price = Column(Float, nullable=False)
    turnaround_hours = Column(Integer, default=24)
    normal_range_male = Column(String(100), nullable=True)
    normal_range_female = Column(String(100), nullable=True)
    unit = Column(String(30), nullable=True)
    description = Column(Text, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "test_code": self.test_code,
            "test_name": self.test_name,
            "category": self.category,
            "specimen_type": self.specimen_type,
            "fasting_required": self.fasting_required,
            "fasting_hours": self.fasting_hours,
            "price": self.price,
            "turnaround_hours": self.turnaround_hours,
            "normal_range_male": self.normal_range_male,
            "normal_range_female": self.normal_range_female,
            "unit": self.unit,
            "description": self.description
        }


class HealthPackage(Base):
    __tablename__ = "health_packages"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    package_name = Column(String(150), nullable=False)
    description = Column(Text, nullable=True)
    price = Column(Float, nullable=False)
    discounted_price = Column(Float, nullable=False)
    test_codes = Column(Text, nullable=False)  # Comma separated list of test codes
    is_popular = Column(Boolean, default=False)

    def to_dict(self):
        return {
            "id": self.id,
            "package_name": self.package_name,
            "description": self.description,
            "price": self.price,
            "discounted_price": self.discounted_price,
            "test_codes": [code.strip() for code in self.test_codes.split(",") if code.strip()],
            "is_popular": self.is_popular
        }


class Appointment(Base):
    __tablename__ = "appointments"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    appointment_type = Column(String(30), default="home_collection")  # home_collection, lab_visit
    scheduled_date = Column(String(30), nullable=False)               # YYYY-MM-DD
    time_slot = Column(String(40), nullable=False)                    # e.g. "07:00 AM - 08:00 AM"
    pickup_address = Column(Text, nullable=True)
    status = Column(String(30), default="booked")                     # booked, sample_collected, processing, completed, cancelled
    tests_requested = Column(Text, nullable=True)                     # Comma-separated test names or codes
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    patient = relationship("Patient", back_populates="appointments")

    def to_dict(self):
        return {
            "id": self.id,
            "patient_id": self.patient_id,
            "patient_name": self.patient.full_name if self.patient else "Unknown",
            "patient_phone": self.patient.phone_number if self.patient else "",
            "appointment_type": self.appointment_type,
            "scheduled_date": self.scheduled_date,
            "time_slot": self.time_slot,
            "pickup_address": self.pickup_address,
            "status": self.status,
            "tests_requested": self.tests_requested,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class Prescription(Base):
    __tablename__ = "prescriptions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=True)
    image_url = Column(String(255), nullable=True)
    image_data = Column(Text, nullable=True)                          # Base64 encoded if uploaded locally
    doctor_name = Column(String(120), nullable=True)
    extracted_text = Column(Text, nullable=True)
    detected_tests = Column(Text, nullable=True)                      # JSON string of detected test matches
    clinical_notes = Column(Text, nullable=True)
    status = Column(String(30), default="analyzed")                   # analyzed, ordered, flagged
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    patient = relationship("Patient", back_populates="prescriptions")

    def to_dict(self):
        return {
            "id": self.id,
            "patient_id": self.patient_id,
            "doctor_name": self.doctor_name,
            "extracted_text": self.extracted_text,
            "detected_tests": self.detected_tests,
            "clinical_notes": self.clinical_notes,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    appointment_id = Column(Integer, ForeignKey("appointments.id"), nullable=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    total_amount = Column(Float, nullable=False)
    discount = Column(Float, default=0.0)
    net_amount = Column(Float, nullable=False)
    payment_status = Column(String(30), default="pending")  # pending, paid, refunded
    payment_method = Column(String(30), default="online")   # online, cod, insurance
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    patient = relationship("Patient", back_populates="orders")
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    reports = relationship("LabReport", back_populates="order", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "appointment_id": self.appointment_id,
            "patient_id": self.patient_id,
            "patient_name": self.patient.full_name if self.patient else "Unknown",
            "total_amount": self.total_amount,
            "discount": self.discount,
            "net_amount": self.net_amount,
            "payment_status": self.payment_status,
            "payment_method": self.payment_method,
            "items": [item.to_dict() for item in self.items],
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    test_id = Column(Integer, ForeignKey("test_catalog.id"), nullable=False)
    price = Column(Float, nullable=False)

    order = relationship("Order", back_populates="items")
    test = relationship("TestCatalog")

    def to_dict(self):
        return {
            "id": self.id,
            "test_id": self.test_id,
            "test_name": self.test.test_name if self.test else "Unknown",
            "test_code": self.test.test_code if self.test else "",
            "price": self.price
        }


class LabReport(Base):
    __tablename__ = "lab_reports"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    test_id = Column(Integer, ForeignKey("test_catalog.id"), nullable=False)
    result_value = Column(String(50), nullable=False)
    reference_range = Column(String(80), nullable=True)
    flag = Column(String(20), default="normal")  # normal, low, high, critical
    pathologist_name = Column(String(120), default="Dr. Sarah Jenkins, MD Pathologist")
    ai_summary = Column(Text, nullable=True)     # Patient-friendly interpretation
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    patient = relationship("Patient", back_populates="reports")
    order = relationship("Order", back_populates="reports")
    test = relationship("TestCatalog")

    def to_dict(self):
        return {
            "id": self.id,
            "order_id": self.order_id,
            "patient_id": self.patient_id,
            "test_name": self.test.test_name if self.test else "Diagnostic Test",
            "test_code": self.test.test_code if self.test else "",
            "result_value": self.result_value,
            "unit": self.test.unit if self.test else "",
            "reference_range": self.reference_range,
            "flag": self.flag,
            "pathologist_name": self.pathologist_name,
            "ai_summary": self.ai_summary,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class CallLog(Base):
    __tablename__ = "call_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    caller_phone = Column(String(30), index=True, nullable=False)
    caller_name = Column(String(120), nullable=True)
    call_sid = Column(String(100), unique=True, index=True, nullable=True)
    call_type = Column(String(20), default="inbound")  # inbound, outbound, simulator
    duration_seconds = Column(Integer, default=0)
    full_transcript = Column(Text, nullable=True)
    detected_intent = Column(String(80), nullable=True)  # book_test, check_policy, query_report, etc.
    actions_taken = Column(Text, nullable=True)          # JSON or text description of actions executed
    satisfaction_score = Column(Float, default=5.0)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "caller_phone": self.caller_phone,
            "caller_name": self.caller_name,
            "call_sid": self.call_sid,
            "call_type": self.call_type,
            "duration_seconds": self.duration_seconds,
            "full_transcript": self.full_transcript,
            "detected_intent": self.detected_intent,
            "actions_taken": self.actions_taken,
            "satisfaction_score": self.satisfaction_score,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class PolicyDocument(Base):
    __tablename__ = "policy_documents"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    title = Column(String(150), nullable=False)
    category = Column(String(80), nullable=False)
    content = Column(Text, nullable=False)
    version = Column(String(20), default="1.0")
    file_path = Column(String(255), nullable=True)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "category": self.category,
            "content": self.content,
            "version": self.version,
            "file_path": self.file_path,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
