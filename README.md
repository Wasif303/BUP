# Smart Campus Energy Optimization Challenge (GridWise)

This repository contains the solution for the BUP CSE FEST 2026 Hackathon (Online Preliminary).

## Architecture Overview
Our solution pipeline follows a strict **Understand -> Validate -> Optimize** flow:
1. **LLM Interpreter:** Uses Google's `gemini-1.5-flash` model to interpret natural language operator notes. It extracts the `directive_type`, `hours`, and values into a strict structured JSON format.
2. **Deterministic Guardrails:** The API validates the LLM output. It ensures time arrays are sorted, integers are valid, and maps human time windows (e.g., 1 PM to 3 PM) to programmatic hours (`[13, 14]`). Irrelevant notes are safely mapped to `no_op`.
3. **Mathematical Optimizer:** Uses the `PuLP` Linear Programming library. We apply the validated directives as constraints (e.g., locking charge rates to 0 during a `no_charge_window`) alongside standard GridWise energy/battery rules. The solver calculates the mathematically optimal 24-hour battery schedule that minimizes the `total_cost_bdt`.

## Model & Technologies
* **LLM Provider:** Google AI Studio (`gemini-1.5-flash`)
* **API Framework:** FastAPI (Python)
* **Mathematical Solver:** PuLP (Linear Programming CBC Solver)

## Local Quickstart & Setup

### Environment Variables
You must provide the following environment variable to run the application:
* `GEMINI_API_KEY`: A valid API key for Google Generative AI.

### Running with Docker (Recommended)
1. Build the Docker image:
   ```bash
   docker build -t bup-gridwise .
   ```
2. Run the container:
   ```bash
   docker run -p 8000:8000 -e GEMINI_API_KEY="your_api_key_here" bup-gridwise
   ```
3. The API will be available at `http://localhost:8000`

### Running with Python Locally
1. Clone the repository and navigate to the directory.
2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Export the API key and start the server:
   ```bash
   export GEMINI_API_KEY="your_api_key_here" # On Windows use `set GEMINI_API_KEY=...`
   uvicorn main:app --host 0.0.0.0 --port 8000
   ```

## API Testing & Public Samples

### 1. Health Check
```bash
curl http://localhost:8000/health
```
**Expected Response:**
```json
{"status": "ok"}
```

### 2. Optimization Endpoint Example
```bash
curl -X POST http://localhost:8000/optimize-energy \
-H "Content-Type: application/json" \
-d '{
  "scenario_id": "GRID-101",
  "operator_notes": ["Do not charge the battery between 2 PM and 4 PM."],
  "hours": [
    {"hour": 0, "demand_kwh": 180, "solar_kwh": 0, "tariff_bdt_per_kwh": 7}
  ],
  "battery": {
    "capacity_kwh": 500,
    "initial_energy_kwh": 200,
    "minimum_energy_kwh": 50,
    "max_charge_kwh_per_hour": 100,
    "max_discharge_kwh_per_hour": 100
  }
}'
```

*(Note: Provide a full 24-hour array for testing based on the `BUP_CSE_FEST_2026_Preli_Public_Sample_Cases.json`)*

## Known Limitations
* The optimization assumes linear charging efficiency and does not account for battery degradation factors outside the provided scenario constraints.
* The system is designed to gracefully handle malformed LLM outputs by trapping parsing errors and returning a controlled failure rather than inventing constraints.

## Docker Fallback Image
Our Docker image is built and available at:
```bash
docker pull wasif303/gridwise:latest
```

To run it locally using the exact judge execution command:
```bash
docker run -d -p 8000:8000 -e GEMINI_API_KEY="your-gemini-api-key" wasif303/gridwise:latest
```
