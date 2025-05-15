import fitz
import re  # For OCR cleaning
from typing import List, IO
from app.parsers.types import TextItem


def clean_ocr_artifacts(text: str) -> str:
    # Remove common OCR noise patterns like [§], [र्ड], single non-alphanumeric chars if they seem like bullets
    # This needs to be careful not to remove legitimate symbols.
    # For the sample: [§], [@] (if it's from OCR of image icon), ◦
    cleaned = re.sub(r"\[§\]|\[@\]|◦", "", text)  # Add more patterns as needed
    # Replace multiple spaces with a single space
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def read_pdf_from_stream(file_stream: IO[bytes]) -> List[TextItem]:
    extracted_text_items: List[TextItem] = []
    try:
        doc = fitz.open(stream=file_stream, filetype="pdf")
    except Exception as e:
        print(f"Error opening PDF with PyMuPDF: {e}")
        return extracted_text_items

    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        blocks = page.get_text(
            "dict",
            flags=fitz.TEXTFLAGS_TEXT
            | fitz.TEXT_PRESERVE_LIGATURES
            | fitz.TEXT_PRESERVE_WHITESPACE,
        )["blocks"]

        current_page_items: List[TextItem] = []
        for block in blocks:
            if block["type"] == 0:
                for line_dict in block["lines"]:
                    for span_dict in line_dict["spans"]:
                        text = span_dict["text"]
                        cleaned_text_soft_hyphen = text.replace("\u00ad", "")
                        final_cleaned_text = clean_ocr_artifacts(
                            cleaned_text_soft_hyphen
                        )  # Apply OCR cleaning

                        if not final_cleaned_text.strip():
                            continue

                        x0, y0, x1, y1 = span_dict["bbox"]
                        font_name = span_dict["font"]
                        if "+" in font_name and len(font_name.split("+", 1)) > 1:
                            font_name = font_name.split("+", 1)[1]

                        item = TextItem(
                            text=final_cleaned_text,  # Use fully cleaned text
                            x=float(x0),
                            y=float(y0),
                            width=float(x1 - x0),
                            height=float(y1 - y0),
                            fontName=font_name,
                        )
                        current_page_items.append(item)

        current_page_items.sort(key=lambda item: (round(item.y), item.x))
        extracted_text_items.extend(current_page_items)

    return extracted_text_items
