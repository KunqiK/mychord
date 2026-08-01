"""Beat-synchronized CQT chroma from the harmony stems."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import scipy.ndimage

from .audio_io import load_mono

HOP = 512


BASS_CHROMA_W = 0.6   # bass-stem low-register chroma folded into the feature


def compute(other_wav: Path, vocals_wav: Path | None, frame_bounds: np.ndarray,
            out_npz: Path, vocals_weight: float = 0.0,
            bass_wav: Path | None = None,
            harm_wavs: list[Path] | None = None) -> dict:
    import librosa

    if harm_wavs:
        # dedicated harmony stems (roformer piano/synth) replace the demucs
        # other stem: other mixes lead/arp/FX into the same pile and was the
        # main source of wrong chords vs the user's reference chart
        ys = [load_mono(w) for w in harm_wavs]
        sr = ys[0][1]
        n = min(len(y_) for y_, _ in ys)
        y = np.sum([y_[:n] for y_, _ in ys], axis=0)
    else:
        y, sr = load_mono(other_wav)
    if vocals_weight > 0 and vocals_wav is not None and vocals_wav.exists():
        yv, _ = load_mono(vocals_wav)
        n = min(len(y), len(yv))
        y = y[:n] + vocals_weight * yv[:n]

    y_h = librosa.effects.harmonic(y, margin=3.0)
    tuning = float(librosa.estimate_tuning(y=y_h, sr=sr) or 0.0)
    # C2..C6 only: leads/arps live above, and they smear the harmony
    C = librosa.feature.chroma_cqt(
        y=y_h, sr=sr, hop_length=HOP, fmin=librosa.note_to_hz('C2'),
        n_octaves=4, bins_per_octave=36, tuning=tuning)
    C = scipy.ndimage.median_filter(C, size=(1, 9))
    C_pad = C.copy()

    # the root often lives ONLY in the bass stem — fold its chroma in
    # (helps the Viterbi keep a stable root; labeling uses C_pad instead)
    if bass_wav is not None and bass_wav.exists():
        yb, _ = load_mono(bass_wav)
        Cb = librosa.feature.chroma_cqt(
            y=yb, sr=sr, hop_length=HOP, fmin=librosa.note_to_hz('C1'),
            n_octaves=3, bins_per_octave=36, tuning=tuning)
        Cb = scipy.ndimage.median_filter(Cb, size=(1, 9))
        T = min(C.shape[1], Cb.shape[1])
        Cbn = Cb[:, :T] / np.maximum(Cb[:, :T].max(axis=0, keepdims=True), 1e-6)
        Cn_ = C[:, :T] / np.maximum(C[:, :T].max(axis=0, keepdims=True), 1e-6)
        C = (Cn_ + BASS_CHROMA_W * Cbn) * np.maximum(C[:, :T].max(axis=0, keepdims=True), 1e-6)
    C_pad = C_pad[:, :C.shape[1]]

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

    # raw per-hop normalized chroma for sustain statistics in chord labeling —
    # PAD-ONLY (pre-bass-fold): stage 2 names the chord from the pads and
    # notates the bass as a slash, so bass pcs must not leak in here
    frames_norm = C_pad / np.maximum(C_pad.max(axis=0, keepdims=True), 1e-6)

    np.savez(out_npz, chroma=chroma_norm, energy=energy_norm,
             bounds=frame_bounds, tuning=tuning,
             frames=frames_norm.astype(np.float32), frame_times=times)
    return load(out_npz)


def load(npz_path: Path) -> dict:
    d = np.load(npz_path)
    out = {'chroma': d['chroma'], 'energy': d['energy'],
           'bounds': d['bounds'], 'tuning': float(d['tuning'])}
    if 'frames' in d:
        out['frames'] = d['frames']
        out['frame_times'] = d['frame_times']
    return out
