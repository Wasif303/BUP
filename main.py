"""
main.py - GridWise Smart Campus Energy Optimization Service
Fully compliant with BUP CSE FEST 2026 Problem Statement & Evaluation Rubric.
"""

import os
import json
import logging
import re
from pathlib import Path
from typing import List, Dict, Any, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import google.generativeai as genai

from guardrails import sanitize_and_validate_directives
from optimizer import run_optimization

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("GridWiseService")

app = FastAPI(
    title="GridWise Smart Campus Energy Optimizer",
    description="LLM-Assisted Operator Directive Interpretation & 24h Energy Optimization API",
    version="2.0"
)

# Enable CORS for cross-origin judging harnesses and web browsers
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- SCHEMA DEFINITIONS (Problem Statement Section 07) ---
class HourData(BaseModel):
    hour: int = Field(..., ge=0, le=23, description="Hour of the day (0-23)")
    demand_kwh: float = Field(..., ge=0, description="Campus demand in kWh")
    solar_kwh: float = Field(..., ge=0, description="Forecasted solar generation in kWh")
    tariff_bdt_per_kwh: float = Field(..., ge=0, description="Grid tariff in BDT/kWh")

class BatteryData(BaseModel):
    capacity_kwh: float = Field(..., gt=0, description="Total battery capacity in kWh")
    initial_energy_kwh: float = Field(..., ge=0, description="Battery energy at start of hour 0")
    minimum_energy_kwh: float = Field(..., ge=0, description="Base minimum reserve in kWh")
    max_charge_kwh_per_hour: float = Field(..., gt=0, description="Maximum charge rate in kWh/h")
    max_discharge_kwh_per_hour: float = Field(..., gt=0, description="Maximum discharge rate in kWh/h")

class RequestPayload(BaseModel):
    scenario_id: str = Field(..., description="Unique scenario identifier")
    operator_notes: List[str] = Field(..., min_length=1, max_length=3, description="1 to 3 operator notes")
    hours: List[HourData] = Field(..., description="Hourly energy parameters for 24 hours")
    battery: BatteryData = Field(..., description="Battery configuration parameters")

# --- GEMINI CLIENT CONFIGURATION ---
api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("API_KEY") or os.environ.get("GOOGLE_API_KEY", "")
model_name = os.environ.get("GEMINI_MODEL", "gemini-1.5-flash")

llm_model = None
if api_key:
    try:
        genai.configure(api_key=api_key)
        llm_model = genai.GenerativeModel(model_name)
        logger.info(f"Initialized GenerativeModel with {model_name}")
    except Exception as e:
        logger.warning(f"Could not initialize GenerativeModel: {e}")
else:
    logger.info("No external GEMINI_API_KEY detected. Active fallback: Deterministic Guardrail Engine.")

# --- SYSTEM PROMPT (Section 04 & Section 08) ---
SYSTEM_PROMPT = """
You are an expert energy grid operator AI. Your task is to convert natural language operator notes into a strict JSON list of directives for a 24-hour campus energy scheduling optimizer (hours 0 to 23).

Output MUST be a JSON array of objects, with EXACTLY one entry per operator note in note_index order (0, 1, ...).

### SUPPORTED DIRECTIVE TYPES:
1. "solar_reduction":
   Use when usable rooftop solar/PV generation drops (cleaning, cloud cover, inverter maintenance).
   - "hours": unique integers (0-23) in ascending order.
   - "factor": float between 0.0 and 1.0 representing the USABLE FRACTION REMAINING.
     * "reduced to 25%" or "leaves 25%" or "treated as 25%" -> factor = 0.25
     * "80% reduction" or "drop by 80%" -> factor = 0.2 (1.0 - 0.8)
     * "half" -> factor = 0.5; "one-fifth" -> factor = 0.2

2. "minimum_battery_reserve":
   Use when operator requires a minimum energy reserve in the battery.
   - "hours": unique integers (0-23) in ascending order.
   - "minimum_energy_kwh": float. If note specifies percentage of battery capacity (e.g. 50%), multiply (percent/100) * battery_capacity_kwh.

3. "no_charge_window":
   Use when battery charging is disabled, isolated, or prohibited.
   - "hours": unique integers (0-23) in ascending order.
   - structured_adjustment: {"hours": [...]}

4. "no_discharge_window":
   Use when battery discharging is disabled, prohibited, or during relay testing.
   - "hours": unique integers (0-23) in ascending order.
   - structured_adjustment: {"hours": [...]}

5. "max_grid_window":
   Use when grid intake, feeder, or transformer limit is capped.
   - "hours": unique integers (0-23) in ascending order.
   - "max_grid_kwh": float (maximum allowed grid import per hour).

6. "no_op":
   Use for distractors or notes unrelated to the 24-hour energy schedule (cafeteria, sports, library, bookings, meetings).
   - "applies": false
   - "directive_type": "no_op"
   - "structured_adjustment": null

### TIME WINDOW CONVENTIONS:
- Windows are START-INCLUSIVE and END-EXCLUSIVE.
- "1 PM to 3 PM" -> [13, 14]
- "noon to 2 PM" -> [12, 13]
- "from 6 PM until 9 PM" -> [18, 19, 20]
- "from 6 PM until 10 PM" -> [18, 19, 20, 21]
- "from 2 AM until 5 AM" -> [2, 3, 4]
"""

