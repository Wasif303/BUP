import json
import os
import requests

# Ensure API key is set for local testing
os.environ["GEMINI_API_KEY"] = "AQ.Ab8RN6KnAM3JdyT4nvKcAYPUjHJOvBNGzvdikXSgL_cpLaiF6w"

from main import optimize_energy, RequestPayload

def run_tests():
    try:
        with open("BUP_CSE_FEST_2026_Preli_Public_Sample_Cases.json", "r") as f:
            data = json.load(f)
        
        # It might be a list of scenarios or a single object. Let's handle both.
        scenarios = data if isinstance(data, list) else [data]
        
        for i, scenario in enumerate(scenarios):
            print(f"\n--- Testing Scenario {i+1}: {scenario.get('scenario_id', 'Unknown')} ---")
            payload = RequestPayload(**scenario)
            result = optimize_energy(payload)
            print("Status: SUCCESS!")
            print(f"Total Cost BDT: {result['total_cost_bdt']}")
            print(f"Plan Summary: {result['plan_summary']}")
            print(f"Interpreted Directives:")
            for d in result['directive_interpretation']:
                print(f"  - {d['directive_type']}: {d.get('structured_adjustment')}")
            
    except Exception as e:
        print(f"\nERROR during testing: {str(e)}")

if __name__ == "__main__":
    run_tests()
