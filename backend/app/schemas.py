from __future__ import annotations
from typing import Any, Optional
from pydantic import BaseModel, Field


# ── Patient input models ───────────────────────────────────────────────────────

class Biomarker(BaseModel):
    gene: str
    variant: str = ""
    type: str = ""          # SNV, fusion, CNV, …
    assay: str = ""         # NGS, IHC, FISH, …
    notes: str = ""


class TreatmentLine(BaseModel):
    line: int
    regimen: str
    best_response: str = ""   # CR, PR, SD, PD
    pfs_months: Optional[float] = None


class PatientProfile(BaseModel):
    age: int
    sex: str
    cancer_type: str = "NSCLC"
    histology: str = "adenocarcinoma"
    stage: str = "IV"
    line_of_therapy: str = "second-line"
    ecog: int = 1
    brain_mets: bool = False
    biomarkers: list[Biomarker] = Field(default_factory=list)
    pdl1_tps_percent: Optional[float] = None
    tmb_mut_per_mb: Optional[float] = None
    treatment_history: list[TreatmentLine] = Field(default_factory=list)
    current_therapy: Optional[str] = None
    concomitant_meds: list[str] = Field(default_factory=list)


class AnalysisOptions(BaseModel):
    max_treatment_options: int = 5
    evidence_sources: list[str] = Field(default_factory=lambda: ["pubmed"])


class AnalyzePatientRequest(BaseModel):
    patient: PatientProfile
    options: AnalysisOptions = Field(default_factory=AnalysisOptions)


# ── Output models ──────────────────────────────────────────────────────────────

class TrialReference(BaseModel):
    trial_id: str = ""
    name: str = ""
    phase: str = ""
    population_summary: str = ""
    intervention: str = ""
    comparator: str = ""
    primary_endpoint: str = ""
    key_results: str = ""
    pmid: str = ""
    link: str = ""


class BiomarkerInterpretation(BaseModel):
    biomarker: str
    context_disease: str = ""
    actionability: str = ""   # targetable | predictive | prognostic | not actionable
    evidence_level: str = ""  # high | moderate | low
    role: list[str] = Field(default_factory=list)
    canonical_trials_or_labels: list[TrialReference] = Field(default_factory=list)
    summary: str = ""
    limitations: list[str] = Field(default_factory=list)


class ScoreBreakdown(BaseModel):
    overall_score: float = 0.0
    evidence_level_score: float = 0.0
    biomarker_match_score: float = 0.0
    population_fit_score: float = 0.0
    toxicity_penalty: float = 0.0


class TreatmentRecommendation(BaseModel):
    rank: int
    regimen: str
    category: str = ""
    headline_rationale: str = ""
    why_this_patient: list[str] = Field(default_factory=list)
    supporting_trials: list[TrialReference] = Field(default_factory=list)
    score_breakdown: ScoreBreakdown = Field(default_factory=ScoreBreakdown)
    model_rationale_short: str = ""
    model_rationale_detailed: str = ""
    limitations: list[str] = Field(default_factory=list)


class PatientSummary(BaseModel):
    display_string: str


class AnalyzePatientResponse(BaseModel):
    patient_summary: PatientSummary
    biomarker_interpretation: list[BiomarkerInterpretation]
    treatment_recommendations: list[TreatmentRecommendation]
    global_limitations: list[str] = Field(default_factory=list)
