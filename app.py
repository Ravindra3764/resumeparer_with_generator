import os
import json
import re
import time
from dotenv import load_dotenv
from flask import Flask, request, jsonify, render_template, send_from_directory

load_dotenv()
from werkzeug.utils import secure_filename
import requests as http

from resume_parser import extract_text_from_file
from doc_generator import generate_resume_docx, generate_cover_letter_docx
from pdf_generator import docx_to_pdf

app = Flask(__name__)

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "outputs")
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ---- CONFIG: Set your Groq API key here, or via environment variable GROQ_API_KEY ----
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "YOUR_GROQ_API_KEY_HERE")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.1-8b-instant")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


def call_groq(system_prompt, user_prompt, max_tokens=4000):
    if not GROQ_API_KEY or GROQ_API_KEY == "YOUR_GROQ_API_KEY_HERE":
        raise RuntimeError(
            "Groq API key not set. Set GROQ_API_KEY environment variable or edit app.py"
        )

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.4,
        "max_tokens": max_tokens,
    }
    max_retries = 5
    for attempt in range(max_retries):
        resp = http.post(GROQ_URL, headers=headers, json=payload, timeout=120)
        if resp.status_code == 429:
            # Respect Retry-After header if present, else exponential backoff
            retry_after = resp.headers.get("Retry-After")
            if retry_after is not None:
                try:
                    wait = float(retry_after)
                except ValueError:
                    wait = 2 ** attempt
            else:
                wait = 2 ** attempt
            if attempt < max_retries - 1:
                time.sleep(wait)
                continue
            raise RuntimeError(
                "Groq rate limit hit (429). Free-tier quota exceeded after retries. "
                "Wait a minute, slow down requests, or upgrade your Groq plan."
            )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]


def extract_json(text):
    """Strip code fences and parse JSON from LLM output."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    # Find first { and last }
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("No JSON object found in LLM response")
    return json.loads(text[start:end + 1])


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/process", methods=["POST"])
def process():
    try:
        if "resume" not in request.files:
            return jsonify({"error": "No resume file uploaded"}), 400

        resume_file = request.files["resume"]
        job_description = request.form.get("job_description", "").strip()
        company_name = request.form.get("company_name", "").strip() or "the company"
        applicant_name = reque st.form.get("applicant_name", "").strip()

        if not job_description:
            return jsonify({"error": "Job description is required"}), 400

        filename = secure_filename(resume_file.filename)
        filepath = os.path.join(UPLOAD_DIR, filename)
        resume_file.save(filepath)

        resume_text = extract_text_from_file(filepath)
        if not resume_text or len(resume_text.strip()) < 30:
            return jsonify({"error": "Could not extract text from resume file"}), 400

        # ---- Step 1: Extract structured resume data ----
        extract_system = (
            "You are an expert resume parser. Extract the resume into structured JSON. "
            "Respond with ONLY valid JSON, no markdown, no commentary, no code fences."
        )
        extract_user = f"""Extract this resume into the following JSON structure exactly:

{{
  "name": "",
  "contact": {{"email": "", "phone": "", "location": "", "linkedin": "", "other": ""}},
  "summary": "",
  "skills": ["skill1", "skill2"],
  "experience": [
    {{"title": "", "company": "", "location": "", "dates": "", "bullets": ["bullet1", "bullet2"]}}
  ],
  "education": [
    {{"degree": "", "school": "", "location": "", "dates": ""}}
  ],
  "certifications": ["cert1"],
  "projects": [
    {{"name": "", "description": "", "bullets": []}}
  ]
}}

Resume text:
---
{resume_text}
---

Return ONLY the JSON object. If a field is missing in the resume, use an empty string or empty array."""

        resume_json_raw = call_groq(extract_system, extract_user)
        resume_data = extract_json(resume_json_raw)

        if applicant_name:
            resume_data["name"] = applicant_name

        # ---- Step 2: Tailor resume to job description ----
        tailor_system = (
            "You are an expert resume writer and ATS optimization specialist. "
            "You rewrite resume content to align with a target job description while staying "
            "truthful to the candidate's actual experience (never invent employers, titles, dates, "
            "or qualifications). You optimize keyword usage for ATS parsing, use strong action verbs, "
            "and quantify impact where the original content allows. "
            "Respond with ONLY valid JSON, no markdown, no commentary, no code fences."
        )
        tailor_user = f"""Here is the candidate's current resume data (JSON):
{json.dumps(resume_data, indent=2)}