def extract_json_array(text: str) -> List[Dict[str, Any]]:
    """Cleans markdown blocks and parses JSON array safely."""
    cleaned = text.strip()
    match = re.search(r'\[.*\]', cleaned, re.DOTALL)
    if match:
        return json.loads(match.group(0))
    return json.loads(cleaned)

# --- ENDPOINTS ---

@app.get("/health")
def health_check():
    """Readiness endpoint for judging harness (Section 06.2)."""
    return {"status": "ok"}

@app.get("/", response_class=HTMLResponse)
def serve_dashboard():
    """Serves the interactive UI Dashboard at root URL."""
    candidates = [
        Path(__file__).parent / "static" / "index.html",
        Path("static/index.html")
    ]
    for p in candidates:
        if p.exists():
            return HTMLResponse(content=p.read_text(encoding="utf-8"))
    return HTMLResponse(content="<h1>GridWise API Running. Visit /health or POST /optimize-energy</h1>")

@app.post("/optimize-energy")
def optimize_energy(payload: RequestPayload):
    """
    Main energy scheduling endpoint (Section 06, 07, 10).
    Pipeline: LLM Interpretation -> Deterministic Guardrails -> PuLP CBC Optimizer.
    """
    # 1. Structural Validation
    if len(payload.hours) != 24:
        raise HTTPException(status_code=400, detail="The hours array must contain exactly 24 hourly entries (0..23).")
    
    # Check that hours array covers hours 0 to 23
    hour_indices = [h.hour for h in payload.hours]
    if sorted(hour_indices) != list(range(24)):
        raise HTTPException(status_code=400, detail="The hours array must contain unique hours from 0 through 23.")

    raw_llm_output = None

    # 2. LLM Interpretation (Gemini API)
    if llm_model:
        prompt = (
            f"Scenario ID: {payload.scenario_id}\n"
            f"Battery Metadata: capacity_kwh={payload.battery.capacity_kwh}, "
            f"initial_energy_kwh={payload.battery.initial_energy_kwh}, "
            f"minimum_energy_kwh={payload.battery.minimum_energy_kwh}\n\n"
            f"Operator Notes to interpret:\n"
        )
        for i, note in enumerate(payload.operator_notes):
            prompt += f"Note {i}: {note}\n"

        for attempt in range(2):
            try:
                response = llm_model.generate_content(
                    SYSTEM_PROMPT + "\n\n" + prompt,
                    generation_config=genai.GenerationConfig(
                        response_mime_type="application/json",
                        temperature=0.0
                    )
                )
                raw_llm_output = extract_json_array(response.text)
                break
            except Exception as e:
                logger.warning(f"LLM interpretation attempt {attempt+1} encountered: {type(e).__name__}")

    # 3. Deterministic Guardrails (Section 08)
    validated_directives = sanitize_and_validate_directives(
        raw_directives=raw_llm_output,
        operator_notes=payload.operator_notes,
        battery_capacity=payload.battery.capacity_kwh
    )

    # 4. Mathematical Optimization (PuLP CBC Solver)
    try:
        hours_dict = [h.dict() for h in payload.hours]
        battery_dict = payload.battery.dict()
        
        result = run_optimization(
            scenario_id=payload.scenario_id,
            hours=hours_dict,
            battery=battery_dict,
            directives=validated_directives
        )
        return result

    except Exception as e:
        logger.error(f"Internal optimization solver failure: {type(e).__name__}")
        # Safe Failure per Section 06.1 & 08: Never leak API keys, prompts, or stack traces
        raise HTTPException(status_code=500, detail="Controlled internal energy optimization failure.")
