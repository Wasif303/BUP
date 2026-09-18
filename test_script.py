"""
test_script.py - Quick local test script for GridWise optimization
"""

import json
import os
import sys

from main import optimize_energy, RequestPayload

def run_tests():
    try:
        sample_file = "BUP_CSE_FEST_2026_Preli_Public_Sample_Cases.json"
        if not os.path.exists(sample_file):
            sample_file = os.path.join(os.path.dirname(__file__), sample_file)

        with open(sample_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        cases = data.get("cases", [])
        print(f"Loaded {len(cases)} test cases from {sample_file}\n")
        
        for i, c in enumerate(cases):
            c_input = c["input"]
            scenario_id = c_input.get("scenario_id", f"Case-{i+1}")
            print(f"--- Testing Scenario {i+1}: {scenario_id} ({c.get('label', '')}) ---")
            payload = RequestPayload(**c_input)
            result = optimize_energy(payload)
            print(f"  Status: SUCCESS")
            print(f"  Total Cost: {result['total_cost_bdt']} BDT | Grid Energy: {result['total_grid_kwh']} kWh | Peak: {result['peak_grid_kwh']} kWh")
            print(f"  Plan Summary: {result['plan_summary']}")
            print(f"  Directives ({len(result['directive_interpretation'])}):")
            for d in result["directive_interpretation"]:
                print(f"    - [{d['directive_type']}] applies={d['applies']}, adj={d.get('structured_adjustment')}")
            print()
            
    except Exception as e:
        print(f"\nERROR during testing: {e}")
        sys.exit(1)

if __name__ == "__main__":
    run_tests()
