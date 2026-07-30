"""Tempo, beat grid, and downbeat-phase estimation from the drums stem.

EDM assumption: near-constant tempo. After tracking we fit a constant grid
(linear regression beat index → time); if the residual is tiny we snap to it.
Downbeat phase is scored by harmonic-change novelty + bass onset energy.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from .audio_io import load_mono

HOP = 512


def _fold_bpm(bpm: float, lo=70.0, hi=180.0) -> float:
    while bpm < lo:
        bpm *= 2
    while bpm > hi:
        bpm /= 2
    return bpm


def _autocorr(env: np.ndarray) -> np.ndarray:
    x = env - env.mean()
    ac = np.correlate(x, x, 'full')[len(x) - 1:]
    return ac / (ac[0] or 1.0)


def _comb_score(ac: np.ndarray, fps: float, bpm: float) -> float:
    """Autocorrelation sampled at 1/2/4 beat lags (fractional, interpolated).
    A true beat period scores at all comb teeth; a triplet/dotted artifact
    doesn't survive the 4-beat tooth."""
    score = 0.0
    for mult, w in ((1, 1.0), (2, 1.0), (4, 1.0)):
        lag = 60.0 / bpm * fps * mult
        if lag >= len(ac) - 1:
            continue
        score += w * float(np.interp(lag, np.arange(len(ac)), ac))
    return score


def _tempo_candidates(env: np.ndarray, sr: int) -> list[float]:
    import librosa
    cands = set()
    est = float(librosa.feature.tempo(onset_envelope=env, sr=sr,
                                      hop_length=HOP)[0])
    cands.add(round(_fold_bpm(est), 2))
    framewise = librosa.feature.tempo(onset_envelope=env, sr=sr,
                                      hop_length=HOP, aggregate=None)
    vals, counts = np.unique(np.round(framewise, 1), return_counts=True)
    for i in np.argsort(counts)[::-1][:3]:
        cands.add(round(_fold_bpm(float(vals[i])), 2))
    peaks = librosa.util.peak_pick(env, pre_max=3, post_max=3, pre_avg=5,
                                   post_avg=5, delta=env.max() * 0.3, wait=4)
    t = librosa.frames_to_time(peaks, sr=sr, hop_length=HOP)
    ioi = np.diff(t)
    ioi = ioi[(ioi > 0.15) & (ioi < 1.2)]
    if len(ioi) > 10:
        hist, edges = np.histogram(ioi, bins=60, range=(0.15, 1.2))
        for i in np.argsort(hist)[::-1][:3]:
            if hist[i] >= 5:
                mid = (edges[i] + edges[i + 1]) / 2
                cands.add(round(_fold_bpm(60.0 / mid), 2))
    return sorted(cands)


def _pick_tempo(env: np.ndarray, sr: int) -> tuple[float, float | None]:
    """Best BPM by comb score over all candidates, locally refined ±3%."""
    ac = _autocorr(env)
    fps = sr / HOP
    cands = _tempo_candidates(env, sr)
    scored = sorted(((c, _comb_score(ac, fps, c)) for c in cands),
                    key=lambda cs: -cs[1])
    best = scored[0][0]
    fine = max((best * f for f in np.linspace(0.97, 1.03, 61)),
               key=lambda b: _comb_score(ac, fps, b))
    alt = next((c for c, _s in scored[1:]
                if abs(c - fine) > 3 and abs(_fold_bpm(c * 2) - fine) > 3
                and abs(_fold_bpm(c / 2) - fine) > 3), None)
    return round(float(fine), 2), (round(float(alt), 2) if alt else None)


def _precise_grid(env: np.ndarray, times: np.ndarray, center_bpm: float,
                  span: float = 0.04) -> tuple[float, float, float]:
    """Sub-frame (period, phase) search maximizing mean onset energy on the
    grid. beat_track output is quantized to the hop (23 ms) — useless for a
    constant grid; sampling the envelope at fractional times is not.
    Returns (period_s, t0_s, lock_ratio = grid energy / global mean)."""
    dur = float(times[-1])
    lo, hi = 60.0 / (center_bpm * (1 + span)), 60.0 / (center_bpm * (1 - span))

    def energy(p, t0):
        ts = np.arange(t0, dur, p)
        return float(np.interp(ts, times, env).mean())

    best = (-1.0, 0.0, 0.0)
    for p in np.linspace(lo, hi, 240):
        for t0 in np.linspace(0, p, 48, endpoint=False):
            e = energy(p, t0)
            if e > best[0]:
                best = (e, p, t0)
    # refine around the winner
    _, p0, t00 = best
    for p in np.linspace(p0 * 0.999, p0 * 1.001, 40):
        for t0 in np.linspace(max(t00 - 0.02, 0), t00 + 0.02, 40):
            e = energy(p, t0)
            if e > best[0]:
                best = (e, p, t0)
    e, p, t0 = best
    ratio = e / (float(env.mean()) or 1.0)
    return p, t0 % p, ratio


GRID_LOCK_MIN = 2.0   # grid/global onset-energy ratio to trust the constant grid


