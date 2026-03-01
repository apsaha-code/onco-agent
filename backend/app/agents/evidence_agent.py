"""Evidence Retrieval & Synthesis Agent.

Pipeline:
  1. Build PubMed search queries from patient + biomarker interpretations.
  2. Fetch titles/abstracts from the NCBI E-utilities (free, no key required).
  3. Parse each record into a structured TrialEvidence object.
  4. Store / cache results in a JSONL evidence memory bank.
  5. Draft treatment recommendations (LLM pass 1).
  6. Critique pass (LLM pass 2) — checks for overstatements.
  7. Final revised ranked list (LLM pass 3).
"""
from __future__ import annotations
import json
import os
import re
import hashlib
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from ..schemas import (
    PatientProfile,
    BiomarkerInterpretation,
    TreatmentRecommendation,
    TrialReference,
    ScoreBreakdown,
)
from ..llm_client import llm_client

# ── Evidence memory bank (JSONL file) ─────────────────────────────────────────

_MEMORY_DIR = Path(__file__).parent.parent / "memory"
_MEMORY_DIR.mkdir(exist_ok=True)
_MEMORY_FILE = _MEMORY_DIR / "evidence_bank.jsonl"


def _cache_key(query: str) -> str:
    return hashlib.md5(query.encode()).hexdigest()


def _load_cached(query: str) -> list[dict] | None:
    key = _cache_key(query)
    if not _MEMORY_FILE.exists():
        return None
    with _MEMORY_FILE.open() as f:
        for line in f:
            try:
                rec = json.loads(line)
                if rec.get("query_hash") == key:
                    return rec["records"]
            except json.JSONDecodeError:
                pass
    return None


def _save_to_cache(query: str, records: list[dict]) -> None:
    key = _cache_key(query)
    entry = {"query_hash": key, "query": query, "records": records}
    with _MEMORY_FILE.open("a") as f:
        f.write(json.dumps(entry) + "\n")


# ── PubMed E-utilities ─────────────────────────────────────────────────────────

_EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


def _pubmed_search(query: str, max_results: int = 8) -> list[str]:
    """Return a list of PMIDs for the query."""
    params = urllib.parse.urlencode({
        "db": "pubmed",
        "term": query,
        "retmax": max_results,
        "retmode": "json",
        "sort": "relevance",
    })
    url = f"{_EUTILS_BASE}/esearch.fcgi?{params}"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read())
        return data.get("esearchresult", {}).get("idlist", [])
    except Exception:
        return []


def _pubmed_fetch_abstracts(pmids: list[str]) -> list[dict]:
    """Fetch title + abstract for a list of PMIDs."""
    if not pmids:
        return []
    ids = ",".join(pmids)
    params = urllib.parse.urlencode({
        "db": "pubmed",
        "id": ids,
        "retmode": "xml",
    })
    url = f"{_EUTILS_BASE}/efetch.fcgi?{params}"
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            xml_data = resp.read()
    except Exception:
        return []

    records = []
    try:
        root = ET.fromstring(xml_data)
        for article in root.findall(".//PubmedArticle"):
            pmid_el = article.find(".//PMID")
            pmid = pmid_el.text if pmid_el is not None else ""
            title_el = article.find(".//ArticleTitle")
            title = "".join(title_el.itertext()) if title_el is not None else ""
            abstract_parts = article.findall(".//AbstractText")
            abstract = " ".join("".join(p.itertext()) for p in abstract_parts)
            year_el = article.find(".//PubDate/Year")
            year = year_el.text if year_el is not None else ""
            records.append({
                "pmid": pmid,
                "title": title,
                "abstract": abstract,
                "year": year,
                "link": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            })
    except ET.ParseError:
        pass
    return records


def _fetch_evidence(query: str, max_results: int = 8) -> list[dict]:
    cached = _load_cached(query)
    if cached is not None:
        return cached
    pmids = _pubmed_search(query, max_results)
    records = _pubmed_fetch_abstracts(pmids)
    _save_to_cache(query, records)
    return records


# ── Query generation ───────────────────────────────────────────────────────────

