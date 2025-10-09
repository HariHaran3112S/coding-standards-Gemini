import os
import re
import html
from flask import Flask, render_template, request
from PyPDF2 import PdfReader
from dotenv import load_dotenv
import google.generativeai as genai
from markupsafe import Markup

# ✅ Load environment variables
load_dotenv()

# ✅ Initialize Flask
app = Flask(__name__)

# ✅ Secure Gemini configuration
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise ValueError("❌ GEMINI_API_KEY missing in .env file")
genai.configure(api_key=api_key)

# ✅ Directory for coding standard PDFs
STANDARDS_DIR = "coding_standards"

# ✅ Map programming languages to their coding standard files
LANGUAGE_MAP = {
    "php": ["Coding_Standards_PHP.pdf"],
    "java": ["Coding_Standards_Java.pdf","Coding_Standards_Java_new.pdf"],
    "ios": ["Coding_Standards_iOS.pdf"],
    "dotnet": ["Coding_Standards_Dot_Net.pdf"],
    "csharp": ["Coding_Standards_Dot_Net.pdf"],
    "c#": ["Coding_Standards_Dot_Net.pdf"],
    "android": ["Coding_Standards_Android.pdf"],
    "c": ["Coding_Standards_C.pdf"],
    "python":[ "Coding_Standards_Python.pdf"]
}

# ✅ Securely extract text from PDF
def extract_pdf_text(pdf_path):
    text = ""
    try:
        reader = PdfReader(pdf_path)
        for page in reader.pages:
            content = page.extract_text()
            if content:
                text += content + "\n"
    except Exception as e:
        text = f"Error reading PDF: {str(e)}"
    return text

# ✅ Safely truncate text to avoid token overflow
def truncate_text(text, max_chars=15000):
    text = re.sub(r"[^\x00-\x7F]+", " ", text)  # remove non-ASCII for safety
    return text[:max_chars] + "\n... [truncated]" if len(text) > max_chars else text

# ✅ Format Gemini output for readability
def format_output(text):
    text = re.sub(r"(\n- )", "\n\n- ", text)
    return html.escape(text)


# ✅ Highlight and format suggestions with proper <br> line breaks (final fix)
def highlight_suggestions(text):
    if not text:
        return ""

    # Normalize newlines — ensures consistent breaks
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Split on every line that starts with "-" or newlines (handles both cases)
    suggestions = re.split(r"\n(?=-|\d+\.)|\n+", text.strip())

    formatted_suggestions = []

    keywords = [
        "optimize", "improve", "naming", "security", "performance",
        "readability", "refactor", "standard", "bug", "error", "unused"
    ]

    for suggestion in suggestions:
        s = suggestion.strip()
        if not s:
            continue

        # Highlight important keywords
        for kw in keywords:
            s = re.sub(rf"\b({kw})\b", r"<b style='color:#e63946'>\1</b>", s, flags=re.IGNORECASE)

        # Ensure bullet points and spacing
        if not s.startswith("-"):
            s = f"- {s}"

        formatted_suggestions.append(s + "<br><br>")

    # ✅ Render HTML safely with proper breaks
    return Markup("".join(formatted_suggestions))

# ✅ Detect domain or code nature
def detect_code_domain(code_input):
    domain_model = genai.GenerativeModel("gemini-2.0-flash")
    prompt = (
        "Analyze the following code and determine what real-world domain or context it belongs to. "
        "Examples: employee management, payroll, HR, inventory, student management, e-commerce, finance, etc.\n"
        "Output format: Domain: <detected domain name>\n\n"
        f"Code:\n{code_input[:1000]}"
    )
    response = domain_model.generate_content(prompt)
    return response.text.strip()

# ✅ Detect programming language
def detect_language(code_input):
    detect_model = genai.GenerativeModel("gemini-2.0-flash")
    prompt = (
        "Identify the main programming language of the following code. "
        "Respond with only one word (e.g., python, java, php, csharp, dotnet, c, android, ios):\n\n"
        f"{code_input[:1000]}"
    )
    response = detect_model.generate_content(prompt)
    lang = response.text.strip().lower()
    # C# fallback detection
    if lang not in LANGUAGE_MAP:
        if re.search(r"\busing\s+[A-Za-z0-9_.]+;", code_input) or "ActionResult" in code_input or "namespace" in code_input:
            return "csharp"
    return lang

