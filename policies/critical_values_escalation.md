# Apex MediLab Policy: Critical Alert & Panic Values Escalation
Policy Reference: AML-POL-CRIT-004 | Version: 4.0 | Effective Date: 2026-01-01

## 1. Definition of Critical Values
A critical (or "panic") laboratory result represents a pathophysiological state at such variance with normal ranges as to be life-threatening unless immediate medical intervention is initiated.

## 2. Established Critical & Panic Values Thresholds
- **Cardiac Biomarkers (Critical Panic Values)**:
  - High Sensitivity Cardiac Troponin I (hs-cTnI): **> 0.04 ng/mL** or above institutional 99th percentile URL. Action: Immediate emergency cardiologist alert.
- **Serum Electrolytes**:
  - Potassium ($K^+$): **< 2.8 mmol/L** (severe hypokalemia risk of arrhythmia) or **> 6.0 mmol/L** (hyperkalemia risk of cardiac arrest).
  - Sodium ($Na^+$): **< 120 mmol/L** or **> 160 mmol/L**.
- **Glucose**:
  - Fasting / Random Plasma Glucose: **< 50 mg/dL** (neuroglycopenic hypoglycemia) or **> 400 mg/dL** (diabetic ketoacidosis / HHS risk).
- **Hematology**:
  - Hemoglobin: **< 6.5 g/dL** (severe anemia requiring immediate transfusion workup).
  - Platelet Count: **< 20,000 / µL** (spontaneous hemorrhage hazard) or **> 1,000,000 / µL**.
  - Absolute Neutrophil Count: **< 500 / µL** (severe neutropenic infection susceptibility).

## 3. Escalation Workflow & SLA
1. **Repeat Verification**: Pathologist re-tests sample from secondary tube on primary analyzer within 15 minutes.
2. **Direct Telephonic Notification**:
   - Laboratory duty medical officer must place a direct telephone call to the referring clinician within **30 minutes** of verified result.
   - If referring physician is unavailable after 2 attempts (5 minutes apart), laboratory contacts patient or emergency contact directly, with advice to seek immediate emergency room evaluation.
3. **Read-Back Protocol**: The recipient of the telephone notification must verbally repeat patient name, hospital ID, test name, and exact numerical value.
4. **AI Agent Protocol**: If an AI voice agent detects a caller reporting symptoms consistent with panic values (crushing chest pain, severe dyspnea, acute confusion, cyanosis), the agent must immediately suspend routine booking, provide emergency disclaimer (call 911 / 112 / 102), and escalate call to human clinical supervisor.
