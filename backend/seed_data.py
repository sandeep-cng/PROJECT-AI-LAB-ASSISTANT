import os
import sys

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import engine, SessionLocal, Base
from backend.models import (
    Patient, Doctor, TestCatalog, HealthPackage, Appointment,
    Order, OrderItem, LabReport, PolicyDocument, CallLog
)

def init_and_seed_db():
    print("Creating all database tables...")
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        # 1. Seed Test Catalog if empty
        if db.query(TestCatalog).count() == 0:
            print("Seeding diagnostic test catalog...")
            tests = [
                TestCatalog(
                    test_code="CBC",
                    test_name="Complete Blood Count (CBC) with Differential",
                    category="Hematology",
                    specimen_type="EDTA Whole Blood",
                    fasting_required=False,
                    fasting_hours=0,
                    price=25.0,
                    turnaround_hours=8,
                    normal_range_male="Hb: 13.5-17.5 g/dL, WBC: 4.5-11.0 10^3/uL, Platelets: 150-450 10^3/uL",
                    normal_range_female="Hb: 12.0-15.5 g/dL, WBC: 4.5-11.0 10^3/uL, Platelets: 150-450 10^3/uL",
                    unit="Mixed",
                    description="Evaluates overall cellular health, screens for anemia, systemic infections, and platelet disorders."
                ),
                TestCatalog(
                    test_code="LIPID",
                    test_name="Comprehensive Lipid Profile",
                    category="Biochemistry",
                    specimen_type="Serum",
                    fasting_required=True,
                    fasting_hours=12,
                    price=45.0,
                    turnaround_hours=12,
                    normal_range_male="Cholesterol <200 mg/dL, Triglycerides <150 mg/dL, HDL >40 mg/dL, LDL <100 mg/dL",
                    normal_range_female="Cholesterol <200 mg/dL, Triglycerides <150 mg/dL, HDL >50 mg/dL, LDL <100 mg/dL",
                    unit="mg/dL",
                    description="Calculates cardiovascular risk metrics: Total Cholesterol, HDL, LDL, VLDL, and Triglycerides."
                ),
                TestCatalog(
                    test_code="FBS",
                    test_name="Fasting Blood Sugar (Glucose)",
                    category="Biochemistry",
                    specimen_type="Fluoride Plasma",
                    fasting_required=True,
                    fasting_hours=10,
                    price=15.0,
                    turnaround_hours=4,
                    normal_range_male="70 - 99 mg/dL",
                    normal_range_female="70 - 99 mg/dL",
                    unit="mg/dL",
                    description="Primary benchmark diagnostic test for pre-diabetes and diabetes mellitus."
                ),
                TestCatalog(
                    test_code="PPBS",
                    test_name="Post-Prandial Blood Sugar (PPBS)",
                    category="Biochemistry",
                    specimen_type="Fluoride Plasma",
                    fasting_required=False,
                    fasting_hours=0,
                    price=15.0,
                    turnaround_hours=4,
                    normal_range_male="< 140 mg/dL (2h post-meal)",
                    normal_range_female="< 140 mg/dL (2h post-meal)",
                    unit="mg/dL",
                    description="Monitors glycemic control precisely 2 hours after commencing a meal."
                ),
                TestCatalog(
                    test_code="HBA1C",
                    test_name="HbA1c (Glycated Hemoglobin)",
                    category="Hematology",
                    specimen_type="EDTA Whole Blood",
                    fasting_required=False,
                    fasting_hours=0,
                    price=35.0,
                    turnaround_hours=12,
                    normal_range_male="< 5.7 % (Normal), 5.7 - 6.4 % (Prediabetes)",
                    normal_range_female="< 5.7 % (Normal), 5.7 - 6.4 % (Prediabetes)",
                    unit="%",
                    description="Measures average blood sugar levels over the preceding 2 to 3 months. No fasting needed."
                ),
                TestCatalog(
                    test_code="TSH",
                    test_name="Thyroid Profile (TSH, Total T3, Total T4)",
                    category="Endocrinology",
                    specimen_type="Serum",
                    fasting_required=False,
                    fasting_hours=0,
                    price=40.0,
                    turnaround_hours=12,
                    normal_range_male="TSH: 0.45 - 4.50 uIU/mL",
                    normal_range_female="TSH: 0.45 - 4.50 uIU/mL",
                    unit="uIU/mL",
                    description="Assesses functional performance of thyroid gland, screening for hypo- and hyperthyroidism."
                ),
                TestCatalog(
                    test_code="LFT",
                    test_name="Liver Function Test (LFT Panel)",
                    category="Biochemistry",
                    specimen_type="Serum",
                    fasting_required=True,
                    fasting_hours=8,
                    price=50.0,
                    turnaround_hours=12,
                    normal_range_male="Bilirubin Total: 0.2-1.2 mg/dL, ALT/SGPT: 7-56 U/L, AST/SGOT: 10-40 U/L",
                    normal_range_female="Bilirubin Total: 0.2-1.2 mg/dL, ALT/SGPT: 7-45 U/L, AST/SGOT: 9-32 U/L",
                    unit="U/L",
                    description="Analyzes Bilirubin, SGOT, SGPT, Alkaline Phosphatase, Total Protein, and Albumin."
                ),
                TestCatalog(
                    test_code="KFT",
                    test_name="Kidney Function Test (KFT / RFT Panel)",
                    category="Biochemistry",
                    specimen_type="Serum",
                    fasting_required=True,
                    fasting_hours=8,
                    price=45.0,
                    turnaround_hours=12,
                    normal_range_male="Creatinine: 0.7 - 1.3 mg/dL, Blood Urea Nitrogen: 7 - 20 mg/dL, Uric Acid: 3.5 - 7.2 mg/dL",
                    normal_range_female="Creatinine: 0.5 - 1.1 mg/dL, Blood Urea Nitrogen: 7 - 20 mg/dL, Uric Acid: 2.6 - 6.0 mg/dL",
                    unit="mg/dL",
                    description="Evaluates glomerular filtration health, serum creatinine, BUN, and uric acid concentrations."
                ),
                TestCatalog(
                    test_code="VITD",
                    test_name="Vitamin D (25-Hydroxy)",
                    category="Biochemistry",
                    specimen_type="Serum",
                    fasting_required=False,
                    fasting_hours=0,
                    price=55.0,
                    turnaround_hours=24,
                    normal_range_male="30.0 - 100.0 ng/mL",
                    normal_range_female="30.0 - 100.0 ng/mL",
                    unit="ng/mL",
                    description="Essential marker for bone mineral density, osteopenia, muscle strength, and immune defense."
                ),
                TestCatalog(
                    test_code="VITB12",
                    test_name="Vitamin B12 (Cyanocobalamin)",
                    category="Biochemistry",
                    specimen_type="Serum",
                    fasting_required=False,
                    fasting_hours=0,
                    price=50.0,
                    turnaround_hours=24,
                    normal_range_male="200 - 900 pg/mL",
                    normal_range_female="200 - 900 pg/mL",
                    unit="pg/mL",
                    description="Crucial for neurological preservation, spinal cord function, and red blood cell proliferation."
                ),
                TestCatalog(
                    test_code="TROP-I",
                    test_name="High-Sensitivity Cardiac Troponin I (hs-cTnI)",
                    category="Cardiac Pathology",
                    specimen_type="Serum",
                    fasting_required=False,
                    fasting_hours=0,
                    price=65.0,
                    turnaround_hours=2,
                    normal_range_male="< 0.04 ng/mL (Critical > 0.04 ng/mL)",
                    normal_range_female="< 0.04 ng/mL (Critical > 0.04 ng/mL)",
                    unit="ng/mL",
                    description="STAT emergency marker for acute myocardial infarction, ischemia, and cardiac necrosis."
                ),
                TestCatalog(
                    test_code="URINE-R",
                    test_name="Urine Routine & Microscopic Examination",
                    category="Clinical Pathology",
                    specimen_type="Clean Catch Midstream Urine",
                    fasting_required=False,
                    fasting_hours=0,
                    price=18.0,
                    turnaround_hours=6,
                    normal_range_male="Protein: Nil, Sugar: Nil, Pus Cells: 0-5 /hpf, RBCs: Nil",
                    normal_range_female="Protein: Nil, Sugar: Nil, Pus Cells: 0-5 /hpf, RBCs: Nil",
                    unit="Microscopic",
                    description="Screening test for urinary tract infections (UTI), proteinuria, renal stones, and hematuria."
                ),
                TestCatalog(
                    test_code="CRP",
                    test_name="High-Sensitivity C-Reactive Protein (hs-CRP)",
                    category="Immunology",
                    specimen_type="Serum",
                    fasting_required=False,
                    fasting_hours=0,
                    price=30.0,
                    turnaround_hours=8,
                    normal_range_male="< 1.0 mg/L (Low cardiac risk), 1.0-3.0 (Average), >3.0 (High)",
                    normal_range_female="< 1.0 mg/L (Low cardiac risk), 1.0-3.0 (Average), >3.0 (High)",
                    unit="mg/L",
                    description="Acute-phase systemic inflammatory reactant and chronic vascular inflammation indicator."
                )
            ]
            db.add_all(tests)
            db.commit()

        # 2. Seed Health Packages
        if db.query(HealthPackage).count() == 0:
            print("Seeding wellness health packages...")
            packages = [
                HealthPackage(
                    package_name="Apex Complete Executive Wellness Package",
                    description="Our ultimate head-to-toe preventive screening covering all vital organs: Heart, Liver, Kidneys, Blood, Thyroid, and Vitamins.",
                    price=245.0,
                    discounted_price=149.0,
                    test_codes="CBC, LIPID, FBS, HBA1C, TSH, LFT, KFT, VITD, VITB12, URINE-R",
                    is_popular=True
                ),
                HealthPackage(
                    package_name="Diabetic Health & Cardiac Guard Panel",
                    description="Comprehensive tracking for diabetic patients: 3-month glycemic history, lipid atherogenic risk, and renal micro-filtration.",
                    price=110.0,
                    discounted_price=79.0,
                    test_codes="FBS, PPBS, HBA1C, LIPID, KFT, URINE-R",
                    is_popular=True
                ),
                HealthPackage(
                    package_name="Senior Citizen Vital Organ Care (60+)",
                    description="Tailored for elderly health: joint & bone health, cognitive & nerve markers, liver-kidney clearance, and cardiac screening.",
                    price=190.0,
                    discounted_price=119.0,
                    test_codes="CBC, KFT, LFT, LIPID, TSH, VITD, VITB12, CRP",
                    is_popular=False
                )
            ]
            db.add_all(packages)
            db.commit()

        # 3. Seed Sample Patients with known phone numbers
        if db.query(Patient).count() == 0:
            print("Seeding sample patients for instant caller ID lookup...")
            p1 = Patient(
                full_name="Robert Vance",
                phone_number="+1 (555) 234-5678",
                email="robert.vance@example.com",
                dob="1972-04-14",
                gender="Male",
                blood_group="O+",
                address="742 Evergreen Terrace, Springfield",
                emergency_contact="+1 (555) 345-6789"
            )
            p2 = Patient(
                full_name="Ananya Sharma",
                phone_number="+91 98765 43210",
                email="ananya.sharma@example.com",
                dob="1994-08-22",
                gender="Female",
                blood_group="B+",
                address="Flat 402, Lotus Heights, Powai, Mumbai",
                emergency_contact="+91 98765 00000"
            )
            p3 = Patient(
                full_name="David Miller",
                phone_number="+1 (555) 987-6543",
                email="david.miller@example.com",
                dob="1981-11-03",
                gender="Male",
                blood_group="A+",
                address="1200 Beacon St, Brookline, MA",
                emergency_contact="+1 (555) 999-1122"
            )
            db.add_all([p1, p2, p3])
            db.commit()

            # Seed Past Appointment & Lab Report for Robert Vance
            cbc_test = db.query(TestCatalog).filter_by(test_code="CBC").first()
            lipid_test = db.query(TestCatalog).filter_by(test_code="LIPID").first()
            fbs_test = db.query(TestCatalog).filter_by(test_code="FBS").first()

            appt1 = Appointment(
                patient_id=p1.id,
                appointment_type="home_collection",
                scheduled_date="2026-09-18",
                time_slot="07:00 AM - 08:00 AM",
                pickup_address=p1.address,
                status="completed",
                tests_requested="CBC, LIPID, FBS",
                notes="Patient requested morning slot before office."
            )
            db.add(appt1)
            db.commit()

            order1 = Order(
                appointment_id=appt1.id,
                patient_id=p1.id,
                total_amount=85.0,
                discount=10.0,
                net_amount=75.0,
                payment_status="paid",
                payment_method="online"
            )
            db.add(order1)
            db.commit()

            rep1 = LabReport(
                order_id=order1.id,
                patient_id=p1.id,
                test_id=lipid_test.id,
                result_value="Total Chol: 215 mg/dL, LDL: 138 mg/dL, HDL: 42 mg/dL",
                reference_range="Total Chol <200, LDL <100, HDL >40",
                flag="high",
                pathologist_name="Dr. Sarah Jenkins, MD Pathologist",
                ai_summary="Slightly elevated LDL (bad cholesterol) and Total Cholesterol. HDL is in acceptable range. Low saturated fat diet and regular aerobic activity advised. Follow up with your doctor."
            )
            rep2 = LabReport(
                order_id=order1.id,
                patient_id=p1.id,
                test_id=fbs_test.id,
                result_value="94 mg/dL",
                reference_range="70 - 99 mg/dL",
                flag="normal",
                pathologist_name="Dr. Sarah Jenkins, MD Pathologist",
                ai_summary="Fasting blood sugar is completely normal within optimal parameters."
            )
            db.add_all([rep1, rep2])
            db.commit()

            # Seed a past call log
            cl = CallLog(
                caller_phone=p1.phone_number,
                caller_name=p1.full_name,
                call_sid="SIM-CALL-001",
                call_type="simulator",
                duration_seconds=92,
                full_transcript="AI: Hello Mr. Vance, welcome to Apex MediLab. Caller: Hi, can I check my lipid report? AI: Your Lipid profile is ready. Total cholesterol was 215 mg/dL. Would you like me to SMS the PDF link? Caller: Yes please.",
                detected_intent="query_report",
                actions_taken="Read out Lipid profile summary, dispatched secure SMS link.",
                satisfaction_score=5.0
            )
            db.add(cl)
            db.commit()

        # 4. Seed Doctors
        if db.query(Doctor).count() == 0:
            print("Seeding referring doctors...")
            d1 = Doctor(
                name="Dr. Rajesh K. Mehta",
                specialization="Consultant Cardiologist & Internal Medicine",
                clinic_hospital="Apex Heart & Specialty Clinic",
                phone="+1 (555) 444-1234",
                license_number="MED-NY-84920"
            )
            d2 = Doctor(
                name="Dr. Emily Chen",
                specialization="Endocrinologist & Diabetologist",
                clinic_hospital="Metropolitan Diabetes Institute",
                phone="+1 (555) 444-5678",
                license_number="MED-MA-61029"
            )
            db.add_all([d1, d2])
            db.commit()

        print("Database initialized and pre-seeded successfully!")

    except Exception as e:
        print(f"Error seeding database: {e}")
        db.rollback()
        raise e
    finally:
        db.close()

if __name__ == "__main__":
    init_and_seed_db()
