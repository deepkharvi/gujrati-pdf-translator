"""
gujarati_pdf_translator_gui.py
================================
Desktop GUI for the Gujarati -> English PDF translator.

Drag a PDF onto the window (or click Browse), pick where to save it,
and click Translate. Runs the same free/open-source engine as the
command-line tool (see core.py) — this is just a friendlier front end,
and it can be packaged into a standalone .exe (see BUILD_EXE.bat).

Run from source:
    pip install PyQt5 pymupdf pytesseract pillow deep-translator
    python gujarati_pdf_translator_gui.py
"""

import os
import sys
import traceback

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QFileDialog, QMessageBox,
    QProgressBar, QSpinBox, QGroupBox, QPlainTextEdit, QCheckBox
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QDragEnterEvent, QDropEvent

from core import translate_pdf, DEFAULT_DPI


def default_tesseract_path():
    """Best-guess Tesseract location on Windows, so most users don't have
    to type anything into the Tesseract path field."""
    candidates = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return ""


# ==========================================================================
# BACKGROUND WORKER (keeps the window responsive during a long translation)
# ==========================================================================
class TranslationWorker(QThread):
    page_done = pyqtSignal(int, int, str)   # page_index, total, mode
    finished_ok = pyqtSignal(dict)
    failed = pyqtSignal(str)

    def __init__(self, input_pdf, output_pdf, dpi, tesseract_cmd, pace):
        super().__init__()
        self.input_pdf = input_pdf
        self.output_pdf = output_pdf
        self.dpi = dpi
        self.tesseract_cmd = tesseract_cmd
        self.pace = pace
        self._cancel_requested = False

    def cancel(self):
        self._cancel_requested = True

    def run(self):
        try:
            result = translate_pdf(
                self.input_pdf, self.output_pdf,
                dpi=self.dpi, tesseract_cmd=self.tesseract_cmd or None,
                pace=self.pace,
                on_page_done=lambda pno, total, mode: self.page_done.emit(pno, total, mode),
                should_cancel=lambda: self._cancel_requested,
            )
            self.finished_ok.emit(result)
        except Exception:
            self.failed.emit(traceback.format_exc())


# ==========================================================================
# DROP TARGET (small reusable drag-and-drop file field)
# ==========================================================================
class DropLineEdit(QLineEdit):
    file_dropped = pyqtSignal(str)

    def __init__(self, placeholder, accept_ext=".pdf"):
        super().__init__()
        self.accept_ext = accept_ext
        self.setPlaceholderText(placeholder)
        self.setReadOnly(True)
        self.setAcceptDrops(True)
        self.setStyleSheet(
            "QLineEdit { padding: 10px; border: 2px dashed #94A3B8; "
            "border-radius: 8px; background-color: #F8FAFC; color: #475569; }"
        )

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            path = event.mimeData().urls()[0].toLocalFile()
            if path.lower().endswith(self.accept_ext):
                event.acceptProposedAction()
                self.setStyleSheet(
                    "QLineEdit { padding: 10px; border: 2px dashed #0052CC; "
                    "border-radius: 8px; background-color: #E8F4FD; color: #0052CC; }"
                )

    def dragLeaveEvent(self, event):
        self.setStyleSheet(
            "QLineEdit { padding: 10px; border: 2px dashed #94A3B8; "
            "border-radius: 8px; background-color: #F8FAFC; color: #475569; }"
        )

    def dropEvent(self, event: QDropEvent):
        path = event.mimeData().urls()[0].toLocalFile()
        self.setText(path)
        self.file_dropped.emit(path)
        self.dragLeaveEvent(event)


