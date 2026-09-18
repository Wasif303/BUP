"""
GridWise - Linear Programming Optimization Engine
Formulates and solves 24-hour cost-optimal energy dispatch using PuLP and COIN-OR CBC.
"""

from typing import Dict, Any, List, Tuple
import pulp

def solve_energy_dispatch(
    hours_data: List[Dict[str, Any]],
    battery_data: Dict[str, Any],
    directives: List[Dict[str, Any]]
) -> Tuple[List[Dict[str, Any]], float, float, float]:
    """
    Solves the 24-hour energy dispatch problem.
    
    Returns:
        hourly_plan: List of 24 hourly dict entries matching the response schema.
        total_grid_kwh: Sum of grid energy purchased.
        total_cost_bdt: Total grid energy cost in BDT.
        peak_grid_kwh: Peak hourly grid import in kWh.
    """
    T = 24
    capacity = float(battery_data["capacity_kwh"])
    initial_energy = min(capacity, float(battery_data["initial_energy_kwh"]))
    base_min_energy = min(capacity, float(battery_data["minimum_energy_kwh"]))
    base_max_charge = float(battery_data["max_charge_kwh_per_hour"])
    base_max_discharge = float(battery_data["max_discharge_kwh_per_hour"])

    # Extract hour-by-hour baseline inputs
    demand = [float(hours_data[t]["demand_kwh"]) for t in range(T)]
    solar_orig = [float(hours_data[t]["solar_kwh"]) for t in range(T)]
    tariff = [float(hours_data[t]["tariff_bdt_per_kwh"]) for t in range(T)]

    # Directive-adjusted constraint vectors
    effective_solar = list(solar_orig)
    min_reserve = [base_min_energy] * T
    max_charge = [base_max_charge] * T
    max_discharge = [base_max_discharge] * T
    max_grid = [1e9] * T  # effectively unbounded unless constrained

    # Apply deterministic directives
    for d in directives:
        if not d.get("applies"):
            continue
        dtype = d.get("directive_type")
        adj = d.get("structured_adjustment") or {}
        hours = adj.get("hours", [])

        if dtype == "solar_reduction":
            factor = float(adj.get("factor", 1.0))
            for h in hours:
                if 0 <= h < T:
                    effective_solar[h] = solar_orig[h] * factor

        elif dtype == "minimum_battery_reserve":
            m = float(adj.get("minimum_energy_kwh", base_min_energy))
            for h in hours:
                if 0 <= h < T:
                    min_reserve[h] = max(min_reserve[h], m)

        elif dtype == "no_charge_window":
            for h in hours:
                if 0 <= h < T:
                    max_charge[h] = 0.0

        elif dtype == "no_discharge_window":
            for h in hours:
                if 0 <= h < T:
                    max_discharge[h] = 0.0

        elif dtype == "max_grid_window":
            g = float(adj.get("max_grid_kwh", 1e9))
            for h in hours:
                if 0 <= h < T:
                    max_grid[h] = min(max_grid[h], g)

    # Formulate PuLP LP Model
    prob = pulp.LpProblem("GridWise_Dispatch", pulp.LpMinimize)

    # Decision variables
    grid_vars = [
        pulp.LpVariable(f"grid_{t}", lowBound=0.0) 
        for t in range(T)
    ]
    slack_grid_vars = [
        pulp.LpVariable(f"slack_grid_{t}", lowBound=0.0)
        for t in range(T)
    ]
    solar_used_vars = [
        pulp.LpVariable(f"solar_used_{t}", lowBound=0.0, upBound=effective_solar[t]) 
        for t in range(T)
    ]
    charge_vars = [
        pulp.LpVariable(f"charge_{t}", lowBound=0.0, upBound=max_charge[t]) 
        for t in range(T)
    ]
    discharge_vars = [
        pulp.LpVariable(f"discharge_{t}", lowBound=0.0, upBound=max_discharge[t]) 
        for t in range(T)
    ]
    soc_vars = [
        pulp.LpVariable(f"soc_{t}", lowBound=0.0, upBound=capacity) 
        for t in range(T)
    ]
    
    # Slack variables for impossible battery constraints
    slack_soc_vars = [
        pulp.LpVariable(f"slack_soc_{t}", lowBound=0.0)
        for t in range(T)
    ]

    # Objective: Minimize total electricity cost (with tiny tie-breaker penalty against battery cycling)
    # And massive penalties for using slack variables (ensuring they are only used if physically impossible)
    prob += (
        pulp.lpSum([grid_vars[t] * tariff[t] for t in range(T)]) +
        pulp.lpSum([1e-6 * (charge_vars[t] + discharge_vars[t]) for t in range(T)]) +
        pulp.lpSum([slack_grid_vars[t] * 1e6 for t in range(T)]) +
        pulp.lpSum([slack_soc_vars[t] * 1e6 for t in range(T)])
    )

    # Constraints
    for t in range(T):
        # 0. Enforce max grid limits using slack (soft constraint)
        prob += (
            grid_vars[t] <= max_grid[t] + slack_grid_vars[t],
            f"Max_Grid_{t}"
        )

        # 1. Hourly Energy Balance: grid + solar_used + discharge = demand + charge
        prob += (
            grid_vars[t] + solar_used_vars[t] + discharge_vars[t] == demand[t] + charge_vars[t],
            f"Energy_Balance_{t}"
        )

        # 2. Battery State Transition (with soft constraint for minimum reserve)
        if t == 0:
            prob += (
                soc_vars[0] == initial_energy + charge_vars[0] - discharge_vars[0],
                f"Battery_State_{t}"
            )
        else:
            prob += (
                soc_vars[t] == soc_vars[t - 1] + charge_vars[t] - discharge_vars[t],
                f"Battery_State_{t}"
            )
            
        # 3. Soft constraint allowing SOC to dip below min_reserve ONLY if mathematically forced
        prob += (
            soc_vars[t] + slack_soc_vars[t] >= min_reserve[t],
            f"Min_Reserve_Soft_{t}"
        )

    # 4. End-of-Day Battery Neutrality: E_23 == initial_energy
    prob += (soc_vars[T - 1] == initial_energy, "Battery_Neutrality")

    # Solve using CBC solver silently
    solver = pulp.PULP_CBC_CMD(msg=False)
    status = prob.solve(solver)

    if status != pulp.LpStatusOptimal:
        raise ValueError(f"Solver failed to find an optimal solution. Status: {pulp.LpStatus[status]}")

    # Build hourly_plan response
    hourly_plan = []
    total_grid = 0.0
    total_cost = 0.0
    peak_grid = 0.0

    for t in range(T):
        g = max(0.0, float(pulp.value(grid_vars[t])))
        s = max(0.0, float(pulp.value(solar_used_vars[t])))
        c = max(0.0, float(pulp.value(charge_vars[t])))
        d = max(0.0, float(pulp.value(discharge_vars[t])))
        soc = max(0.0, float(pulp.value(soc_vars[t])))

        # Determine battery action
        if c > 1e-3:
            b_action = "charge"
            b_kwh = round(c, 4)
        elif d > 1e-3:
            b_action = "discharge"
            b_kwh = round(d, 4)
        else:
            b_action = "idle"
            b_kwh = 0.0

        # Energy balance numerical cleanup: ensure exact match
        g = round(g, 4)
        s = round(s, 4)
        soc = round(soc, 4)

        total_grid += g
        total_cost += g * tariff[t]
        if g > peak_grid:
            peak_grid = g

        hourly_plan.append({
            "hour": t,
            "grid_kwh": round(g, 2),
            "solar_used_kwh": round(s, 2),
            "battery_action": b_action,
            "battery_kwh": round(b_kwh, 2),
            "battery_energy_after_kwh": round(soc, 2)
        })

    # Recalculate totals directly from hourly plan to guarantee 100% agreement
    recalc_grid = round(sum(p["grid_kwh"] for p in hourly_plan), 2)
    recalc_cost = round(sum(p["grid_kwh"] * tariff[t] for t, p in enumerate(hourly_plan)), 2)
    recalc_peak = round(max(p["grid_kwh"] for p in hourly_plan), 2)

    return hourly_plan, recalc_grid, recalc_cost, recalc_peak