def _build_queries(
    patient: PatientProfile, interpretations: list[BiomarkerInterpretation]
) -> list[str]:
    queries = []
    cancer = patient.cancer_type  # "NSCLC"
    line = patient.line_of_therapy  # "second-line"

    for interp in interpretations:
        if interp.actionability in ("targetable", "predictive"):
            bm = interp.biomarker  # "KRAS G12C"
            queries.append(
                f'"{bm}" AND "{cancer}" AND {line} AND (randomized OR phase 3 OR phase 2)'
            )

    if patient.pdl1_tps_percent is not None and patient.pdl1_tps_percent >= 50:
        queries.append(
            f'"PD-L1 high" AND pembrolizumab AND {line} AND "{cancer}" AND randomized'
        )
    elif patient.pdl1_tps_percent is not None and patient.pdl1_tps_percent >= 1:
        queries.append(
            f'checkpoint inhibitor AND {line} AND "{cancer}" AND randomized'
        )

    # Always add a broad second-line NSCLC query for context
    queries.append(f'"{cancer}" AND {line} AND overall survival AND randomized')

    return queries[:5]  # cap to avoid excessive API calls


# ── LLM prompts ───────────────────────────────────────────────────────────────

_SYNTHESIS_SYSTEM = """\
You are an expert oncology clinical trialist and evidence synthesiser. \
Your role is to produce ranked treatment recommendations for a given patient, \
grounded in the evidence records provided. \
Do NOT invent or hallucinate trials. Use only the abstracts and information given. \
If evidence is weak, say so explicitly. \
Return ONLY valid JSON — no markdown fences, no commentary.
"""

_SYNTHESIS_USER_TPL = """\
## Patient profile
{patient_json}

## Biomarker interpretations
{biomarker_json}

## Retrieved evidence records (from PubMed)
{evidence_json}

## Task
Based on the evidence records above (and your general oncology knowledge where evidence records are absent), \
produce a ranked list of up to {max_options} treatment options for this patient.

Each option must include:
- rank (1 = most preferred)
- regimen (drug name or combination)
- category (targeted therapy | immunotherapy | chemotherapy | combination | other)
- headline_rationale (1–2 sentences)
- why_this_patient (list of 2–4 bullets explaining patient match)
- supporting_trials (list of trial objects, using pmid from evidence records where possible)
- score_breakdown (overall_score 0–1, evidence_level_score, biomarker_match_score, population_fit_score, toxicity_penalty)
- model_rationale_short (≤2 sentences)
- model_rationale_detailed (≤4 sentences, note evidence gaps)
- limitations (list of 1–3 caveats)

Return a JSON array of treatment recommendation objects matching this schema exactly.
"""

_CRITIQUE_SYSTEM = """\
You are a critical reviewer of oncology AI-generated treatment recommendations. \
Your job is to identify:
1. Overstatements or claims not supported by the provided evidence records.
2. Missing pivotal drug classes that should be considered for this patient profile.
3. Hallucinated trial results or PMIDs.
Return your critique as a JSON object with keys:
  "overstatements": [list of strings],
  "missing_drug_classes": [list of strings],
  "hallucinations": [list of strings],
  "overall_quality": "good|acceptable|poor",
  "suggested_changes": [list of strings]
Return ONLY valid JSON.
"""

_REVISED_SYSTEM = """\
You are an expert oncology evidence synthesiser. \
Using the original draft recommendations AND the critique below, \
produce a final, more cautious ranked list of treatment recommendations. \
Address all critique points. Downgrade or remove unsupported recommendations. \
Return ONLY a valid JSON array of treatment recommendation objects (same schema as before).
"""


def _run_synthesis(
    patient: PatientProfile,
    interpretations: list[BiomarkerInterpretation],
    evidence: list[dict],
    max_options: int,
) -> str:
    user_msg = _SYNTHESIS_USER_TPL.format(
        patient_json=patient.model_dump_json(indent=2),
        biomarker_json=json.dumps([i.model_dump() for i in interpretations], indent=2),
        evidence_json=json.dumps(evidence, indent=2),
        max_options=max_options,
    )
    return llm_client.generate(
        [
            {"role": "system", "content": _SYNTHESIS_SYSTEM},
            {"role": "user", "content": user_msg},
        ],
        temperature=0.2,
        max_tokens=6000,
    )


