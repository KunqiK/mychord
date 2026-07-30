"""Ear-verification preview: numpy chord pad (+click) mixed under the original.

Wrong chords clash audibly against the song — turns transcription into
proofreading.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import soundfile as sf

from .midi_out import chord_voicing

SR = 44100
PAD_DB = -18.0
MIX_GAIN = 0.5
N_HARM = 8
ATTACK_S = 0.010
RELEASE_S = 0.080
SUSTAIN = 0.8


def _tone(freq: float, dur_s: float) -> np.ndarray:
    n = int(dur_s * SR)
    t = np.arange(n) / SR
    y = np.zeros(n)
    for h in range(1, N_HARM + 1):
        f = freq * h
        if f > SR / 2 - 1000:
            break
        amp = (1.0 / h) * (0.5 + 0.5 * np.cos(np.pi * (h - 1) / N_HARM))
        y += amp * np.sin(2 * np.pi * f * t)
    # ADSR (A - sustain - R)
    env = np.full(n, SUSTAIN)
    a = min(int(ATTACK_S * SR), n)
    env[:a] = np.linspace(0, SUSTAIN, a)
    r = min(int(RELEASE_S * SR), n)
    if r > 0:
        env[n - r:] *= np.linspace(1, 0, r)
    return y * env


def _click(freq: float) -> np.ndarray:
    n = int(0.03 * SR)
    t = np.arange(n) / SR
    return np.sin(2 * np.pi * freq * t) * np.exp(-t * 120)


def render_pad(segments: list[dict], duration: float) -> np.ndarray:
    out = np.zeros(int(duration * SR) + SR)
    for seg in segments:
        if seg['chord'] == 'N' or seg.get('root_pc') is None:
            continue
        dur = seg['end'] - seg['start']
        if dur <= 0.02:
            continue
        i0 = int(seg['start'] * SR)
        pitches = chord_voicing(seg['root_pc'], seg.get('sfx', ''),
                                seg.get('bass_pc'))
        for p in pitches:
            freq = 440.0 * 2 ** ((p - 69) / 12)
            tone = _tone(freq, dur)
            out[i0:i0 + len(tone)] += tone
    peak = np.abs(out).max() or 1.0
    out = out / peak * 10 ** (PAD_DB / 20)
    return out


def render_melody(notes: list[dict], duration: float) -> np.ndarray:
    out = np.zeros(int(duration * SR) + SR)
    for n in notes:
        dur = n['end'] - n['start']
        if dur <= 0.02:
            continue
        freq = 440.0 * 2 ** ((n['midi'] - 69) / 12)
        t = np.arange(int(dur * SR)) / SR
        y = np.sin(2 * np.pi * freq * t)
        a = min(int(0.005 * SR), len(y))
        if a:
            y[:a] *= np.linspace(0, 1, a)
        r = min(int(0.04 * SR), len(y))
        if r:
            y[-r:] *= np.linspace(1, 0, r)
        i0 = int(n['start'] * SR)
        out[i0:i0 + len(y)] += 0.35 * y
    return out


def render_clicks(beats: dict, duration: float) -> np.ndarray:
    out = np.zeros(int(duration * SR) + SR)
    bpb = beats['beats_per_bar']
    phase = beats['downbeat_phase']
    hi, lo = _click(1600), _click(1000)
    for i, t in enumerate(beats['beat_times']):
        if t >= duration:
            break
        c = hi if (i - phase) % bpb == 0 else lo
        i0 = int(t * SR)
        out[i0:i0 + len(c)] += 0.5 * c
    return out


def write_preview(input_wav: Path, segments: list[dict], beats: dict,
                  out_path: Path, click: bool = False,
                  melody_notes: list[dict] | None = None):
    orig, in_sr = sf.read(str(input_wav), always_2d=True, dtype='float32')
    mono = orig.mean(axis=1)
    if in_sr != SR:
        import librosa
        mono = librosa.resample(mono, orig_sr=in_sr, target_sr=SR)
    duration = len(mono) / SR

    mix = MIX_GAIN * mono
    layers = [render_pad(segments, duration)]
    if click:
        layers.append(render_clicks(beats, duration))
    if melody_notes:
        layers.append(render_melody(melody_notes, duration))
    for layer in layers:
        n = min(len(mix), len(layer))
        mix = np.concatenate([mix[:n] + layer[:n], mix[n:]])
    peak = np.abs(mix).max()
    if peak > 0.99:
        mix = mix / peak * 0.99
    sf.write(str(out_path), mix, SR, subtype='PCM_16')
