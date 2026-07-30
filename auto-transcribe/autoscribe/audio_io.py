"""Audio decode/load helpers. Everything downstream consumes 44.1 kHz WAV."""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import numpy as np
import soundfile as sf

SR = 44100
ANALYSIS_SR = 22050


def ffmpeg_exe() -> str | None:
    """ffmpeg from PATH, or the winget Links dir (PATH updates need a new
    terminal; the absolute path works immediately)."""
    exe = shutil.which('ffmpeg')
    if exe:
        return exe
    winget = Path(os.environ.get('LOCALAPPDATA', '')) / 'Microsoft' / 'WinGet'
    link = winget / 'Links' / 'ffmpeg.exe'
    if link.exists():
        return str(link)
    for hit in (winget / 'Packages').glob('Gyan.FFmpeg*/*/bin/ffmpeg.exe'):
        return str(hit)
    return None


def have_ffmpeg() -> bool:
    return ffmpeg_exe() is not None


def decode_to_wav(src: Path, dst: Path) -> None:
    """Decode any input to 44.1 kHz stereo 16-bit WAV at dst."""
    if src.suffix.lower() in ('.wav', '.flac'):
        try:
            data, sr = sf.read(str(src), always_2d=True)
            if data.shape[1] == 1:
                data = np.repeat(data, 2, axis=1)
            elif data.shape[1] > 2:
                data = data[:, :2]
            if sr != SR:
                import librosa
                data = librosa.resample(data.T, orig_sr=sr, target_sr=SR).T
            sf.write(str(dst), data, SR, subtype='PCM_16')
            return
        except (sf.LibsndfileError, RuntimeError):
            pass  # fall through to ffmpeg
    if not have_ffmpeg():
        raise RuntimeError(
            f'Cannot decode {src.name}: ffmpeg not found on PATH and soundfile '
            f'cannot read it. Install ffmpeg: winget install Gyan.FFmpeg')
    subprocess.run(
        [ffmpeg_exe(), '-y', '-i', str(src), '-ac', '2', '-ar', str(SR),
         '-c:a', 'pcm_s16le', '-loglevel', 'error', str(dst)],
        check=True)


def load_mono(path: Path, sr: int = ANALYSIS_SR) -> tuple[np.ndarray, int]:
    data, in_sr = sf.read(str(path), always_2d=True, dtype='float32')
    y = data.mean(axis=1)
    if in_sr != sr:
        import librosa
        y = librosa.resample(y, orig_sr=in_sr, target_sr=sr)
    return y, sr


def duration_seconds(path: Path) -> float:
    info = sf.info(str(path))
    return info.frames / info.samplerate
