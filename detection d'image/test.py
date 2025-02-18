import pytesseract

# Spécifie le chemin de Tesseract
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# Test avec une image (exemple)
print(pytesseract.image_to_string("test_image.png"))
