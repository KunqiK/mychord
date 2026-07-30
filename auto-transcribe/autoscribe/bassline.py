"""Per-frame bass root pitch class from the bass stem (pyin + chroma fallback)."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from .audio_io import load_mono

HOP = 512


def analyze(bass_wav: Path, frame_bounds: np.ndarray, out_json: Path) -> dict:
    import librosa

    y, sr = load_mono(bass_wav)
    f0, voiced, vprob = librosa.pyin(
        y, sr=sr, fmin=32, fmax=350, frame_length=4096, hop_length=HOP)
    times = librosa.times_like(f0, sr=sr, hop_length=HOP)

    # low-register chroma fallback (C1..C4)
    C = librosa.feature.chroma_cqt(y=y, sr=sr, hop_length=HOP,
                                   fmin=librosa.note_to_hz('C1'), n_octaves=3)
    rms = librosa.feature.rms(y=y, hop_length=HOP)[0]
    rms_med = float(np.median(rms[rms > 0])) if (rms > 0).any() else 1.0

    F = len(frame_bounds) - 1
    idx = np.searchsorted(times, frame_bounds)
    pcs, confs = [], []
    for f in range(F):
        a, b = idx[f], max(idx[f + 1], idx[f] + 1)
        vf = voiced[a:b]
        if vf.size and vf.any():
            fs = f0[a:b][vf]
            pc = int(np.round(librosa.hz_to_midi(float(np.median(fs))))) % 12
            conf = float(vf.mean()) * float(np.nanmean(vprob[a:b][vf]))
        else:
            seg = C[:, a:b]
            r = rms[a:b]
            if seg.size and r.size and float(r.mean()) > 0.15 * rms_med:
                pc = int(np.argmax(np.median(seg, axis=1)))
                conf = 0.3
            else:
                pc, conf = -1, 0.0
        pcs.append(pc)
        confs.append(round(conf, 3))

    result = {'pc': pcs, 'conf': confs}
    out_json.write_text(json.dumps(result), encoding='utf-8')
    return result


def load(bass_json: Path) -> dict:
    return json.loads(bass_json.read_text(encoding='utf-8'))
