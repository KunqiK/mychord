"""ChordHUD v5 project emitter.

Roman-numeral tables live right here at the top — tweak to taste.
"""
from __future__ import annotations

import json
from pathlib import Path

from .hud_port import key_notes

# degree (semitones above tonic) → roman base, per mode.  Case is adjusted
# from chord quality afterward (upper = major-ish, lower = minor-ish).
ROMAN_MAJOR = ['I', '♭II', 'II', '♭III', 'III', 'IV',
               '♭V', 'V', '♭VI', 'VI', '♭VII', 'VII']
ROMAN_MINOR = ['i', '♭II', 'ii', 'III', '♯III', 'iv',
               '♯iv', 'v', 'VI', '♯vi', 'VII', '♯vii']

MINORISH = ('m', 'm7', 'm6', 'm9', 'mMaj7', 'dim', 'dim7', 'm7b5')
SUFFIX_LABEL = {
    '': '', 'm': '', 'maj7': 'maj7', 'mMaj7': 'maj7', 'm7': '7', '7': '7',
    'maj9': 'maj9', 'm9': '9', '9': '9', '7b9': '7♭9', '7#9': '7♯9',
    '6': '6', 'm6': '6', 'add9': 'add9', 'sus2': 'sus2', 'sus4': 'sus4',
    '7sus4': '7sus4', 'dim': '°', 'dim7': '°7', 'm7b5': 'ø7',
    'aug': '+', 'augMaj7': '+maj7',
}
CONF_FLAG_BELOW = 0.45   # segments under this confidence get a trailing "?"


def roman_for(root_pc: int, sfx: str, key: dict) -> str:
    deg = (root_pc - key['tonic_pc']) % 12
    base = (ROMAN_MINOR if key['mode'] == 'min' else ROMAN_MAJOR)[deg]
    if sfx in MINORISH:
        base = base.lower()
    else:
        head = ''.join(c for c in base if c in '♭♯')
        base = head + base.replace('♭', '').replace('♯', '').upper()
    return base + SUFFIX_LABEL.get(sfx, sfx)


def emit(segments: list[dict], beats: dict, key: dict, duration: float,
         title: str, out_path: Path, grid_zero: bool = False) -> dict:
    offset = beats.get('first_downbeat', 0.0) if grid_zero else 0.0
    from .beats import bar_beat_at

    timeline = []
    for seg in segments:
        if seg['chord'] == 'N' or seg.get('root_pc') is None:
            continue
        t = seg['start'] - offset
        if t < -0.05:
            continue
        t = max(t, 0.0)
        roman = roman_for(seg['root_pc'], seg.get('sfx', ''), key)
        if seg.get('conf', 1.0) < CONF_FLAG_BELOW:
            roman += '?'
        bar, beat = bar_beat_at(seg['start'], beats)
        timeline.append({
            'time': round(t, 3),
            'bar': bar, 'beat': beat,
            'chord': seg['chord'],
            'group': '',
            'annotation': roman,
            'carry': 0,
            'emphasis': False,
            'active': [(seg['root_pc'] - key['tonic_pc']) % 12],
            'alts': seg.get('alts', []),
        })

    project = {
        'version': 5,
        'bpm': str(int(round(beats['bpm']))),
        'key': key['name'],
        'title': title,
        'total': str(int(round(max(duration - offset, 1)))),  # in-total is a seconds <input type=number>
        'accidental': 'sharp' if key['dir_sharp'] else 'flat',
        'timingMode': 'seconds',
        'beatsPerBar': beats['beats_per_bar'],
        'meterMap': [{'startBar': 1, 'beatsPerBar': beats['beats_per_bar']}],
        'globalNotes': key_notes(key['root'], key['mode']),
        'activeKey': key['active_key'],
        'timeline': timeline,
    }
    out_path.write_text(json.dumps(project, ensure_ascii=False, indent=2),
                        encoding='utf-8')
    return project
