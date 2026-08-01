"""Score our chords.json directly against the user's correct chord chart
(gt/correct chord.mid — the piano comping part: 202 chord events, each a
voicing; the intended chord = detect_chords on that voicing + its bass note).

This is THE metric the user cares about (和弦要正确). Unlike evaluate_gt's
sounding-pcs sampling over Pad+Piano+String, the chart has explicit,
unambiguous chord boundaries and voicings.

Usage:
  .venv\\Scripts\\python.exe eval_chords_ref.py --cache cache\\<slug> \
      [--ref "gt\\correct chord.mid"] [--offset 2.04] [--details]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from evaluate_gt import load_midi_notes, quality_family   # noqa: E402
from autoscribe.hud_port import detect_chords             # noqa: E402

ONSET_EPS = 0.03      # notes within this of each other = same chord event
BOUNDARY_TOL = 0.15   # seconds, ~ a 16th at 150 BPM


def chart_events(notes):
    """Chart interpretation (verified on the data): onset groups with >=3 pcs
    are the actual chord voicings; 1-2 note groups in between are fills /
    partial re-voicings of the SAME harmony. A chord therefore spans from its
    voicing onset to the NEXT >=3-pc voicing onset — the true harmonic rhythm
    (~1.8s/chord here), not the raw onset rhythm (0.89s)."""
    notes = sorted(notes, key=lambda n: (n['start'], n['midi']))
    events = []
    for n in notes:
        if events and n['start'] - events[-1]['t'] <= ONSET_EPS:
            events[-1]['notes'].append(n)
        else:
            events.append({'t': n['start'], 'notes': [n]})
    chords = []
    for ev in events:
        pcs = sorted({n['midi'] % 12 for n in ev['notes']})
        if len(pcs) < 3:
            continue
        bass = min(ev['notes'], key=lambda n: n['midi'])['midi'] % 12
        cands = detect_chords(pcs, bass)
        chords.append({'start': ev['t'], 'pcs': pcs, 'bass': bass,
                       'label': cands[0] if cands else None})
    for i, c in enumerate(chords):
        c['end'] = chords[i + 1]['start'] if i + 1 < len(chords) \
            else max(n['end'] for n in notes)
    return [c for c in chords if c['label']]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cache', required=True)
    ap.add_argument('--ref', default=str(ROOT / 'gt' / 'correct chord.mid'))
    ap.add_argument('--offset', type=float, default=2.04)
    ap.add_argument('--details', action='store_true')
    args = ap.parse_args()

    tracks, _ = load_midi_notes(Path(args.ref))
    notes = [n for tr in tracks.values() for n in tr]
    labeled = chart_events(notes)
    events = labeled
    print(f'chart: {len(labeled)} chord voicings, '
          f'{events[0]["start"]:.2f}-{events[-1]["end"]:.2f}s midi time, '
          f'mean {np.mean([e["end"] - e["start"] for e in events]):.2f}s/chord')

    segs = json.loads((Path(args.cache) / 'chords.json')
                      .read_text(encoding='utf-8'))['segments']

    from autoscribe.hud_port import CHORD_TEMPLATES, _NOTE_PC
    tmpl_by_sfx = dict(CHORD_TEMPLATES)

    # ── frame-level (0.25s) ──
    tot = root_ok = fam_ok = exact_ok = compat_ok = alts_ok = n_out = 0
    mism = []
    for ev in labeled:
        for t in np.arange(ev['start'], ev['end'], 0.25):
            ta = t + args.offset
            seg = next((s for s in segs if s['start'] <= ta < s['end']), None)
            tot += 1
            if seg is None or seg['chord'] == 'N' or seg.get('root_pc') is None:
                n_out += 1
                mism.append((t, ev, '—'))
                continue
            gt_root = ev['label']['root']
            chart_pcs = set(ev['pcs']) | {ev['bass']}
            our_pcs = {(seg['root_pc'] + iv) % 12
                       for iv in tmpl_by_sfx.get(seg.get('sfx', ''), (0, 4, 7))}
            if seg.get('bass_pc') is not None:
                our_pcs.add(seg['bass_pc'] % 12)
            if our_pcs and len(our_pcs & chart_pcs) / len(our_pcs) >= 0.75:
                compat_ok += 1
            alt_roots = set()
            for a in seg.get('alts', []):
                for ln in (2, 1):
                    if a[:ln] in _NOTE_PC:
                        alt_roots.add(_NOTE_PC[a[:ln]])
                        break
            if seg['root_pc'] == gt_root or gt_root in alt_roots:
                alts_ok += 1
            if seg['root_pc'] == gt_root:
                root_ok += 1
                if quality_family(seg.get('sfx', '')) == quality_family(ev['label']['sfx']) \
                        or 'sus' in (quality_family(seg.get('sfx', '')),
                                     quality_family(ev['label']['sfx'])):
                    fam_ok += 1
                if seg.get('sfx', '') == ev['label']['sfx']:
                    exact_ok += 1
            else:
                mism.append((t, ev, seg['chord']))

    print(f'\n== vs CORRECT CHART (frames n={tot}) ==')
    print(f'root accuracy:        {root_ok / tot:.1%}')
    print(f'root+family:          {fam_ok / tot:.1%}')
    print(f'exact sfx:            {exact_ok / tot:.1%}')
    print(f'chart-compat (pcs):   {compat_ok / tot:.1%}')
    print(f'root in top1+alts:    {alts_ok / tot:.1%}')
    print(f'we output N:          {n_out / tot:.1%}')

    # ── boundary metrics ──
    chart_on = [e['start'] + args.offset for e in events]
    ours_on = [s['start'] for s in segs if s['chord'] != 'N']
    hit_chart = sum(1 for c in chart_on
                    if any(abs(c - o) <= BOUNDARY_TOL for o in ours_on))
    hit_ours = sum(1 for o in ours_on
                   if any(abs(c - o) <= BOUNDARY_TOL for c in chart_on))
    r = hit_chart / len(chart_on)
    p = hit_ours / len(ours_on) if ours_on else 0
    f1 = 2 * p * r / (p + r) if p + r else 0
    print(f'\n== BOUNDARIES (chart {len(chart_on)}, ours {len(ours_on)}, tol ±{BOUNDARY_TOL}s) ==')
    print(f'recall {r:.1%}  precision {p:.1%}  F1 {f1:.2f}')

    if args.details and mism:
        print('\nmismatches (midi-time, chart, ours):')
        last = -10
        for t, ev, o in mism:
            if t - last > 0.9:
                lab = ev['label']
                print(f"  {int(t) // 60}:{t % 60:05.2f}  chart={lab['name']:10s} "
                      f"pcs={ev['pcs']} bass={ev['bass']}  ours={o}")
            last = t


if __name__ == '__main__':
    main()
