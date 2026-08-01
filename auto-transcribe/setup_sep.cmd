@echo off
rem One-time setup for the instrument-separation engine (.venv-sep + MSST).
rem Safe to re-run. Needs internet; ~1GB of downloads on first model use.
chcp 65001 >nul
setlocal
set ROOT=%~dp0

if not exist "%ROOT%.venv-sep\Scripts\python.exe" (
  echo creating .venv-sep ...
  py -3.12 -m venv "%ROOT%.venv-sep"
)

"%ROOT%.venv-sep\Scripts\python.exe" -m pip install --upgrade pip
"%ROOT%.venv-sep\Scripts\python.exe" -m pip install torch==2.5.1 torchaudio==2.5.1 --index-url https://download.pytorch.org/whl/cpu
"%ROOT%.venv-sep\Scripts\python.exe" -m pip install numpy librosa soundfile einops rotary-embedding-torch beartype omegaconf ml_collections tqdm pyyaml loralib

if not exist "%ROOT%msst\inference.py" (
  echo cloning MSST ...
  git clone --depth 1 https://github.com/ZFTurbo/Music-Source-Separation-Training "%ROOT%msst"
)

echo.
echo setup done. Models auto-download on first use into models\sep\
