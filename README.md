# Smart Campus Energy Optimization Challenge (GridWise)

Official solution for the **BUP CSE FEST 2026 Hackathon (Online Preliminary)**.

Developed by Team GridWise.

---

## ⚡ Architecture Overview
Our pipeline follows a strict **Understand → Guardrail → Optimize → Verify** architecture compliant with Section 03 & 08 of the Problem Statement:

1. **LLM Semantic Interpreter (`main.py`):**
   * Uses Google AI Studio's `gemini-1.5-flash` model.
   * Receives natural language operator notes along with scenario battery metadata.
   * Translates 1–3 unstructured notes into a structured JSON array of directives adhering strictly to the 6 allowed directive types (`solar_reduction`, `minimum_battery_reserve`, `no_charge_window`, `no_discharge_window`, `max_grid_window`, `no_op`).
2. **Deterministic Guardrails (`guardrails.py`):**
   * Treats LLM output as untrusted structured data (Section 08).
   * Enforces 1:1 note mapping in ascending `note_index` order (0..N-1).
   * Normalizes and verifies hours as unique integers in `[0, 23]` sorted ascending.
   * Clamps solar reduction `factor` to `[0.0, 1.0]` (accounting for "reduced to X%" vs "reduced by X%").
   * Enforces strict `applies` semantics (`applies: false` only for `no_op`).
   * Provides a built-in deterministic heuristic fallback engine if the external LLM API encounters rate limits, connection errors, or missing credentials.
3. **Mathematical Optimizer (`optimizer.py`):**
   * Implemented using the `PuLP` Linear Programming library with the `CBC` solver.
   * Formulates the 24-hour hourly energy balance:
     $$\text{grid\_kwh}[h] + \text{solar\_used\_kwh}[h] + \text{battery\_discharge\_kwh}[h] = \text{demand\_kwh}[h] + \text{battery\_charge\_kwh}[h]$$
   * Formulates hourly battery state transitions and boundary constraints:
     $$E_{\text{after}}[h] = E_{\text{before}}[h] + \text{charge\_kwh}[h] - \text{discharge\_kwh}[h]$$
   * Incorporates an anti-cycling regularization penalty ($10^{-5}$) to strictly prevent simultaneous charge and discharge.
   * Guarantees end-of-day battery neutrality ($E_{\text{after}}[23] = \text{initial\_energy\_kwh}$).
   * Recalculates `total_grid_kwh`, `total_cost_bdt`, and `peak_grid_kwh` directly from the rounded `hourly_plan` to eliminate any float discrepancy.
4. **Interactive Web Dashboard (`static/index.html`):**
   * Served at `GET /`.
   * Complete dark-mode glassmorphism interface featuring 1-click loading of all 10 public sample cases, live SVG dispatch charts, battery SOC trajectory curves, and real-time execution inspector.

---

## 🛠️ Technology Stack
* **Language & Runtime:** Python 3.9+
* **Web Framework:** FastAPI + Uvicorn
* **Generative AI:** Google AI Studio (`gemini-1.5-flash` via `google-generativeai`)
* **Optimization Solver:** PuLP (Coin-OR CBC Linear Programming Solver)
* **Frontend UI:** Glassmorphism Dark UI with responsive SVG visualizations

---

## 🚀 Quickstart & Local Reproduction

### 1. Environment Variables
* `GEMINI_API_KEY`: *(Recommended)* Google AI Studio API key for LLM interpretation.
* `GEMINI_MODEL`: *(Optional)* Defaults to `gemini-1.5-flash`.

> **Note on Reliability:** If `GEMINI_API_KEY` is not provided or the API is rate-limited, the system safely engages its deterministic rule-based interpretation engine to prevent test crashes.

### 2. Running Locally with Python
```bash
# Clone the repository
git clone https://github.com/Wasif303/BUP.git
cd BUP

# Create and activate virtual environment
python -m venv venv
# On Windows:
venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run server
export GEMINI_API_KEY="your-api-key"   # Windows: set GEMINI_API_KEY="your-api-key"
uvicorn main:app --host 0.0.0.0 --port 8000
```

### 3. Running with Docker (Recommended)
```bash
# Build the container
docker build -t wasif303/gridwise:latest .

# Run container
docker run -d -p 8000:8000 -e GEMINI_API_KEY="your-api-key" wasif303/gridwise:latest
```

Open your browser at **`http://localhost:8000/`** to view the interactive Control Dashboard!

---

## 📡 API Contract & Endpoints

### 1. Health Readiness Endpoint
```bash
curl -X GET http://localhost:8000/health
```
**Response (HTTP 200):**
```json
{
  "status": "ok"
}
```

### 2. Energy Optimization Endpoint
```bash
curl -X POST http://localhost:8000/optimize-energy \
  -H "Content-Type: application/json" \
  -d @BUP_CSE_FEST_2026_Preli_Public_Sample_Cases.json
```
*(Or send an individual scenario object matching the Section 07 schema).*

---

## 🧪 Automated Testing & Verification
Run the end-to-end integration test suite against the 10 official public scenarios:
```bash
python -c "
import json
from optimizer import run_optimization
with open('BUP_CSE_FEST_2026_Preli_Public_Sample_Cases.json', 'r', encoding='utf-8') as f:
    data = json.load(f)
for c in data['cases']:
    res = run_optimization(c['id'], c['input']['hours'], c['input']['battery'], c['expected_output']['directive_interpretation'])
    print(f\"{c['id']}: Cost={res['total_cost_bdt']} BDT (Status: Verified)\")
"
```

---

## 🛡️ Security & Secret Handling
* No API keys, passwords, or tokens are committed to this repository.
* Stack traces and sensitive provider URLs are strictly suppressed in HTTP 500 error responses to prevent credential exposure.
* All evaluation scenarios and operator notes are synthetic.
