# 🎬 GridWise — 3-Minute Video Presentation Script
**Event**: BUP CSE Fest 2026 Hackathon (Online Preliminary)  
**Track**: Smart Campus Energy Optimization Challenge (GridWise LLM)  
**Time Limit**: STRICTLY 3 MINUTES MAXIMUM (Target runtime: 2 minutes 50 seconds)  
**Speaker Pace**: Calm, confident, conversational (~130–140 words per minute)

---

## ⏱️ Video Structure & Visual Cue Map

| Timecode | Section | Visual on Screen |
| :--- | :--- | :--- |
| **0:00 – 0:35** | 1. Problem Understanding | Slide or Diagram showing BUP Campus with Solar, Grid, Battery, and Operator Notes |
| **0:35 – 1:25** | 2. Architecture & Pipeline | Architecture Diagram: LLM ➔ Guardrails ➔ PuLP Linear Program |
| **1:25 – 1:55** | 3. Key Technical Decisions | Code snippet of `main.py` guardrail validator & `optimizer.py` LP formulation |
| **1:55 – 2:40** | 4. Live Demonstration | Screen recording of Terminal: running `test_public_samples.py` & cURL requests |
| **2:40 – 3:00** | 5. Deployment & Conclusion | Browser showing Render.com live URL and Docker Hub fallback repository |

---

## 🎙️ Spoken Script (Word-for-Word)

### [0:00 – 0:35] Problem Understanding & Real-World Challenge
*(Visual: Display project title and campus microgrid overview diagram)*

> "Hello judges! Welcome to our presentation of **GridWise**, an intelligent energy optimization engine engineered for the BUP CSE Fest 2026 Hackathon.
>
> In modern smart campuses, managing electricity costs requires orchestrating three dynamic components: fluctuating rooftop solar generation, time-varying grid tariffs, and a centralized battery storage system. 
> 
> However, real-world microgrids face a critical hurdle: campus operators frequently issue real-time operational constraints as unstructured human notes—such as emergency solar panel cleaning or charging restrictions. Our mission is to seamlessly parse these natural-language notes, translate them into hard operational constraints, and compute the mathematically cheapest 24-hour dispatch schedule."

---

### [0:35 – 1:25] Three-Tier Pipeline Architecture
*(Visual: Show the Architecture Flowchart highlighting LLM ➔ Guardrails ➔ PuLP Solver)*

> "To guarantee absolute reliability and mathematical precision, we architected GridWise as a decoupled **Three-Tier Neuro-Symbolic Pipeline**:
>
> 1. **First, the Semantic Interpretation Tier**: Powered by Google Gemini Flash, this layer parses natural-language operator notes into structured JSON directives—such as `solar_reduction`, `minimum_battery_reserve`, `no_charge_window`, or `max_grid_window`. Irrelevant notes are strictly classified as `no_op`.
>
> 2. **Second, our Deterministic Guardrail Engine**: Large Language Models should never be trusted as raw mathematicians. Our guardrail layer validates directive types, verifies that time windows are sorted unique integers between 0 and 23, bounds solar reduction factors, and guarantees safe failure handling if unexpected input occurs.
>
> 3. **Third, the Mathematical Optimization Engine**: Validated constraints are fed into a Linear Programming formulation using PuLP and the COIN-OR CBC solver. It simultaneously balances hourly supply and demand, respects battery discharge limits, and guarantees end-of-day battery state neutrality."

---

### [1:25 – 1:55] Key Implementation Choices
*(Visual: Show lines of code in `optimizer.py` and `main.py`)*

> "Why this decoupled approach? 
> 
> Asking an LLM to generate 24 hourly numerical schedules directly leads to floating-point drift, energy-balance violations, and hallucinated battery levels. 
>
> By letting the LLM excel at what it does best—semantic understanding of human text—and letting a simplex linear solver do what it does best—global cost minimization—our solver guarantees the exact global optimum with zero constraint violations in less than 20 milliseconds."

---

### [1:55 – 2:40] Live Demonstration & Validation
*(Visual: Terminal running `curl` and `python test_public_samples.py`)*

> "Let’s see it in action!
> 
> First, our readiness endpoint: hitting `GET /health` immediately returns `status: ok`.
>
> Now, let's test a complex scenario from the official dataset: **SAMPLE-01**. The prompt contains two notes: a solar panel washing window from noon to 2 PM, and an unrelated distractor about sports registration.
>
> Sending this to `POST /optimize-energy`... Notice the result!
> - The Gemini interpreter accurately extracted `solar_reduction` for hours 12 and 13 with a factor of 0.25.
> - The distractor was cleanly identified as `no_op` with `applies: false`.
> - The PuLP solver produced a complete 24-hour schedule, shifting battery discharge into peak tariff hours where electricity costs 28 to 30 BDT, while returning the battery to its initial 110 kilowatt-hour state by hour 23.
> 
> Running our automated test suite across all 10 public challenge cases shows a **100% pass rate** with sub-3-second p95 response time."

---

### [2:40 – 3:00] Deployment, Fallback & Conclusion
*(Visual: Browser showing live Render URL and Docker Hub repository)*

> "For deployment, our service is live on Render.com with continuous uptime and zero authentication barriers.
>
> In addition, we have provided a pre-built Docker fallback image on Docker Hub that can be pulled and run anywhere in seconds using a single command.
>
> GridWise bridges the gap between natural human operator communication and mathematically rigorous energy optimization. Thank you!"

---

## 💡 Quick Tips for Recording:
1. **Total Word Count**: ~410 words. At 135 wpm, this takes ~2 minutes 45 seconds. Keep your pace steady!
2. **Audio**: Use a clear headset or USB microphone, speak with enthusiasm.
3. **Screen Setup**: Keep two windows open side-by-side or tabbed: your browser showing the live Render URL / Swagger docs, and your terminal showing curl requests or `python test_public_samples.py`.
4. **Resolution & Format**: Record in 1080p (1920x1080) and export as `.mp4`. Make sure it is strictly **under 3 minutes (e.g. 2:50)** to avoid penalty.
