from flask import Flask, request, jsonify, render_template
from werkzeug.utils import secure_filename
import pytesseract
from PIL import Image
import PyPDF2
import re
from pdf2image import convert_from_bytes

app = Flask(__name__)

# Allowed file extensions
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg'}

try:
    pytesseract.get_tesseract_version()
except EnvironmentError:
    print("Warning: Tesseract OCR not found. Image/PDF OCR will fail.")

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def format_to_regex(number_format: str) -> re.Pattern:
    """
    Converts user-defined format with '#' (digit placeholder) into a regex pattern.
    Supports flexible spacing and separators.
    """
    if '#' not in number_format:
        raise ValueError("Invalid format: must contain at least one '#' character.")

    escaped = ''
    for char in number_format:
        if char == '#':
            escaped += r'\d'
        elif char.isspace():
            escaped += r'\s*'  # Flexible spacing
        else:
            escaped += r'\s*' + re.escape(char) + r'\s*'  # Allow space around separators
    return re.compile(escaped)

def clean_extracted_text(text: str) -> str:
    # Normalize spaces and hyphens
    text = re.sub(r'(\d)\s+(\d)', r'\1\2', text)
    text = re.sub(r'\s*-\s*', '-', text)
    return text.strip()

def extract_text_from_file(file):
    # PDF
    if file.filename.lower().endswith('.pdf'):
        try:
            pdf_reader = PyPDF2.PdfReader(file)
            text = "".join(page.extract_text() or '' for page in pdf_reader.pages)
            if text.strip():
                return text
            # If empty, fallback to OCR
            file.seek(0)
            images = convert_from_bytes(file.read())
            return ''.join(pytesseract.image_to_string(img) for img in images)
        except Exception as e:
            return str(e)
    # Image
    else:
        try:
            image = Image.open(file)
            image = image.convert('L')  # Grayscale
            return pytesseract.image_to_string(image, lang='eng', config='--psm 6')
        except Exception as e:
            return str(e)

@app.route('/', methods=['GET'])
def home():
    return render_template("index.html")

@app.route('/test', methods=['POST'])
def test():
    number_format = request.form['format']
    return jsonify({
        "found": True,
        "format": number_format
    })

@app.route('/extract-number', methods=['POST'])
def extract_number():
    if 'file' not in request.files or 'format' not in request.form:
        return jsonify({"error": "Missing file or format parameter"}), 400

    file = request.files['file']
    number_format = request.form['format']

    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    if not allowed_file(file.filename):
        return jsonify({"error": "Invalid file type"}), 400

    try:
        pattern = format_to_regex(number_format)
        print(f"Regex pattern: {pattern.pattern}")

        text = extract_text_from_file(file)
        if isinstance(text, str):
            text = clean_extracted_text(text)
        else:
            return jsonify({"error": "Failed to extract text from file"}), 500

        print(f"Extracted text: {text}")
        matches = pattern.findall(text)

        if matches:
            return jsonify({
                "found": True,
                "matches": matches,
                "format": number_format
            })
        else:
            return jsonify({
                "found": False,
                "message": "No matching number found",
                "format": number_format
            })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
