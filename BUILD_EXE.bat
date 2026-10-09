@echo off
REM ==========================================================================
REM BUILD_EXE.bat
REM Packages gujarati_pdf_translator_gui.py into a single standalone
REM Windows .exe using PyInstaller. Run this ON WINDOWS, in this folder
REM (the same one that has core.py and gujarati_pdf_translator_gui.py).
REM ==========================================================================

echo Installing/upgrading required packages...
pip install --upgrade pyinstaller PyQt5 pymupdf pytesseract pillow deep-translator

echo.
echo Building GujaratiPdfTranslator.exe ...
pyinstaller --onefile --windowed --name "GujaratiPdfTranslator" ^
    --hidden-import=PyQt5.sip ^
    gujarati_pdf_translator_gui.py

echo.
echo ==========================================================================
echo Done. Your .exe is at:  dist\GujaratiPdfTranslator.exe
echo.
echo NOTE: Tesseract OCR itself is NOT bundled into this .exe (it's a
echo separate program the tool calls out to). Anyone running this .exe
echo still needs Tesseract + the Gujarati language pack installed
echo separately — see README.md.
echo ==========================================================================
pause