def _run_critique(
    patient: PatientProfile,
    interpretations: list[BiomarkerInterpretation],
    evidence: list[dict],
    draft: str,
) -> str:
    return llm_client.generate(
        [
            {"role": "system", "content": _CRITIQUE_SYSTEM},
            {
                "role": "user",
                "content": (
                    f"## Patient\n{patient.model_dump_json()}\n\n"
                    f"## Evidence records\n{json.dumps(evidence)}\n\n"
                    f"## Draft recommendations\n{draft}"
                ),
            },
        ],
        temperature=0.1,
        max_tokens=2000,
    )


def _run_revised(draft: str, critique: str, evidence: list[dict], max_options: int) -> str:
    return llm_client.generate(
        [
            {"role": "system", "content": _REVISED_SYSTEM},
            {
                "role": "user",
                "content": (
                    f"## Original draft\n{draft}\n\n"
                    f"## Critique\n{critique}\n\n"
                    f"## Evidence records\n{json.dumps(evidence)}\n\n"
                    f"Produce final ranked list of up to {max_options} options."
                ),
            },
        ],
        temperature=0.15,
        max_tokens=6000,
    )


# ── Parsing helpers ────────────────────────────────────────────────────────────

def _extract_json_array(raw: str) -> list[dict]:
    raw = re.sub(r"```(?:json)?\s*", "", raw).strip().rstrip("```").strip()
    start = raw.find("[")
    end = raw.rfind("]")
    if start == -1 or end == -1:
        raise ValueError(f"No JSON array found: {raw[:300]}")
    return json.loads(raw[start : end + 1])


def _dict_to_recommendation(d: dict[str, Any], rank: int) -> TreatmentRecommendation:
    trials = []
    for t in d.get("supporting_trials", []):
        if isinstance(t, dict):
            trials.append(TrialReference(**{k: str(v) for k, v in t.items()}))

    sb_raw = d.get("score_breakdown", {})
    sb = ScoreBreakdown(
        overall_score=float(sb_raw.get("overall_score", 0)),
        evidence_level_score=float(sb_raw.get("evidence_level_score", 0)),
        biomarker_match_score=float(sb_raw.get("biomarker_match_score", 0)),
        population_fit_score=float(sb_raw.get("population_fit_score", 0)),
        toxicity_penalty=float(sb_raw.get("toxicity_penalty", 0)),
    )

    return TreatmentRecommendation(
        rank=d.get("rank", rank),
        regimen=d.get("regimen", ""),
        category=d.get("category", ""),
        headline_rationale=d.get("headline_rationale", ""),
        why_this_patient=d.get("why_this_patient", []),
        supporting_trials=trials,
        score_breakdown=sb,
        model_rationale_short=d.get("model_rationale_short", ""),
        model_rationale_detailed=d.get("model_rationale_detailed", ""),
        limitations=d.get("limitations", []),
    )


# ── Public entry point ─────────────────────────────────────────────────────────

def synthesize_evidence(
    patient: PatientProfile,
    interpretations: list[BiomarkerInterpretation],
    max_options: int = 5,
) -> list[TreatmentRecommendation]:
    """
    Full evidence retrieval + synthesis + self-reflection pipeline.
    Returns a ranked list of TreatmentRecommendation objects.
    """
    # 1. Build queries and fetch evidence
    queries = _build_queries(patient, interpretations)
    all_evidence: list[dict] = []
    seen_pmids: set[str] = set()
    for q in queries:
        for rec in _fetch_evidence(q):
            if rec["pmid"] not in seen_pmids:
                seen_pmids.add(rec["pmid"])
                all_evidence.append(rec)

    # Cap evidence records to avoid exceeding context window
    evidence_subset = all_evidence[:30]

    # 2. Draft synthesis
    draft_raw = _run_synthesis(patient, interpretations, evidence_subset, max_options)

    # 3. Critique pass
    try:
        critique_raw = _run_critique(patient, interpretations, evidence_subset, draft_raw)
    except Exception:
        critique_raw = "{}"

    # 4. Revised synthesis incorporating critique
    try:
        final_raw = _run_revised(draft_raw, critique_raw, evidence_subset, max_options)
        recs_data = _extract_json_array(final_raw)
    except Exception:
        # Fall back to draft if revision fails
        recs_data = _extract_json_array(draft_raw)

    return [_dict_to_recommendation(d, i + 1) for i, d in enumerate(recs_data[:max_options])]
