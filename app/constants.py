# Not all constants from the original are directly used in the parser logic itself,
# but included for completeness if other parts of a larger app needed them.
PX_PER_PT = 4 / 3

LETTER_WIDTH_PT = 612
LETTER_HEIGHT_PT = 792
LETTER_WIDTH_PX = LETTER_WIDTH_PT * PX_PER_PT
LETTER_HEIGHT_PX = LETTER_HEIGHT_PT * PX_PER_PT

A4_WIDTH_PT = 595
A4_HEIGHT_PT = 842
A4_WIDTH_PX = A4_WIDTH_PT * PX_PER_PT
A4_HEIGHT_PX = A4_HEIGHT_PT * PX_PER_PT

DEBUG_RESUME_PDF_FLAG = None  # True or None
