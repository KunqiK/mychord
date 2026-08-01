r"""Distill Chordonomicon (667k songs, CC BY 4.0) into a transposition-
invariant chord-progression prior for the chords stage.

Reads  models\chordonomicon\chordonomicon_v2.csv   (HuggingFace ailsntua/
       Chordonomicon; 'chords' column = space-separated tokens with <section>
       markers, sharps written as 's': "Cs" = C#, "Csmin7" = C#m7)
Writes models\progressions.npz:
       logp   float32 (8, 12, 8)  log P(droot, q_to | q_from), add-1 smoothed
              over consecutive DISTINCT chords; droot = (root_to - root_from) % 12
       counts float32 (8, 12, 8)  raw bigram counts (for later re-weighting)
       qualities = the 8 core qualities in chords.py stage-1 order

Run:  .venv\Scripts\python.exe build_progressions.py [main_genre_filter]
"""
from __future__ import annotations

import csv
import re
import sys
from collections import Counter
from pathlib import Path

import numpy as np

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

HERE = Path(__file__).resolve().parent
CSV = HERE / 'models' / 'chordonomicon' / 'chordonomicon_v2.csv'
OUT = HERE / 'models' / 'progressions.npz'

QUALITIES = ['maj', 'min', '7', 'maj7', 'm7', 'sus4', 'dim', 'm7b5']
Q_IDX = {q: i for i, q in enumerate(QUALITIES)}

_ROOT = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}

# suffix (after root) -> core quality; longest match wins
_SUFFIX = {
    '': 'maj', 'maj': 'maj', '5': 'maj', '6': 'maj', 'add9': 'maj',
    'maj9': 'maj7', 'maj7': 'maj7', 'maj11': 'maj7', 'maj13': 'maj7',
    'min': 'min', 'min6': 'min', 'minadd9': 'min',
    'min7': 'm7', 'min9': 'm7', 'min11': 'm7', 'min13': 'm7',
    'minmaj7': 'm7',
    '7': '7', '9': '7', '11': '7', '13': '7', '7sus4': '7',
    'sus2': 'sus4', 'sus4': 'sus4', 'sus': 'sus4',
    'dim': 'dim', 'dim7': 'dim', 'aug': 'maj',
    'min7b5': 'm7b5', 'm7b5': 'm7b5',
    'no3d': 'maj', '7no3d': '7', 'add13': 'maj', 'add11': 'maj',
    'Gadd13': 'maj', 'maj6': 'maj', 'min6/9': 'min', '6/9': 'maj',
}
# 's' is a sharp ONLY when not the start of 'sus' (Dsus4 != D# 'us4')
_TOKEN = re.compile(r'^([A-G])(s(?!us)|b)?(.*)$')


def parse(tok: str):
    """-> (root_pc, quality_idx) or None."""
    tok = tok.split('/')[0]                   # slash bass: chord part only
    m = _TOKEN.match(tok)
    if not m:
        return None
    root = _ROOT[m.group(1)]
    if m.group(2) == 's':
        root = (root + 1) % 12
    elif m.group(2) == 'b':
        root = (root - 1) % 12
    q = _SUFFIX.get(m.group(3))
    if q is None:
        return None
    return root, Q_IDX[q]


def main() -> None:
    genre_filter = sys.argv[1] if len(sys.argv) > 1 else None
    counts = np.zeros((8, 12, 8), dtype=np.float64)
    unmapped: Counter = Counter()
    n_songs = n_bigrams = 0
    with open(CSV, encoding='utf-8', errors='replace', newline='') as f:
        rd = csv.DictReader(f)
        for row in rd:
            if genre_filter and genre_filter not in (row.get('main_genre') or ''):
                continue
            seq = []
            for tok in row['chords'].split():
                if tok.startswith('<'):
                    continue
                pq = parse(tok)
                if pq is None:
                    unmapped[tok] += 1
                    continue
                if not seq or seq[-1] != pq:      # collapse repeats
                    seq.append(pq)
            if len(seq) < 2:
                continue
            n_songs += 1
            for (r1, q1), (r2, q2) in zip(seq[:-1], seq[1:]):
                counts[q1, (r2 - r1) % 12, q2] += 1
                n_bigrams += 1
    smoothed = counts + 1.0
    logp = np.log(smoothed / smoothed.sum(axis=(1, 2), keepdims=True))
    np.savez_compressed(OUT, logp=logp.astype(np.float32),
                        counts=counts.astype(np.float32),
                        qualities=np.array(QUALITIES))
    print(f'{n_songs} songs, {n_bigrams} bigrams -> {OUT.name}'
          + (f' (main_genre~{genre_filter})' if genre_filter else ' (all genres)'))
    print('top unmapped tokens:', unmapped.most_common(12))
    up = np.log(1.0 / 96)
    top = np.argsort(logp, axis=None)[::-1][:8]
    for t in top:
        q1, dr, q2 = np.unravel_index(t, logp.shape)
        print(f'  P({QUALITIES[q1]} -> +{dr} {QUALITIES[q2]}) '
              f'logp {logp[q1, dr, q2]:.2f} (uniform {up:.2f})')


if __name__ == '__main__':
    main()
