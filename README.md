## Onco Agent Demo – Architecture & Plan

This project is an **Oncology decision-support demo** for metastatic NSCLC and related scenarios. It takes a structured patient profile (e.g., 62-year-old woman, stage IV NSCLC adenocarcinoma, KRAS G12C, PD-L1 TPS 80%, TMB high, prior carboplatin+pemetrexed, ECOG 1, no brain mets) and produces:

- **Biomarker interpretation** (e.g., KRAS G12C is targetable; PD-L1 TPS 80% indicates strong ICI candidacy).
- **Evidence retrieval & synthesis** from literature/abstracts.
- **Ranked treatment options with explanations and citations**, so users can see *how* each recommendation was derived.

The system is designed for **demo and research/educational use only**, not for direct clinical decision-making.

---

## High-Level Architecture

The repo contains a new subproject:

- `onco-agent/`
  - `backend/` – FastAPI-based API, agents, and LLM integration.
  - `web/` – Minimal web UI that calls the backend and visualizes results.

The backend orchestrates:

1. **Biomarker Interpreter Agent**
   - Interprets molecular and clinical biomarkers in context (e.g., KRAS G12C, TP53, PD-L1, TMB).
   - Classifies biomarkers as targetable / predictive / prognostic / not actionable.
   - Maps to canonical trials or label-level evidence where possible.

2. **Evidence Retrieval & Synthesis Agent**
   - Uses the biomarker interpretation + patient context to search external sources (initially PubMed + meeting abstracts).
   - Parses key trials/abstracts into structured evidence objects.
   - Builds a small **evidence memory bank**.
   - Runs a synthesis + self-reflection loop to generate a **ranked list of treatment options with citations**.

3. **Synthetic Patient Generator**
   - Creates realistic, fully synthetic NSCLC cases for testing and demos (including your KRAS G12C, PD-L1-high example).
   - Provides both **fixed example profiles** and **random but realistic** cases.

The frontend offers a simple browser-based interface, inspired by OpenEvidence, to:

- Enter or load patient profiles.
- Trigger analysis.
- Display biomarker cards and ranked treatment options.
- Show **explicit reasoning and citations** for each recommendation.

---

## Tech Stack

- **Language**: Python 3.10+ for backend.
- **Backend framework**: FastAPI.
- **Web server**: Uvicorn during development.
- **LLM providers**:
  - **OpenAI** (primary; via `openai` Python SDK).
  - **Anthropic** (optional; via `anthropic` Python SDK).
- **Frontend**:
  - Initially a **minimal HTML/JS app** in `web/` that calls the FastAPI backend via JSON.
  - Can be upgraded later to React/Next.js if needed.

---

## Backend Layout

Planned backend directory structure:

- `backend/`
  - `app/`
    - `main.py` – FastAPI app and API endpoints.
    - `schemas.py` – Pydantic models for patient input and output objects.
    - `config.py` – Environment-driven configuration (API keys, models, provider selection).
    - `llm_client.py` – Unified LLM client wrapping OpenAI and Anthropic.
    - `synthetic_patients.py` – Functions to generate example and random synthetic patients.
    - `agents/`
      - `biomarker_agent.py` – Biomarker Interpreter Agent.
      - `evidence_agent.py` – Evidence Retrieval & Synthesis Agent.

Additional supporting files:

- `backend/requirements.txt` – Python dependencies.
- `.env` / environment variables – API keys and config (not committed).

---

## Patient Data Model

The core input is a **structured patient profile**, represented as a Pydantic model and JSON over the API. Conceptually:

- **Demographics**
  - `age` (e.g., 62)
  - `sex` (e.g., `"female"`)

- **Disease**
  - `cancer_type` (e.g., `"NSCLC"`)
  - `histology` (e.g., `"adenocarcinoma"`)
  - `stage` (e.g., `"IV"`)
  - `line_of_therapy` (e.g., `"second-line"`)

- **Biomarkers**
  - `biomarkers`: list of objects:
    - `gene` (e.g., `"KRAS"`)
    - `variant` (e.g., `"G12C"`)
    - `type` (e.g., `"SNV"`, `"fusion"`)
    - `assay` (e.g., `"NGS"`)
    - `notes`
  - `pdl1_tps_percent` (e.g., `80`)
  - `tmb_mut_per_mb` (e.g., `12`)

