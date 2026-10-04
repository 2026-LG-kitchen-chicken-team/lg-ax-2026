"""Run with an existing Python that has pypdf; no dependency installation or OCR."""

import json
import sys

from pypdf import PdfReader


def main():
    reader = PdfReader(sys.argv[1])
    if reader.is_encrypted or len(reader.pages) > 200:
        raise ValueError("Encrypted or oversized document")
    pages = [page.extract_text() or "" for page in reader.pages]
    if not any(text.strip() for text in pages):
        raise ValueError("No text layer; OCR not executed")
    if sum(map(len, pages)) > 2_000_000:
        raise ValueError("Document text too large")
    print(json.dumps({"pages": pages, "parser": "pypdf", "parser_version": __import__("pypdf").__version__,
                      "ocr_used": False}, ensure_ascii=False))


if __name__ == "__main__":
    main()
