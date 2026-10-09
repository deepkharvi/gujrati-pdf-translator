"""
core.py - shared Gujarati -> English PDF translation engine.

Used by both gujarati_pdf_translator.py (command line) and
gujarati_pdf_translator_gui.py (drag-and-drop desktop app). Keeping the
actual logic in one place means both interfaces always behave
identically and a bug fix only has to happen once.

See README.md for what this does and how to install its dependencies.
"""

import json
import os
import re
import sys
import time

import fitz  # PyMuPDF
import pytesseract
from PIL import Image, ImageDraw, ImageFont
from deep_translator import GoogleTranslator

# --------------------------------------------------------------------------
# CONFIG
# --------------------------------------------------------------------------
GUJARATI_RANGE = re.compile(r"[\u0A80-\u0AFF]")
DEFAULT_DPI = 300
ENGLISH_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "C:\\Windows\\Fonts\\arial.ttf",
]


def find_english_font():
    for path in ENGLISH_FONT_CANDIDATES:
        if os.path.exists(path):
            return path
    return None  # PIL will fall back to its built-in bitmap font


ENGLISH_FONT_PATH = find_english_font()


# --------------------------------------------------------------------------
# TRANSLATION LAYER (cached, retried, swappable)
# --------------------------------------------------------------------------
class Translator:
    """Thin wrapper around deep-translator with an on-disk cache so that
    (a) repeated phrases (running headers, page numbers, etc.) cost only
    one network call across the whole book, and (b) a crashed run
    doesn't lose already-paid-for translations."""

    def __init__(self, cache_path, src="gu", tgt="en", pace=0.15,
                 mock=False):
        self.cache_path = cache_path
        self.src = src
        self.tgt = tgt
        self.pace = pace
        self.mock = mock
        self.cache = {}
        if cache_path and os.path.exists(cache_path):
            with open(cache_path, "r", encoding="utf-8") as f:
                self.cache = json.load(f)
        self._backend = None if mock else GoogleTranslator(source=src, target=tgt)
        self._dirty = 0

    def save(self):
        if not self.cache_path:
            return
        with open(self.cache_path, "w", encoding="utf-8") as f:
            json.dump(self.cache, f, ensure_ascii=False)
        self._dirty = 0

    def translate(self, text):
        text = text.strip()
        if not text:
            return ""
        if text in self.cache:
            return self.cache[text]

        if self.mock:
            # Offline stand-in used only for testing the pipeline without
            # network access.
            result = f"[EN] {text}"
        else:
            result = self._retry_translate(text)

        self.cache[text] = result
        self._dirty += 1
        if self._dirty >= 20:
            self.save()
        return result

    def _retry_translate(self, text, max_retries=5):
        delay = 1.0
        last_err = None
        # Google's endpoint has a practical length limit; split very long
        # blocks on sentence-ish boundaries and translate in pieces.
        chunks = self._chunk_text(text, limit=4500)
        for attempt in range(max_retries):
            try:
                pieces = [self._backend.translate(c) or "" for c in chunks]
                time.sleep(self.pace)
                return " ".join(pieces).strip()
            except Exception as e:  # noqa: BLE001 - network lib raises many types
                last_err = e
                time.sleep(delay)
                delay = min(delay * 2, 20)
        print(f"  [warn] translation failed after retries, leaving original: {last_err}",
              file=sys.stderr)
        return text

    @staticmethod
    def _chunk_text(text, limit):
        if len(text) <= limit:
            return [text]
        parts, current = [], ""
        for sentence in re.split(r"(?<=[.।!?\n])\s+", text):
            if len(current) + len(sentence) + 1 > limit:
                if current:
                    parts.append(current)
                current = sentence
            else:
                current = f"{current} {sentence}".strip()
        if current:
            parts.append(current)
        return parts or [text[:limit]]


