import fitz  # PyMuPDF


def extract_text_from_pdf(uploaded_file) -> str:
    """
    Extract plain text from an uploaded PDF file.
    Works with Streamlit's UploadedFile object.
    """
    try:
        pdf_bytes = uploaded_file.read()
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")

        text = ""
        for page in doc:
            text += page.get_text()

        doc.close()

        if not text.strip():
            return None  # Scanned PDF with no extractable text

        return text.strip()

    except Exception as e:
        raise ValueError(f"Failed to extract text from PDF: {str(e)}")
