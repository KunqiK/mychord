"""NNLS harmonic-template verification (Mauch & Dixon, ISMIR 2010).

The automated version of "play the candidate and hear if it clashes": fit the
segment's log-frequency spectrum with note templates (fundamental + geometric
harmonic series), RESTRICTED to the candidate chord's pitch classes. A chord
whose tones (via their harmonics) explain the spectrum leaves a small
residual; a wrong root leaves energy unexplained. Crucially this recovers
masked roots: a quiet fundamental's 2nd/3rd/4th harmonics still sit in the
spectrum, and only the note dictionary can attribute them back to the root.

Runs on other.wav + bass.wav (the mix minus drums minus vocals) — chords.py's
chroma already excludes vocals/drums for the same reason, and the bass stem
carries most root fundamentals.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

SR = 22050
HOP = 4096                 # ~0.19 s frames — chord segments span many
BINS_PER_SEMI = 3          # Mauch's log-frequency resolution
MIDI_LO = 24               # C1
N_NOTES = 84               # C1..B7
N_BINS = N_NOTES * BINS_PER_SEMI
N_HARM = 8
HARM_DECAY = 0.75          # geometric rolloff s^k over harmonics


def _dictionary() -> np.ndarray:
    """(N_BINS, N_NOTES) note templates with harmonic series."""
    D = np.zeros((N_BINS, N_NOTES), dtype=np.float32)
    for n in range(N_NOTES):
        base = n * BINS_PER_SEMI + 1          # center bin of the semitone
        for h in range(1, N_HARM + 1):
            b = base + int(round(BINS_PER_SEMI * 12 * np.log2(h)))
            if b >= N_BINS:
                break
            w = HARM_DECAY ** (h - 1)
            D[b, n] += w
            if b - 1 >= 0:
                D[b - 1, n] += 0.33 * w        # slight spread for tuning slop
            if b + 1 < N_BINS:
                D[b + 1, n] += 0.33 * w
        D[:, n] /= np.linalg.norm(D[:, n]) or 1.0
    return D


_DICT: np.ndarray | None = None


def compute_spec(other_wav: Path, bass_wav: Path | None):
    """CQT magnitude frames of the harmonic mix. Returns (spec[T,N_BINS], times)."""
    import librosa
    y, _ = librosa.load(str(other_wav), sr=SR, mono=True)
    if bass_wav is not None and Path(bass_wav).exists():
        yb, _ = librosa.load(str(bass_wav), sr=SR, mono=True)
        n = min(len(y), len(yb))
        y = y[:n] + yb[:n]
    C = np.abs(librosa.cqt(y, sr=SR, hop_length=HOP, n_bins=N_BINS,
                           bins_per_octave=12 * BINS_PER_SEMI,
                           fmin=librosa.midi_to_hz(MIDI_LO)))
    # log compression (Mauch's mapping): tame the loudest partials so quiet
    # mid-voice harmonics — the buried roots — still steer the fit
    C = np.log1p(10.0 * C / (np.median(C[C > 0]) or 1.0))
    times = np.arange(C.shape[1]) * (HOP / SR)
    return C.T.astype(np.float32), times


def fit_residuals(spec_med: np.ndarray, cand_tone_sets: list[set[int]],
                  bass_pc: int | None) -> list[float] | None:
    """Relative NNLS residual per candidate (lower = explains the segment
    better). cand_tone_sets are pitch-class sets; the bass pc is always
    allowed (it is audibly sounding regardless of the chord reading)."""
    from scipy.optimize import nnls
    global _DICT
    if _DICT is None:
        _DICT = _dictionary()
    norm = float(np.linalg.norm(spec_med))
    if norm <= 1e-6:
        return None
    out = []
    for tones in cand_tone_sets:
        allow = set(tones)
        if bass_pc is not None:
            allow.add(bass_pc % 12)
        cols = [n for n in range(N_NOTES) if (MIDI_LO + n) % 12 in allow]
        sub = _DICT[:, cols]
        try:
            _, r = nnls(sub, spec_med, maxiter=200)
        except Exception:                                     # noqa: BLE001
            return None
        out.append(float(r) / norm)
    return out