- **Treatment history**
  - `treatment_history`: list of lines:
    - `line` (1, 2, 3, ...)
    - `regimen` (e.g., `"Carboplatin + pemetrexed"`)
    - `best_response` (e.g., `"PR"`)
    - `pfs_months` (e.g., `4`)

- **Status & comorbidities**
  - `ecog` (e.g., `1`)
  - `brain_mets` (boolean)
  - `concomitant_meds` (e.g., `["Omeprazole", "Lisinopril", "Metformin"]`)
  - `current_therapy` (optional)

This schema is used consistently across:

- The **web form** (for input and synthetic auto-fill).
- The **Biomarker Interpreter Agent**.
- The **Evidence Agent**.

---

## API Design

The backend exposes a small set of JSON endpoints.

### `POST /api/analyze-patient`

Main endpoint that:

1. Runs the **Biomarker Interpreter Agent** on the patient profile.
2. Runs the **Evidence Retrieval & Synthesis Agent**, including:
   - External evidence retrieval.
   - Memory bank updates.
   - Synthesis + critique loop.
3. Returns:
   - Standardized patient summary.
   - Biomarker interpretations.
   - Ranked treatment options with explanations and citations.

#### Request (conceptual)

```json
{
  "patient": {
    "age": 62,
    "sex": "female",
    "cancer_type": "NSCLC",
    "histology": "adenocarcinoma",
    "stage": "IV",
    "line_of_therapy": "second-line",
    "ecog": 1,
    "brain_mets": false,
    "biomarkers": [
      { "gene": "KRAS", "variant": "G12C", "type": "SNV", "assay": "NGS", "notes": "" },
      { "gene": "TP53", "variant": "unknown", "type": "SNV", "assay": "NGS", "notes": "" }
    ],
    "pdl1_tps_percent": 80,
    "tmb_mut_per_mb": 12,
    "treatment_history": [
      {
        "line": 1,
        "regimen": "Carboplatin + pemetrexed",
        "best_response": "PR",
        "pfs_months": 4
      }
    ],
    "current_therapy": "Osimertinib",
    "concomitant_meds": ["Omeprazole", "Lisinopril", "Metformin"]
  },
  "options": {
    "max_treatment_options": 5,
    "evidence_sources": ["pubmed", "meeting_abstracts"]
  }
}
```

#### Response (conceptual)

```json
{
  "patient_summary": {
    "display_string": "62-year-old woman with metastatic NSCLC (adenocarcinoma), KRAS G12C+, PD-L1 TPS 80%, TMB 12 mut/Mb, post carboplatin + pemetrexed, ECOG 1, no brain mets."
  },
  "biomarker_interpretation": [
    {
      "biomarker": "KRAS G12C",
      "context_disease": "metastatic NSCLC",
      "actionability": "targetable",
      "evidence_level": "high",
      "role": ["predictive"],
      "canonical_trials_or_labels": [
        {
          "id": "codebreak-200",
          "name": "CodeBreaK 200",
          "citation": "Langen et al., N Engl J Med 2023",
          "pmid": "12345678",
          "link": "https://pubmed.ncbi.nlm.nih.gov/12345678/"
        }
      ],
      "summary": "KRAS G12C is an actionable driver in metastatic NSCLC with covalent inhibitors that improved PFS vs docetaxel in post-platinum patients.",
      "limitations": [
        "Regulatory approval and coverage vary by region."
      ]
    }
  ],
  "treatment_recommendations": [
    {
      "rank": 1,
      "regimen": "Sotorasib",
      "category": "targeted therapy",
      "headline_rationale": "Preferred second-line option targeting KRAS G12C with phase 3 evidence vs docetaxel in a population similar to this patient.",
      "why_this_patient": [
        "Patient has KRAS G12C mutation, which matches the inclusion criteria of CodeBreaK 200.",
        "Patient previously received platinum-based chemotherapy, as in the trial population.",
        "ECOG 1 matches ECOG 0–1 eligibility in the pivotal trial.",
        "No brain metastases, consistent with the main trial cohort."
      ],
      "supporting_trials": [
        {
          "trial_id": "codebreak-200",
          "name": "CodeBreaK 200",
          "phase": "3",
          "population_summary": "KRAS G12C-mutated advanced NSCLC after platinum-based chemotherapy, ECOG 0–1.",
          "intervention": "Sotorasib",
          "comparator": "Docetaxel",
          "primary_endpoint": "PFS",
          "key_results": "Median PFS 5.6 vs 4.5 months; HR 0.66 (95% CI ...).",
          "pmid": "12345678",
          "link": "https://pubmed.ncbi.nlm.nih.gov/12345678/"
        }
      ],
      "score_breakdown": {
        "overall_score": 0.87,
        "evidence_level_score": 0.4,
        "biomarker_match_score": 0.3,
        "population_fit_score": 0.15,
        "toxicity_penalty": -0.03
      },
      "model_rationale_short": "High-level evidence and strong biomarker match support sotorasib over cytotoxic chemotherapy in this setting.",
      "model_rationale_detailed": "Based on trials X and Y, sotorasib improved PFS vs docetaxel in KRAS G12C-mutated, post-platinum NSCLC with ECOG 0–1. Given this patient’s similar characteristics and lack of contraindications, it ranks above docetaxel-based options.",
      "limitations": [
        "Limited mature overall survival data.",
        "No direct head-to-head comparison versus adagrasib."
      ]
    }
  ],
  "global_limitations": [
    "This output is for research and educational purposes and is not a treatment recommendation.",
    "Regulatory approval and reimbursement vary by country.",
    "The system may not have captured all relevant trials or guidelines."
  ]
}
```

