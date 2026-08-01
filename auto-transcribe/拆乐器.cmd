@echo off
chcp 65001 >nul
title instrument-split
"K:\Claude Projects\!!!ChordHUD\auto-transcribe\.venv\Scripts\python.exe" "K:\Claude Projects\!!!ChordHUD\auto-transcribe\sep_drop.py" %1
pause
