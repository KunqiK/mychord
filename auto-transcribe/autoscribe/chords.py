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

from .hud_port import (CHORD_TEMPLATES, INTERVAL_WEIGHTS, NOTE_NAMES,
                       detect_chords)

_TMPL_BY_SFX = dict(CHORD_TEMPLATES)


def _candidates_ext(pitch_classes, bass_pc=None, note_names=None,
                    cap=16, missing_pen=1.5):
    """Widened detect_chords (mirrors hud_port's verbatim port): more
    candidates survive to evidence rescoring, and rootless shell voicings
    (3rd+5th+7th present, root absent — jazz comping norm) are punished a
    little less. The port itself stays untouched; alts/labels remain
    ChordHUD-compatible names."""
    import math
    names = note_names if note_names is not None else NOTE_NAMES
    pcs = list(dict.fromkeys(int(p) % 12 for p in pitch_classes))
    out = []
    for root in range(12):
        for sfx, ivs in CHORD_TEMPLATES:
            needed = [(root + iv) % 12 for iv in ivs]
            hits = sum(1 for n in needed if n in pcs)
            if hits < math.ceil(len(ivs) * 0.75):
                continue
            missing = len(ivs) - hits
            extra = sum(1 for p in pcs if p not in needed)
            score = sum(INTERVAL_WEIGHTS[iv] for iv in ivs
                        if (root + iv) % 12 in pcs) \
                - missing * missing_pen - extra * 1
            name = names[root] + sfx
            if bass_pc is not None and bass_pc % 12 != root:
                name += '/' + names[bass_pc % 12]
            out.append({'name': name, 'score': score, 'root': root, 'sfx': sfx})
    out.sort(key=lambda c: -c['score'])
    return out[:cap]

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
BASS_ROOT_BONUS = 2.0               # x bass conf, when bass pc == root
BASS_TONE_BONUS = 0.6               # x bass conf, when bass pc is another chord tone
BASS_MISS_PENALTY = 0.6             # x bass conf, when bass pc is NOT a chord tone
EMIT_TEMP = 0.35                    # divide scores by this → log-emission scale
CHANGE_COST = 8.0                   # base log-cost of switching chords
# (re-tuned 2026-07-31 on the corrected chart reading: the TRUE harmonic
#  rhythm is ~1.8s/chord — the earlier 0.89s figure counted piano fills as
#  changes and led to 2.4x oversegmentation at CHANGE_COST 3.5. Piano voicing
#  onsets get a discount via cost_mult, so real changes still go through.)
CHANGE_MULT = {'downbeat': 0.4, 'midbar': 0.7, 'beat': 1.0, 'offbeat': 1.6}
ENERGY_DAMP_FLOOR = 0.25            # quiet-but-structured frames keep >=sqrt(.25) weight
N_ENERGY_FLOOR = 0.15               # N needs BOTH low energy (x median) ...
N_STRUCTURE_FLOOR = 2.0             # ... and flat chroma (1/mean of max-normed chroma)
MIN_SEG_BEATS = 2.0                 # absorb shorter segments into neighbors
PC_KEEP = 0.4                       # stage-2: keep pcs with chroma >= this
PC_KEEP_TMPL = 0.25                 # ...or template tones above this
PC_CAP = 6
BASS_STABLE_FRAC = 0.5              # modal bass must cover this to be trusted
BASS_CONF_MIN = 0.35                # ...at at least this mean pyin confidence
STAGE2_BASS_ROOT_BONUS = 0.5        # stage-2 candidates rooted on the bass pc
# (was 1.5 — the user's reference chart roots on the bass only 38% of the
#  time; the bass is usually a pedal under the comping stack, so a big bonus
#  produced wrong-root readings like Bbm9 for Fm7/Bb)
EXOTIC_SFX = {'7b9', '7#9', 'mMaj7', 'augMaj7'}   # rarely correct on dirty chroma
EXOTIC_PENALTY = 0.8                # prior against exotic labels in ties
EVIDENCE_W = 6.0                    # weight of mean per-tone evidence strength
ROOT_EV_W = 3.0                     # extra weight on the root tone's evidence
UNCOV_W = 0.0                       # penalty per unit of evidence mass the reading leaves
                                    # unexplained — measured NEUTRAL-to-worse (evidence pc
                                    # sets carry ~25% spurious pcs, so demanding full
                                    # coverage backfires); kept as an experiment knob
