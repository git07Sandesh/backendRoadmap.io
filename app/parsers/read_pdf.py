import fitz  # PyMuPDF
from typing import List, IO
from app.parsers.types import TextItem


def read_pdf_from_stream(file_stream: IO[bytes]) -> List[TextItem]:
    """
    Reads a PDF from a file stream and extracts text items.
    """
    text_items: List[TextItem] = []
    try:
        doc = fitz.open(stream=file_stream, filetype="pdf")
    except Exception as e:
        print(f"Error opening PDF: {e}")
        return text_items

    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        # Using "dict" output provides rich details per span
        # A "block" contains "lines", and a "line" contains "spans"
        # A "span" is a contiguous run of text with the same font, size, color.
        blocks = page.get_text("dict", flags=fitz.TEXTFLAGS_TEXT)["blocks"]

        page_y_start = page.rect.y0  # Top of page

        for block in blocks:
            if block["type"] == 0:  # Text block
                for line_dict in block["lines"]:
                    current_line_items = []
                    for span_dict in line_dict["spans"]:
                        text = span_dict["text"]
                        # PyMuPDF coordinates: (0,0) is top-left.
                        # Original pdfjs coordinates: (0,0) is bottom-left.
                        # We need to be consistent. Let's stick to top-left (PyMuPDF default)
                        # and adjust logic if it relied on bottom-left.
                        # The original sorting `Math.round(b.y) - Math.round(a.y)` suggests it expected
                        # higher y for items appearing earlier (bottom-left origin).
                        # PyMuPDF y increases downwards.
                        # For now, let's use PyMuPDF's y. If sorting/grouping breaks, we might invert y.
                        x0, y0, x1, y1 = span_dict["bbox"]

                        # Original code replaces "-­‐" with "-". This is a soft hyphen issue.
                        # Python's str.replace might handle this if the encoding is right.
                        # Soft hyphens (U+00AD) might be invisible or render as hyphens.
                        new_text = text.replace("\u00ad", "")  # Remove soft hyphens

                        item = TextItem(
                            text=new_text,
                            x=x0,
                            y=y0,  # Using top y-coordinate
                            width=x1 - x0,
                            height=y1 - y0,
                            fontName=span_dict["font"],
                        )
                        current_line_items.append(item)

                    # The original filters out empty space textItem noise
                    # PyMuPDF spans are usually meaningful, but let's add a similar filter
                    current_line_items = [
                        ti for ti in current_line_items if ti.text.strip() != ""
                    ]
                    text_items.extend(current_line_items)

    # The original code has a commented out sort:
    # pageTextItems.sort((a, b) => Math.round(b.y) - Math.round(a.y));
    # This implies y increases upwards (bottom-left origin).
    # Since PyMuPDF has y increasing downwards (top-left origin),
    # an equivalent sort would be:
    # text_items.sort(key=lambda item: round(item.y))
    # This natural reading order sort is often implicitly handled by PyMuPDF's block/line ordering.
    # If explicit sort is needed:
    # text_items.sort(key=lambda item: (round(item.y), round(item.x)))

    return text_items
