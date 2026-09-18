import pulp
from typing import List, Dict, Any

def run_optimization(scenario_id: str, hours: List[Dict[str, Any]], battery: Dict[str, Any], directives: List[Dict[str, Any]]) -> Dict[str, Any]:
    # 1. Prepare Base Data
    N = 24
    demand = [h['demand_kwh'] for h in hours]
    base_solar = [h['solar_kwh'] for h in hours]
    tariff = [h['tariff_bdt_per_kwh'] for h in hours]
    
    # 2. Apply Directives to Constraints
    effective_solar = list(base_solar)
    min_reserve = [battery['minimum_energy_kwh']] * N
    charge_allowed = [True] * N
    discharge_allowed = [True] * N
    max_grid_limits = [None] * N
    
    for d in directives:
        if not d.get('applies', False):
            continue
        
        dtype = d['directive_type']
        adj = d.get('structured_adjustment', {})
        if not adj:
            continue
            
        affected_hours = adj.get('hours', [])
        
        if dtype == 'solar_reduction':
            factor = adj.get('factor', 1.0)
            for h in affected_hours:
                effective_solar[h] = base_solar[h] * factor
                
        elif dtype == 'minimum_battery_reserve':
            req_reserve = adj.get('minimum_energy_kwh', 0)
            for h in affected_hours:
                min_reserve[h] = max(min_reserve[h], req_reserve)
                
        elif dtype == 'no_charge_window':
            for h in affected_hours:
                charge_allowed[h] = False
                
        elif dtype == 'no_discharge_window':
            for h in affected_hours:
                discharge_allowed[h] = False
                
        elif dtype == 'max_grid_window':
            mg = adj.get('max_grid_kwh', 0)
            for h in affected_hours:
                max_grid_limits[h] = mg

    # 3. Setup Linear Programming Problem
    prob = pulp.LpProblem("SmartCampusOptimization", pulp.LpMinimize)
    
    # Variables
    grid_kwh = [pulp.LpVariable(f"grid_{i}", lowBound=0) for i in range(N)]
    solar_used = [pulp.LpVariable(f"solar_used_{i}", lowBound=0, upBound=effective_solar[i]) for i in range(N)]
    charge_kwh = [pulp.LpVariable(f"charge_{i}", lowBound=0, upBound=battery['max_charge_kwh_per_hour'] if charge_allowed[i] else 0) for i in range(N)]
    discharge_kwh = [pulp.LpVariable(f"discharge_{i}", lowBound=0, upBound=battery['max_discharge_kwh_per_hour'] if discharge_allowed[i] else 0) for i in range(N)]
    e_after = [pulp.LpVariable(f"e_after_{i}", lowBound=min_reserve[i], upBound=battery['capacity_kwh']) for i in range(N)]
    
    # Objective: Minimize Total Grid Cost
    prob += pulp.lpSum([grid_kwh[i] * tariff[i] for i in range(N)])
    
    # Constraints
    for i in range(N):
        # Grid limit directive
        if max_grid_limits[i] is not None:
            prob += grid_kwh[i] <= max_grid_limits[i]
            
        # Energy Balance: Grid + Solar + Battery_Discharge = Demand + Battery_Charge
        prob += grid_kwh[i] + solar_used[i] + discharge_kwh[i] == demand[i] + charge_kwh[i]
        
        # Battery State
        e_before = battery['initial_energy_kwh'] if i == 0 else e_after[i-1]
        prob += e_after[i] == e_before + charge_kwh[i] - discharge_kwh[i]
        
    # End-of-day neutrality
    prob += e_after[23] == battery['initial_energy_kwh']
    
    # Solve
    prob.solve(pulp.PULP_CBC_CMD(msg=False))
    
    # Extract Results
    hourly_plan = []
    total_grid = 0.0
    total_cost = 0.0
    peak_grid = 0.0
    
    if pulp.LpStatus[prob.status] == 'Optimal':
        for i in range(N):
            g = pulp.value(grid_kwh[i])
            su = pulp.value(solar_used[i])
            c = pulp.value(charge_kwh[i])
            d = pulp.value(discharge_kwh[i])
            ea = pulp.value(e_after[i])
            
            total_grid += g
            total_cost += g * tariff[i]
            if g > peak_grid:
                peak_grid = g
                
            action = "idle"
            bat_val = 0.0
            if c > 0.001:
                action = "charge"
                bat_val = c
            elif d > 0.001:
                action = "discharge"
                bat_val = d
                
            hourly_plan.append({
                "hour": i,
                "grid_kwh": round(g, 2),
                "solar_used_kwh": round(su, 2),
                "battery_action": action,
                "battery_kwh": round(bat_val, 2),
                "battery_energy_after_kwh": round(ea, 2)
            })
            
        summary = "Successfully optimized 24-hour schedule honoring all guardrails."
    else:
        # Fallback if infeasible (shouldn't happen on valid organizer cases)
        summary = "Optimization failed or infeasible."
        
    return {
        "scenario_id": scenario_id,
        "directive_interpretation": directives,
        "hourly_plan": hourly_plan,
        "total_grid_kwh": round(total_grid, 2),
        "total_cost_bdt": round(total_cost, 2),
        "peak_grid_kwh": round(peak_grid, 2),
        "plan_summary": summary
    }