# (candidates were previously ranked on pc membership alone — a weak bleed pc
#  like a Bb pedal could anchor a wrong-root reading such as Bbm9 over the
#  user's Fm7/Bb; scoring by evidence strength keeps the root on strong tones)
# ── stem note evidence (the user's reference chart IS the comping
#    instrument: tertian stacking over its voiced pcs is how chords get named) ──
PIANO_PC_KEEP = 0.25                # keep pcs >= this share of the strongest pc
PIANO_MIN_PCS = 3                   # need a real voicing, not a fill
PIANO_MIN_COVER = 0.35              # piano must sound over this share of the segment
PIANO_ONSET_EPS = 0.05              # chord-onset grouping window (s)
PIANO_ONSET_DISCOUNT = 0.5          # change-cost multiplier near a piano voicing onset
SYNTH_MIN_COVER = 0.8               # synth-stem-alone fallback needs denser coverage
SYNTH_BLEND_W = 0.15                # synth (pad) evidence folded UNDER gating piano evidence:
                                    # the piano-stem transcription drops quiet mid-voice
                                    # tones — often the ROOT itself (Fm7/Bb came out as
                                    # {Ab,Bb,C,Eb}, no F) — while the pad voices it
PIANO_BLEND_W = 0.0                 # piano folded under gating synth evidence: keep OFF —
                                    # a piano source that failed its own gate is noise
BLEED_FACTOR = 1.0                  # sustained-in notes count fully (penalizing them measured WORSE
                                    # — held pedal chords are genuine harmony, not bleed)
SPLIT_AT_ONSETS = False             # cutting segments at piano onsets measured WORSE on root
                                    # (short pieces lose context) despite +compat/+boundary-F;
                                    # kept as an experiment switch
MIN_PIECE_BEATS = 1.5               # do not create pieces shorter than this


def _emissions(chroma: np.ndarray, energy: np.ndarray, bass: dict) -> np.ndarray:
    """(F, N_STATE) log-domain emission scores."""
    F = chroma.shape[1]
    scores = np.zeros((F, N_STATE))
    bass_pc = np.asarray(bass['pc'])
    bass_conf = np.asarray(bass['conf'])
    # damp quiet frames only mildly: chroma is max-normalized, so a quiet but
    # harmonically clear intro still deserves a chord (the N state handles
    # true silence via the structure test below)
    energy_damp = np.sqrt(np.clip(energy, ENERGY_DAMP_FLOOR, 1.5))
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
                          np.where(np.isin(bass_pc, tones), BASS_TONE_BONUS,
                                   -BASS_MISS_PENALTY))
            bb = np.where(bass_pc >= 0, bb, 0.0)
            scores[:, root * N_QUAL + qi] = s + bb * bass_conf
    # N needs BOTH low energy and an unstructured (flat) chroma frame
    structure = 1.0 / np.maximum(chroma.mean(axis=0), 1e-3)
    scores[:, N_IDX] = (1.2 * (N_ENERGY_FLOOR - np.clip(energy, 0, 2)) / N_ENERGY_FLOOR
                        + 1.2 * (N_STRUCTURE_FLOOR - structure) / N_STRUCTURE_FLOOR)
    logits = scores / EMIT_TEMP
    return logits - logits.max(axis=1, keepdims=True)


def _note_pc_weights(notes, t0: float, t1: float) -> np.ndarray:
    """(12,) duration x velocity pc mass of notes inside [t0, t1).

    Notes that onset before the segment are bleed from the previous voicing
    (sustain/pedal tails, separation smear) and count at BLEED_FACTOR."""
    w = np.zeros(12)
    for n in notes:
        ov = min(n['end'], t1) - max(n['start'], t0)
        if ov <= 0.03:
            continue
        f = 1.0 if n['start'] >= t0 - 0.08 else BLEED_FACTOR
        w[n['midi'] % 12] += ov * n.get('amp', 0.5) * f
    return w


