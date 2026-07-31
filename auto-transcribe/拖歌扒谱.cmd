@echo off
chcp 65001 >nul
title auto-transcribe
"K:\Claude Projects\!!!ChordHUD\auto-transcribe\.venv\Scripts\python.exe" "K:\Claude Projects\!!!ChordHUD\auto-transcribe\drag_drop.py" %1
pause
