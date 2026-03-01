from __future__ import annotations
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .schemas import (
    AnalyzePatientRequest,
    AnalyzePatientResponse,
    PatientProfile,
)
from .config import settings

app = FastAPI(
    title="Onco Agent API",
    description="Oncology decision-support demo for metastatic NSCLC. Research/educational use only.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Health & connectivity ──────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "llm_provider": settings.llm_provider, "model": settings.active_model}


@app.get("/api/llm-test")
def llm_test():
    """Quick smoke-test: sends a minimal prompt to confirm LLM connectivity."""
    from .llm_client import llm_client

    try:
        reply = llm_client.generate(
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Say the word CONNECTED and nothing else."},
            ],
            max_tokens=10,
        )
        return {"status": "ok", "reply": reply.strip()}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ── Synthetic patient examples ─────────────────────────────────────────────────

@app.get("/api/examples/nsclc-kras-g12c", response_model=PatientProfile)
def example_nsclc_kras_g12c():
    """Returns the canonical NSCLC KRAS G12C, PD-L1 80%, TMB-high synthetic case."""
    from .synthetic_patients import example_nsclc_kras_g12c_high_pdl1
    return example_nsclc_kras_g12c_high_pdl1()


@app.get("/api/examples/nsclc-random", response_model=PatientProfile)
def example_nsclc_random():
    """Returns a random but realistic synthetic NSCLC case."""
    from .synthetic_patients import random_nsclc_case
    return random_nsclc_case()


# ── Main analysis endpoint ─────────────────────────────────────────────────────

@app.post("/api/analyze-patient", response_model=AnalyzePatientResponse)
async def analyze_patient(req: AnalyzePatientRequest):
    """
    Runs Biomarker Interpreter + Evidence Retrieval & Synthesis agents and
    returns ranked treatment options with citations and explicit reasoning.

    This is for research/educational demos only.
    """
    from .agents.biomarker_agent import interpret_biomarkers
    from .agents.evidence_agent import synthesize_evidence

    patient = req.patient

    # Step 1 – Biomarker interpretation
    biomarker_interpretations = interpret_biomarkers(patient)

    # Step 2 – Evidence retrieval + synthesis + self-reflection
    treatment_recommendations = synthesize_evidence(
        patient,
        biomarker_interpretations,
        max_options=req.options.max_treatment_options,
    )

    # Step 3 – Build patient summary string
    bm_summary = ", ".join(
        f"{b.gene} {b.variant}".strip() for b in patient.biomarkers
    )
    pdl1_str = f"PD-L1 TPS {patient.pdl1_tps_percent}%" if patient.pdl1_tps_percent is not None else ""
    tmb_str = f"TMB {patient.tmb_mut_per_mb} mut/Mb" if patient.tmb_mut_per_mb is not None else ""
    prior_regimens = " + ".join(t.regimen for t in patient.treatment_history)
    brain_str = "brain mets" if patient.brain_mets else "no brain mets"
    parts = filter(None, [bm_summary, pdl1_str, tmb_str, f"post {prior_regimens}" if prior_regimens else "", f"ECOG {patient.ecog}", brain_str])
    display = (
        f"{patient.age}-year-old {patient.sex} with metastatic {patient.cancer_type} "
        f"({patient.histology}), {', '.join(parts)}."
    )

    from .schemas import PatientSummary, AnalyzePatientResponse

    return AnalyzePatientResponse(
        patient_summary=PatientSummary(display_string=display),
        biomarker_interpretation=biomarker_interpretations,
        treatment_recommendations=treatment_recommendations,
        global_limitations=[
            "This output is for research and educational purposes only and is NOT a treatment recommendation.",
            "Regulatory approval and reimbursement vary by country.",
            "The system may not have captured all relevant trials or guidelines.",
            "Always cross-check with NCCN/ESMO guidelines and qualified clinical judgement.",
        ],
    )
