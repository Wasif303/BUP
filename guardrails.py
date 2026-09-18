"""
guardrails.py - Deterministic Validation and Interpretation Guardrails
Strictly adheres to Section 08 and Section 04 of the BUP CSE Fest 2026 Problem Statement.
"""

import re
import json
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger("GridWiseGuardrails")

ALLOWED_DIRECTIVES = {
    "solar_reduction",
    "minimum_battery_reserve",
    "no_charge_window",
    "no_discharge_window",
    "max_grid_window",
    "no_op"
}

def parse_time_window_heuristics(text: str) -> List[int]:
    """
    Deterministic time extractor supporting 12h/24h, words, and intervals.
    Follows start-inclusive and end-exclusive convention (e.g. 1 PM to 3 PM -> [13, 14]).
    """
    clean_text = re.sub(r'[^\w\s:\-]', ' ', text.lower())
    clean_text = clean_text.replace("noon", "12 pm").replace("midnight", "12 am")
    clean_text = clean_text.replace("one", "1").replace("two", "2").replace("three", "3")
    clean_text = clean_text.replace("four", "4").replace("five", "5").replace("six", "6")
    clean_text = clean_text.replace("seven", "7").replace("eight", "8").replace("nine", "9")
    clean_text = clean_text.replace("ten", "10").replace("eleven", "11").replace("twelve", "12")
    
    # 24-hour formats: 13:00 to 15:00 or 13:00 - 15:00
    m24 = re.search(r'(\d{1,2}):00\s*(?:to|until|and|-)\s*(\d{1,2}):00', clean_text)
    if m24:
        start, end = int(m24.group(1)), int(m24.group(2))
        return list(range(max(0, start), min(24, end)))
        
    # 12-hour formats: 11 am until 1 pm, 2 pm and 4 pm, 6 pm until 9 pm, 1-3 pm
    m_range = re.search(r'(\d{1,2})\s*(am|pm)?\s*(?:to|until|and|-)\s*(\d{1,2})\s*(am|pm)', clean_text)
    if m_range:
        h1 = int(m_range.group(1))
        merid1 = m_range.group(2)
        h2 = int(m_range.group(3))
        merid2 = m_range.group(4)
        if not merid1:
            merid1 = merid2
            
        def to_24(h, m):
            if m == 'pm' and h != 12: return h + 12
            if m == 'am' and h == 12: return 0
            return h
            
        start = to_24(h1, merid1)
        end = to_24(h2, merid2)
        if 0 <= start <= end <= 24:
            return list(range(start, end))
            
    return []

def fallback_interpret_note(note: str, note_index: int, battery_capacity: float) -> Dict[str, Any]:
    """
    Robust heuristic interpreter used as backup if the external LLM is offline or rate-limited.
    """
    lower = note.lower()
    energy_keywords = ["solar", "pv", "panel", "battery", "charge", "discharge", "grid", "feeder", "transformer", "substation", "kwh", "reserve"]
    
    if not any(k in lower for k in energy_keywords):
        return {
            "note_index": note_index,
            "applies": False,
            "directive_type": "no_op",
            "structured_adjustment": None,
            "explanation": "This note does not affect today's 24-hour energy schedule."
        }
        
    hours = parse_time_window_heuristics(note)
    if not hours:
        return {
            "note_index": note_index,
            "applies": False,
            "directive_type": "no_op",
            "structured_adjustment": None,
            "explanation": "No operational time window identified; defaulted safely to no_op."
        }

    # 1. Solar reduction
    if any(w in lower for w in ["solar", "pv", "panel"]) and any(w in lower for w in ["reduc", "drop", "wash", "cloud", "roughly", "usable", "leave"]):
        factor = 0.5
        m_pct_drop = re.search(r'(\d{1,2})%\s*(?:reduction|drop)', lower)
        m_pct_to = re.search(r'(?:drop to|treated as|leaves?|to about|to roughly|roughly)\s*(\d{1,2})%', lower)
        if m_pct_drop:
            factor = round(1.0 - float(m_pct_drop.group(1)) / 100.0, 4)
        elif m_pct_to:
            factor = round(float(m_pct_to.group(1)) / 100.0, 4)
        elif "one-fifth" in lower:
            factor = 0.2
        elif "half" in lower:
            factor = 0.5
        elif "quarter" in lower or "one-fourth" in lower:
            factor = 0.25
        elif "three-quarters" in lower:
            factor = 0.75
            
        return {
            "note_index": note_index,
            "applies": True,
            "directive_type": "solar_reduction",
            "structured_adjustment": {"hours": hours, "factor": factor},
            "explanation": f"Solar output adjusted to {factor*100:.0f}% of forecast during maintenance."
        }

    # 2. No charge window
    if any(w in lower for w in ["charge", "charger", "charging"]) and any(w in lower for w in ["not charge", "do not charge", "isolated", "unavailable", "disabled", "prevent", "outage"]):
        return {
            "note_index": note_index,
            "applies": True,
            "directive_type": "no_charge_window",
            "structured_adjustment": {"hours": hours},
            "explanation": "Battery charging is unavailable during the specified maintenance window."
        }

    # 3. No discharge window
    if any(w in lower for w in ["discharge", "discharging"]) and any(w in lower for w in ["not discharge", "do not discharge", "disabled", "unavailable", "prevent", "testing"]):
        return {
            "note_index": note_index,
            "applies": True,
            "directive_type": "no_discharge_window",
            "structured_adjustment": {"hours": hours},
            "explanation": "Battery discharging is disabled during testing window."
        }

    # 4. Minimum battery reserve
    if "reserve" in lower or "remain in the battery" in lower or "stored in the battery" in lower:
        m_pct = re.search(r'(\d{1,2})%\s*(?:of (?:the )?battery capacity)?', lower)
        m_kwh = re.search(r'(\d+(?:\.\d+)?)\s*kwh', lower)
        reserve_kwh = 0.0
        if "capacity" in lower and m_pct:
            pct = float(m_pct.group(1))
            reserve_kwh = round((pct / 100.0) * battery_capacity, 2)
        elif m_kwh:
            reserve_kwh = float(m_kwh.group(1))
            
        return {
            "note_index": note_index,
            "applies": True,
            "directive_type": "minimum_battery_reserve",
            "structured_adjustment": {"hours": hours, "minimum_energy_kwh": reserve_kwh},
            "explanation": f"Emergency reserve of {reserve_kwh} kWh maintained."
        }

    # 5. Max grid window
    if any(w in lower for w in ["grid", "feeder", "transformer", "substation", "intake"]):
        m_kwh = re.search(r'(\d+(?:\.\d+)?)\s*kwh', lower)
        grid_kwh = float(m_kwh.group(1)) if m_kwh else 0.0
        return {
            "note_index": note_index,
            "applies": True,
            "directive_type": "max_grid_window",
            "structured_adjustment": {"hours": hours, "max_grid_kwh": grid_kwh},
            "explanation": f"Grid import limited to {grid_kwh} kWh during constraint window."
        }

    return {
        "note_index": note_index,
        "applies": False,
        "directive_type": "no_op",
        "structured_adjustment": None,
        "explanation": "This note does not affect today's 24-hour energy schedule."
    }