### `GET /api/examples/nsclc-kras-g12c`

Returns a **fixed synthetic NSCLC KRAS G12C high-PD-L1 case**, matching the canonical demo patient.

### `GET /api/examples/nsclc-random`

Returns a **random synthetic NSCLC case** sampled from realistic distributions (age, sex, biomarkers, PD-L1, TMB, prior lines).

These are generated by `synthetic_patients.py` and used to quickly populate the UI form for demos.

---

## LLM Integration (OpenAI + Anthropic)

The backend uses a **unified LLM client** to support OpenAI and optionally Anthropic.

Environment variables:

- `OPENAI_API_KEY` – required for OpenAI.
- `OPENAI_MODEL` – e.g., `gpt-5.2` (or best available).
- `ANTHROPIC_API_KEY` – optional (to enable Anthropic).
- `ANTHROPIC_MODEL` – e.g., `claude-opus-4-6`.
- `LLM_PROVIDER` – `"openai"`, `"anthropic"`, or `"auto"` (prefer OpenAI if configured, else Anthropic).

The `llm_client.py` module:

- Wraps:
  - `OpenAI()` client (`openai` SDK, using `chat.completions.create`).
  - `Anthropic()` client (`anthropic` SDK, using `messages.create`).
- Exposes a single method:
  - `generate(messages, model=None, provider=None) -> str`
  - `messages` is a list of dicts like:
    - `{ "role": "system" | "developer" | "user" | "assistant", "content": "..." }`
- Handles:
  - Splitting system vs user messages for Anthropic.
  - Selecting provider and model from config.

Both the **Biomarker Agent** and **Evidence Agent** call into this unified client, so switching LLM providers is a configuration change, not a code change.

---

## Agents

### Biomarker Interpreter Agent

**Input**:

- The patient profile, focusing on:
  - Disease context (NSCLC, stage, line of therapy).
  - Gene-level biomarkers (e.g., KRAS G12C, TP53).
  - PD-L1 TPS, TMB.

**Behavior**:

- For each biomarker, determines:
  - `actionability`: targetable / predictive / prognostic / not actionable.
  - `evidence_level`: qualitative label (e.g., high, moderate).
  - `role` (predictive vs prognostic).
  - `canonical_trials_or_labels`: list of key trials or labels.
  - `summary`: short natural language explanation.
  - `limitations`: explicit caveats.

**Output**:

- Structured list of biomarker interpretation objects, as returned in the main API response.

The agent is prompted to:

- Stay oncology-specific (e.g., metastatic NSCLC).
- Avoid making dosing or prescriptive statements.
- Separate **factual evidence** from **model inferences** and include limitations.

### Evidence Retrieval & Synthesis Agent

**Input**:

- Patient profile.
- Biomarker interpretation results.

**Behavior (MVP)**:

- Constructs search queries for PubMed and meeting abstracts, such as:
  - `"KRAS G12C" AND "non-small cell lung cancer" AND second-line AND randomized`.
  - `"PD-L1 high" AND pembrolizumab AND first-line AND NSCLC`.
- Fetches:
  - Titles, abstracts, year, trial phase, key identifiers.
- Parses each study into a structured record:
  - `trial_id`, `name`, `phase`, `population_summary`, `intervention`, `comparator`, `primary_endpoint`, `key_results`, `pmid`, `link`.
