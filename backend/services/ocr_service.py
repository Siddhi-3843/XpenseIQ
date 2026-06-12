def validate_image_file(file_bytes: bytes, content_type: str) -> dict:
    """
    Validates a file before sending it to OCR.
    Prevents processing empty, blank, or invalid files.
    Returns a dict with is_valid and reason.
    """
    import numpy as np

    # Check 1 — File must not be empty
    if len(file_bytes) < 5000:
        return {
            "is_valid": False,
            "reason": "File is too small or empty. Please upload a valid receipt image."
        }

    # Check 2 — For images, check if it's completely blank
    if content_type in ["image/jpeg", "image/png", "image/jpg", "image/webp"]:
        try:
            image = Image.open(io.BytesIO(file_bytes))
            image = image.convert("RGB")

            # Convert to numpy array and check variance
            img_array = np.array(image)

            # If variance is very low, image is blank or single color
            variance = np.var(img_array)
            if variance < 100:
                return {
                    "is_valid": False,
                    "reason": "Image appears to be blank or empty. Please upload a clear receipt photo."
                }

        except Exception:
            return {
                "is_valid": False,
                "reason": "Could not read the image file. Please upload a valid JPG or PNG."
            }

    # Check 3 — PDF must have readable content
    if content_type == "application/pdf":
        if len(file_bytes) < 10000:
            return {
                "is_valid": False,
                "reason": "PDF file appears to be empty or corrupted."
            }

    return {"is_valid": True, "reason": None}

# ocr_service.py
# Handles OCR for images and PDFs.
# Supports JPG, PNG, WEBP, TIFF, BMP and PDF formats.
# Works on both Windows (local) and Linux (Railway/Docker).

import pytesseract
from PIL import Image
import io
import re
import platform

# Tell pytesseract where Tesseract is installed on Windows
# On Linux (Railway), Tesseract is in PATH automatically
if platform.system() == "Windows":
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'


def extract_text_from_image(image_bytes: bytes) -> dict:
    """
    Takes raw image bytes and extracts text using Tesseract OCR.
    Supports JPG, PNG, WEBP, TIFF, BMP formats.
    """

    image = Image.open(io.BytesIO(image_bytes))
    image = image.convert("RGB")

    raw_text = pytesseract.image_to_string(image, lang="eng")

    from pytesseract import Output
    data = pytesseract.image_to_data(image, output_type=Output.DICT)

    confidences = [
        int(c) for c in data["conf"]
        if str(c).strip() != "-1" and str(c).strip() != ""
    ]
    avg_confidence = sum(confidences) / len(confidences) if confidences else 0
    confidence_score = round(avg_confidence / 100, 2)

    cleaned_text = clean_ocr_text(raw_text)

    return {
        "raw_text": raw_text,
        "cleaned_text": cleaned_text,
        "confidence_score": confidence_score,
        "word_count": len(cleaned_text.split()),
        "source": "image"
    }


def extract_text_from_pdf(pdf_bytes: bytes) -> dict:
    """
    Extracts text from a PDF file.
    Uses poppler to convert each page to an image,
    then runs Tesseract OCR on each page.
    Works on Windows locally and Linux on Railway.
    """
    try:
        from pdf2image import convert_from_bytes

        # On Windows use the local poppler path
        # On Linux (Railway/Docker) poppler is installed via apt-get
        # and is automatically available in PATH — pass None
        if platform.system() == "Windows":
            poppler_path = r"C:\Users\ASUS\Downloads\Release-26.02.0-0\poppler\Library\bin"
        else:
            poppler_path = None

        images = convert_from_bytes(
            pdf_bytes,
            poppler_path=poppler_path
        )

        all_text = ""
        all_confidences = []

        for i, image in enumerate(images):
            image = image.convert("RGB")
            page_text = pytesseract.image_to_string(image, lang="eng")
            all_text += f"\n--- Page {i+1} ---\n{page_text}"

            from pytesseract import Output
            data = pytesseract.image_to_data(image, output_type=Output.DICT)
            confidences = [
                int(c) for c in data["conf"]
                if str(c).strip() != "-1" and str(c).strip() != ""
            ]
            if confidences:
                all_confidences.extend(confidences)

        avg_confidence = sum(all_confidences) / len(all_confidences) if all_confidences else 0
        confidence_score = round(avg_confidence / 100, 2)

        cleaned = clean_ocr_text(all_text)

        return {
            "raw_text": all_text,
            "cleaned_text": cleaned,
            "confidence_score": confidence_score,
            "word_count": len(cleaned.split()),
            "pages": len(images),
            "source": "pdf"
        }

    except Exception as e:
        return {
            "error": str(e),
            "raw_text": "",
            "cleaned_text": "",
            "confidence_score": 0.0,
            "word_count": 0,
            "source": "pdf"
        }


def clean_ocr_text(text: str) -> str:
    """
    Cleans up raw OCR output.
    Removes empty lines, fixes common OCR mistakes,
    and normalizes whitespace.
    """

    lines = text.split("\n")
    non_empty_lines = [line.strip() for line in lines if line.strip()]
    cleaned = "\n".join(non_empty_lines)

    cleaned = cleaned.replace("|", "I")
    cleaned = cleaned.replace("{}", "0")
    cleaned = re.sub(r' +', ' ', cleaned)

    return cleaned