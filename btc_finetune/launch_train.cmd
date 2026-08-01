@echo off
rem Detached launcher for the BTC chord fine-tune. Appends to train.log so
rem restarts (auto-resume from latest.pt) keep the full history.
cd /d "K:\Claude Projects\!!!ChordHUD\btc_finetune"
"K:\Claude Projects\!!!ChordHUD\auto-transcribe\.venv\Scripts\python.exe" -u train.py >> train.log 2>&1
