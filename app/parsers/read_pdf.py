import fitz  # PyMuPDF
from typing import List, IO
from app.parsers.types import TextItem  # Your Pydantic TextItem


def read_pdf_from_stream(file_stream: IO[bytes]) -> List[TextItem]:
    extracted_text_items: List[TextItem] = []
    try:
        doc = fitz.open(stream=file_stream, filetype="pdf")
    except Exception as e:
        print(f"Error opening PDF with PyMuPDF: {e}")
        return extracted_text_items

    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        # TEXTFLAGS_WORDS might be useful later if span-level is too granular or not granular enough
        # For now, default span extraction used by TEXTFLAGS_TEXT is fine.
        # TEXT_PRESERVE_LIGATURES and TEXT_PRESERVE_WHITESPACE are good for accurate text.
        blocks = page.get_text(
            "dict",
            flags=fitz.TEXTFLAGS_TEXT
            | fitz.TEXT_PRESERVE_LIGATURES
            | fitz.TEXT_PRESERVE_WHITESPACE,
        )["blocks"]

        current_page_items: List[TextItem] = []
        for block in blocks:
            if block["type"] == 0:  # Text block
                for line_dict in block["lines"]:
                    for span_dict in line_dict["spans"]:
                        text = span_dict["text"]
                        cleaned_text = text.replace("\u00ad", "")  # Remove soft hyphens

                        if not cleaned_text.strip():
                            continue

                        x0, y0, x1, y1 = span_dict["bbox"]

                        font_name = span_dict["font"]
                        # Simplify font name by removing subset prefix like "ABCDEF+"
                        if "+" in font_name and len(font_name.split("+", 1)) > 1:
                            font_name = font_name.split("+", 1)[1]
                        # Further cleanups (e.g., remove version numbers if any) could be added if needed

                        item = TextItem(
                            text=cleaned_text,
                            x=float(x0),
                            y=float(y0),
                            width=float(x1 - x0),
                            height=float(y1 - y0),
                            fontName=font_name,
                        )
                        current_page_items.append(item)

        # Sort items on the page by their y then x coordinates for natural reading order.
        # Rounding y helps group items on the same visual line more effectively.
        # Using a small tolerance for y comparison might be better than exact rounding if font sizes vary slightly.
        # For now, round to nearest integer for y, then use x.
        current_page_items.sort(key=lambda item: (round(item.y), item.x))
        extracted_text_items.extend(current_page_items)

    return extracted_text_items