def sanitize_and_validate_directives(
    raw_directives: Optional[List[Dict[str, Any]]],
    operator_notes: List[str],
    battery_capacity: float
) -> List[Dict[str, Any]]:
    """
    Strict Section 08 Guardrail Validator.
    Takes untrusted structured data from LLM (or None if LLM failed) and guarantees:
    - Exactly 1 directive per note in note_index order (0..N-1)
    - Applies semantics: applies == False for no_op and True for all others
    - Valid enums and exact structured_adjustment shapes
    - Unique ascending hours 0..23
    - Bounded numerical ranges (factor in [0, 1], non-negative reserves/caps)
    """
    cleaned = []
    parsed_by_index = {}

    if isinstance(raw_directives, list):
        for idx, item in enumerate(raw_directives):
            if isinstance(item, dict):
                n_idx = item.get("note_index", idx)
                parsed_by_index[n_idx] = item

    for i, note in enumerate(operator_notes):
        raw_item = parsed_by_index.get(i)
        
        # If missing or malformed from LLM, use safe heuristic fallback
        if not raw_item or not isinstance(raw_item, dict):
            fallback = fallback_interpret_note(note, i, battery_capacity)
            cleaned.append(fallback)
            continue

        d_type = str(raw_item.get("directive_type", "no_op")).strip().lower()
        if d_type not in ALLOWED_DIRECTIVES:
            d_type = "no_op"

        explanation = str(raw_item.get("explanation", "")).strip()
        if not explanation:
            explanation = "Directive validated by guardrails."

        if d_type == "no_op":
            cleaned.append({
                "note_index": i,
                "applies": False,
                "directive_type": "no_op",
                "structured_adjustment": None,
                "explanation": explanation
            })
            continue

        # Non-no_op directives require valid structured_adjustment
        raw_adj = raw_item.get("structured_adjustment")
        if not isinstance(raw_adj, dict):
            fallback = fallback_interpret_note(note, i, battery_capacity)
            cleaned.append(fallback)
            continue

        raw_hours = raw_adj.get("hours", [])
        if not isinstance(raw_hours, list):
            raw_hours = []
        valid_hours = sorted(list(set(int(h) for h in raw_hours if isinstance(h, (int, float)) and 0 <= int(h) <= 23)))

        if not valid_hours:
            valid_hours = parse_time_window_heuristics(note)

        if not valid_hours:
            cleaned.append({
                "note_index": i,
                "applies": False,
                "directive_type": "no_op",
                "structured_adjustment": None,
                "explanation": "No valid hours found; mapped safely to no_op."
            })
            continue

        adj: Dict[str, Any] = {"hours": valid_hours}

        if d_type == "solar_reduction":
            factor = raw_adj.get("factor", 1.0)
            try:
                factor = float(factor)
                if factor > 1.0:
                    factor = factor / 100.0
                factor = max(0.0, min(1.0, factor))
            except (ValueError, TypeError):
                factor = 1.0
            adj["factor"] = round(factor, 4)

        elif d_type == "minimum_battery_reserve":
            reserve = raw_adj.get("minimum_energy_kwh", 0.0)
            try:
                reserve = max(0.0, min(float(reserve), battery_capacity))
            except (ValueError, TypeError):
                reserve = 0.0
            adj["minimum_energy_kwh"] = round(reserve, 2)

        elif d_type in ("no_charge_window", "no_discharge_window"):
            pass

        elif d_type == "max_grid_window":
            grid_cap = raw_adj.get("max_grid_kwh", 0.0)
            try:
                grid_cap = max(0.0, float(grid_cap))
            except (ValueError, TypeError):
                grid_cap = 0.0
            adj["max_grid_kwh"] = round(grid_cap, 2)

        cleaned.append({
            "note_index": i,
            "applies": True,
            "directive_type": d_type,
            "structured_adjustment": adj,
            "explanation": explanation
        })

    return cleaned