- Stores these in a local **evidence memory bank** (JSONL/SQLite + embeddings).
- Scores each study’s **population match** to the patient (biomarker, line of therapy, ECOG, brain mets).
- Proposes a ranked list of **treatment options**, each supported by one or more studies.

**Self-reflection loop**:

1. First pass: generate draft recommendations + evidence summaries.
2. Critique pass: a separate model call reviews draft vs raw evidence objects, looks for:
   - Overstatements or hallucinations.
   - Missing pivotal trials for major drug classes.
3. Revised pass: combine critique + original into a final, more cautious ranked list.

**Output**:

- The `treatment_recommendations` list, including:
  - `rank`, `regimen`, `headline_rationale`.
  - `why_this_patient` bullets.
  - `supporting_trials` array.
  - `score_breakdown` and `limitations`.

---

## Web UI Design

The web UI (inspired by OpenEvidence) focuses on **transparent explanations** and **citations**.

### Layout

- **Header**
  - App name.
  - Buttons:
    - **Example KRAS G12C NSCLC** – loads the fixed synthetic case.
    - **Random NSCLC synthetic** – loads a random synthetic patient profile.

- **Left column – Patient Input**
  - Form fields for:
    - Demographics, disease, biomarkers, PD-L1, TMB, treatment history, ECOG, brain mets, concomitant meds.
  - Buttons:
    - `Run analysis` – POSTs to `/api/analyze-patient`.
    - `Reset`.

- **Right column – Results**
  - **Panel A – Biomarker Interpretation**
    - Card per biomarker:
      - Title (e.g., `KRAS G12C`).
      - Tags (targetable, high evidence).
      - Short summary text.
      - Evidence chips (clicking reveals trial details/citations).
  - **Panel B – Ranked Treatment Options**
    - Accordion/list of options:
      - Collapsed view: `#1 Sotorasib` + score badge + 1–2 line rationale.
      - Expanded view:
        - **Why this for this patient?**
        - **Evidence table** (trials, endpoints, key results, citations).
        - **Model reasoning (short)** – high-level, non-exhaustive trace.
        - **Limitations** and caveats.

At the top of the results, a persistent **disclaimer banner** makes clear that this is not a clinical decision tool.

---

## Synthetic Patient Generator

`synthetic_patients.py` will provide:

- **Fixed examples**, e.g.:
  - `example_nsclc_kras_g12c_high_pdl1()` – returns the canonical NSCLC KRAS G12C, PD-L1 80%, TMB high profile.
- **Random generators**, e.g.:
  - `random_nsclc_case(seed=None)` – samples realistic distributions for age, sex, KRAS/EGFR/ALK/other biomarkers, PD-L1 bins, TMB bins, prior lines, ECOG, brain mets.

These functions return Python objects already matching the **patient schema**, so they can be:

- Returned directly via `/api/examples/...` endpoints.
- Used internally for testing the agents.

---

## Safety, Scope, and Disclaimers

- This project is for **research and educational demos** only.
- It does **not** provide medical advice or treatment recommendations.
- Regulatory status, reimbursement, and local guidelines are **not enforced** by this system.
- All outputs should be cross-checked against:
  - Formal clinical guidelines (e.g., NCCN, ESMO).
  - Original trial publications and labels.
  - Clinical judgement of qualified professionals.

---

## Next Steps / Implementation Roadmap

1. **Backend scaffolding**
   - Implement `config.py`, `schemas.py`, and `llm_client.py`.
   - Add a `/health` endpoint and `/api/llm-test` to verify LLM connectivity.
2. **Biomarker Interpreter Agent**
   - Implement `biomarker_agent.py` using the unified LLM client.
   - Ensure stable, JSON-parseable outputs for several test profiles.
3. **Evidence Agent (MVP)**
   - Implement `evidence_agent.py` with PubMed/abstract search and minimal parsing.
   - Build a simple JSONL/SQLite memory bank.
4. **End-to-end `/api/analyze-patient`**
   - Orchestrate biomarker + evidence agents into a single endpoint returning the full response schema.
5. **Web UI**
   - Build a minimal HTML/JS UI in `web/` that:
     - Loads example/random synthetic patients.
     - Calls `/api/analyze-patient`.
     - Renders biomarker cards and ranked options with explanations.
6. **Refinement**
   - Improve evidence parsing and population matching.
   - Add more synthetic patient templates.
   - Iterate on UI explainability and usability.

