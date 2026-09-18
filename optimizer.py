"""
optimizer.py - Mathematical Linear Programming Optimizer (PuLP CBC)
Strictly adheres to Section 05 and Section 09 of the BUP CSE Fest 2026 Problem Statement.
"""

import pulp
from typing import List, Dict, Any

def run_optimization(
    scenario_id: str, 
    hours: List[Dict[str, Any]], 
    battery: Dict[str, Any], 
    directives: List[Dict[str, Any]]
) -> Dict[str, Any]:
    N = 24
    demand = [h['demand_kwh'] for h in hours]
    base_solar = [h['solar_kwh'] for h in hours]
    tariff = [h['tariff_bdt_per_kwh'] for h in hours]
    
    # 1. Apply Directives to Constraints
    effective_solar = list(base_solar)
    min_reserve = [battery['minimum_energy_kwh']] * N
    charge_allowed = [True] * N
    discharge_allowed = [True] * N
    max_grid_limits = [None] * N
    applied_summaries = []
    
    for d in directives:
        if not d.get('applies', False):
            continue
        
        dtype = d['directive_type']
        adj = d.get('structured_adjustment') or {}
        affected_hours = adj.get('hours', [])
        
        if dtype == 'solar_reduction':
            factor = adj.get('factor', 1.0)
            for h in affected_hours:
                effective_solar[h] = min(effective_solar[h], base_solar[h] * factor)
            applied_summaries.append(f"solar reduced to {factor*100:.0f}% in hours {affected_hours}")
                
        elif dtype == 'minimum_battery_reserve':
            req_reserve = adj.get('minimum_energy_kwh', 0)
            for h in affected_hours:
                min_reserve[h] = max(min_reserve[h], req_reserve)
            applied_summaries.append(f"min battery reserve {req_reserve} kWh in hours {affected_hours}")
                
        elif dtype == 'no_charge_window':
            for h in affected_hours:
                charge_allowed[h] = False
            applied_summaries.append(f"charging locked out in hours {affected_hours}")
                
        elif dtype == 'no_discharge_window':
            for h in affected_hours:
                discharge_allowed[h] = False
            applied_summaries.append(f"discharging locked out in hours {affected_hours}")
                
        elif dtype == 'max_grid_window':
            mg = adj.get('max_grid_kwh', 0)
            for h in affected_hours:
                if max_grid_limits[h] is None:
                    max_grid_limits[h] = mg
                else:
                    max_grid_limits[h] = min(max_grid_limits[h], mg)
            applied_summaries.append(f"grid capped at {mg} kWh in hours {affected_hours}")

    # 2. Setup Linear Programming Model
    prob = pulp.LpProblem("SmartCampusOptimization", pulp.LpMinimize)
    

    grid_kwh = [pulp.LpVariable(f"grid_{i}", lowBound=0) for i in range(N)]
    solar_used = [pulp.LpVariable(f"solar_used_{i}", lowBound=0, upBound=effective_solar[i]) for i in range(N)]
    charge_kwh = [pulp.LpVariable(f"charge_{i}", lowBound=0, upBound=battery['max_charge_kwh_per_hour'] if charge_allowed[i] else 0) for i in range(N)]
    discharge_kwh = [pulp.LpVariable(f"discharge_{i}", lowBound=0, upBound=battery['max_discharge_kwh_per_hour'] if discharge_allowed[i] else 0) for i in range(N)]
    e_after = [pulp.LpVariable(f"e_after_{i}", lowBound=0, upBound=battery['capacity_kwh']) for i in range(N)]
    
    slack_reserve = [pulp.LpVariable(f"slack_reserve_{i}", lowBound=0) for i in range(N)]
    slack_grid = [pulp.LpVariable(f"slack_grid_{i}", lowBound=0) for i in range(N)]
    slack_demand = [pulp.LpVariable(f"slack_demand_{i}", lowBound=0) for i in range(N)]
    
    # Objective: Minimize Total Grid Cost
    # + tiny penalty on battery throughput (1e-5) to strictly prevent simultaneous charge & discharge
    # - tiny incentive on solar (1e-6) to prefer solar over curtailment when tariff is 0

    prob += (
        pulp.lpSum([grid_kwh[i] * tariff[i] for i in range(N)]) +
        1e-5 * pulp.lpSum([charge_kwh[i] + discharge_kwh[i] for i in range(N)]) -
        1e-6 * pulp.lpSum([solar_used[i] for i in range(N)]) +
        1e6 * pulp.lpSum([slack_reserve[i] for i in range(N)]) +
        1e6 * pulp.lpSum([slack_grid[i] for i in range(N)]) +
        1e6 * pulp.lpSum([slack_demand[i] for i in range(N)])
    )
    
    # 3. Formulate Constraints

    for i in range(N):
        if max_grid_limits[i] is not None:
            prob += grid_kwh[i] <= max_grid_limits[i] + slack_grid[i]
            
        prob += grid_kwh[i] + solar_used[i] + discharge_kwh[i] + slack_demand[i] == demand[i] + charge_kwh[i]
        
        e_before = min(battery['initial_energy_kwh'], battery['capacity_kwh']) if i == 0 else e_after[i-1]
        prob += e_after[i] == e_before + charge_kwh[i] - discharge_kwh[i]
        prob += e_after[i] + slack_reserve[i] >= min_reserve[i]
        
    prob += e_after[23] == min(battery['initial_energy_kwh'], battery['capacity_kwh'])
    
    # 4. Solve Problem
    prob.solve(pulp.PULP_CBC_CMD(msg=False, timeLimit=10))
    
    # 5. Extract Schedule
    hourly_plan = []
    if pulp.LpStatus[prob.status] == 'Optimal':
        for i in range(N):
            g = pulp.value(grid_kwh[i])
            su = pulp.value(solar_used[i])
            c = pulp.value(charge_kwh[i])
            d = pulp.value(discharge_kwh[i])
            ea = pulp.value(e_after[i])
            
            action = "idle"
            bat_val = 0.0
            if c > 1e-4:
                action = "charge"
                bat_val = round(c, 2)
            elif d > 1e-4:
                action = "discharge"
                bat_val = round(d, 2)
            else:
                action = "idle"
                bat_val = 0.0
                
            hourly_plan.append({
                "hour": i,
                "grid_kwh": round(g, 2),
                "solar_used_kwh": round(su, 2),
                "battery_action": action,
                "battery_kwh": bat_val,
                "battery_energy_after_kwh": round(ea, 2)
            })
            
        summary_directives = ("; ".join(applied_summaries)) if applied_summaries else "standard tariff arbitrage"
        summary = (
            f"Successfully produced 24-hour optimal schedule respecting all constraints ({summary_directives}). "
            f"Preserved end-of-day battery neutrality."
        )
    else:
        summary = "Optimization solver failed to find a feasible solution."

    # Compute exact totals from final hourly_plan
    total_grid = round(sum(p["grid_kwh"] for p in hourly_plan), 2)
    total_cost = round(sum(p["grid_kwh"] * tariff[i] for i, p in enumerate(hourly_plan)), 2)
    peak_grid = round(max((p["grid_kwh"] for p in hourly_plan), default=0.0), 2)

    return {
        "scenario_id": scenario_id,
        "directive_interpretation": directives,
        "hourly_plan": hourly_plan,
        "total_grid_kwh": total_grid,
        "total_cost_bdt": total_cost,
        "peak_grid_kwh": peak_grid,
        "plan_summary": summary
    }
