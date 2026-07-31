"""Melody extraction: basic-pitch (ONNX) or pyin fallback → NoteEvents.

Vocal path: basic-pitch on the vocals stem, reduced to monophonic by amplitude.
Instrumental path: basic-pitch on the other stem + skyline above a floor pitch.
Both emit the same note-event list; quantization happens at MIDI-write time.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from .audio_io import load_mono

VOCAL_DB_THRESH = -35.0
VOCAL_FRAC_THRESH = 0.15
MIN_NOTE_S = 0.06
GAP_MERGE_S = 0.06


def vocals_present(vocals_wav: Path) -> bool:
    import librosa
    y, sr = load_mono(vocals_wav)
    if not len(y):
        return False
    rms = librosa.feature.rms(y=y, frame_length=2048, hop_length=512)[0]
    db = librosa.amplitude_to_db(rms, ref=1.0)
    return float((db > VOCAL_DB_THRESH).mean()) > VOCAL_FRAC_THRESH


def basic_pitch_available() -> bool:
    try:
        from basic_pitch.inference import predict  # noqa: F401
        return True
    except Exception:
        return False


def _predict_notes(stem_wav: Path, onset: float = 0.5, frame: float = 0.3,
                   minlen: float = 90.0, fmin: float = 80.0,
                   fmax: float = 1000.0) -> list[dict]:
    from basic_pitch.inference import predict
    _model_out, _midi, note_events = predict(
        str(stem_wav),
        onset_threshold=onset, frame_threshold=frame,
        minimum_note_length=minlen,
        minimum_frequency=fmin, maximum_frequency=fmax,
    )
    notes = [{'start': float(s), 'end': float(e), 'midi': int(p),
              'amp': float(a)} for (s, e, p, a, _bends) in note_events]
    notes.sort(key=lambda n: n['start'])
    return notes


def _monophonic_by_amp(notes: list[dict]) -> list[dict]:
    """At overlaps keep the louder note (10 ms sampling), then rebuild segments."""
    return _reduce(notes, prefer='amp')


def _skyline(notes: list[dict], floor_midi: int) -> list[dict]:
    notes = [n for n in notes if n['midi'] >= floor_midi]
    return _reduce(notes, prefer='pitch')


def _reduce(notes: list[dict], prefer: str) -> list[dict]:
    if not notes:
        return []
    t_end = max(n['end'] for n in notes)
    dt = 0.01
    F = int(np.ceil(t_end / dt)) + 1
    best = np.full(F, -1, dtype=np.int64)
    key = np.full(F, -np.inf)
    for i, n in enumerate(notes):
        a, b = int(n['start'] / dt), int(np.ceil(n['end'] / dt))
        k = n['amp'] if prefer == 'amp' else n['midi']
        sel = slice(max(a, 0), min(b, F))
        upd = key[sel] < k
        best[sel] = np.where(upd, i, best[sel])
        key[sel] = np.where(upd, k, key[sel])
    # rebuild contiguous same-note runs
    out = []
    run_start, cur = None, -1
    for f in range(F):
        i = best[f]
        if i != cur:
            if cur >= 0:
                out.append({'start': run_start * dt, 'end': f * dt,
                            'midi': notes[cur]['midi'],
                            'amp': notes[cur]['amp']})
            run_start, cur = f, i
    if cur >= 0:
        out.append({'start': run_start * dt, 'end': F * dt,
                    'midi': notes[cur]['midi'], 'amp': notes[cur]['amp']})
    # merge same-pitch runs separated by small gaps; drop dust
    merged = []
    for n in out:
        if merged and merged[-1]['midi'] == n['midi'] \
                and n['start'] - merged[-1]['end'] <= GAP_MERGE_S:
            merged[-1]['end'] = n['end']
        else:
            merged.append(dict(n))
    return [n for n in merged if n['end'] - n['start'] >= MIN_NOTE_S]


def _pyin_notes(stem_wav: Path) -> list[dict]:
    """Fallback: pyin f0 → segment into notes (monophonic by construction)."""
    import librosa
    import scipy.signal
    y, sr = load_mono(stem_wav)
    f0, voiced, vprob = librosa.pyin(y, sr=sr, fmin=65, fmax=1047,
                                     frame_length=2048, hop_length=512)
    times = librosa.times_like(f0, sr=sr, hop_length=512)
    midi = librosa.hz_to_midi(np.where(voiced, f0, np.nan))
    # median-filter the voiced pitch track
    v = np.where(np.isnan(midi), 0.0, midi)
    v = scipy.signal.medfilt(v, 7)
    midi = np.where(np.isnan(midi), np.nan, v)

    notes = []
    cur = None
    for i, t in enumerate(times):
        m = midi[i]
        if np.isnan(m):
            if cur:
                notes.append(cur)
                cur = None
            continue
        sm = int(np.round(m))
        if cur is None:
            cur = {'start': t, 'end': t + 0.0116, 'midi': sm, 'amp': 0.7,
                   '_pitches': [m]}
        elif abs(m - np.median(cur['_pitches'])) > 0.6:
            notes.append(cur)
            cur = {'start': t, 'end': t + 0.0116, 'midi': sm, 'amp': 0.7,
                   '_pitches': [m]}
        else:
            cur['end'] = t + 0.0116
            cur['_pitches'].append(m)
            cur['midi'] = int(np.round(np.median(cur['_pitches'])))
    if cur:
        notes.append(cur)
    for n in notes:
        n.pop('_pitches', None)
    return [n for n in notes if n['end'] - n['start'] >= MIN_NOTE_S]


VOCAL_RANGE = (45, 83)   # sung melody register (A2..B5); outside = ghost/harmonic


def _vocal_section_gate(notes, vocals_wav: Path, mix_wav: Path,
                        thresh: float) -> list[dict]:
    """Keep notes only inside sections where the vocals stem carries a
    sustained share of the mix energy (3 s smoothed). Kills the pitched
    synth bleed / vocal-chop ghosts that litter instrumental sections."""
    import librosa
    import scipy.ndimage
    yv, sr = load_mono(vocals_wav)
    ym, _ = load_mono(mix_wav)
    n = min(len(yv), len(ym))
    rv = librosa.feature.rms(y=yv[:n], frame_length=2048, hop_length=512)[0]
    rm = librosa.feature.rms(y=ym[:n], frame_length=2048, hop_length=512)[0]
    ratio = rv / (rm + 1e-8)
    fps = sr / 512
    smooth = scipy.ndimage.median_filter(ratio, size=max(int(3.0 * fps), 1))
    times = librosa.times_like(rv, sr=sr, hop_length=512)
    # adaptive: in material where the vocal share is globally modest, scale
    # the threshold down instead of gating everything away
    eff = min(thresh, 0.6 * float(np.percentile(smooth, 90)))
    kept = []
    for o in notes:
        a = int(np.searchsorted(times, o['start']))
        b = max(int(np.searchsorted(times, o['end'])), a + 1)
        if float(np.median(smooth[a:b])) >= eff:
            kept.append(o)
    return kept


def extract(stems_dir: Path, out_json: Path, source: str = 'auto',
            lead_floor_midi: int = 60, vocal_gate: float = 0.25) -> dict:
    vocals = stems_dir / 'vocals.wav'
    other = stems_dir / 'other.wav'
    if source == 'auto':
        source = 'vocals' if vocals_present(vocals) else 'other'
    if source == 'none':
        result = {'source': 'none', 'engine': None, 'notes': []}
        out_json.write_text(json.dumps(result), encoding='utf-8')
        return result

    stem = vocals if source == 'vocals' else other
    poly = []
    lead_line = []
    if basic_pitch_available():
        engine = 'basic-pitch'
        raw = _predict_notes(stem)
        notes = _monophonic_by_amp(raw) if source == 'vocals' \
            else _skyline(raw, lead_floor_midi)
        if source == 'vocals':
            notes = [n for n in notes
                     if VOCAL_RANGE[0] <= n['midi'] <= VOCAL_RANGE[1]]
            mix_wav = stems_dir.parent / 'input.wav'
            if vocal_gate > 0 and mix_wav.exists():
                notes = _vocal_section_gate(notes, vocals, mix_wav, vocal_gate)
        # full polyphonic draft of the instrumental stem, sensitive settings:
        # catches lead/arp/piano lines the monophonic reduction can't —
        # over-detects on purpose, meant for DAW piano-roll cleanup
        if other.exists():
            poly = _predict_notes(other, onset=0.3, frame=0.2, minlen=60.0,
                                  fmin=60.0, fmax=2500.0)
            lead_line = _skyline(poly, lead_floor_midi)
    else:
        engine = 'pyin'
        notes = _pyin_notes(stem)
        if source == 'other':
            notes = [n for n in notes if n['midi'] >= lead_floor_midi]

    def pack(ns):
        return [{'start': round(n['start'], 4), 'end': round(n['end'], 4),
                 'midi': n['midi'], 'amp': round(n.get('amp', 0.7), 3)}
                for n in ns]

    result = {'source': source, 'engine': engine, 'notes': pack(notes),
              'poly': pack(poly), 'lead_line': pack(lead_line)}
    out_json.write_text(json.dumps(result), encoding='utf-8')
    return result


def load(melody_json: Path) -> dict:
    return json.loads(melody_json.read_text(encoding='utf-8'))
