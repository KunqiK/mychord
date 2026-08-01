"""新模式: after instrument separation, transcribe EVERY stem to its own
MIDI so the user can pick the chord/melody tracks themselves in the DAW.

Piano stem uses the ByteDance engine (velocity + pedal); all other pitched
stems use basic-pitch at sensitive thresholds (velocity = confidence, meant
for DAW cleanup). Drums are skipped. MIDI is written at the given BPM
(times stay absolute seconds, so a constant-tempo song aligns to the DAW
grid when the project BPM matches)."""
from __future__ import annotations

import json
from pathlib import Path

SKIP = {'drums'}
PIANOISH = {'piano'}


def _write_mid(notes, path: Path, bpm: float) -> None:
    import mido
    mid = mido.MidiFile(ticks_per_beat=480)
    tr = mido.MidiTrack()
    mid.tracks.append(tr)
    tr.append(mido.MetaMessage('set_tempo', tempo=mido.bpm2tempo(bpm), time=0))
    spt = 60.0 / bpm / 480.0
    evs = []
    for n in notes:
        v = max(1, min(127, int(round(n.get('amp', 0.6) * 127))))
        evs.append((max(n['start'], 0.0), 1, int(n['midi']), v))
        evs.append((max(n['end'], 0.0), 0, int(n['midi']), 0))
    evs.sort(key=lambda e: (e[0], e[1]))
    t_prev = 0.0
    for t, kind, pitch, v in evs:
        dt = max(0, int(round((t - t_prev) / spt)))
        tr.append(mido.Message('note_on' if kind else 'note_off',
                               note=pitch, velocity=v, time=dt))
        t_prev += dt * spt
    mid.save(str(path))


def _energy_gate(notes, wav: Path):
    """Drop notes where the stem itself is near-silent: separation residue
    smeared into quiet regions is the main source of ghost notes."""
    import librosa
    import numpy as np
    from .audio_io import load_mono
    y, sr = load_mono(wav)
    rms = librosa.feature.rms(y=y, frame_length=2048, hop_length=512)[0]
    times = librosa.times_like(rms, sr=sr, hop_length=512)
    active = rms[rms > 1e-5]
    if not len(active):
        return []
    floor = max(10 ** (-45 / 20), 0.15 * float(np.percentile(active, 90)))
    kept = []
    for n in notes:
        a = int(np.searchsorted(times, n['start']))
        b = max(int(np.searchsorted(times, n['end'])), a + 1)
        if float(np.median(rms[a:b])) >= floor:
            kept.append(n)
    return kept


def transcribe_stems(stems_dir: Path, bpm: float | None = None,
                     cache_dir: Path | None = None, log=print) -> list[Path]:
    from .melody import _predict_notes, basic_pitch_available
    bpm = bpm or 120.0
    made = []
    for wav in sorted(stems_dir.glob('*.flac')):
        name = wav.stem
        if name in SKIP:
            continue
        mid_path = stems_dir / f'{name}.mid'
        if mid_path.exists():
            continue
        try:
            if name in PIANOISH:
                from . import piano as piano_mod
                pj = (cache_dir or stems_dir) / f'_{name}_engine.json'
                piano_mod.transcribe(wav, pj)
                notes = json.loads(pj.read_text(encoding='utf-8'))['notes']
            elif basic_pitch_available():
                # standard thresholds, NOT the over-detecting draft settings:
                # this mode wants faithful stems, less DAW cleanup (user
                # feedback 2026-07-31: strings had 2492 notes of bleed).
                # bass keeps sensitive thresholds — low notes score low
                # confidence in basic-pitch and standard settings kill them
                if name == 'bass':
                    notes = _predict_notes(wav, onset=0.3, frame=0.2,
                                           minlen=90.0, fmin=25.0, fmax=1200.0)
                else:
                    notes = _predict_notes(wav, onset=0.5, frame=0.3,
                                           minlen=90.0, fmin=30.0, fmax=3000.0)
                    notes = _energy_gate(notes, wav)
            else:
                continue
            if not notes:
                log(f'    [{name}] silent — no MIDI')
                continue
            _write_mid(notes, mid_path, bpm)
            made.append(mid_path)
            log(f'    [{name}] {len(notes)} notes → {mid_path.name}')
        except Exception as e:  # noqa: BLE001 — one bad stem must not kill the rest
            log(f'    [{name}] transcription failed: {e}')
    return made