def _piano_chord_onsets(piano_notes) -> list[float]:
    """Times where the piano lands a real voicing (>=3 distinct pcs at once)."""
    groups: list[dict] = []
    for n in sorted(piano_notes, key=lambda x: x['start']):
        if groups and n['start'] - groups[-1]['t'] <= PIANO_ONSET_EPS:
            groups[-1]['pcs'].add(n['midi'] % 12)
        else:
            groups.append({'t': n['start'], 'pcs': {n['midi'] % 12}})
    return [g['t'] for g in groups if len(g['pcs']) >= PIANO_MIN_PCS]


def _viterbi(emis: np.ndarray, kinds: list[str],
             cost_mult: np.ndarray | None = None) -> np.ndarray:
    F, S = emis.shape
    dp = emis[0].copy()
    back = np.zeros((F, S), dtype=np.int32)
    for f in range(1, F):
        cost = CHANGE_COST * CHANGE_MULT.get(kinds[f], 1.0)
        if cost_mult is not None:
            cost *= cost_mult[f]
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


def _label_segment(seg, chroma, energy, bass, note_names, viterbi_margin,
                   raw=None, ev_sources=None, seg_t=None):
    f0, f1 = seg['f0'], seg['f1']
    med = np.median(chroma[:, f0:f1], axis=1)
    m = med.max() or 1.0
    med = med / m
    piano_used = False
    ev_used = 'chroma'
    ev_bass = None
    if ev_sources and seg_t:
        # stem note evidence: duration x velocity pc mass over the segment.
        # When the comping instrument actually voices a chord here, its pcs
        # ARE the chord (tertian stacking downstream) — far cleaner than
        # chroma medians, which mix pads/leads/bleed. Sources are tried in
        # trust order (piano first, synth-stem fallback for buried sections).
        t0, t1 = seg_t
        seg_dur = max(t1 - t0, 1e-3)
        norms = []
        for src_name, notes, min_cover, w in ev_sources:
            pw = _note_pc_weights(notes, t0, t1)
            if pw.max() <= 0:
                continue
            strong = pw >= PIANO_PC_KEEP * pw.max()
            cover = pw.sum() / seg_dur          # ~ weighted sounding seconds
            passes = strong.sum() >= PIANO_MIN_PCS and cover >= min_cover
            norms.append((src_name, pw / pw.max(), w, passes, notes))
        gating = next((x for x in norms if x[3]), None)
        if gating is not None:
            # the gating source anchors the blend at full weight; the others
            # fold in at their configured weight so e.g. the pad can supply
            # tones the piano-stem transcription lost (often the root)
            blend = np.zeros(12)
            for name, pn, w, _passes, _notes in norms:
                blend += (1.0 if name == gating[0] else w) * pn
            med = blend / (blend.max() or 1.0)
            piano_used = True
            ev_used = gating[0]
            lows = [n['midi'] for n in gating[4]
                    if min(n['end'], t1) - max(n['start'], t0) > 0.05]
            ev_bass = min(lows) % 12 if lows else None
    if not piano_used and raw is not None:
        # sustain x magnitude on raw hop frames: pads hold the whole segment,
        # melody notes flicker — suppresses lead bleed the median can't
        Fr, a, b = raw
        if b - a >= 8:
            sus = (Fr[:, a:b] >= 0.25).mean(axis=1)
            medn = np.median(Fr[:, a:b], axis=1)
            feat = sus * np.sqrt(np.maximum(medn, 0.0))
            fm = feat.max()
            if fm > 0:
                med = feat / fm

    state = seg['state']
    if state == N_IDX:
        return None
    root1 = state // N_QUAL
    ivs1 = CORE_QUALITIES[state % N_QUAL][1]
    tmpl_tones = [(root1 + iv) % 12 for iv in ivs1]

    # modal bass over the segment (before pc selection — the root is often
    # carried by the bass alone while pads voice upper structure)
    bpc = np.asarray(bass['pc'][f0:f1])
    bconf = np.asarray(bass['conf'][f0:f1])
    voiced = bpc >= 0
    bass_pc = None
    if voiced.any():
        vals, counts = np.unique(bpc[voiced], return_counts=True)
        mode_pc = int(vals[np.argmax(counts)])
        frac = counts.max() / voiced.sum()
        if frac >= BASS_STABLE_FRAC and float(bconf[voiced].mean()) > BASS_CONF_MIN:
            bass_pc = mode_pc

    pcs = {pc for pc in range(12) if med[pc] >= PC_KEEP}
    pcs |= {pc for pc in tmpl_tones if med[pc] >= PC_KEEP_TMPL}
    if len(pcs) < 3:              # sparse frame (arp / single line) — dig deeper
        pcs |= {pc for pc in tmpl_tones if med[pc] >= 0.12}
    if len(pcs) > PC_CAP:
        pcs = set(sorted(pcs, key=lambda p: -med[p])[:PC_CAP])
    if not pcs:
        return None

    # the chord is named from the pad content; the bass becomes a slash.
    # (bass pc is NOT injected into the pc set — "Abmaj7/Db", not "Dbmaj9",
    # unless the pads themselves also voice the bass note)
    cands = _candidates_ext(sorted(pcs), bass_pc, note_names)
    if not cands:
        # fewer than 3 usable pcs — trust the Viterbi state (it had temporal
        # context) instead of reporting a bogus no-chord
        qname = CORE_QUALITIES[state % N_QUAL][0]
        sfx = {'maj': '', 'min': 'm'}.get(qname, qname)
        name = note_names[root1] + sfx
        if bass_pc is not None and bass_pc != root1:
            name += '/' + note_names[bass_pc]
        return {'chord': name, 'root_pc': root1, 'sfx': sfx,
                'bass_pc': bass_pc, 'alts': [], 'conf': 0.3, 'ev': ev_used}
    for c in cands:
        if c['root'] == root1:
            c['score'] += 1.0
        # root-position reading only when the pads corroborate the bass note
        if bass_pc is not None and c['root'] == bass_pc and med[bass_pc] >= 0.3:
            c['score'] += STAGE2_BASS_ROOT_BONUS
        if c['sfx'] in EXOTIC_SFX:
            c['score'] -= EXOTIC_PENALTY
        # evidence-strength rescoring: mean med over the candidate's template
        # tones + the root tone's own strength − mass it leaves unexplained
        tones = [(c['root'] + iv) % 12
                 for iv in _TMPL_BY_SFX.get(c['sfx'], (0, 4, 7))]
        uncov = [p for p in pcs
                 if p not in tones and p != bass_pc and p != ev_bass]
        c['score'] += EVIDENCE_W * float(np.mean([med[t] for t in tones])) \
            + ROOT_EV_W * float(med[c['root']]) \
            - UNCOV_W * float(sum(med[p] for p in uncov))
    cands.sort(key=lambda c: -c['score'])

    top = cands[0]
    # confidence keyed to the best DIFFERENT-root rival: a wrong root is the
    # costly error; same-root quality variants are one click away in alts
    rival = next((c for c in cands[1:] if c['root'] != top['root']), None)
    gap = top['score'] - rival['score'] if rival else 4.0
    conf = float(1 / (1 + np.exp(-gap / 2.0))) * float(np.clip(viterbi_margin, 0.2, 1.0))
    # alts: prefer ROOT DIVERSITY — same-root quality variants are near-
    # duplicates; a different root is the correction the user actually needs
    alt_names = []
    seen_roots = {top['root']}
    for c in cands[1:]:
        if c['root'] not in seen_roots and c['name'] != top['name']:
            alt_names.append(c['name'])
            seen_roots.add(c['root'])
        if len(alt_names) == 3:
            break
    for c in cands[1:]:
        if len(alt_names) == 4:
            break
        if c['name'] != top['name'] and c['name'] not in alt_names:
            alt_names.append(c['name'])
    return {'chord': top['name'], 'root_pc': top['root'], 'sfx': top['sfx'],
            'bass_pc': bass_pc, 'alts': alt_names, 'conf': round(conf, 3),
            'ev': ev_used}


