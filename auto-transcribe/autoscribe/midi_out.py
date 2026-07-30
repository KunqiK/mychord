"""MIDI writing (mido). Seconds → ticks via the measured beat grid, so notes
land on-grid in any DAW at the nominal BPM even if the recording drifts."""
from __future__ import annotations

from pathlib import Path

import mido
import numpy as np

from .hud_port import CHORD_TEMPLATES

TPB = 480
SUBDIV = 4          # quantization grid = 16ths
SNAP_MAX_S = 0.08   # onset snap tolerance (also capped at 30% of a subdivision)


class BeatMapper:
    def __init__(self, beat_times: list[float]):
        self.bt = np.asarray(beat_times, dtype=float)

    def beats_at(self, t: float) -> float:
        bt = self.bt
        if t <= bt[0]:
            step = bt[1] - bt[0]
            return (t - bt[0]) / step
        if t >= bt[-1]:
            step = bt[-1] - bt[-2]
            return (len(bt) - 1) + (t - bt[-1]) / step
        return float(np.interp(t, bt, np.arange(len(bt))))

    def ticks_at(self, t: float) -> int:
        return int(round(self.beats_at(t) * TPB))

    def quantize_note(self, start: float, end: float) -> tuple[int, int] | None:
        b0 = self.beats_at(start)
        b1 = self.beats_at(end)
        sub = 1.0 / SUBDIV
        q0 = round(b0 / sub) * sub
        step = self.bt[1] - self.bt[0] if len(self.bt) > 1 else 0.5
        tol_beats = min(SNAP_MAX_S / step, 0.3 * sub)
        if abs(b0 - q0) > tol_beats:
            q0 = b0  # too far from grid — keep the played position
        q1 = max(round(b1 / sub) * sub, q0 + sub)
        return int(round(q0 * TPB)), int(round(q1 * TPB))


def _new_file(bpm: float, key_name: str | None = None) -> tuple[mido.MidiFile, mido.MidiTrack]:
    mid = mido.MidiFile(ticks_per_beat=TPB)
    track = mido.MidiTrack()
    mid.tracks.append(track)
    track.append(mido.MetaMessage('set_tempo', tempo=mido.bpm2tempo(bpm), time=0))
    track.append(mido.MetaMessage('time_signature', numerator=4, denominator=4, time=0))
    if key_name:
        try:
            track.append(mido.MetaMessage('key_signature', key=key_name, time=0))
        except ValueError:
            pass
    return mid, track


def _write_notes(track: mido.MidiTrack, events: list[tuple[int, int, int, int]]):
    """events: (tick_on, tick_off, midi, velocity), already sorted by tick_on."""
    msgs = []
    for on, off, pitch, vel in events:
        msgs.append((on, 1, mido.Message('note_on', note=pitch, velocity=vel, time=0)))
        msgs.append((off, 0, mido.Message('note_off', note=pitch, velocity=0, time=0)))
    msgs.sort(key=lambda m: (m[0], m[1]))
    prev = 0
    for tick, _order, msg in msgs:
        msg.time = max(tick - prev, 0)
        track.append(msg)
        prev = tick
    track.append(mido.MetaMessage('end_of_track', time=0))


def write_melody(notes: list[dict], mapper: BeatMapper, bpm: float,
                 out_path: Path, quantize: bool, key_name: str | None = None):
    mid, track = _new_file(bpm, key_name)
    events = []
    for n in notes:
        if quantize:
            q = mapper.quantize_note(n['start'], n['end'])
            if q is None:
                continue
            on, off = q
        else:
            on, off = mapper.ticks_at(n['start']), mapper.ticks_at(n['end'])
            if off <= on:
                off = on + TPB // SUBDIV
        vel = int(np.clip(40 + n.get('amp', 0.7) * 70, 1, 127))
        events.append((max(on, 0), max(off, 1), int(n['midi']), vel))
    events.sort(key=lambda e: e[0])
    _write_notes(track, events)
    mid.save(str(out_path))


def chord_voicing(root_pc: int, sfx: str, bass_pc: int | None) -> list[int]:
    """Root-position voicing packed into C3-B4, slash bass an octave below."""
    ivs = next((ivs for s, ivs in CHORD_TEMPLATES if s == sfx), (0, 4, 7))
    base = 48 + root_pc            # 48..59
    tones = []
    for iv in ivs:
        p = base + iv
        while p > 74 and p - 12 > base:
            p -= 12
        tones.append(p)
    bass = 36 + (bass_pc if bass_pc is not None else root_pc)
    return sorted(set([bass] + tones))


def write_chords(segments: list[dict], mapper: BeatMapper, bpm: float,
                 out_path: Path, key_name: str | None = None):
    mid, track = _new_file(bpm, key_name)
    events = []
    for seg in segments:
        if seg['chord'] == 'N' or seg.get('root_pc') is None:
            continue
        on = mapper.ticks_at(seg['start'])
        off = max(mapper.ticks_at(seg['end']), on + TPB // 4)
        vel = int(np.clip(40 + seg.get('conf', 0.5) * 70, 1, 127))
        for pitch in chord_voicing(seg['root_pc'], seg.get('sfx', ''),
                                   seg.get('bass_pc')):
            events.append((on, off, pitch, vel))
    events.sort(key=lambda e: e[0])
    _write_notes(track, events)
    mid.save(str(out_path))