# --------------------------------------------------------------------------
# PAGE-TYPE DETECTION
# --------------------------------------------------------------------------
def page_has_real_text(page, min_gujarati_chars=15):
    text = page.get_text("text")
    gujarati_chars = len(GUJARATI_RANGE.findall(text))
    return gujarati_chars >= min_gujarati_chars


# --------------------------------------------------------------------------
# TEXT-LAYER PAGE HANDLING
# --------------------------------------------------------------------------
def process_text_page(page, translator):
    blocks = page.get_text("dict")["blocks"]
    for block in blocks:
        if block.get("type") != 0:  # 0 = text block, 1 = image block
            continue
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                original = span["text"]
                if not original.strip() or not GUJARATI_RANGE.search(original):
                    continue

                bbox = fitz.Rect(span["bbox"])
                translated = translator.translate(original)
                if not translated:
                    continue

                # Cover the original Gujarati text.
                page.draw_rect(bbox, color=None, fill=(1, 1, 1), overlay=True)

                # Write the English text back into the same box, shrinking
                # the font until it fits.
                fontsize = max(span.get("size", 11), 6)
                inserted = False
                while fontsize >= 5:
                    overflow = page.insert_textbox(
                        bbox, translated,
                        fontsize=fontsize, fontname="helv",
                        color=(0, 0, 0), align=0,
                    )
                    if overflow >= 0:
                        inserted = True
                        break
                    fontsize -= 0.5
                if not inserted:
                    # Last resort: force it in at the smallest size, may clip.
                    page.insert_textbox(
                        bbox, translated, fontsize=5,
                        fontname="helv", color=(0, 0, 0), align=0,
                    )


# --------------------------------------------------------------------------
# SCANNED / IMAGE PAGE HANDLING
# --------------------------------------------------------------------------
def group_ocr_lines(ocr_data):
    """Groups Tesseract's word-level output into line-level boxes."""
    lines = {}
    n = len(ocr_data["text"])
    for i in range(n):
        word = ocr_data["text"][i].strip()
        if not word:
            continue
        key = (ocr_data["block_num"][i], ocr_data["par_num"][i], ocr_data["line_num"][i])
        x, y, w, h = (ocr_data["left"][i], ocr_data["top"][i],
                      ocr_data["width"][i], ocr_data["height"][i])
        if key not in lines:
            lines[key] = {"words": [], "x0": x, "y0": y, "x1": x + w, "y1": y + h}
        entry = lines[key]
        entry["words"].append(word)
        entry["x0"] = min(entry["x0"], x)
        entry["y0"] = min(entry["y0"], y)
        entry["x1"] = max(entry["x1"], x + w)
        entry["y1"] = max(entry["y1"], y + h)
    return [
        {"text": " ".join(v["words"]), "bbox": (v["x0"], v["y0"], v["x1"], v["y1"])}
        for v in lines.values()
    ]


def fit_font_size(draw, text, box_w, box_h, font_path, max_size=48):
    size = max_size
    while size > 6:
        font = ImageFont.truetype(font_path, size) if font_path else ImageFont.load_default()
        bbox = draw.textbbox((0, 0), text, font=font)
        w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
        if w <= box_w and h <= box_h:
            return font
        size -= 1
    return ImageFont.truetype(font_path, 6) if font_path else ImageFont.load_default()


def process_scanned_page(doc, page, translator, dpi, ocr_lang, tesseract_cmd=None):
    if tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

    zoom = dpi / 72
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)

    ocr_data = pytesseract.image_to_data(img, lang=ocr_lang, output_type=pytesseract.Output.DICT)
    lines = group_ocr_lines(ocr_data)

    draw = ImageDraw.Draw(img)
    for line in lines:
        original = line["text"]
        if not GUJARATI_RANGE.search(original):
            continue
        translated = translator.translate(original)
        if not translated:
            continue

        x0, y0, x1, y1 = line["bbox"]
        pad = 2
        draw.rectangle([x0 - pad, y0 - pad, x1 + pad, y1 + pad], fill="white")

        font = fit_font_size(draw, translated, x1 - x0, y1 - y0, ENGLISH_FONT_PATH)
        draw.text((x0, y0), translated, fill="black", font=font)

    # Replace the page with the edited image, at the original page size.
    rect = page.rect
    old_index = page.number
    out_pixmap = fitz.Pixmap(fitz.csRGB, img.width, img.height, img.tobytes(), 0)
    new_page = doc.new_page(pno=old_index, width=rect.width, height=rect.height)
    new_page.insert_image(rect, pixmap=out_pixmap)
    doc.delete_page(old_index + 1)  # remove the old page (now shifted by +1)


