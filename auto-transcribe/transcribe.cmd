@echo off
rem Always use the venv CPython — the `python` on PATH is MSYS2 MinGW and
rem cannot run this pipeline.
"%~dp0.venv\Scripts\python.exe" "%~dp0transcribe.py" %*
