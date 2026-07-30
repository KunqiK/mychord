"""1:1 ports of ChordHUD v17.4 chord-detection and key-spelling code.

Port sources (chord_hud_v17.4.html):
  NOTE_NAMES        line 3385
  CHORD_TEMPLATES   lines 3386-3412
  INTERVAL_WEIGHTS  line 3765
  detectChords      lines 3767-3789
  _NOTE_PC/_KEY_SHARPS/keyNotes  lines 3975-4014

Keep behavior identical to the HTML so pipeline output names match what
ChordHUD's own MIDI import would produce.
"""
from __future__ import annotations

NOTE_NAMES = ['C', 'C#', 'D', 'Eb', 'E', 'F', 'F#', 'G', 'Ab', 'A', 'Bb', 'B']
SHARP_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
FLAT_NAMES = ['C', 'Db', 'D', 'Eb', 'E', 'F', 'Gb', 'G', 'Ab', 'A', 'Bb', 'B']

# (suffix, intervals) — order matters only for tie display; scoring is absolute
CHORD_TEMPLATES = [
    # 5-note
    ('maj9',    (0, 2, 4, 7, 11)),
    ('m9',      (0, 2, 3, 7, 10)),
    ('9',       (0, 2, 4, 7, 10)),
    ('7b9',     (0, 1, 4, 7, 10)),
    ('7#9',     (0, 3, 4, 7, 10)),
    # 4-note
    ('maj7',    (0, 4, 7, 11)),
    ('mMaj7',   (0, 3, 7, 11)),
    ('m7',      (0, 3, 7, 10)),
    ('m7b5',    (0, 3, 6, 10)),
    ('7',       (0, 4, 7, 10)),
    ('7sus4',   (0, 5, 7, 10)),
    ('augMaj7', (0, 4, 8, 11)),
    ('dim7',    (0, 3, 6, 9)),
    ('6',       (0, 4, 7, 9)),
    ('m6',      (0, 3, 7, 9)),
    ('add9',    (0, 2, 4, 7)),
    # 3-note
    ('aug',     (0, 4, 8)),
    ('dim',     (0, 3, 6)),
    ('sus4',    (0, 5, 7)),
    ('sus2',    (0, 2, 7)),
    ('',        (0, 4, 7)),
    ('m',       (0, 3, 7)),
]

# Per-semitone weights: root, m2, M2, m3, M3, P4, TT, P5, m6, M6, m7, M7
INTERVAL_WEIGHTS = [3, 0.5, 1, 2.5, 2.5, 1, 1.5, 1.5, 1, 1.5, 2, 2]

import math


def detect_chords(pitch_classes, bass_pc=None, note_names=None):
    """Port of ChordHUD detectChords(). Returns up to 8 (name, score) desc.

    note_names lets the caller spell roots per key direction (ChordHUD's
    transpose parser accepts both # and b spellings).
    """
    names = note_names if note_names is not None else NOTE_NAMES
    pcs = list(dict.fromkeys(int(p) % 12 for p in pitch_classes))
    candidates = []
    for root in range(12):
        for sfx, ivs in CHORD_TEMPLATES:
            needed = [(root + iv) % 12 for iv in ivs]
            hits = sum(1 for n in needed if n in pcs)
            if hits < math.ceil(len(ivs) * 0.75):
                continue
            missing = len(ivs) - hits
            extra = sum(1 for p in pcs if p not in needed)
            score = sum(INTERVAL_WEIGHTS[iv] for iv in ivs
                        if (root + iv) % 12 in pcs) - missing * 1.5 - extra * 1
            name = names[root] + sfx
            if bass_pc is not None and bass_pc % 12 != root:
                name += '/' + names[bass_pc % 12]
            candidates.append({'name': name, 'score': score, 'root': root, 'sfx': sfx})
    candidates.sort(key=lambda c: -c['score'])
    return candidates[:8]


# ── key spelling engine (port of _KEY_SHARPS / keyNotes) ──
_NOTE_PC = {'C': 0, 'C#': 1, 'Db': 1, 'D': 2, 'D#': 3, 'Eb': 3, 'E': 4, 'Fb': 4,
            'E#': 5, 'F': 5, 'F#': 6, 'Gb': 6, 'G': 7, 'G#': 8, 'Ab': 8, 'A': 9,
            'A#': 10, 'Bb': 10, 'B': 11, 'Cb': 11, 'B#': 0}
