"""Biomarker Interpreter Agent.

Uses the unified LLM client to classify each biomarker in the patient profile
as targetable / predictive / prognostic / not actionable and maps it to
canonical trials / FDA labels where applicable.
"""
from __future__ import annotations
import json
import re
from typing import Any

from ..schemas import PatientProfile, BiomarkerInterpretation, TrialReference
from ..llm_client import llm_client


_SYSTEM_PROMPT = """\
You are an expert oncology biomarker analyst specialising in thoracic oncology \
(metastatic NSCLC and related settings). Your role is to interpret molecular \
and clinical biomarkers for a given patient case.

For EACH biomarker provided, produce a structured interpretation with:
- actionability: one of targetable | predictive | prognostic | not actionable
- evidence_level: high | moderate | low
- role: list (predictive, prognostic, diagnostic — may overlap)
- canonical_trials_or_labels: key pivotal trials or FDA/EMA label references
- summary: 2–4 sentence plain-language explanation
- limitations: 1–3 explicit caveats

Rules:
1. Stay strictly oncology-specific and focused on metastatic NSCLC or the \
   provided cancer context.
2. Do NOT make dosing or prescriptive clinical recommendations.
3. Separate factual evidence from model inferences.
4. Cite PMID where known; if unsure write "".
5. Return ONLY a valid JSON array — no markdown fences, no commentary.

Output format (JSON array of objects):
[
  {
    "biomarker": "<gene> <variant>",
    "context_disease": "<cancer type and stage>",
    "actionability": "targetable|predictive|prognostic|not actionable",
    "evidence_level": "high|moderate|low",
    "role": ["predictive"],
    "canonical_trials_or_labels": [
      {
        "trial_id": "",
        "name": "",
        "phase": "",
        "population_summary": "",
        "intervention": "",
        "comparator": "",
        "primary_endpoint": "",
        "key_results": "",
        "pmid": "",
        "link": ""
      }
    ],
    "summary": "",
    "limitations": [""]
  }
]
"""


def _build_user_message(patient: PatientProfile) -> str:
    bm_lines = []
    for b in patient.biomarkers:
        parts = [f"{b.gene} {b.variant}".strip()]
        if b.type:
            parts.append(f"type={b.type}")
        if b.assay:
            parts.append(f"assay={b.assay}")
        if b.notes:
            parts.append(f"notes={b.notes}")
        bm_lines.append(", ".join(parts))

    if patient.pdl1_tps_percent is not None:
        bm_lines.append(f"PD-L1 TPS {patient.pdl1_tps_percent}% (IHC)")
    if patient.tmb_mut_per_mb is not None:
        bm_lines.append(f"TMB {patient.tmb_mut_per_mb} mut/Mb")

    bm_str = "\n".join(f"  - {b}" for b in bm_lines)

    prior = ", ".join(t.regimen for t in patient.treatment_history) or "none"

    return f"""\
Patient context:
  Cancer: metastatic {patient.cancer_type} ({patient.histology}), stage {patient.stage}
  Line of therapy: {patient.line_of_therapy}
  Prior treatments: {prior}
  ECOG: {patient.ecog}
  Brain metastases: {patient.brain_mets}

Biomarkers to interpret:
{bm_str}

Return a JSON array interpreting ALL of the biomarkers listed above.
"""


def _parse_response(raw: str) -> list[dict[str, Any]]:
    """Extract the first JSON array from the LLM response."""
    # Strip markdown fences if present
    raw = re.sub(r"```(?:json)?\s*", "", raw).strip().rstrip("```").strip()
    # Find first '[' to last ']'
    start = raw.find("[")
    end = raw.rfind("]")
    if start == -1 or end == -1:
        raise ValueError(f"No JSON array found in LLM response: {raw[:300]}")
    return json.loads(raw[start : end + 1])


def _dict_to_interpretation(d: dict[str, Any]) -> BiomarkerInterpretation:
    trials = [
        TrialReference(**{k: str(v) for k, v in t.items()})
        for t in d.get("canonical_trials_or_labels", [])
        if isinstance(t, dict)
    ]
    return BiomarkerInterpretation(
        biomarker=d.get("biomarker", ""),
        context_disease=d.get("context_disease", ""),
        actionability=d.get("actionability", ""),
        evidence_level=d.get("evidence_level", ""),
        role=d.get("role", []),
        canonical_trials_or_labels=trials,
        summary=d.get("summary", ""),
        limitations=d.get("limitations", []),
    )


def interpret_biomarkers(patient: PatientProfile) -> list[BiomarkerInterpretation]:
    """Run the Biomarker Interpreter Agent and return structured interpretations."""
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": _build_user_message(patient)},
    ]
    raw = llm_client.generate(messages, temperature=0.1, max_tokens=4096)
    data = _parse_response(raw)
    return [_dict_to_interpretation(d) for d in data]