# --------------------------------------------------------------------------
# CHECKPOINTING (resume support for very large books)
# --------------------------------------------------------------------------
def load_checkpoint(path):
    if path and os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()


def save_checkpoint(path, done_pages):
    if not path:
        return
    with open(path, "w", encoding="utf-8") as f:
        json.dump(sorted(done_pages), f)


def safe_save(doc, output_path):
    """Saves via a temp file + atomic replace, so this works whether `doc`
    was opened fresh from the input file or re-opened from a
    partially-built output file of the same name (resume case)."""
    tmp_path = output_path + ".tmp"
    doc.save(tmp_path, deflate=True)
    os.replace(tmp_path, output_path)


# --------------------------------------------------------------------------
# HIGH-LEVEL ENTRY POINT (shared by CLI and GUI)
# --------------------------------------------------------------------------
class Cancelled(Exception):
    """Raised internally to unwind cleanly when the caller asks to stop."""


def translate_pdf(
    input_pdf, output_pdf, *,
    start=0, end=None, dpi=DEFAULT_DPI, ocr_lang="guj",
    src_lang="gu", tgt_lang="en", pace=0.15, tesseract_cmd=None,
    engine="google", force_ocr=False,
    checkpoint_path=None, cache_path=None,
    on_page_done=None, should_cancel=None,
):
    """Translates input_pdf -> output_pdf.

    on_page_done(page_index_0based, total_pages, mode) is called after
    every page ("text" or "ocr" mode) so a caller (CLI or GUI) can show
    progress.

    should_cancel() is polled between pages; if it returns True, the
    function saves whatever is done so far and stops cleanly.

    Returns a dict: {"pages_done": int, "total": int, "cancelled": bool}
    """
    if checkpoint_path is None and output_pdf:
        checkpoint_path = output_pdf + ".progress.json"
    if cache_path is None and input_pdf:
        cache_path = input_pdf + ".translation_cache.json"

    done_pages = load_checkpoint(checkpoint_path)
    translator = Translator(cache_path, src=src_lang, tgt=tgt_lang,
                             pace=pace, mock=(engine == "mock"))

    if os.path.exists(output_pdf):
        doc = fitz.open(output_pdf)
    else:
        doc = fitz.open(input_pdf)

    end_page = end if end is not None else doc.page_count - 1
    end_page = min(end_page, doc.page_count - 1)

    cancelled = False
    try:
        for pno in range(start, end_page + 1):
            if should_cancel and should_cancel():
                cancelled = True
                break
            if pno in done_pages:
                continue

            page = doc[pno]
            if not force_ocr and page_has_real_text(page):
                mode = "text"
                process_text_page(page, translator)
            else:
                mode = "ocr"
                process_scanned_page(doc, page, translator, dpi, ocr_lang, tesseract_cmd)

            done_pages.add(pno)
            if on_page_done:
                on_page_done(pno, doc.page_count, mode)

            if pno % 5 == 0:
                safe_save(doc, output_pdf)
                save_checkpoint(checkpoint_path, done_pages)
                translator.save()
    finally:
        safe_save(doc, output_pdf)
        save_checkpoint(checkpoint_path, done_pages)
        translator.save()
        page_count = doc.page_count
        doc.close()

    return {"pages_done": len(done_pages), "total": page_count, "cancelled": cancelled}
