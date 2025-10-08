import os
import re
from flask import Flask, render_template, request
from PyPDF2 import PdfReader
from dotenv import load_dotenv
import google.generativeai as genai
 
# ✅ Load .env file
load_dotenv()
 
# ✅ Initialize Flask
app = Flask(__name__)
 
# ✅ Initialize Gemini client
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise ValueError("❌ GEMINI_API_KEY is missing! Please set it in .env file.")
genai.configure(api_key=api_key)
 
# Folder holding coding standards
STANDARDS_DIR = "coding_standards"
 
# Map languages to their PDF files
LANGUAGE_MAP = {
    "php": "Coding_Standards_PHP.pdf",
    "java": "Coding_Standards_Java.pdf",
    "ios": "Coding_Standards_iOS.pdf",
    "dotnet": "Coding_Standards_Dot_Net.pdf",
    "android": "Coding_Standards_Android.pdf",
    "c": "Coding_Standards_C.pdf",
    "python": "Coding_Standards_Python.pdf"
}
 
def extract_pdf_text(pdf_path):
    """Extract text from PDF"""
    text = ""
    try:
        reader = PdfReader(pdf_path)
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    except Exception as e:
        text = f"Error reading PDF: {str(e)}"
    return text
 
# ✅ Truncate function to prevent token limit issues
def truncate_text(text, max_chars=15000):
    return text[:max_chars] + "\n... [truncated]" if len(text) > max_chars else text
 
# ✅ Format errors and suggestions with line breaks
def format_output(text):
    return re.sub(r"(\n- )", "\n\n- ", text)
 
@app.route("/", methods=["GET", "POST"])
def index():
    code_input = ""
    errors, suggestions, revised_code = "", "", ""
    selected_language = None
 
    if request.method == "POST":
        if "clear" in request.form:
            code_input, errors, suggestions, revised_code, selected_language = "", "", "", "", None
        elif "analyze" in request.form:
            code_input = request.form.get("code", "").strip()
 
            if code_input:
                try:
                    # ✅ Ask Gemini to detect the programming language first
                    detect_model = genai.GenerativeModel("gemini-2.0-flash")
                    detect_prompt = (
                        "Identify the main programming language of the following code. "
                        "Respond with only one word — the language name (e.g., python, java, php, c, dotnet, android, ios):\n\n"
                        f"{code_input[:1000]}"
                    )
                    detect_response = detect_model.generate_content(detect_prompt)
                    selected_language = detect_response.text.strip().lower()
 
                    print(f"✅ Detected Language: {selected_language}")
 
                    if selected_language not in LANGUAGE_MAP:
                        errors = f"⚠️ Unable to match detected language '{selected_language}' with any standard file."
                        return render_template(
                            "index.html",
                            code_input=code_input,
                            errors=errors,
                            suggestions="",
                            revised_code="",
                            languages=list(LANGUAGE_MAP.keys()),
                            selected_language=None
                        )
 
                    pdf_file = LANGUAGE_MAP.get(selected_language)
                    pdf_path = os.path.join(STANDARDS_DIR, pdf_file)
                    coding_standards = extract_pdf_text(pdf_path)
                    coding_standards = truncate_text(coding_standards, 15000)
                    code_input_trunc = truncate_text(code_input, 15000)
 
                    # ✅ Proceed with the code review
                    model = genai.GenerativeModel("gemini-2.0-flash")
                    prompt = (
                        "You are a strict code review assistant. "
                        "Always output in the exact format:\n\n"
                        "Errors:\n- List each error or violation here\n\n"
                        "Suggestions:\n- List each suggestion or improvement here\n\n"
                        "Revised Code:\n```<language>\n<corrected code>\n```"
                        f"\n\nHere is the coding standard:\n{coding_standards}\n\n"
                        f"Here is the user's code:\n{code_input_trunc}\n\n"
                        "Check for violations, suggest improvements, and provide a corrected version of the code."
                    )
 
                    response = model.generate_content(prompt)
                    analysis = response.text.strip()
 
                    error_match = re.search(
                        r"Errors:\s*(.*?)(?=Suggestions:|Revised Code:|$)",
                        analysis,
                        re.DOTALL | re.IGNORECASE,
                    )
                    suggestion_match = re.search(
                        r"Suggestions:\s*(.*?)(?=Revised Code:|$)",
                        analysis,
                        re.DOTALL | re.IGNORECASE,
                    )
                    revised_match = re.search(
                        r"Revised Code:\s*(.*)",
                        analysis,
                        re.DOTALL | re.IGNORECASE,
                    )
 
                    errors = format_output(error_match.group(1).strip()) if error_match else "No errors found."
                    suggestions = format_output(suggestion_match.group(1).strip()) if suggestion_match else "No suggestions found."
                    revised_code = revised_match.group(1).strip() if revised_match else "No revised code provided."
 
                except Exception as e:
                    errors = f"⚠️ Error calling Gemini API: {str(e)}"
                    suggestions, revised_code = "", ""
 
    return render_template(
        "index.html",
        code_input=code_input,
        errors=errors,
        suggestions=suggestions,
        revised_code=revised_code,
        languages=list(LANGUAGE_MAP.keys()),
        selected_language=selected_language
    )
 
if __name__ == "__main__":
    app.run(debug=True)