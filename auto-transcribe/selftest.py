"""Synthetic round-trip regression test (Milestone M2).

Renders a known 16-bar progression (own synth: chord pad + bass + kick +
noise + sine melody), pre-seeds the stem cache (bypassing demucs), runs the
full analysis chain, and asserts recovery of key, BPM, and >=90% of bars.

Run:  .venv\\Scripts\\python.exe selftest.py
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from autoscribe import cache, cli  # noqa: E402
from autoscribe.hud_port import _NOTE_PC  # noqa: E402
from autoscribe.synthesize import SR, _tone  # noqa: E402

BPM = 120.0
BEATS_PER_BAR = 4
BAR_S = 60.0 / BPM * BEATS_PER_BAR  # 2.0 s

# (chord name for humans, root pc, template intervals, bass pc)
PROG = [
    ('C',     0, (0, 4, 7),     0),
    ('G/B',   7, (0, 4, 7),     11),
    ('Am7',   9, (0, 3, 7, 10), 9),
    ('F',     5, (0, 4, 7),     5),
    ('C',     0, (0, 4, 7),     0),
    ('F',     5, (0, 4, 7),     5),
    ('G',     7, (0, 4, 7),     7),
    ('C',     0, (0, 4, 7),     0),
    ('Dm7',   2, (0, 3, 7, 10), 2),
    ('G7',    7, (0, 4, 7, 10), 7),
    ('Cmaj7', 0, (0, 4, 7, 11), 0),
    ('Am',    9, (0, 3, 7),     9),
    ('F',     5, (0, 4, 7),     5),
    ('Gsus4', 7, (0, 5, 7),     7),
    ('G',     7, (0, 4, 7),     7),
    ('C',     0, (0, 4, 7),     0),
]
N_BARS = len(PROG)
DUR = N_BARS * BAR_S

# melody: one note per beat over the first 8 bars (C major scale runs), vocals stem
MELODY_DEGREES = [72, 74, 76, 77, 79, 77, 76, 74]  # C5 D5 E5 F5 G5 F5 E5 D5


def synth_stems():
    n = int(DUR * SR) + SR
    other = np.zeros(n)
    bass = np.zeros(n)
    drums = np.zeros(n)
    vocals = np.zeros(n)

    for b, (_name, root, ivs, bass_pc) in enumerate(PROG):
        i0 = int(b * BAR_S * SR)
        for iv in ivs:
            freq = 440.0 * 2 ** ((60 + ((root + iv) % 12) - 69) / 12)
            tone = _tone(freq, BAR_S * 0.98)
            other[i0:i0 + len(tone)] += 0.25 * tone
        bfreq = 440.0 * 2 ** ((36 + bass_pc - 69) / 12)
        btone = _tone(bfreq, BAR_S * 0.95)
        bass[i0:i0 + len(btone)] += 0.5 * btone

    # four-on-the-floor kick: 55 Hz decaying thump on every beat
    beat_s = 60.0 / BPM
    for i in range(int(DUR / beat_s)):
        i0 = int(i * beat_s * SR)
        t = np.arange(int(0.12 * SR)) / SR
        kick = np.sin(2 * np.pi * 55 * t) * np.exp(-t * 40)
        drums[i0:i0 + len(kick)] += 0.8 * kick

    # sine melody on vocals, loud enough for vocals_present()
    for i, midi in enumerate(MELODY_DEGREES * 4):
        i0 = int(i * beat_s * SR)
        freq = 440.0 * 2 ** ((midi - 69) / 12)
        t = np.arange(int(beat_s * 0.9 * SR)) / SR
        note = np.sin(2 * np.pi * freq * t)
        fade = int(0.01 * SR)
        note[:fade] *= np.linspace(0, 1, fade)
        note[-fade:] *= np.linspace(1, 0, fade)
        # loud enough to survive the vocal section gate (real vocal share)
        vocals[i0:i0 + len(note)] += 0.6 * note

    rng = np.random.default_rng(42)
    other += 10 ** (-30 / 20) * rng.standard_normal(n)
    mix = other + bass + drums + vocals
    peak = np.abs(mix).max()
    if peak > 0.99:
        scale = 0.99 / peak
        mix, other, bass, drums, vocals = (x * scale for x in
                                           (mix, other, bass, drums, vocals))
    return mix, {'other': other, 'bass': bass, 'drums': drums, 'vocals': vocals}


def main() -> int:
    print('rendering synthetic song…')
    mix, stems = synth_stems()
    cache_root = ROOT / 'cache'
    cache_root.mkdir(exist_ok=True)
    song = cache_root / 'selftest_input.wav'
    sf.write(str(song), np.stack([mix, mix], axis=1), SR, subtype='PCM_16')
    import os
    os.utime(song, (1700000000, 1700000000))  # fixed mtime → stable cache slug

    sc = cache.SongCache(cache_root, song)
    if sc.dir.exists():
        shutil.rmtree(sc.dir)
    sc = cache.SongCache(cache_root, song)
    sf.write(str(sc.path('input.wav')), np.stack([mix, mix], axis=1), SR,
             subtype='PCM_16')
    stems_dir = sc.path('stems')
    stems_dir.mkdir()
    for name, y in stems.items():
        sf.write(str(stems_dir / f'{name}.wav'), np.stack([y, y], axis=1), SR,
                 subtype='PCM_16')
    sc.mark_done('separate', {'model': 'htdemucs'})
    print(f'stems seeded at {sc.dir}')

    rc = cli.main([str(song), '--title', 'selftest', '--click'])
    if rc != 0:
        print(f'FAIL: pipeline exit {rc}')
        return 1

    # ── evaluate ──
    beats = json.loads(sc.path('beats.json').read_text(encoding='utf-8'))
    key = json.loads(sc.path('key.json').read_text(encoding='utf-8'))
    segments = json.loads(sc.path('chords.json').read_text(encoding='utf-8'))['segments']
    melody = json.loads(sc.path('melody.json').read_text(encoding='utf-8'))

    failures = []
    if not (118.5 <= beats['bpm'] <= 121.5):
        failures.append(f"BPM {beats['bpm']} not ~120")
    if not (key['tonic_pc'] == 0 and key['mode'] == 'maj'):
        failures.append(f"key {key['name']} != C Major")

    minorish = {'m', 'm7', 'm6', 'm9', 'mMaj7', 'dim', 'dim7', 'm7b5'}
    neutral = {'sus2', 'sus4', '7sus4'}
    correct = 0
    rows = []
    for b, (name, root, ivs, _bass_pc) in enumerate(PROG):
        t_mid = (b + 0.5) * BAR_S
        seg = next((s for s in segments if s['start'] <= t_mid < s['end']), None)
        got = seg['chord'] if seg else '—'
        ok = False
        if seg and seg.get('root_pc') is not None and seg['root_pc'] == root:
            want_minor = 3 in ivs
            sfx = seg.get('sfx', '')
            if sfx in neutral or ('sus' in name.lower()):
                ok = True
            else:
                ok = (sfx in minorish) == want_minor
        correct += ok
        rows.append(f'  bar {b + 1:2d}: want {name:6s} got {got:10s} {"✓" if ok else "✗"}')
    print('\n'.join(rows))
    acc = correct / N_BARS
    print(f'chord accuracy: {correct}/{N_BARS} = {acc:.0%}')
    if acc < 0.9:
        failures.append(f'chord accuracy {acc:.0%} < 90%')

    n_seg = len([s for s in segments if s['chord'] != 'N'])
    if n_seg > 24:
        failures.append(f'{n_seg} chord segments (flicker? expected ~14-20)')

    want_pitches = set(MELODY_DEGREES)
    hit = sum(1 for n in melody['notes'] if n['midi'] in want_pitches)
    print(f"melody: engine={melody['engine']} notes={len(melody['notes'])} "
          f'in-scale-hits={hit}')
    if melody['engine'] and hit < 16:
        failures.append(f'melody recovered only {hit}/32 expected notes')

    if failures:
        print('\nSELFTEST FAIL:')
        for f in failures:
            print(f'  - {f}')
        return 1
    print('\nSELFTEST PASS')
    return 0


if __name__ == '__main__':
    sys.exit(main())
