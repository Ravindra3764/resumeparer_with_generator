const uploadBox = document.getElementById("uploadBox");
const fileInput = document.getElementById("resume");
const filenameEl = document.getElementById("filename");
const form = document.getElementById("tailorForm");
const submitBtn = document.getElementById("submitBtn");
const statusEl = document.getElementById("status");
const results = document.getElementById("results");

const themeToggleBtn = document.getElementById("themeToggleBtn");
themeToggleBtn.addEventListener("click", () => {
  document.body.classList.toggle("light-theme");
  const isLight = document.body.classList.contains("light-theme");
  themeToggleBtn.textContent = isLight ? "Toggle Dark Mode" : "Toggle Light Mode";
});

uploadBox.addEventListener("click", () => fileInput.click());

fileInput.addEventListener("change", () => {
  if (fileInput.files.length) {
    filenameEl.textContent = fileInput.files[0].name;
  }
});

["dragover", "dragleave", "drop"].forEach(evt => {
  uploadBox.addEventListener(evt, (e) => {
    e.preventDefault();
    if (evt === "dragover") uploadBox.classList.add("dragover");
    else uploadBox.classList.remove("dragover");
    if (evt === "drop" && e.dataTransfer.files.length) {
      fileInput.files = e.dataTransfer.files;
      filenameEl.textContent = e.dataTransfer.files[0].name;
    }
  });
});

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  statusEl.classList.remove("error");
  statusEl.innerHTML = '<span class="spinner"></span>Tailoring your resume... this can take 20-60 seconds';
  submitBtn.disabled = true;
  results.style.display = "none";

  const formData = new FormData(form);

  try {
    const res = await fetch("/api/process", { method: "POST", body: formData });
    const data = await res.json();

    if (!res.ok || data.error) {
      throw new Error(data.error || "Something went wrong");
    }

    renderResults(data);
    statusEl.textContent = "Done.";
  } catch (err) {
    statusEl.textContent = "Error: " + err.message;
    statusEl.classList.add("error");
  } finally {
    submitBtn.disabled = false;
  }
});

function renderResults(data) {
  const origMatch = data.original_match_analysis || {};
  document.getElementById("origScoreNum").textContent = origMatch.match_score ?? "--";
  renderKeywords("origMatchedKeywords", origMatch.matched_keywords, false);
  renderKeywords("origMissingKeywords", origMatch.missing_keywords, true);

  const tailorMatch = data.tailored_match_analysis || {};
  document.getElementById("tailorScoreNum").textContent = tailorMatch.match_score ?? "--";
  renderKeywords("tailorMatchedKeywords", tailorMatch.matched_keywords, false);
  renderKeywords("tailorMissingKeywords", tailorMatch.missing_keywords, true);

  // Downloads
  const downloadsEl = document.getElementById("downloads");
  downloadsEl.innerHTML = "";
  const files = data.files || {};
  const fileLabels = {
    resume_docx: "Resume (.docx)",
    resume_pdf: "Resume (.pdf)",
    cover_letter_docx: "Cover Letter (.docx)",
    cover_letter_pdf: "Cover Letter (.pdf)"
  };
  Object.entries(fileLabels).forEach(([key, label]) => {
    if (files[key]) {
      const a = document.createElement("a");
      a.href = "/download/" + files[key];
      a.textContent = "\u2193 " + label;
      downloadsEl.appendChild(a);
    }
  });

  // Resume preview
  document.getElementById("resumePreview").innerHTML = renderResumeHTML(data.tailored_resume);

  // Cover letter preview
  document.getElementById("coverPreview").textContent = data.cover_letter;

  results.style.display = "block";
  results.scrollIntoView({ behavior: "smooth" });
}

function renderResumeHTML(r) {
  let html = "";
  html += `<div class="name">${escapeHtml(r.name || "")}</div>`;

  const contact = r.contact || {};
  const contactParts = [contact.email, contact.phone, contact.location, contact.linkedin, contact.other].filter(Boolean);
  if (contactParts.length) {
    html += `<div class="contact">${contactParts.map(escapeHtml).join(" | ")}</div>`;
  }

  if (r.summary) {
    html += `<h3>Professional Summary</h3><p>${escapeHtml(r.summary)}</p>`;
  }

  if (r.skills && r.skills.length) {
    html += `<h3>Skills</h3><p>${r.skills.map(escapeHtml).join(" &bull; ")}</p>`;
  }

  if (r.experience && r.experience.length) {
    html += `<h3>Experience</h3>`;
    r.experience.forEach(job => {
      html += `<div class="job-row"><span>${escapeHtml(job.title || "")} &mdash; ${escapeHtml(job.company || "")}</span>`;
      const meta = [job.location, job.dates].filter(Boolean).map(escapeHtml).join(" | ");
      html += `<span class="job-meta">${meta}</span></div>`;
      if (job.bullets && job.bullets.length) {
        html += "<ul>" + job.bullets.map(b => `<li>${escapeHtml(b)}</li>`).join("") + "</ul>";
      }
    });
  }

  if (r.projects && r.projects.length) {
    html += `<h3>Projects</h3>`;
    r.projects.forEach(proj => {
      html += `<div style="font-weight:700;margin-top:8px;">${escapeHtml(proj.name || "")}</div>`;
      if (proj.description) html += `<p>${escapeHtml(proj.description)}</p>`;
      if (proj.bullets && proj.bullets.length) {
        html += "<ul>" + proj.bullets.map(b => `<li>${escapeHtml(b)}</li>`).join("") + "</ul>";
      }
    });
  }

  if (r.education && r.education.length) {
    html += `<h3>Education</h3>`;
    r.education.forEach(edu => {
      html += `<div class="job-row"><span>${escapeHtml(edu.degree || "")} &mdash; ${escapeHtml(edu.school || "")}</span>`;
      const meta = [edu.location, edu.dates].filter(Boolean).map(escapeHtml).join(" | ");
      html += `<span class="job-meta">${meta}</span></div>`;
    });
  }

  if (r.certifications && r.certifications.length) {
    html += `<h3>Certifications</h3><ul>` + r.certifications.map(c => `<li>${escapeHtml(c)}</li>`).join("") + "</ul>";
  }

  return html;
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str ?? "";
  return div.innerHTML;
}

function renderKeywords(elementId, keywords, isMissing) {
  const el = document.getElementById(elementId);
  if (!el) return;
  el.innerHTML = "";
  (keywords || []).forEach(kw => {
    const span = document.createElement("span");
    span.className = isMissing ? "kw missing" : "kw";
    span.textContent = isMissing ? "Missing: " + kw : kw;
    el.appendChild(span);
  });
}
