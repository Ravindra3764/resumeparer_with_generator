import subprocess
import os


def docx_to_pdf(docx_path, output_dir):
    """Convert a .docx file to .pdf using LibreOffice. Returns the pdf path, or None on failure."""
    try:
        result = subprocess.run(
            ["libreoffice", "--headless", "--convert-to", "pdf", "--outdir", output_dir, docx_path],
            capture_output=True, text=True, timeout=120
        )
        pdf_name = os.path.splitext(os.path.basename(docx_path))[0] + ".pdf"
        pdf_path = os.path.join(output_dir, pdf_name)
        if result.returncode == 0 and os.path.exists(pdf_path):
            return pdf_path
        return None
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
