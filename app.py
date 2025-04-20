from flask import Flask, request, jsonify, render_template
from werkzeug.utils import secure_filename
import pytesseract
from PIL import Image
import PyPDF2
from pdf2image import convert_from_bytes
import re
import os

app = Flask(__name__)

ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg'}

# Check Tesseract installation
try:
    pytesseract.get_tesseract_version()
except EnvironmentError:
    print("Warning: Tesseract OCR not found. Image/PDF OCR will fail.")

# Normalize OCR text misreads
def normalize_text_for_license(text: str) -> str:
    replacements = {
        'O': '0',
        'I': '1',
        'Z': '2',
        'S': '5',
        'B': '8',
    }
    return ''.join(replacements.get(c.upper(), c) for c in text)

# Check allowed file extensions
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Validate Algerian license plate format
def is_valid_algerian_license_plate(license_plate: str) -> bool:
    license_plate = license_plate.upper().replace('I', '1')
    pattern = r'^\d{5,6}[-\s/.]?\d{2,3}[-\s/.]?\d{2}$'
    return bool(re.match(pattern, license_plate))

# Format license plate with spacing
def format_license_plate_with_spaces(license_plate: str) -> str:
    license_plate = re.sub(r'[\s\-/.]', '', license_plate)
    match = re.match(r"^(\d{5,6})(\d{2,3})(\d{2})$", license_plate)
    if match:
        part1, part2, part3 = match.groups()
        return f"{part1} {part2} {part3}"
    return license_plate

# Clean extracted text
def clean_extracted_text(text: str) -> str:
    text = ''.join(c for c in text if c.isprintable())
    text = re.sub(r'\s*-\s*', '-', text)
    return text.strip()

# OCR from image or PDF
def extract_text_from_file(file):
    if file.filename.lower().endswith('.pdf'):
        try:
            pdf_reader = PyPDF2.PdfReader(file)
            text = "".join(page.extract_text() or '' for page in pdf_reader.pages)
            if text.strip():
                return text
            file.seek(0)
            images = convert_from_bytes(file.read())
            return ''.join(pytesseract.image_to_string(img, config='--psm 6') for img in images)
        except Exception as e:
            return str(e)
    else:
        try:
            image = Image.open(file)
            image = image.convert('L')
            return pytesseract.image_to_string(image, config='--psm 6')
        except Exception as e:
            return str(e)

# Main endpoint to extract and validate license plates
@app.route('/extract-number', methods=['POST'])
def extract_number():
    if 'file' not in request.files:
        return jsonify({"error": "Missing file parameter"}), 400

    file = request.files['file']

    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    if not allowed_file(file.filename):
        return jsonify({"error": "Invalid file type"}), 400

    try:
        text = extract_text_from_file(file)
        if not isinstance(text, str):
            return jsonify({"error": "Failed to extract text from file"}), 500

        text = clean_extracted_text(text)
        text = normalize_text_for_license(text)

        print(f"Extracted text: {text}")

        license_plates = re.findall(r'\d{5,6}[-\s/.]?\d{2,3}[-\s/.]?\d{2}', text)
        license_plates = [plate.replace(" ", "") for plate in license_plates]

        valid_plates = [
            format_license_plate_with_spaces(plate)
            for plate in license_plates
            if is_valid_algerian_license_plate(plate)
        ]

        if valid_plates:
            return jsonify({
                "valid": True,
                "plates": valid_plates
            })
        else:
            return jsonify({
                "valid": False,
                "message": "No valid Algerian license plates found"
            })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Endpoint to test license plate format manually
@app.route('/test-format', methods=['POST'])
def test_format():
    try:
        license_plate = request.form['plate']
        license_plate = normalize_text_for_license(license_plate)
        if is_valid_algerian_license_plate(license_plate):
            formatted_plate = format_license_plate_with_spaces(license_plate)
            return jsonify({"valid": True, "plate": formatted_plate})
        else:
            return jsonify({
                "valid": False,
                "plate": license_plate,
                "message": "Invalid format"
            }), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Optional: Simple HTML form to test upload
@app.route('/')
def index():
    return '''
    <!doctype html>
    <title>License Plate OCR</title>
    <h1>Upload an image or PDF</h1>
    <form method=post enctype=multipart/form-data action="/extract-number">
      <input type=file name=file>
      <input type=submit value=Upload>
    </form>
    '''

if __name__ == '__main__':
    app.run(debug=True)