_LETTERS7 = ['C', 'D', 'E', 'F', 'G', 'A', 'B']
_LETTER_PC = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}
_NAT_PC = {0: 'C', 2: 'D', 4: 'E', 5: 'F', 7: 'G', 9: 'A', 11: 'B'}
_SHARP_PC = {1: 'C#', 3: 'D#', 6: 'F#', 8: 'G#', 10: 'A#'}
_FLAT_PC = {1: 'Db', 3: 'Eb', 6: 'Gb', 8: 'Ab', 10: 'Bb'}
KEY_SHARPS = {
    'C|maj': 0, 'G|maj': 1, 'D|maj': 2, 'A|maj': 3, 'E|maj': 4, 'B|maj': 5,
    'F#|maj': 6, 'C#|maj': 7, 'F|maj': -1, 'Bb|maj': -2, 'Eb|maj': -3,
    'Ab|maj': -4, 'Db|maj': -5, 'Gb|maj': -6, 'Cb|maj': -7,
    'A|min': 0, 'E|min': 1, 'B|min': 2, 'F#|min': 3, 'C#|min': 4, 'G#|min': 5,
    'D#|min': 6, 'A#|min': 7, 'D|min': -1, 'G|min': -2, 'C|min': -3,
    'F|min': -4, 'Bb|min': -5, 'Eb|min': -6, 'Ab|min': -7,
}

# tonic pc + mode → the root spelling used by ChordHUD's key buttons
# (chosen to exist in KEY_SHARPS; ties resolved toward fewer accidentals)
MAJOR_ROOT_FOR_PC = {0: 'C', 1: 'Db', 2: 'D', 3: 'Eb', 4: 'E', 5: 'F',
                     6: 'Gb', 7: 'G', 8: 'Ab', 9: 'A', 10: 'Bb', 11: 'B'}
MINOR_ROOT_FOR_PC = {0: 'C', 1: 'C#', 2: 'D', 3: 'Eb', 4: 'E', 5: 'F',
                     6: 'F#', 7: 'G', 8: 'G#', 9: 'A', 10: 'Bb', 11: 'B'}


def _acc_str(letter, pc):
    d = (pc - _LETTER_PC[letter] + 12) % 12
    if d > 6:
        d -= 12
    return letter + ('#' * d if d > 0 else 'b' * -d)


def key_notes(root, mode):
    """Port of keyNotes(): 12 chromatic note names, index 0 = tonic."""
    root_pc = _NOTE_PC[root]
    root_letter_idx = _LETTERS7.index(root[0])
    steps = [0, 2, 3, 5, 7, 8, 10] if mode == 'min' else [0, 2, 4, 5, 7, 9, 11]
    dir_sharp = KEY_SHARPS.get(root + '|' + mode, 0) > 0
    notes = [None] * 12
    for i in range(7):
        letter = _LETTERS7[(root_letter_idx + i) % 7]
        notes[steps[i]] = _acc_str(letter, (root_pc + steps[i]) % 12)
    for pos in range(12):
        if notes[pos]:
            continue
        pc = (root_pc + pos) % 12
        if pc in _NAT_PC:
            notes[pos] = _NAT_PC[pc]
            continue
        use_sharp = dir_sharp
        if mode == 'min' and pos in (9, 11):  # raised 6/7
            use_sharp = True
        notes[pos] = _SHARP_PC[pc] if use_sharp else _FLAT_PC[pc]
    return notes


def key_spelling(tonic_pc, mode):
    """Return (root_name, active_key, dir_sharp, note_names_for_roots)."""
    root = (MINOR_ROOT_FOR_PC if mode == 'min' else MAJOR_ROOT_FOR_PC)[tonic_pc % 12]
    active_key = f'{root}|{mode}'
    dir_sharp = KEY_SHARPS.get(active_key, 0) > 0
    return root, active_key, dir_sharp, (SHARP_NAMES if dir_sharp else FLAT_NAMES)
