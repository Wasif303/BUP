from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

app = FastAPI()

# --- SCHEMA DEFINITIONS (From the PDF) ---
class HourData(BaseModel):
    hour: int
    demand_kwh: float
    solar_kwh: float
    tariff_bdt_per_kwh: float

class BatteryData(BaseModel):
    capacity_kwh: float
    initial_energy_kwh: float
    minimum_energy_kwh: float
    max_charge_kwh_per_hour: float
    max_discharge_kwh_per_hour: float

class RequestPayload(BaseModel):
    scenario_id: str
    operator_notes: List[str]
    hours: List[HourData]
    battery: BatteryData

# --- ENDPOINTS ---

@app.get("/health")
def health_check():
    # The judges' bot will hit this to make sure you are online
    return {"status": "ok"}

import google.generativeai as genai
from optimizer import run_optimization
import json
import os

# Initialize Gemini API securely from Environment Variables
api_key = os.environ.get("GEMINI_API_KEY", "")
genai.configure(api_key=api_key)
model = genai.GenerativeModel('gemini-3.1-pro-preview')

@app.post("/optimize-energy")
def optimize_energy(payload: RequestPayload):
    try:
        # STEP 1: Parse Operator Notes with LLM
        system_prompt = """
        You are an energy grid operator AI. You must convert natural language notes into a strict JSON array of directives.
        There must be exactly one entry per note, in the same order.
        Supported directive_type: solar_reduction, minimum_battery_reserve, no_charge_window, no_discharge_window, max_grid_window, no_op.
        If a note is irrelevant, applies=false, directive_type="no_op", structured_adjustment=null.
        Otherwise applies=true, and structured_adjustment contains "hours" (array of ints 0-23) and the required value field ("factor", "minimum_energy_kwh", "max_grid_kwh", etc).
        For windows, start hour is inclusive, end is exclusive (e.g. 1 PM to 3 PM is hours: [13, 14]).
        Respond ONLY with a valid JSON array.
        """
        
        prompt = f"Operator notes:\n"
        for i, note in enumerate(payload.operator_notes):
            prompt += f"Note {i}: {note}\n"
            
        # Call the LLM
        response = model.generate_content(
            system_prompt + "\n\n" + prompt,
            generation_config=genai.GenerationConfig(response_mime_type="application/json")
        )
        
        # Parse the JSON array
        llm_output = json.loads(response.text)
        
        # Format it exactly as the PDF requires
        directives = []
        for i, parsed in enumerate(llm_output):
            directives.append({
                "note_index": i,
                "applies": parsed.get("applies", False),
                "directive_type": parsed.get("directive_type", "no_op"),
                "structured_adjustment": parsed.get("structured_adjustment", None),
                "explanation": "Interpreted by LLM"
            })
            
        # STEP 2: Pass LLM rules to the Math Optimizer
        # Convert Pydantic objects to dicts
        hours_dict = [h.dict() for h in payload.hours]
        battery_dict = payload.battery.dict()
        
        result = run_optimization(
            scenario_id=payload.scenario_id,
            hours=hours_dict,
            battery=battery_dict,
            directives=directives
        )

        # STEP 3: Return the final optimized schedule!
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

