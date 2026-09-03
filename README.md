# 🛡️ FinSpectra — Investigation Planner

An autonomous, evidence-backed Financial Crime Investigation Planner engine and interactive web console built with **FastAPI**, **Pydantic v2**, and **React (Vite)**.

---

## 🎯 What is the Investigation Planner? (Task Explained)

When a bank or fintech detects an alert (e.g. *"₹485,000 international transfer to a new beneficiary"*), traditional systems either trigger a fixed checklist or jump to premature conclusions.

The **FinSpectra Investigation Planner** solves this by receiving an alert and systematically computing:
1. **What happened**: Normalized case understanding separating known attributes from missing data.
2. **What facts are available**: Objective, sourced facts (no subjective interpretations or premature guilt).
3. **What is unusual/suspicious**: Risk indicators & red flags with comparison baselines.
4. **Which category/typology it belongs to**: Configurable taxonomy classification (e.g. *Potential Layering*, *Structuring*, *Account Takeover*).
5. **Why it belongs to that category**: Complete, auditable reasoning chain (`Classification → Red Flags → Facts → Source Fields`).
6. **What information is missing**: Identification of information gaps without assuming guilt.
7. **What questions must be answered**: Actionable, objective investigation questions with expected answer types.
8. **What evidence is required**: Concrete evidence mapping with source category and availability status.
9. **What to investigate first**: Urgency and severity-based prioritization.
10. **The investigation sequence**: Dependency-linked, ordered investigation steps.
11. **Conditional decision branching**: Structured `IF TRUE` / `IF FALSE` rules for downstream execution.
12. **Possible outcomes**: Possibility matrix at planning time (`LEGITIMATE_ACTIVITY`, `SUSPICIOUS_ACTIVITY`, etc.).

---

## 🏗️ 12-Stage Planning Pipeline Architecture

```
ALERT INPUT
     │
     ▼
[Stage 1: CASE NORMALIZATION]           -> Explicit sentinel handling for missing data
     │
     ▼
[Stage 2: FACT EXTRACTION]              -> Objective facts tied to alert field sources
     │
     ▼
[Stage 3: RED-FLAG / ISSUE ID]          -> Anomaly indicators & baselines
     │
     ▼
[Stage 4: ALERT CLASSIFICATION]         -> Configurable taxonomy mapping
     │
     ▼
[Stage 5: CLASSIFICATION RATIONALE]     -> Audit-traceable reasoning chain
     │
     ▼
[Stage 6: INFORMATION GAPS]             -> Separates KNOWN from UNKNOWN
     │
     ▼
[Stage 7: INVESTIGATION QUESTIONS]      -> Actionable, objective questions
     │
     ▼
[Stage 8: REQUIRED EVIDENCE]            -> Sourced evidence requirements
     │
     ▼
[Stage 9: PRIORITIZATION]               -> Severity-weighted priority ordering
     │
     ▼
[Stage 10: INVESTIGATION SEQUENCE]      -> Dependency-linked ordered steps
     │
     ▼
[Stage 11: DECISION / NEXT-STEP LOGIC]  -> Branching conditions for orchestration
     │
     ▼
[Stage 12: DETERMINISTIC VALIDATION]    -> External validator & schema check
     │
     ▼
STRUCTURED INVESTIGATION PLAN JSON
```

---

## ⚙️ Prerequisites & System Requirements

- **Python**: 3.10, 3.11, 3.12, or 3.14
- **Node.js**: 18.x or higher
- **npm**: 9.x or higher
- **Git**

---

## 🚀 Step-by-Step Instructions to Run the Project

### Option A: Local Development (Recommended)

#### 1. Clone the Repository
```bash
git clone https://github.com/Siddarth-cmd/inv.plan.git
cd inv.plan
```

#### 2. Start the Backend API (FastAPI)
Open a terminal in the project root:

```bash
# Navigate to backend directory
cd backend

# Create and activate a Python virtual environment (optional but recommended)
python -m venv venv
# On Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# On Linux / macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the FastAPI server
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
- **Backend API**: `http://localhost:8000`
- **Interactive Swagger Docs**: `http://localhost:8000/api/docs`

---

#### 3. Start the Frontend Web UI (React + Vite)
Open a second terminal in the project root:

```bash
# Navigate to frontend directory
cd frontend

# Install Node dependencies
npm install

# Start the Vite development server
npm run dev
```
- **Interactive Web Console**: `http://localhost:5173`

---

### Option B: Docker Compose (All-in-One)

You can run both backend and frontend via Docker:

```bash
docker-compose up --build
```
- Web Application: `http://localhost:3000` or `http://localhost:8000`

---

## 🧪 Running the Automated Test Suite

The project includes 32 deterministic unit and integration tests covering all 8 scenario types:

```bash
cd backend
python -m pytest tests/test_investigation_planner.py -v
```