# ==========================================================================
# MAIN WINDOW
# ==========================================================================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.worker = None
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Gujarati → English PDF Translator")
        self.setGeometry(150, 150, 720, 620)
        self.setAcceptDrops(True)
        self.setStyleSheet("""
            QMainWindow { background-color: #F4F6F9; }
            QGroupBox {
                font-weight: bold; font-size: 10.5pt; color: #1F2937;
                border: 1px solid #D8DEE6; border-radius: 8px;
                margin-top: 14px; padding-top: 14px; background-color: #FFFFFF;
            }
            QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 6px; }
            QLabel { color: #374151; }
            QPushButton {
                padding: 8px 14px; border-radius: 6px; border: 1px solid #D1D5DB;
                background-color: #FFFFFF;
            }
            QPushButton:hover { background-color: #F0F4FF; }
            QPushButton:disabled { color: #9CA3AF; background-color: #F3F4F6; }
            QSpinBox, QLineEdit { padding: 5px; border: 1px solid #D1D5DB; border-radius: 5px; }
            QPlainTextEdit {
                background-color: #0B1220; color: #D1E7FF; border-radius: 6px;
                font-family: Consolas, monospace; font-size: 9.5pt;
            }
            QProgressBar {
                border: 1px solid #D1D5DB; border-radius: 6px; text-align: center; height: 22px;
                background-color: #EEF1F5;
            }
            QProgressBar::chunk { background-color: #0052CC; border-radius: 5px; }
        """)

        main = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(14)

        title = QLabel("Gujarati → English PDF Translator")
        f = QFont(); f.setPointSize(17); f.setBold(True)
        title.setFont(f)
        title.setStyleSheet("color: #111827;")
        layout.addWidget(title)

        subtitle = QLabel("Drag a Gujarati PDF below, or click Browse. Text-layer and scanned "
                           "pages are both handled — layout is preserved.")
        subtitle.setStyleSheet("color: #6B7280;")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        # --- Input file group ---
        input_group = QGroupBox("SOURCE PDF")
        input_layout = QVBoxLayout()
        self.input_drop = DropLineEdit("Drag a Gujarati PDF here, or click Browse...")
        self.input_drop.file_dropped.connect(self.on_input_chosen)
        input_layout.addWidget(self.input_drop)
        browse_row = QHBoxLayout()
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self.browse_input)
        browse_row.addWidget(browse_btn)
        browse_row.addStretch()
        input_layout.addLayout(browse_row)
        input_group.setLayout(input_layout)
        layout.addWidget(input_group)

        # --- Output group ---
        output_group = QGroupBox("SAVE ENGLISH PDF AS")
        output_layout = QHBoxLayout()
        self.output_input = QLineEdit()
        self.output_input.setReadOnly(True)
        output_layout.addWidget(self.output_input)
        output_btn = QPushButton("Choose...")
        output_btn.clicked.connect(self.browse_output)
        output_layout.addWidget(output_btn)
        output_group.setLayout(output_layout)
        layout.addWidget(output_group)

        # --- Options group ---
        options_group = QGroupBox("OPTIONS")
        options_layout = QVBoxLayout()

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Scan quality (DPI):"))
        self.dpi_spin = QSpinBox()
        self.dpi_spin.setRange(100, 600)
        self.dpi_spin.setValue(DEFAULT_DPI)
        self.dpi_spin.setSingleStep(50)
        row1.addWidget(self.dpi_spin)
        row1.addSpacing(20)
        row1.addWidget(QLabel("Pace between requests (sec):"))
        self.pace_spin = QSpinBox()
        self.pace_spin.setRange(0, 5)
        self.pace_spin.setValue(0)
        row1.addWidget(self.pace_spin)
        row1.addStretch()
        options_layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Tesseract path (only needed if not on PATH):"))
        self.tesseract_input = QLineEdit()
        self.tesseract_input.setText(default_tesseract_path())
        self.tesseract_input.setPlaceholderText(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
        row2.addWidget(self.tesseract_input)
        tess_browse = QPushButton("...")
        tess_browse.setFixedWidth(32)
        tess_browse.clicked.connect(self.browse_tesseract)
        row2.addWidget(tess_browse)
        options_layout.addLayout(row2)

        info = QLabel("ℹ️  Large files (100+ pages) can take a while — the free translation "
                       "service is paced to avoid rate limits. Progress is saved as it goes: "
                       "if you close the app or it crashes, running Translate again on the "
                       "same files picks up where it left off.")
        info.setWordWrap(True)
        info.setStyleSheet("background-color: #E8F4FD; padding: 8px 10px; border-radius: 5px; color: #0052CC;")
        options_layout.addWidget(info)

        options_group.setLayout(options_layout)
        layout.addWidget(options_group)

        # --- Log group ---
        log_group = QGroupBox("PROGRESS")
        log_layout = QVBoxLayout()
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setFixedHeight(140)
        log_layout.addWidget(self.log)
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        log_layout.addWidget(self.progress_bar)
        log_group.setLayout(log_layout)
        layout.addWidget(log_group, stretch=1)

        # --- Buttons ---
        btn_row = QHBoxLayout()
        self.translate_btn = QPushButton("Translate")
        self.translate_btn.setStyleSheet(
            "background-color: #0052CC; color: white; font-weight: bold; "
            "padding: 12px; font-size: 12pt; border: none;")
        self.translate_btn.clicked.connect(self.start_translation)
        btn_row.addWidget(self.translate_btn, stretch=1)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setStyleSheet(
            "background-color: #FFFFFF; color: #B91C1C; font-weight: bold; "
            "padding: 12px; font-size: 12pt; border: 1px solid #FCA5A5;")
        self.cancel_btn.clicked.connect(self.cancel_translation)
        self.cancel_btn.setEnabled(False)
        btn_row.addWidget(self.cancel_btn)

        layout.addLayout(btn_row)

        main.setLayout(layout)
        self.setCentralWidget(main)

    # ---- Drag-and-drop onto the whole window too ----
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            path = event.mimeData().urls()[0].toLocalFile()
            if path.lower().endswith(".pdf"):
                event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        path = event.mimeData().urls()[0].toLocalFile()
        self.input_drop.setText(path)
        self.on_input_chosen(path)

    # ---- File pickers ----
    def browse_input(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Gujarati PDF", "", "PDF files (*.pdf)")
        if path:
            self.input_drop.setText(path)
            self.on_input_chosen(path)

    def on_input_chosen(self, path):
        if not self.output_input.text():
            base, ext = os.path.splitext(path)
            self.output_input.setText(f"{base}_english.pdf")

    def browse_output(self):
        default = self.output_input.text() or "output_english.pdf"
        path, _ = QFileDialog.getSaveFileName(self, "Save English PDF As", default, "PDF files (*.pdf)")
        if path:
            self.output_input.setText(path)

    def browse_tesseract(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select tesseract.exe", "", "Executable (*.exe);;All files (*)")
        if path:
            self.tesseract_input.setText(path)

    # ---- Translation lifecycle ----
    def start_translation(self):
        input_pdf = self.input_drop.text().strip()
        output_pdf = self.output_input.text().strip()

        if not input_pdf or not os.path.exists(input_pdf):
            QMessageBox.warning(self, "No source file", "Please drag in or browse to a Gujarati PDF first.")
            return
        if not output_pdf:
            QMessageBox.warning(self, "No output location", "Please choose where to save the English PDF.")
            return

        self.log.clear()
        self.progress_bar.setValue(0)
        self.translate_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.append_log(f"Starting: {os.path.basename(input_pdf)}")

        self.worker = TranslationWorker(
            input_pdf, output_pdf,
            dpi=self.dpi_spin.value(),
            tesseract_cmd=self.tesseract_input.text().strip(),
            pace=float(self.pace_spin.value()) if self.pace_spin.value() else 0.15,
        )
        self.worker.page_done.connect(self.on_page_done)
        self.worker.finished_ok.connect(self.on_finished)
        self.worker.failed.connect(self.on_failed)
        self.worker.start()

    def cancel_translation(self):
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.append_log("Cancelling — finishing current page, then saving progress...")
            self.cancel_btn.setEnabled(False)

    def on_page_done(self, pno, total, mode):
        pct = int(((pno + 1) / total) * 100) if total else 0
        self.progress_bar.setValue(pct)
        self.append_log(f"page {pno + 1}/{total} [{mode}] done")

    def on_finished(self, result):
        self.translate_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        if result.get("cancelled"):
            self.append_log("Cancelled. Progress was saved — click Translate again to resume.")
            QMessageBox.information(self, "Cancelled",
                                     "Translation stopped early. Run Translate again on the "
                                     "same files to pick up where it left off.")
        else:
            self.append_log(f"Done. {result['pages_done']}/{result['total']} pages processed.")
            QMessageBox.information(self, "Done",
                                     f"Saved:\n{self.output_input.text()}")

    def on_failed(self, error_text):
        self.translate_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.append_log("ERROR — see details below:")
        self.append_log(error_text)
        QMessageBox.critical(self, "Translation failed",
                              "Something went wrong. Check the Progress log for details.\n\n"
                              "Common causes: Tesseract path not set correctly, or no internet "
                              "connection for translation.")

    def append_log(self, text):
        self.log.appendPlainText(text)


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
