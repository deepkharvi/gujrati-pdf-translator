#!/usr/bin/env python3
"""
merge_pdfs.py - glue chunked translation outputs back into one PDF.

If you translated a 1000-page book in chunks (recommended - safer, and
easy to re-run just the chunk that failed), e.g.:

    python gujarati_pdf_translator.py book.pdf part1.pdf --start 0   --end 199
    python gujarati_pdf_translator.py book.pdf part2.pdf --start 200 --end 399
    python gujarati_pdf_translator.py book.pdf part3.pdf --start 400 --end 599
    python gujarati_pdf_translator.py book.pdf part4.pdf --start 600 --end 799
    python gujarati_pdf_translator.py book.pdf part5.pdf --start 800 --end 999

...note each "partN.pdf" is a FULL copy of the book with only its page
range translated (untouched pages keep the original Gujarati). Merge by
taking the right page range out of each part:

    python merge_pdfs.py final.pdf \
        part1.pdf:0-199 part2.pdf:200-399 part3.pdf:400-599 \
        part4.pdf:600-799 part5.pdf:800-999
"""
import sys
import fitz


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    output_path = sys.argv[1]
    out = fitz.open()

    for spec in sys.argv[2:]:
        path, page_range = spec.rsplit(":", 1)
        start, end = (int(x) for x in page_range.split("-"))
        src = fitz.open(path)
        out.insert_pdf(src, from_page=start, to_page=end)
        print(f"Added pages {start}-{end} from {path}")

    out.save(output_path, deflate=True)
    print(f"Saved merged file: {output_path} ({out.page_count} pages)")


if __name__ == "__main__":
    main()