Here is the target job description:
---
{job_description}
---

Tailor this resume for the job description. Rules:
1. Rewrite the "summary" (3-4 sentences) to align with the role, mentioning relevant skills/experience naturally.
2. Reorder "skills" so the most relevant skills (matching the job description) appear first. You may add closely related skills the candidate likely has based on their experience, but do NOT fabricate unrelated skills.
3. For each experience entry, rewrite the bullets to emphasize achievements and responsibilities relevant to the target job, using keywords from the job description where truthful. Keep facts (companies, titles, dates) unchanged. Keep 3-5 bullets per role, each starting with a strong action verb.
4. Do not fabricate new jobs, degrees, or certifications.
5. Identify a "match_analysis" object with:
   - "match_score": integer 0-100 estimating how well the tailored resume matches the job description
   - "matched_keywords": array of important keywords from the JD found in the resume
   - "missing_keywords": array of important keywords from the JD NOT found in the candidate's background (skill gaps)

Return ONLY a JSON object with this exact structure:
{{
  "name": "",
  "contact": {{"email": "", "phone": "", "location": "", "linkedin": "", "other": ""}},
  "summary": "",
  "skills": [],
  "experience": [{{"title": "", "company": "", "location": "", "dates": "", "bullets": []}}],
  "education": [{{"degree": "", "school": "", "location": "", "dates": ""}}],
  "certifications": [],
  "projects": [{{"name": "", "description": "", "bullets": []}}],
  "match_analysis": {{"match_score": 0, "matched_keywords": [], "missing_keywords": []}}
}}"""

        tailored_raw = call_groq(tailor_system, tailor_user, max_tokens=4000)
        tailored_data = extract_json(tailored_raw)

        # ---- Step 3: Generate cover letter ----
        cover_system = (
            "You are an expert cover letter writer. Write concise, compelling, natural-sounding "
            "cover letters tailored to a specific job and company, based on the candidate's real "
            "background. Avoid generic filler and clichés. Respond with ONLY valid JSON, no markdown, no code fences."
        )
        cover_user = f"""Candidate resume data (JSON):
{json.dumps(tailored_data, indent=2)}

Target company: {company_name}

Job description:
---
{job_description}
---

Write a professional cover letter (3-4 paragraphs, ~250-350 words) for this candidate applying to this role at {company_name}. Reference 1-2 specific, relevant achievements from their experience. Address it generically (e.g. "Dear Hiring Manager") unless a name is given in the job description.

Return ONLY a JSON object:
{{
  "cover_letter_body": "full cover letter text with paragraphs separated by \\n\\n"
}}"""

        cover_raw = call_groq(cover_system, cover_user, max_tokens=1500)
        cover_data = extract_json(cover_raw)

        # ---- Step 4: Generate documents ----
        base_name = secure_filename(tailored_data.get("name", "resume")).replace(" ", "_") or "resume"

        resume_docx_path = os.path.join(OUTPUT_DIR, f"{base_name}_tailored_resume.docx")
        cover_docx_path = os.path.join(OUTPUT_DIR, f"{base_name}_cover_letter.docx")

        generate_resume_docx(tailored_data, resume_docx_path)
        generate_cover_letter_docx(
            tailored_data, cover_data["cover_letter_body"], company_name, cover_docx_path
        )

        resume_pdf_path = docx_to_pdf(resume_docx_path, OUTPUT_DIR)
        cover_pdf_path = docx_to_pdf(cover_docx_path, OUTPUT_DIR)

        return jsonify({
            "success": True,
            "tailored_resume": tailored_data,
            "cover_letter": cover_data["cover_letter_body"],
            "match_analysis": tailored_data.get("match_analysis", {}),
            "files": {
                "resume_docx": os.path.basename(resume_docx_path),
                "resume_pdf": os.path.basename(resume_pdf_path) if resume_pdf_path else None,
                "cover_letter_docx": os.path.basename(cover_docx_path),
                "cover_letter_pdf": os.path.basename(cover_pdf_path) if cover_pdf_path else None,
            }
        })

    except RuntimeError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Unexpected error: {str(e)}"}), 500


@app.route("/download/<filename>")
def download(filename):
    return send_from_directory(OUTPUT_DIR, filename, as_attachment=True)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
