/* Onco Agent – frontend app */

const API_BASE = "http://localhost:8000";

// ── DOM references ─────────────────────────────────────────────────────────────
const $ = id => document.getElementById(id);

// ── Parse form to PatientProfile ──────────────────────────────────────────────

function parseForm() {
  // Biomarkers
  const bmsRaw = $("biomarkers_raw").value.trim().split("\n").filter(Boolean);
  const biomarkers = bmsRaw.map(line => {
    const parts = line.trim().split(/\s+/);
    return {
      gene: parts[0] || "",
      variant: parts[1] || "",
      type: parts[2] || "",
      assay: parts[3] || "",
    };
  });

  // Treatment history
  const txRaw = $("treatment_history_raw").value.trim().split("\n").filter(Boolean);
  const treatment_history = txRaw.map((line, idx) => {
    const parts = line.split("|").map(s => s.trim());
    return {
      line: idx + 1,
      regimen: parts[0] || "",
      best_response: parts[1] || "",
      pfs_months: parts[2] ? parseFloat(parts[2]) : null,
    };
  });

  const meds = $("concomitant_meds").value
    .split(",").map(s => s.trim()).filter(Boolean);

  return {
    age: parseInt($("age").value, 10),
    sex: $("sex").value,
    cancer_type: $("cancer_type").value,
    histology: $("histology").value,
    stage: $("stage").value,
    line_of_therapy: $("line_of_therapy").value,
    ecog: parseInt($("ecog").value, 10),
    brain_mets: $("brain_mets").checked,
    biomarkers,
    pdl1_tps_percent: $("pdl1_tps_percent").value !== "" ? parseFloat($("pdl1_tps_percent").value) : null,
    tmb_mut_per_mb: $("tmb_mut_per_mb").value !== "" ? parseFloat($("tmb_mut_per_mb").value) : null,
    treatment_history,
    concomitant_meds: meds,
  };
}

// ── Populate form from a PatientProfile object ─────────────────────────────────

function populateForm(p) {
  $("age").value = p.age ?? "";
  $("sex").value = p.sex ?? "female";
  $("cancer_type").value = p.cancer_type ?? "";
  $("histology").value = p.histology ?? "";
  $("stage").value = p.stage ?? "IV";
  $("line_of_therapy").value = p.line_of_therapy ?? "second-line";
  $("ecog").value = String(p.ecog ?? 1);
  $("brain_mets").checked = !!p.brain_mets;
  $("pdl1_tps_percent").value = p.pdl1_tps_percent ?? "";
  $("tmb_mut_per_mb").value = p.tmb_mut_per_mb ?? "";

  const bmsStr = (p.biomarkers || []).map(b =>
    [b.gene, b.variant, b.type, b.assay].filter(Boolean).join(" ")
  ).join("\n");
  $("biomarkers_raw").value = bmsStr;

  const txStr = (p.treatment_history || []).map(t =>
    `${t.regimen} | ${t.best_response} | ${t.pfs_months ?? ""}`
  ).join("\n");
  $("treatment_history_raw").value = txStr;

  $("concomitant_meds").value = (p.concomitant_meds || []).join(", ");
}

// ── Rendering helpers ─────────────────────────────────────────────────────────

function escHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function actionabilityTag(a) {
  const cls = {
    targetable: "tag-targetable",
    predictive: "tag-predictive",
    prognostic: "tag-prognostic",
    "not actionable": "tag-not-actionable",
  }[a?.toLowerCase()] || "tag-not-actionable";
  return `<span class="tag ${cls}">${escHtml(a || "")}</span>`;
}

function evidenceTag(level) {
  const cls = {
    high: "tag-evidence-high",
    moderate: "tag-evidence-moderate",
    low: "tag-evidence-low",
  }[level?.toLowerCase()] || "tag-evidence-low";
  return `<span class="tag ${cls}">Evidence: ${escHtml(level || "")}</span>`;
}

function trialLink(t) {
  const label = t.name || t.trial_id || t.pmid || "ref";
  if (t.link) return `<a href="${escHtml(t.link)}" target="_blank" rel="noopener">${escHtml(label)}</a>`;
  return escHtml(label);
}

