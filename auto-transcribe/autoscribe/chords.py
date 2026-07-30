"""Chord recognition: Viterbi segmentation over a core vocabulary, then
exact ChordHUD-vocabulary labeling per segment.

Stage 1 keeps the state space small (12 roots x 8 qualities + N) so the HMM
is robust on noisy chroma; stage 2 re-labels each segment with the full
22-template ChordHUD detector so names/alts match the HUD exactly.
All tuning constants live at the top for easy tweaking.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from .hud_port import INTERVAL_WEIGHTS, detect_chords

# ── stage-1 vocabulary ──
CORE_QUALITIES = [
    ('maj',  (0, 4, 7)),
    ('min',  (0, 3, 7)),
    ('7',    (0, 4, 7, 10)),
    ('maj7', (0, 4, 7, 11)),
    ('m7',   (0, 3, 7, 10)),
    ('sus4', (0, 5, 7)),
    ('dim',  (0, 3, 6)),
    ('m7b5', (0, 3, 6, 10)),
]
N_QUAL = len(CORE_QUALITIES)
N_STATE = 12 * N_QUAL + 1          # +1 = N (no chord)
N_IDX = N_STATE - 1

# ── tuning constants ──
NON_TEMPLATE_PENALTY = 0.7          # per unit chroma mass outside the template
BASS_ROOT_BONUS = 1.2               # x bass conf, when bass pc == root
BASS_TONE_BONUS = 0.6               # x bass conf, when bass pc is another chord tone
EMIT_TEMP = 0.35                    # divide scores by this → log-emission scale
CHANGE_COST = 4.5                   # base log-cost of switching chords
CHANGE_MULT = {'downbeat': 0.4, 'midbar': 0.7, 'beat': 1.0, 'offbeat': 1.6}
N_ENERGY_FLOOR = 0.35               # below this (x median energy) N looks likely
MIN_SEG_BEATS = 1.0                 # absorb shorter segments into neighbors
PC_KEEP = 0.4                       # stage-2: keep pcs with chroma >= this
PC_KEEP_TMPL = 0.25                 # ...or template tones above this
PC_CAP = 6
BASS_STABLE_FRAC = 0.6              # modal bass must cover this to make a slash


def _emissions(chroma: np.ndarray, energy: np.ndarray, bass: dict) -> np.ndarray:
    """(F, N_STATE) log-domain emission scores."""
    F = chroma.shape[1]
    scores = np.zeros((F, N_STATE))
    bass_pc = np.asarray(bass['pc'])
    bass_conf = np.asarray(bass['conf'])
    energy_damp = np.sqrt(np.clip(energy, 0.0, 1.5))
    for qi, (_name, ivs) in enumerate(CORE_QUALITIES):
        w = np.array([INTERVAL_WEIGHTS[iv] for iv in ivs])
        for root in range(12):
            tones = [(root + iv) % 12 for iv in ivs]
            mask = np.zeros(12, bool)
            mask[tones] = True
            s = (w[:, None] * chroma[tones, :]).sum(axis=0)
            s = s - NON_TEMPLATE_PENALTY * chroma[~mask, :].sum(axis=0)
            s = s * energy_damp
            bb = np.where(bass_pc == root, BASS_ROOT_BONUS,
                          np.where(np.isin(bass_pc, tones), BASS_TONE_BONUS, 0.0))
            scores[:, root * N_QUAL + qi] = s + bb * bass_conf
    scores[:, N_IDX] = 2.0 * (N_ENERGY_FLOOR - np.clip(energy, 0, 2))
    logits = scores / EMIT_TEMP
    return logits - logits.max(axis=1, keepdims=True)


def _viterbi(emis: np.ndarray, kinds: list[str]) -> np.ndarray:
    F, S = emis.shape
    dp = emis[0].copy()
    back = np.zeros((F, S), dtype=np.int32)
    for f in range(1, F):
        cost = CHANGE_COST * CHANGE_MULT.get(kinds[f], 1.0)
        best_prev = int(np.argmax(dp))
        stay = dp                       # no cost to stay in the same state
        move = dp[best_prev] - cost     # best single predecessor for a switch
        take_move = move > stay
        back[f] = np.where(take_move, best_prev, np.arange(S))
        dp = np.where(take_move, move, stay) + emis[f]
    path = np.zeros(F, dtype=np.int32)
    path[-1] = int(np.argmax(dp))
    for f in range(F - 1, 0, -1):
        path[f - 1] = back[f, path[f]]
    return path


def _merge_segments(path: np.ndarray, bounds: np.ndarray,
                    beat_pos: np.ndarray) -> list[dict]:
    segs = []
    start = 0
    for f in range(1, len(path) + 1):
        if f == len(path) or path[f] != path[start]:
            segs.append({'state': int(path[start]), 'f0': start, 'f1': f})
            start = f
    # absorb tiny segments into the longer neighbor
    def seg_beats(s):
        return beat_pos[min(s['f1'], len(beat_pos) - 1)] - beat_pos[s['f0']] \
            if s['f1'] < len(beat_pos) else beat_pos[-1] - beat_pos[s['f0']] + 0.5
    changed = True
    while changed and len(segs) > 1:
        changed = False
        for i, s in enumerate(segs):
            if seg_beats(s) >= MIN_SEG_BEATS:
                continue
            left = segs[i - 1] if i > 0 else None
            right = segs[i + 1] if i < len(segs) - 1 else None
            target = left if (right is None or (left is not None and
                              seg_beats(left) >= seg_beats(right))) else right
            if target is None:
                continue
            if target is left:
                left['f1'] = s['f1']
            else:
                right['f0'] = s['f0']
            segs.pop(i)
            changed = True
            break
    return segs


def _label_segment(seg, chroma, energy, bass, note_names, viterbi_margin):
    f0, f1 = seg['f0'], seg['f1']
    med = np.median(chroma[:, f0:f1], axis=1)
    m = med.max() or 1.0
    med = med / m

    state = seg['state']
    if state == N_IDX:
        return None
    root1 = state // N_QUAL
    ivs1 = CORE_QUALITIES[state % N_QUAL][1]
    tmpl_tones = [(root1 + iv) % 12 for iv in ivs1]

    pcs = {pc for pc in range(12) if med[pc] >= PC_KEEP}
    pcs |= {pc for pc in tmpl_tones if med[pc] >= PC_KEEP_TMPL}
    if len(pcs) > PC_CAP:
        pcs = set(sorted(pcs, key=lambda p: -med[p])[:PC_CAP])
    if not pcs:
        return None

    # modal bass over the segment
    bpc = np.asarray(bass['pc'][f0:f1])
    bconf = np.asarray(bass['conf'][f0:f1])
    voiced = bpc >= 0
    bass_pc = None
    if voiced.any():
        vals, counts = np.unique(bpc[voiced], return_counts=True)
        mode_pc = int(vals[np.argmax(counts)])
        frac = counts.max() / voiced.sum()
        if frac >= BASS_STABLE_FRAC and float(bconf[voiced].mean()) > 0.5:
            bass_pc = mode_pc

    cands = detect_chords(sorted(pcs), bass_pc, note_names)
    if not cands:
        return None
    for c in cands:
        if c['root'] == root1:
            c['score'] += 1.0
    cands.sort(key=lambda c: -c['score'])

    top = cands[0]
    # confidence keyed to the best DIFFERENT-root rival: a wrong root is the
    # costly error; same-root quality variants are one click away in alts
    rival = next((c for c in cands[1:] if c['root'] != top['root']), None)
    gap = top['score'] - rival['score'] if rival else 4.0
    conf = float(1 / (1 + np.exp(-gap / 2.0))) * float(np.clip(viterbi_margin, 0.2, 1.0))
    alt_names = []
    for c in cands[1:]:
        if c['name'] != top['name'] and c['name'] not in alt_names:
            alt_names.append(c['name'])
        if len(alt_names) == 4:
            break
    return {'chord': top['name'], 'root_pc': top['root'], 'sfx': top['sfx'],
            'bass_pc': bass_pc, 'alts': alt_names, 'conf': round(conf, 3)}


def recognize(chroma_data: dict, bass: dict, grid: dict, key: dict,
              note_names: list[str], out_json: Path) -> dict:
    chroma = chroma_data['chroma']
    energy = chroma_data['energy']
    bounds = grid['bounds']
    kinds = grid['kind']
    beat_pos = grid['beat_pos']

    emis = _emissions(chroma, energy, bass)
    path = _viterbi(emis, kinds)
    segs = _merge_segments(path, bounds, beat_pos)

    # per-frame emission margin of the chosen state vs the best other state
    margins = np.zeros(len(path))
    for f in range(len(path)):
        row = emis[f]
        chosen = row[path[f]]
        other = np.delete(row, path[f]).max()
        margins[f] = 1 / (1 + np.exp(-(chosen - other)))

    segments = []
    for seg in segs:
        t0 = float(bounds[seg['f0']])
        t1 = float(bounds[min(seg['f1'], len(bounds) - 1)])
        vm = float(margins[seg['f0']:seg['f1']].mean())
        lab = _label_segment(seg, chroma, energy, bass, note_names, vm)
        if lab is None:
            segments.append({'start': round(t0, 4), 'end': round(t1, 4),
                             'chord': 'N', 'alts': [], 'conf': 1.0,
                             'root_pc': None, 'sfx': '', 'bass_pc': None})
        else:
            segments.append({'start': round(t0, 4), 'end': round(t1, 4), **lab})

    # merge consecutive identical chord names (ChordHUD import behavior)
    merged = []
    for s in segments:
        if merged and merged[-1]['chord'] == s['chord']:
            merged[-1]['end'] = s['end']
            merged[-1]['conf'] = min(merged[-1]['conf'], s['conf'])
        else:
            merged.append(s)

    result = {'segments': merged}
    out_json.write_text(json.dumps(result), encoding='utf-8')
    return result


def load(chords_json: Path) -> dict:
    return json.loads(chords_json.read_text(encoding='utf-8'))