# ✅ Secure route
@app.route("/", methods=["GET", "POST"])
def index():
    code_input = ""
    errors, suggestions, revised_code, code_domain, domain_issues = "", "", "", "", ""
    selected_language = None

    if request.method == "POST":
        if "clear" in request.form:
            return render_template(
                "index.html",
                code_input="", errors="", suggestions="", revised_code="",
                code_domain="", domain_issues="",
                languages=list(LANGUAGE_MAP.keys()), selected_language=None
            )

        elif "analyze" in request.form:
            code_input = request.form.get("code", "").strip()

            if code_input:
                try:
                    # Detect code language
                    selected_language = detect_language(code_input)
                    print(f"✅ Detected Language: {selected_language}")

                    # Detect code domain
                    code_domain = detect_code_domain(code_input)
                    print(f"✅ Detected Domain: {code_domain}")

                    # Ensure coding standards exist
                    if selected_language not in LANGUAGE_MAP:
                        errors = f"⚠️ Unrecognized language '{selected_language}'. No coding standard available."
                        return render_template(
                            "index.html", code_input=code_input, errors=errors,
                            suggestions="", revised_code="", code_domain=code_domain,
                            domain_issues="", languages=list(LANGUAGE_MAP.keys()),
                            selected_language=None
                        )

                    # Truncate user input to avoid token overflow
                    code_input_trunc = truncate_text(code_input)

                    # Combine all coding standard PDFs for that language
                    coding_standards = ""
                    for file_name in LANGUAGE_MAP[selected_language]:
                        pdf_path = os.path.join(STANDARDS_DIR, file_name)
                        coding_standards += extract_pdf_text(pdf_path) + "\n"
                    coding_standards = truncate_text(coding_standards)

                    # Ask Gemini to perform review + domain consistency check
                    review_model = genai.GenerativeModel("gemini-2.0-flash")
                    review_prompt = (
                        "You are a senior secure code reviewer. Perform the following tasks strictly:\n"
                        "1️⃣ Check for coding standard violations and logic errors.\n"
                        "2️⃣ Check if any function, class, or variable name is unrelated to the domain (e.g., "
                        "if domain is Employee Management but includes terms like Product or Invoice, flag it).\n"
                        "3️⃣ Suggest secure and performance-based improvements.\n"
                        "4️⃣ Output must be strictly in this format:\n\n"
                        "Errors:\n- <error list>\n\n"
                        "Suggestions:\n- <suggestion list>\n\n"
                        "Revised Code:\n```<language>\n<fixed code>\n```\n\n"
                        "Now analyze this code:\n\n"
                        f"Detected Domain: {code_domain}\n\n"
                        f"Coding Standards:\n{coding_standards}\n\n"
                        f"User Code:\n{code_input_trunc}\n\n"
                    )

                    response = review_model.generate_content(review_prompt)
                    analysis = response.text.strip()

                    # Extract sections
                    error_match = re.search(r"Errors:\s*(.*?)(?=Suggestions:|Revised Code:|$)", analysis, re.DOTALL | re.IGNORECASE)
                    suggestion_match = re.search(r"Suggestions:\s*(.*?)(?=Revised Code:|$)", analysis, re.DOTALL | re.IGNORECASE)
                    revised_match = re.search(r"Revised Code:\s*(.*)", analysis, re.DOTALL | re.IGNORECASE)

                    errors = format_output(error_match.group(1).strip()) if error_match else "No errors found."
                    raw_suggestions = suggestion_match.group(1).strip() if suggestion_match else "No suggestions found."
                    suggestions = highlight_suggestions(raw_suggestions)
                    revised_code = revised_match.group(1).strip() if revised_match else "No revised code provided."

                except Exception as e:
                    errors = f"⚠️ Gemini API Error: {str(e)}"
                    suggestions, revised_code = "", ""

    return render_template(
        "index.html",
        code_input=code_input,
        errors=errors,
        suggestions=suggestions,
        revised_code=revised_code,
        code_domain=code_domain,
        languages=list(LANGUAGE_MAP.keys()),
        selected_language=selected_language
    )


if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=5000)