function renderBiomarkerCard(interp) {
  const trialChips = (interp.canonical_trials_or_labels || []).map(t => {
    const lbl = t.name || t.trial_id || `PMID:${t.pmid}` || "ref";
    const href = t.link || (t.pmid ? `https://pubmed.ncbi.nlm.nih.gov/${t.pmid}/` : "#");
    return `<a href="${escHtml(href)}" target="_blank" rel="noopener">${escHtml(lbl)}</a>`;
  }).join(" · ");

  const limHtml = (interp.limitations || []).length
    ? `<ul class="limitations-list">${(interp.limitations).map(l => `<li>${escHtml(l)}</li>`).join("")}</ul>`
    : "";

  return `
    <div class="biomarker-card">
      <div class="biomarker-card-header">
        <span class="biomarker-name">${escHtml(interp.biomarker)}</span>
        ${actionabilityTag(interp.actionability)}
        ${evidenceTag(interp.evidence_level)}
      </div>
      <p class="biomarker-summary">${escHtml(interp.summary || "")}</p>
      ${trialChips ? `<div class="biomarker-trials">Key evidence: ${trialChips}</div>` : ""}
      ${limHtml}
    </div>
  `;
}

function renderTrialTable(trials) {
  if (!trials || trials.length === 0) return "<p style='color:#94a3b8;font-size:0.8rem'>No trial data.</p>";
  return `
    <table class="evidence-table">
      <thead>
        <tr>
          <th>Trial</th>
          <th>Phase</th>
          <th>Population</th>
          <th>Intervention</th>
          <th>Key results</th>
          <th>Ref</th>
        </tr>
      </thead>
      <tbody>
        ${trials.map(t => `
          <tr>
            <td>${escHtml(t.name || t.trial_id || "")}</td>
            <td>${escHtml(t.phase || "")}</td>
            <td>${escHtml(t.population_summary || "")}</td>
            <td>${escHtml(t.intervention || "")}${t.comparator ? " vs " + escHtml(t.comparator) : ""}</td>
            <td>${escHtml(t.key_results || "")}</td>
            <td>${trialLink(t)}</td>
          </tr>
        `).join("")}
      </tbody>
    </table>
  `;
}

function scoreClass(score) {
  if (score >= 0.7) return "";
  if (score >= 0.4) return "score-mid";
  return "score-low";
}

function renderTreatmentCard(rec, idx) {
  const rankClass = idx < 3 ? `rank-${idx + 1}` : "";
  const score = rec.score_breakdown?.overall_score ?? 0;
  const scorePct = Math.round(score * 100);
  const whyHtml = (rec.why_this_patient || []).map(w => `<li>${escHtml(w)}</li>`).join("");
  const sb = rec.score_breakdown || {};

  const scoreItems = [
    ["Evidence", sb.evidence_level_score],
    ["Biomarker match", sb.biomarker_match_score],
    ["Population fit", sb.population_fit_score],
    ["Toxicity penalty", sb.toxicity_penalty],
  ].map(([lbl, v]) =>
    v !== undefined ? `<span class="score-item">${lbl}: ${(v >= 0 ? "+" : "")}${Number(v).toFixed(2)}</span>` : ""
  ).join("");

  return `
    <div class="treatment-card" id="tx-card-${idx}">
      <div class="treatment-card-header" onclick="toggleCard(${idx})">
        <div class="rank-badge ${rankClass}">${rec.rank}</div>
        <span class="treatment-name">${escHtml(rec.regimen)}</span>
        <span class="category-tag">${escHtml(rec.category || "")}</span>
        <span class="score-badge ${scoreClass(score)}">${scorePct}%</span>
        <span class="chevron">▼</span>
      </div>
      <div class="treatment-card-body">
        <p style="font-size:0.88rem;color:#334155;margin-bottom:8px">${escHtml(rec.headline_rationale || "")}</p>

        <div class="section-label">Why this patient?</div>
        <ul class="why-list">${whyHtml}</ul>

        <div class="section-label">Supporting evidence</div>
        ${renderTrialTable(rec.supporting_trials)}

        <div class="section-label">Model reasoning</div>
        <div class="rationale-block">${escHtml(rec.model_rationale_detailed || rec.model_rationale_short || "")}</div>

        ${scoreItems ? `<div class="section-label">Score breakdown</div><div class="score-row">${scoreItems}</div>` : ""}

        ${(rec.limitations || []).length ? `
          <div class="section-label">Limitations</div>
          <ul class="limitations-list">${rec.limitations.map(l => `<li>${escHtml(l)}</li>`).join("")}</ul>
        ` : ""}
      </div>
    </div>
  `;
}

