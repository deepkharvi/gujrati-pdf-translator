#!/usr/bin/env python3
"""
gujarati_pdf_translator.py
===========================
Translates a Gujarati PDF (text-layer, scanned, or a mix of both) into an
English PDF that keeps the ORIGINAL page layout: same page size, same
approximate position of every line of text, tables/images untouched.

100% free / open-source stack — nothing paid, no API key required:
    - PyMuPDF (fitz)      -> reads the real text layer + coordinates,
                              redraws pages, rasterizes scanned pages
    - Tesseract OCR       -> reads text OFF scanned/image pages (needs the
                              'guj' language pack)
    - deep-translator     -> free wrapper around Google Translate's public
                              web endpoint (no key, no billing)

--------------------------------------------------------------------------
INSTALL (Ubuntu / Debian / WSL)
--------------------------------------------------------------------------
    sudo apt-get install -y tesseract-ocr tesseract-ocr-guj
    pip install pymupdf pytesseract pillow deep-translator tqdm

INSTALL (Windows)
    1. Install Tesseract from:
       https://github.com/UB-Mannheim/tesseract/wiki
       During setup, tick the "Gujarati" additional language.
    2. pip install pymupdf pytesseract pillow deep-translator tqdm
    3. If tesseract.exe isn't on PATH, set TESSERACT_CMD below or via
       the --tesseract-cmd flag, e.g.
       --tesseract-cmd "C:\\Program Files\\Tesseract-OCR\\tesseract.exe"

--------------------------------------------------------------------------
USAGE
--------------------------------------------------------------------------
    # Whole 1000-page file in one go
    python gujarati_pdf_translator.py input.pdf output.pdf

    # Do it in chunks (recommended for very large files — safer, resumable)
    python gujarati_pdf_translator.py input.pdf output.pdf --start 0    --end 199
    python gujarati_pdf_translator.py input.pdf output.pdf --start 200  --end 399
    ... etc, then merge with merge_pdfs.py (included below as a snippet)

    # If it crashes / you Ctrl+C partway, just re-run the SAME command —
    # a checkpoint file (input.progress.json) remembers which pages are
    # already done and skips them.

--------------------------------------------------------------------------
HOW EACH PAGE IS HANDLED
--------------------------------------------------------------------------
    1. The page's real text layer is inspected.
    2. If it has a meaningful amount of real (selectable) Gujarati text,
       the page is treated as a TEXT page:
         - every text block is translated
         - the original Gujarati is painted over with a white box
         - the English translation is written back into the SAME box,
           auto-shrinking the font until it fits
       -> output stays a normal, still-selectable-text PDF page.

    3. Otherwise the page is treated as a SCANNED / IMAGE page:
         - the page is rendered to a high-res image
         - Tesseract OCR reads the Gujarati text + the exact bounding
           box of every line
         - each line is translated
         - the image is edited: original text boxed out in white,
           English text drawn in the same spot
         - the edited image becomes the new page
       -> output page looks the same, but is now a flattened image
          (expected for a scan — there is no original text layer to
          preserve here).

    A page can't always be judged perfectly; edge cases (very sparse
    text, watermarks, etc.) default to the safer OCR path.

--------------------------------------------------------------------------
LIMITATIONS (please read)
--------------------------------------------------------------------------
    - English is usually longer than Gujarati for the same sentence, so
      exact 1:1 layout is not always possible. The tool auto-shrinks
      font size to fit each text box; extremely tight boxes may still
      wrap or clip slightly.
    - deep-translator uses Google Translate's free public endpoint. It
      is unofficial and can be rate-limited if hammered too fast — the
      tool already paces + retries requests, but on a 1000-page book
      expect the run to take a while (this is normal, not a bug).
    - OCR quality depends on scan quality (resolution, skew, noise).
      300 DPI, straight scans give the best results.
    - Complex layouts (multi-column pages, tables with embedded text)
      are translated block-by-block; column order is usually preserved
      but not guaranteed for unusual layouts.
"""

import argparse
import os
import sys

from core import translate_pdf, DEFAULT_DPI


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("input_pdf")
    parser.add_argument("output_pdf")
    parser.add_argument("--start", type=int, default=0, help="First page to process (0-indexed, inclusive)")
    parser.add_argument("--end", type=int, default=None, help="Last page to process (0-indexed, inclusive). Default: last page.")
    parser.add_argument("--dpi", type=int, default=DEFAULT_DPI, help="Render DPI for scanned pages (default 300)")
    parser.add_argument("--ocr-lang", default="guj", help="Tesseract language code (default 'guj')")
    parser.add_argument("--src-lang", default="gu", help="Source language code for translation (default 'gu')")
    parser.add_argument("--tgt-lang", default="en", help="Target language code for translation (default 'en')")
    parser.add_argument("--pace", type=float, default=0.15, help="Seconds to sleep between translation calls (default 0.15)")
    parser.add_argument("--tesseract-cmd", default=None, help="Full path to tesseract executable (Windows users usually need this)")
    parser.add_argument("--engine", choices=["google", "mock"], default="google",
                         help="'google' = real free translation, 'mock' = offline dry-run for testing the pipeline")
    parser.add_argument("--force-ocr", action="store_true", help="Treat every page as scanned, even if it has a text layer")
    args = parser.parse_args()

    if not os.path.exists(args.input_pdf):
        sys.exit(f"Input file not found: {args.input_pdf}")

    def on_page_done(pno, total, mode):
        print(f"  page {pno + 1}/{total} [{mode}] done")

    print(f"Processing pages {args.start}-{args.end if args.end is not None else 'end'} "
          f"of {args.input_pdf} (engine={args.engine})")

    try:
        result = translate_pdf(
            args.input_pdf, args.output_pdf,
            start=args.start, end=args.end, dpi=args.dpi, ocr_lang=args.ocr_lang,
            src_lang=args.src_lang, tgt_lang=args.tgt_lang, pace=args.pace,
            tesseract_cmd=args.tesseract_cmd, engine=args.engine, force_ocr=args.force_ocr,
            on_page_done=on_page_done,
        )
    except KeyboardInterrupt:
        print("\nInterrupted — progress up to the last checkpoint was saved.")
        sys.exit(1)

    print(f"Saved: {args.output_pdf}")
    print(f"Pages done: {result['pages_done']} / {result['total']}")
    print(f"Progress checkpoint: {args.output_pdf}.progress.json")
    print(f"Translation cache:   {args.input_pdf}.translation_cache.json")


if __name__ == "__main__":
    main()
