# Resume Tailor

A local web app that reads a job description, tailors your resume to match it,
generates a custom cover letter, and exports both as .docx and .pdf — ready
for ATS-friendly submission.

## What it does

1. Upload your resume (PDF, DOCX, or TXT)
2. Paste a job description + company name
3. The app:
   - Extracts your resume into structured data
   - Rewrites your summary, reorders skills, and rewrites experience bullets
     to match the job description (without inventing fake experience)
   - Generates a tailored cover letter
   - Gives you a match score + matched/missing keywords (basic ATS gap analysis)
   - Produces downloadable .docx and .pdf files in a clean, ATS-friendly format

You then review and submit the application yourself — this tool does NOT
auto-submit applications (most job sites block automated submissions and risk
banning your account).

## Setup

### 1. Install Python dependencies

```bash
cd resume-tailor
pip install -r requirements.txt
```

### 2. Install system tools (for file parsing & PDF export)

These are usually pre-installed on most systems, but if not:

- **poppler-utils** (for `pdftotext`, reading PDF resumes)
- **pandoc** (for reading .docx resumes)
- **LibreOffice** (for converting output .docx to .pdf)

On Ubuntu/Debian:

```bash
sudo apt install poppler-utils pandoc libreoffice
```

On macOS (Homebrew):

```bash
brew install poppler pandoc
brew install --cask libreoffice
```

If these aren't available, the app still works — it'll fall back to
python-docx/pypdf for reading files, and PDF export will simply be skipped
(you'll still get .docx files).

### 3. Get a free Groq API key

1. Go to https://console.groq.com
2. Sign up (free)
3. Create an API key under "API Keys"

### 4. Set your API key

Either set it as an environment variable before running:

```bash
export GROQ_API_KEY="your_key_here"
```

Or open `app.py` and replace `"YOUR_GROQ_API_KEY_HERE"` directly.

### 5. Run the app

```bash
python app.py
```

Then open **http://localhost:5000** in your browser.

## Notes

- The default model is `llama-3.1-8b-instant` (fast, free tier on Groq). You
  can change it via the `GROQ_MODEL` environment variable — e.g.
  `llama-3.3-70b-versatile` for higher quality at slightly slower speed.
- The tool will not invent job titles, employers, dates, or fake skills — it
  only rewrites/reorders/emphasizes your real content.
- Always proofread the generated resume and cover letter before sending —
  LLM output can occasionally misformat details or misinterpret context.
- Outputs are saved in the `outputs/` folder and served via download links.
