"""Auto-classify tracks of a full multitrack GT MIDI into roles.

The user will supply reference MIDIs containing ALL tracks (no manual
split). This finds which tracks carry harmony (chords), melody, bass and
drums so evaluate_gt / future training can use them automatically.

Heuristics per track (measured on the S.A.T.E.L.L.I.T.E. 24-track GT):
- drums: name contains drum/kick/perc/hat/snare/cymbal (GM channel 10 is
  not preserved by our loader, names are)
- bass: low register (median pitch < 50) and essentially monophonic
- harmony: polyphonic — mean simultaneous sounding notes >= 2.2
- melody: monophonic, mid/high register, enough notes to be a line
Everything else: 'other' (FX, doubles, sparse pads).

Usage:
  .venv\\Scripts\\python.exe gt_tracks.py "path\\to\\full GT.mid"
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from evaluate_gt import load_midi_notes  # noqa: E402

DRUM_RE = re.compile(r'drum|kick|snare|hat|perc|cymbal|tom|clap',
                     re.IGNORECASE)
VOCAL_RE = re.compile(r'vocal|vox|sing|唱', re.IGNORECASE)
LEAD_RE = re.compile(r'lead|melody|主旋', re.IGNORECASE)


def _polyphony(notes) -> float:
    """Mean number of simultaneously sounding notes (sampled at onsets)."""
    if len(notes) < 4:
        return 1.0
    counts = []
    for n in notes:
        t = n['start'] + 0.02
        counts.append(sum(1 for m in notes if m['start'] <= t < m['end']))
    return float(np.mean(counts))


def classify(tracks: dict) -> dict:
    """track name → role in {'harmony','melody','bass','drums','other'}."""
    roles = {}
    for name, notes in tracks.items():
        if not notes:
            continue
        pitches = [n['midi'] for n in notes]
        med = float(np.median(pitches))
        poly = _polyphony(notes)
        span = max(n['end'] for n in notes) - min(n['start'] for n in notes)
        if DRUM_RE.search(name or ''):
            roles[name] = 'drums'
        elif med < 50 and poly < 1.4:
            roles[name] = 'bass'
        elif poly >= 1.8 and med >= 48:
            # >=1.8 catches string sections (overlapping bows read ~1.9);
            # med>=48 keeps low FX growls out of the harmony pool
            roles[name] = 'harmony'
        elif poly < 1.6 and 52 <= med <= 88 and len(notes) >= 30 and span > 20:
            # 1.6 tolerates release-tail overlaps of synth leads
            roles[name] = 'melody'
        else:
            roles[name] = 'other'
    return roles


def pick(tracks: dict) -> dict:
    """Role → comma-joined track names (evaluate_gt argument format)."""
    roles = classify(tracks)
    out = {}
    for role in ('harmony', 'melody', 'bass', 'drums'):
        names = [n for n, r in roles.items() if r == role]
        if role == 'melody' and len(names) > 1:
            # THE melody: vocals first, then lead-named, then busiest
            names.sort(key=lambda n: (0 if VOCAL_RE.search(n or '') else
                                      1 if LEAD_RE.search(n or '') else 2,
                                      -len(tracks[n])))
        out[role] = names
    return out


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    tracks, bpm = load_midi_notes(Path(sys.argv[1]))
    print(f'{len(tracks)} tracks, bpm {bpm:.1f}')
    roles = classify(tracks)
    for name, notes in sorted(tracks.items(), key=lambda kv: -len(kv[1])):
        pitches = [n['midi'] for n in notes]
        print(f'  {roles.get(name, "?"):8s} {name!r:22s} n={len(notes):5d} '
              f'medpitch={int(np.median(pitches)):3d} '
              f'poly={_polyphony(notes):.1f}')
    sel = pick(tracks)
    print('\nevaluate_gt suggestion:')
    print(f"  --harmony \"{','.join(sel['harmony'])}\"")
    print(f"  --melody \"{','.join(sel['melody'][:1])}\"")
    print(f"  --bass \"{','.join(sel['bass'])}\"")
    print(f"  --drums \"{','.join(sel['drums'])}\"")
    return 0


if __name__ == '__main__':
    sys.exit(main())
