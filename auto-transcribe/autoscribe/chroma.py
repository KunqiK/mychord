"""Beat-synchronized CQT chroma from the harmony stems."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import scipy.ndimage

from .audio_io import load_mono

HOP = 512


def compute(other_wav: Path, vocals_wav: Path | None, frame_bounds: np.ndarray,
            out_npz: Path, vocals_weight: float = 0.0) -> dict:
    import librosa

    y, sr = load_mono(other_wav)
    if vocals_weight > 0 and vocals_wav is not None and vocals_wav.exists():
        yv, _ = load_mono(vocals_wav)
        n = min(len(y), len(yv))
        y = y[:n] + vocals_weight * yv[:n]

    y_h = librosa.effects.harmonic(y, margin=3.0)
    tuning = float(librosa.estimate_tuning(y=y_h, sr=sr) or 0.0)
    C = librosa.feature.chroma_cqt(
        y=y_h, sr=sr, hop_length=HOP, fmin=librosa.note_to_hz('C2'),
        n_octaves=6, bins_per_octave=36, tuning=tuning)
    C = scipy.ndimage.median_filter(C, size=(1, 9))

    # frame energy (RMS of the harmonic signal), same hop
    rms = librosa.feature.rms(y=y_h, hop_length=HOP)[0]

    times = librosa.frames_to_time(np.arange(C.shape[1]), sr=sr, hop_length=HOP)
    F = len(frame_bounds) - 1
    chroma_sync = np.zeros((12, F))
    energy = np.zeros(F)
    idx = np.searchsorted(times, frame_bounds)
    for f in range(F):
        a, b = idx[f], max(idx[f + 1], idx[f] + 1)
        seg = C[:, a:b]
        chroma_sync[:, f] = np.median(seg, axis=1) if seg.size else 0.0
        r = rms[a:b]
        energy[f] = float(np.sqrt(np.mean(r ** 2))) if r.size else 0.0

    # per-frame max-normalize (keep raw energy separately)
    maxes = chroma_sync.max(axis=0)
    maxes[maxes == 0] = 1.0
    chroma_norm = chroma_sync / maxes

    med = float(np.median(energy[energy > 0])) if (energy > 0).any() else 1.0
    energy_norm = energy / (med or 1.0)

    np.savez(out_npz, chroma=chroma_norm, energy=energy_norm,
             bounds=frame_bounds, tuning=tuning)
    return {'chroma': chroma_norm, 'energy': energy_norm,
            'bounds': frame_bounds, 'tuning': tuning}


def load(npz_path: Path) -> dict:
    d = np.load(npz_path)
    return {'chroma': d['chroma'], 'energy': d['energy'],
            'bounds': d['bounds'], 'tuning': float(d['tuning'])}
