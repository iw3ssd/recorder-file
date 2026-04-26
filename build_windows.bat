@echo off
REM ============================================================
REM Build script per creare gli eseguibili Windows (.exe)
REM Richiede Python 3.10+ installato
REM ============================================================

echo === Installazione dipendenze ===
python -m pip install --upgrade pip
pip install pyinstaller requests beautifulsoup4

echo.
echo === Build WindRose ERC4 ===
pyinstaller wind_rose_erc4.spec --noconfirm
if errorlevel 1 (
    echo ERRORE: build WindRose fallito!
    pause
    exit /b 1
)

echo.
echo === Build ContestViewer ===
pyinstaller contest_viewer.spec --noconfirm
if errorlevel 1 (
    echo ERRORE: build ContestViewer fallito!
    pause
    exit /b 1
)

echo.
echo === Build completato! ===
echo Gli eseguibili si trovano nella cartella dist\
echo   - dist\WindRose_ERC4.exe
echo   - dist\ContestViewer.exe
echo.
pause
