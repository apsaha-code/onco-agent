"""Synthetic patient generators for testing and demo purposes."""
from __future__ import annotations
import random
from .schemas import PatientProfile, Biomarker, TreatmentLine


def example_nsclc_kras_g12c_high_pdl1() -> PatientProfile:
    """Canonical NSCLC KRAS G12C, PD-L1 TPS 80%, TMB-high second-line case."""
    return PatientProfile(
        age=62,
        sex="female",
        cancer_type="NSCLC",
        histology="adenocarcinoma",
        stage="IV",
        line_of_therapy="second-line",
        ecog=1,
        brain_mets=False,
        biomarkers=[
            Biomarker(gene="KRAS", variant="G12C", type="SNV", assay="NGS"),
            Biomarker(gene="TP53", variant="unknown", type="SNV", assay="NGS"),
        ],
        pdl1_tps_percent=80,
        tmb_mut_per_mb=12,
        treatment_history=[
            TreatmentLine(
                line=1,
                regimen="Carboplatin + pemetrexed",
                best_response="PR",
                pfs_months=4,
            )
        ],
        concomitant_meds=["Omeprazole", "Lisinopril", "Metformin"],
    )


# ── Distributions for random case generation ──────────────────────────────────

_SEXES = ["male", "female"]

_BIOMARKER_PROFILES = [
    # (gene, variant, type, assay)
    ("KRAS", "G12C", "SNV", "NGS"),
    ("KRAS", "G12V", "SNV", "NGS"),
    ("EGFR", "exon 19 deletion", "deletion", "NGS"),
    ("EGFR", "L858R", "SNV", "NGS"),
    ("EGFR", "T790M", "SNV", "NGS"),
    ("ALK", "fusion", "fusion", "FISH"),
    ("ROS1", "fusion", "fusion", "FISH"),
    ("MET", "exon 14 skipping", "splice", "NGS"),
    ("BRAF", "V600E", "SNV", "NGS"),
    ("RET", "fusion", "fusion", "NGS"),
    ("NTRK1", "fusion", "fusion", "NGS"),
    ("STK11", "loss", "deletion", "NGS"),
    ("KEAP1", "mutation", "SNV", "NGS"),
]

_FIRST_LINE_REGIMENS = [
    "Carboplatin + pemetrexed",
    "Carboplatin + paclitaxel",
    "Cisplatin + pemetrexed",
    "Pembrolizumab + carboplatin + pemetrexed",
    "Osimertinib",
    "Alectinib",
    "Erlotinib",
]

_RESPONSES = ["CR", "PR", "SD", "PD"]
_RESPONSE_WEIGHTS = [0.05, 0.40, 0.35, 0.20]

_LINES = ["first-line", "second-line", "third-line"]

_MEDS = [
    "Omeprazole", "Lisinopril", "Metformin", "Atorvastatin",
    "Amlodipine", "Levothyroxine", "Pantoprazole", "Aspirin",
]


def random_nsclc_case(seed: int | None = None) -> PatientProfile:
    """Generate a random but realistic synthetic NSCLC case."""
    rng = random.Random(seed)

    age = rng.randint(45, 78)
    sex = rng.choice(_SEXES)

    # Pick 1–3 biomarkers (first one is the "driver", others are co-mutations)
    n_bm = rng.choices([1, 2, 3], weights=[0.5, 0.35, 0.15])[0]
    bm_pool = rng.sample(_BIOMARKER_PROFILES, k=min(n_bm, len(_BIOMARKER_PROFILES)))
    biomarkers = [
        Biomarker(gene=g, variant=v, type=t, assay=a) for g, v, t, a in bm_pool
    ]

    pdl1 = rng.choices(
        [0, 1, 10, 49, 50, 75, 100],
        weights=[0.15, 0.1, 0.15, 0.1, 0.15, 0.15, 0.2],
    )[0]
    tmb = round(rng.uniform(1, 25), 1)

    ecog = rng.choices([0, 1, 2], weights=[0.3, 0.5, 0.2])[0]
    brain_mets = rng.random() < 0.20

    n_prior_lines = rng.choices([0, 1, 2], weights=[0.3, 0.5, 0.2])[0]
    treatment_history: list[TreatmentLine] = []
    for line_num in range(1, n_prior_lines + 1):
        regimen = rng.choice(_FIRST_LINE_REGIMENS)
        response = rng.choices(_RESPONSES, weights=_RESPONSE_WEIGHTS)[0]
        pfs = round(rng.uniform(1.5, 18), 1)
        treatment_history.append(
            TreatmentLine(line=line_num, regimen=regimen, best_response=response, pfs_months=pfs)
        )

    line_of_therapy = _LINES[min(n_prior_lines, len(_LINES) - 1)]

    n_meds = rng.randint(0, 4)
    meds = rng.sample(_MEDS, k=n_meds)

    return PatientProfile(
        age=age,
        sex=sex,
        cancer_type="NSCLC",
        histology=rng.choices(["adenocarcinoma", "squamous cell"], weights=[0.75, 0.25])[0],
        stage="IV",
        line_of_therapy=line_of_therapy,
        ecog=ecog,
        brain_mets=brain_mets,
        biomarkers=biomarkers,
        pdl1_tps_percent=float(pdl1),
        tmb_mut_per_mb=tmb,
        treatment_history=treatment_history,
        concomitant_meds=meds,
    )