def recognize(chroma_data: dict, bass: dict, grid: dict, key: dict,
              note_names: list[str], out_json: Path,
              piano_notes: list | None = None,
              synth_notes: list | None = None) -> dict:
    chroma = chroma_data['chroma']
    energy = chroma_data['energy']
    bounds = grid['bounds']
    kinds = grid['kind']
    beat_pos = grid['beat_pos']

    ev_sources = []
    if piano_notes:
        ev_sources.append(('piano', sorted(piano_notes, key=lambda n: n['start']),
                           PIANO_MIN_COVER, PIANO_BLEND_W))
    if synth_notes:
        ev_sources.append(('synth', sorted(synth_notes, key=lambda n: n['start']),
                           SYNTH_MIN_COVER, SYNTH_BLEND_W))
    cost_mult = None
    if piano_notes:
        onsets = _piano_chord_onsets(piano_notes)
        if onsets:
            cost_mult = np.ones(len(bounds) - 1)
            oa = np.asarray(onsets)
            for f in range(1, len(bounds) - 1):
                if np.abs(oa - bounds[f]).min() <= 0.12:
                    cost_mult[f] = PIANO_ONSET_DISCOUNT

    emis = _emissions(chroma, energy, bass)
    path = _viterbi(emis, kinds, cost_mult)
    segs = _merge_segments(path, bounds, beat_pos)

    if SPLIT_AT_ONSETS and cost_mult is not None:
        cut_frames = np.where(cost_mult < 1.0)[0]
        split = []
        for seg in segs:
            cuts = [int(f) for f in cut_frames if seg['f0'] < f < seg['f1']]
            edges = [seg['f0']]
            for c in cuts:
                if (beat_pos[c] - beat_pos[edges[-1]] >= MIN_PIECE_BEATS
                        and beat_pos[min(seg['f1'], len(beat_pos) - 1)]
                        - beat_pos[c] >= MIN_PIECE_BEATS):
                    edges.append(c)
            edges.append(seg['f1'])
            for a, b in zip(edges[:-1], edges[1:]):
                split.append({'state': seg['state'], 'f0': a, 'f1': b})
        segs = split

    # per-frame emission margin of the chosen state vs the best other state
    margins = np.zeros(len(path))
    for f in range(len(path)):
        row = emis[f]
        chosen = row[path[f]]
        other = np.delete(row, path[f]).max()
        margins[f] = 1 / (1 + np.exp(-(chosen - other)))

    raw_frames = chroma_data.get('frames')
    frame_times = chroma_data.get('frame_times')

    def label_at(seg):
        t0 = float(bounds[seg['f0']])
        t1 = float(bounds[min(seg['f1'], len(bounds) - 1)])
        vm = float(margins[seg['f0']:seg['f1']].mean())
        raw = None
        if raw_frames is not None:
            a = int(np.searchsorted(frame_times, t0))
            b = int(np.searchsorted(frame_times, t1))
            raw = (raw_frames, a, b)
        lab = _label_segment(seg, chroma, energy, bass, note_names, vm, raw,
                             ev_sources=ev_sources, seg_t=(t0, t1))
        return t0, t1, lab

    segments = []
    for seg in segs:
        t0, t1, lab = label_at(seg)
        if lab is None:
            segments.append({'start': round(t0, 4), 'end': round(t1, 4),
                             'chord': 'N', 'alts': [], 'conf': 1.0,
                             'root_pc': None, 'sfx': '', 'bass_pc': None})
        else:
            segments.append({'start': round(t0, 4), 'end': round(t1, 4), **lab})

    # (relabel-merge of adjacent segments was tried and REJECTED: the union
    #  label nearly always matches one side, so merging cascades to a single
    #  segment — see RESEARCH.md 2026-07-31)

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