function toggleCard(idx) {
  const card = document.getElementById(`tx-card-${idx}`);
  if (card) card.classList.toggle("expanded");
}

// ── Render full results ────────────────────────────────────────────────────────

function renderResults(data) {
  $("patient-summary-box").textContent = data.patient_summary?.display_string || "";

  const bmContainer = $("biomarker-cards");
  bmContainer.className = "biomarker-cards";
  bmContainer.innerHTML = (data.biomarker_interpretation || [])
    .map(renderBiomarkerCard).join("");

  const txContainer = $("treatment-list");
  txContainer.className = "treatment-list";
  txContainer.innerHTML = (data.treatment_recommendations || [])
    .map((rec, idx) => renderTreatmentCard(rec, idx)).join("");

  // Expand the top recommendation by default
  const firstCard = document.getElementById("tx-card-0");
  if (firstCard) firstCard.classList.add("expanded");

  const limBox = $("global-limitations");
  const lims = data.global_limitations || [];
  limBox.innerHTML = lims.length
    ? `<strong>Global limitations:</strong><ul>${lims.map(l => `<li>${escHtml(l)}</li>`).join("")}</ul>`
    : "";

  $("results-placeholder").style.display = "none";
  $("results-content").style.display = "block";
  $("loading-spinner").style.display = "none";
  $("error-box").style.display = "none";
}

function showError(msg) {
  $("loading-spinner").style.display = "none";
  $("results-placeholder").style.display = "none";
  const box = $("error-box");
  box.style.display = "block";
  box.textContent = "Error: " + msg;
}

// ── API calls ─────────────────────────────────────────────────────────────────

async function runAnalysis() {
  const analyzeBtn = $("btn-analyze");
  analyzeBtn.disabled = true;
  $("results-placeholder").style.display = "none";
  $("results-content").style.display = "none";
  $("error-box").style.display = "none";
  $("loading-spinner").style.display = "block";

  const patient = parseForm();
  const maxOptions = parseInt($("max_options").value, 10);

  try {
    const resp = await fetch(`${API_BASE}/api/analyze-patient`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ patient, options: { max_treatment_options: maxOptions } }),
    });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({ detail: resp.statusText }));
      throw new Error(err.detail || resp.statusText);
    }
    const data = await resp.json();
    renderResults(data);
  } catch (e) {
    showError(e.message);
  } finally {
    analyzeBtn.disabled = false;
  }
}

async function loadExample(endpoint) {
  try {
    const resp = await fetch(`${API_BASE}${endpoint}`);
    if (!resp.ok) throw new Error(resp.statusText);
    const data = await resp.json();
    populateForm(data);
  } catch (e) {
    alert("Could not load example: " + e.message);
  }
}

function resetForm() {
  populateForm({
    age: 60,
    sex: "female",
    cancer_type: "NSCLC",
    histology: "adenocarcinoma",
    stage: "IV",
    line_of_therapy: "second-line",
    ecog: 1,
    brain_mets: false,
    biomarkers: [],
    pdl1_tps_percent: null,
    tmb_mut_per_mb: null,
    treatment_history: [],
    concomitant_meds: [],
  });
  $("results-placeholder").style.display = "block";
  $("results-content").style.display = "none";
  $("error-box").style.display = "none";
}

// ── Event listeners ───────────────────────────────────────────────────────────

document.addEventListener("DOMContentLoaded", () => {
  $("btn-analyze").addEventListener("click", runAnalysis);
  $("btn-reset").addEventListener("click", resetForm);
  $("btn-load-kras").addEventListener("click", () => loadExample("/api/examples/nsclc-kras-g12c"));
  $("btn-load-random").addEventListener("click", () => loadExample("/api/examples/nsclc-random"));
});