### Expected Output:
```text
tests/test_investigation_planner.py::TestAllScenariosGenerateValidPlans::test_all_scenarios_pass_validation PASSED
tests/test_investigation_planner.py::TestNoHallucination::test_facts_reference_known_sources PASSED
tests/test_investigation_planner.py::TestClassification::test_structuring_scenario_classification PASSED
tests/test_investigation_planner.py::TestMaterialDifferences::test_different_scenarios_produce_different_classifications PASSED
...
============================= 32 passed in 0.07s ==============================
```

---

## 📋 Pre-Configured Test Alert Scenarios

The planner includes 8 built-in scenarios ready for one-click testing in the UI or via API:

| # | Scenario Name | Typology Trigger | Key Behavior Tested |
| :- | :--- | :--- | :--- |
| **1** | **High-Value Unusual Transaction** | Potential Layering / Cross-Border | ₹485,000 transfer to new UAE beneficiary |
| **2** | **Potential Structuring Pattern** | Structuring / Smurfing | Repeated deposits just below ₹50,000 threshold |
| **3** | **Potential Mule Account** | Mule Activity / Rapid In-Out | Immediate pass-through on newly opened account |
| **4** | **High-Risk International Transfer** | Cross-Border / Sanctions Risk | $250,000 wire to high-risk jurisdiction |
| **5** | **Account Takeover Alert** | Account Takeover / Device Anomaly | 2:14 AM device change followed by 2:17 AM transfer |
| **6** | **Identity / KYC Anomaly** | Identity/KYC Risk / Synthetic ID | Inconsistent documentation and KYC flags |
| **7** | **Insufficient Information Alert** | Unknown / Requires Review | Bare-minimum payload — no hallucinated facts |
| **8** | **Legitimate-Looking Unusual Transaction** | Legitimate / Profile Matched | High amount matching declared business history |

---

## 📡 API Reference

### 1. Generate Investigation Plan
```http
POST /api/investigation-planner/plan
Content-Type: application/json
```
**Sample Request:**
```json
{
  "alert_id": "ALT-1001",
  "customer_id": "CUST-4421",
  "transaction_id": "TXN-8801",
  "transaction_amount": 485000.0,
  "currency": "INR",
  "transaction_type": "International Wire Transfer",
  "origin_country": "IN",
  "destination_country": "AE",
  "beneficiary_information": { "status": "NEW" },
  "alert_reason": "₹485,000 international transfer to a new beneficiary"
}
```

### 2. Retrieve All Scenarios
```http
GET /api/investigation-planner/scenarios
```

### 3. Get Active Taxonomy Configuration
```http
GET /api/investigation-planner/taxonomy
```

### 4. Validate an Investigation Plan
```http
POST /api/investigation-planner/validate
Content-Type: application/json
```

---

## 📂 Project Structure

```
inv.plan/
├── README.md                               # Project documentation & run guide
├── docker-compose.yml                      # Containerized deployment config
├── backend/
│   ├── requirements.txt                    # Python dependencies
│   ├── tests/
│   │   ├── conftest.py
│   │   └── test_investigation_planner.py   # 32 comprehensive tests
│   └── app/
│       ├── main.py                         # FastAPI application entry point
│       └── investigation_planner/          # Core Investigation Planner Package
│           ├── api.py                      # REST endpoints
│           ├── config/
│           │   └── taxonomy.py             # Configurable typologies & thresholds
│           ├── schemas/                    # Strongly typed Pydantic models
│           │   ├── alert.py
│           │   ├── case.py
│           │   ├── fact.py
│           │   ├── red_flag.py
│           │   ├── classification.py
│           │   ├── information_gap.py
│           │   ├── question.py
│           │   ├── evidence.py
│           │   ├── sequence.py
│           │   ├── decision.py
│           │   └── plan.py
│           ├── pipeline/                   # 12-stage planning engine
│           │   ├── normalize.py
│           │   ├── facts.py
│           │   ├── red_flags.py
│           │   ├── classification.py
│           │   ├── rationale.py
│           │   ├── information_gaps.py
│           │   ├── questions.py
│           │   ├── evidence.py
│           │   ├── prioritization.py
│           │   ├── sequencing.py
│           │   ├── decisions.py
│           │   └── engine.py
│           ├── validation/
│           │   └── plan_validator.py       # Deterministic schema & ID validator
│           └── scenarios/
│               └── sample_alerts.py        # 8 test scenarios
└── frontend/
    ├── package.json                        # Node dependencies
    ├── vite.config.js                      # Vite build configuration
    └── src/
        ├── App.jsx                         # Main dashboard navigation
        ├── InvestigationPlannerView.jsx    # Interactive Planner UI component
        ├── App.css
        └── index.css
```

---

## 📄 License & Auditability

All investigation plans generated by this engine are strictly schema-validated and adhere to financial regulatory compliance standards with end-to-end traceability (`Classification → Red Flags → Facts → Source Fields`).