def estimate(drums_wav: Path, other_wav: Path, bass_wav: Path, out_json: Path,
             duration: float, bpm_override: float | None = None,
             beats_per_bar: int = 4, downbeat_shift: int | None = None) -> dict:
    import librosa

    y, sr = load_mono(drums_wav)
    if float(np.abs(y).max() or 0) < 1e-4:  # near-silent drums → use full-band other
        y, sr = load_mono(other_wav)
    onset_env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=HOP,
                                             aggregate=np.median)
    env_times = librosa.frames_to_time(np.arange(len(onset_env)), sr=sr,
                                       hop_length=HOP)

    # coarse tempo (multi-source + comb-autocorrelation scoring)
    if bpm_override:
        coarse, bpm_alt = float(bpm_override), None
        span = 0.015   # trust the user; search just enough for exactness
    else:
        coarse, bpm_alt = _pick_tempo(onset_env, sr)
        span = 0.04

    # sub-frame constant-grid search (EDM default)
    period, t0, lock = _precise_grid(onset_env, env_times, coarse, span)
    grid_fitted = lock >= GRID_LOCK_MIN
    if grid_fitted:
        bpm = 60.0 / period
        n = int(np.floor((duration - t0) / period)) + 1
        beat_times = t0 + period * np.arange(max(n, 2))
    else:
        # weak periodicity (breakbeat / live drift) → dynamic beat tracking
        bpm = coarse
        _tempo, beat_times = librosa.beat.beat_track(
            onset_envelope=onset_env, sr=sr, hop_length=HOP, bpm=bpm,
            trim=False, units='time')
        if len(beat_times) >= 2:
            beat_times = list(beat_times)
            step0 = beat_times[1] - beat_times[0]
            while beat_times[0] - step0 > 0:
                beat_times.insert(0, beat_times[0] - step0)
            step1 = beat_times[-1] - beat_times[-2]
            while beat_times[-1] + step1 < duration:
                beat_times.append(beat_times[-1] + step1)
            beat_times = np.asarray(beat_times)

    # ── downbeat phase ──
    if downbeat_shift is not None:
        phase = int(downbeat_shift) % beats_per_bar
        phase_scores = None
    else:
        yo, _ = load_mono(other_wav)
        chroma = librosa.feature.chroma_stft(y=yo, sr=sr, hop_length=HOP)
        novelty = np.concatenate([[0.0], np.abs(np.diff(chroma, axis=1)).sum(axis=0)])
        yb, _ = load_mono(bass_wav)
        bass_on = librosa.onset.onset_strength(y=yb, sr=sr, hop_length=HOP)

        def at_beats(sig):
            fr = librosa.time_to_frames(beat_times, sr=sr, hop_length=HOP)
            fr = np.clip(fr, 0, len(sig) - 1)
            return sig[fr]

        nov_b = at_beats(novelty)
        bass_b = at_beats(bass_on)
        nov_b = nov_b / (nov_b.max() or 1)
        bass_b = bass_b / (bass_b.max() or 1)
        phase_scores = []
        for p in range(beats_per_bar):
            sel = np.arange(p, len(beat_times), beats_per_bar)
            phase_scores.append(float(nov_b[sel].mean() + 0.6 * bass_b[sel].mean()))
        phase = int(np.argmax(phase_scores))

    result = {
        'bpm': round(float(bpm), 3),
        'bpm_alt': round(float(bpm_alt), 3) if bpm_alt else None,
        'grid_fitted': grid_fitted,
        'grid_lock': round(float(lock), 2),
        'beats_per_bar': beats_per_bar,
        'downbeat_phase': phase,
        'phase_scores': phase_scores,
        'first_downbeat': float(beat_times[phase]) if len(beat_times) > phase else 0.0,
        'beat_times': [round(float(t), 5) for t in beat_times],
    }
    out_json.write_text(json.dumps(result), encoding='utf-8')
    return result


def load(beats_json: Path) -> dict:
    return json.loads(beats_json.read_text(encoding='utf-8'))


def frame_grid(beats: dict, subdiv: int = 2) -> dict:
    """Half-beat frame boundaries + per-frame metadata.

    Returns dict with 'bounds' (F+1,), 'beat_pos' (F,) float beat index,
    'kind' (F,) in {downbeat, midbar, beat, offbeat}.
    """
    bt = np.asarray(beats['beat_times'])
    bpb = beats['beats_per_bar']
    phase = beats['downbeat_phase']
    bounds, beat_pos = [], []
    for i in range(len(bt) - 1):
        for s in range(subdiv):
            bounds.append(bt[i] + (bt[i + 1] - bt[i]) * s / subdiv)
            beat_pos.append(i + s / subdiv)
    bounds.append(bt[-1])
    kind = []
    for bp in beat_pos:
        if bp != int(bp):
            kind.append('offbeat')
            continue
        rel = (int(bp) - phase) % bpb
        if rel == 0:
            kind.append('downbeat')
        elif bpb >= 4 and rel == bpb // 2:
            kind.append('midbar')
        else:
            kind.append('beat')
    return {'bounds': np.asarray(bounds), 'beat_pos': np.asarray(beat_pos),
            'kind': kind}


def bar_beat_at(t: float, beats: dict) -> tuple[int, int]:
    """1-based (bar, beat) of time t; bar clamps to >=1 before first downbeat."""
    bt = np.asarray(beats['beat_times'])
    bpb = beats['beats_per_bar']
    phase = beats['downbeat_phase']
    i = int(np.searchsorted(bt, t + 1e-4) - 1)
    i = max(i, 0)
    rel = i - phase
    if rel < 0:
        return 1, 1
    return rel // bpb + 1, rel % bpb + 1
