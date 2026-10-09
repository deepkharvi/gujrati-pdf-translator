# Gujarati → English PDF Translator

Translates a Gujarati PDF (real text, scanned images, or a mix of both)
into an English PDF that keeps the **same page layout** — same page
size, and English text placed in roughly the same spot as the original
Gujarati it replaces.

Everything used is **free and open-source** — no paid API, no API key.

There are two ways to use it:
- **Command line** (`gujarati_pdf_translator.py`) — best for very large
  files, chunked/resumable batch runs.
- **Desktop app with drag-and-drop** (`gujarati_pdf_translator_gui.py`)
  — a window where you drag a PDF in, pick where to save it, and click
  Translate. Can be packaged into a standalone `.exe` (see Section 5).

Both share the same engine (`core.py`), so results are identical.

| Job | Tool used |
|---|---|
| Read real/selectable text + coordinates | **PyMuPDF** (`fitz`) |
| Read text off scanned/image pages | **Tesseract OCR** + Gujarati language pack |
| Translate Gujarati → English | **deep-translator** (free Google Translate web front-end, no key) |

## 1. Install

**Ubuntu / Debian / WSL:**
```bash
sudo apt-get install -y tesseract-ocr tesseract-ocr-guj
pip install pymupdf pytesseract pillow deep-translator tqdm
```

**Windows:**
1. Install Tesseract from https://github.com/UB-Mannheim/tesseract/wiki
   — during setup, tick the **Gujarati** additional language.
2. `pip install pymupdf pytesseract pillow deep-translator tqdm`
3. If `tesseract.exe` isn't on your PATH, pass it explicitly:
   `--tesseract-cmd "C:\Program Files\Tesseract-OCR\tesseract.exe"`

**macOS:**
```bash
brew install tesseract tesseract-lang   # includes Gujarati
pip install pymupdf pytesseract pillow deep-translator tqdm
```

Additionally, for the GUI:
```bash
pip install PyQt5
```

## 2. Basic usage (command line)

```bash
python gujarati_pdf_translator.py input.pdf output.pdf
```

That's it for a small file. It auto-detects, per page, whether to use
the fast text-layer path or the OCR path.

## 2b. Basic usage (desktop app)

```bash
python gujarati_pdf_translator_gui.py
```

A window opens. Drag your Gujarati PDF onto the dashed box (or click
Browse), choose where to save the English version, and click
**Translate**. A live log and progress bar show page-by-page status.
Click **Cancel** any time — progress is saved, and clicking Translate
again on the same files resumes where it left off.

If Tesseract isn't on your system PATH, fill in its path in the
"Tesseract path" field (the app auto-detects the common Windows install
locations, so this is often already filled in for you).

## 3. For a 1000-page book (recommended approach)

Doing 1000 pages in one run is *possible* but risky — a single network
hiccup 800 pages in shouldn't cost you the whole run. Two safety nets
are built in:

**a) Automatic resume.** If the script crashes or you `Ctrl+C`, just run
the exact same command again — a `input.pdf.progress.json` checkpoint
file remembers which pages are already done and skips them. A
`input.pdf.translation_cache.json` file also remembers every phrase
already translated, so repeated headers/footers/page numbers only cost
one network call for the whole book.

**b) Manual chunking**, if you'd rather split the work up explicitly
(e.g. run overnight in batches, or split across page ranges):

```bash
python gujarati_pdf_translator.py book.pdf part1.pdf --start 0   --end 199
python gujarati_pdf_translator.py book.pdf part2.pdf --start 200 --end 399
python gujarati_pdf_translator.py book.pdf part3.pdf --start 400 --end 599
python gujarati_pdf_translator.py book.pdf part4.pdf --start 600 --end 799
python gujarati_pdf_translator.py book.pdf part5.pdf --start 800 --end 999
```

Each `partN.pdf` is a full copy of the book with only its slice
translated. Stitch the final book together with the included helper:

```bash
python merge_pdfs.py final.pdf \
    part1.pdf:0-199 part2.pdf:200-399 part3.pdf:400-599 \
    part4.pdf:600-799 part5.pdf:800-999
```

## 4. Packaging the desktop app as a standalone .exe

If you'd rather hand someone a single double-clickable program instead
of a Python script, package the GUI with PyInstaller:

**On Windows**, in the folder with `core.py` and
`gujarati_pdf_translator_gui.py`, just run:

```bat
BUILD_EXE.bat
```

This installs PyInstaller if needed and produces
`dist\GujaratiPdfTranslator.exe` — a single file that runs without
Python installed on the target machine.

**Important:** Tesseract OCR itself is a separate program, not bundled
into the `.exe`. Anyone running the `.exe` still needs Tesseract + the
Gujarati language pack installed on their machine (Section 1) — the
app will ask for its path if it can't find it automatically.

*(PyInstaller builds for whatever OS it runs on, so this step has to
happen on a Windows machine to produce a Windows `.exe`.)*

## 5. How a page is handled

1. The page's real text layer is checked for a meaningful amount of
   Gujarati text.
2. **Has real text →** each text block is translated, the original
   Gujarati is painted over with white, and the English translation is
   written back into the same box (auto-shrinking the font to fit).
   Output stays a normal, selectable-text PDF page.
3. **No real text (a scan) →** the page is rendered to a high-res
   image, Tesseract OCR reads the Gujarati text and its exact position,
   each line is translated, and the image is edited in place (white-out
   + English text drawn in the same spot). The edited image becomes the
   new page.

## 6. Useful flags (command line)

| Flag | Meaning |
|---|---|
| `--start N --end M` | Only process pages N through M (0-indexed) |
| `--dpi 300` | Resolution for rendering scanned pages (higher = better OCR, slower) |
| `--ocr-lang guj` | Tesseract language code |
| `--pace 0.15` | Seconds between translation requests (raise this if you get rate-limited) |
| `--force-ocr` | Treat every page as a scan (use if a page's text layer is garbled/unusable) |
| `--engine mock` | Offline dry run — skips real translation, useful only for testing the pipeline itself |
| `--tesseract-cmd PATH` | Point at your tesseract executable if it's not on PATH |

## 7. Realistic expectations

- **Speed:** each translation call is paced (`--pace`, default 0.15s)
  and retried with backoff if the free endpoint briefly rate-limits
  you. A 1000-page book with a few lines each will likely take a few
  hours end-to-end — this is normal for a free, unofficial endpoint,
  not a bug. Run it in the chunks above and let it work in the
  background.
- **Layout:** English is usually longer than Gujarati for the same
  sentence, so pixel-perfect layout isn't always possible. The tool
  auto-shrinks the font to fit each original text box; extremely tight
  boxes may still wrap or clip a little.
- **Scanned pages become images:** there's no original text layer to
  preserve on a scan, so those output pages are flattened images
  (visually identical layout, but not text-selectable). Text-layer
  pages stay selectable.
- **OCR quality** depends on scan quality — 300 DPI, straight,
  non-blurry scans give much better results than crumpled/skewed ones.
