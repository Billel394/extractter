from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename
import pytesseract
from PIL import Image
import PyPDF2
import re
# import io
# import os
# import tempfile
from pdf2image import convert_from_bytes

app = Flask(__name__)

# Allowed file extensions
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg'}

try:
    pytesseract.get_tesseract_version()
except EnvironmentError:
    print("Warning: Tesseract OCR not found. Image/PDF OCR will fail.")

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# def format_to_regex(number_format):
#     # Convert custom format to regex pattern
#     # Example: "###-##-####" -> r"\d{3}-\d{2}-\d{4}"
#     regex_pattern = re.escape(number_format).replace(r'\#', r'\d')
#     return re.compile(regex_pattern)
def format_to_regex(number_format):
    # Convert custom format to regex pattern
    # Example: "######-###-####" -> r"\d{6}\s*-?\s*\d{3}\s*-?\s*\d{4}"
    parts = number_format.split('-')
    regex_parts = []
    
    for part in parts:
        count = len(part)
        regex_parts.append(r'\d{' + str(count) + r'}\s*')
    
    regex_pattern = r'-?\s*'.join(regex_parts)
    return re.compile(regex_pattern)

def clean_extracted_text(text):
    # Remove extra spaces between digits
    text = re.sub(r'(\d)\s+(\d)', r'\1\2', text)
    # Normalize hyphens
    text = re.sub(r'\s*-\s*', '-', text)
    return text.strip()

def extract_text_from_file(file):
    # Check if file is PDF
    if file.filename.lower().endswith('.pdf'):
        try:
            # First try to extract text directly
            pdf_reader = PyPDF2.PdfReader(file)
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text()
            if text.strip():
                return text
            
            # If no text found, try OCR
            file.seek(0)
            images = convert_from_bytes(file.read())
            text = ""
            for image in images:
                text += pytesseract.image_to_string(image)
            return text
            
        except Exception as e:
            return str(e)
    
    # Handle image files
    else:
        try:
            # Open and preprocess image
            image = Image.open(file)
            
            # Convert to grayscale (improves OCR accuracy)
            image = image.convert('L')
            
            # Add sharpening/enhancement if needed
            # image = image.filter(ImageFilter.SHARPEN)
            
            # Extract text with explicit language
            text = pytesseract.image_to_string(
                image,
                lang='eng',  # Specify language
                config='--psm 6'  # Page segmentation mode
            )

            # image = Image.open(file)
            # x=pytesseract.image_to_string(image)
            print(f"Extracted text from image: {text}")
            # Perform OCR on the image
            return text
        except Exception as e:
            return str(e)

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
        # Convert custom format to regex
        pattern = format_to_regex(number_format)
        
        print(f"Regex pattern: {pattern}")

        # Extract text from file
        text = extract_text_from_file(file)
        if isinstance(text, str):
            text = clean_extracted_text(text)
        else:
            return jsonify({"error": "Failed to extract text from file"}), 500

        print(f"Extracted text: {text}")
        
        # Search for the first matching number
        match = pattern.search(text)

        print(f"Match found: {match}")
        
        if match:
            return jsonify({
                "found": True,
                "number": match.group(),
                "format": number_format
            })
        else:
            return jsonify({
                "found": False,
                "message": "No matching number found"
            })
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)