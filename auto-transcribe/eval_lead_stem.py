"""Score a separated instrument stem against a GT MIDI track.

Purpose: quantify whether an instrument-separation model (e.g. the community
lead-synth BS-Roformer, or Mega-53 "synth") actually unblocks lead
transcription — the representation-layer ceiling measured 2026-07-30 was
31.5% frame-level pitch-class accuracy (CQT comb + Viterbi on the demucs
other stem), with basic-pitch-on-other at 23% and skyline at 22%.

Method here: basic-pitch (sensitive thresholds) on the SEPARATED stem →
frame-level pc accuracy on GT-active frames (top-note and any-note), plus
note-event coverage (onset ±0.12s, pc match) comparable to the lines.mid
poly-draft coverage figures (Lead 61% / Arp 81% on the other stem).

Usage:
  .venv\\Scripts\\python.exe eval_lead_stem.py --stem <stem.flac> \
      --midi "C:\\Users\\kunqi\\Downloads\\S.A.T.E.L.L.I.T.E.mid" \
      --track Lead --offset 2.04
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, str(Path(__file__).resolve().parent))
from evaluate_gt import load_midi_notes            # noqa: E402

FPS = 50.0


def predict_notes(stem: Path):
    from basic_pitch.inference import predict
    _, _, events = predict(
        str(stem),
        onset_threshold=0.3, frame_threshold=0.2,
        minimum_note_length=60.0)
    # events: (start, end, pitch, amplitude, pitch_bends)
    return [{'start': e[0], 'end': e[1], 'midi': int(e[2]),
             'amp': float(e[3])} for e in events]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--stem', required=True)
    ap.add_argument('--midi', required=True)
    ap.add_argument('--track', default='Lead')
    ap.add_argument('--offset', type=float, required=True,
                    help='audio-minus-midi offset in seconds (SATELLITE: 2.04)')
    args = ap.parse_args()

    tracks, _ = load_midi_notes(Path(args.midi))
    gt = sorted(tracks.get(args.track, []), key=lambda n: n['start'])
    if not gt:
        sys.exit(f'track "{args.track}" not in GT (have: {sorted(tracks)})')
    print(f'GT {args.track}: {len(gt)} notes, '
          f'{gt[0]["start"]:.1f}-{gt[-1]["end"]:.1f}s (midi time)')

    stem = Path(args.stem)
    print(f'stem: {stem}')
    ours = predict_notes(stem)
    print(f'basic-pitch (sensitive): {len(ours)} notes')

    # shift ours into midi time
    for n in ours:
        n['start'] -= args.offset
        n['end'] -= args.offset

    # ── frame-level pc accuracy on GT-active frames ──
    t_end = gt[-1]['end']
    n_frames = int(t_end * FPS) + 1
    gt_pc = np.full(n_frames, -1, dtype=int)
    for g in gt:
        a, b = int(g['start'] * FPS), int(g['end'] * FPS)
        gt_pc[a:b] = g['midi'] % 12          # later notes overwrite (melody is mono-ish)

    active = np.where(gt_pc >= 0)[0]
    top_ok = any_ok = 0
    for fi in active:
        t = fi / FPS
        sounding = [n for n in ours if n['start'] <= t < n['end']]
        if not sounding:
            continue
        top = max(sounding, key=lambda n: n['midi'])
        pcs = {n['midi'] % 12 for n in sounding}
        top_ok += (top['midi'] % 12 == gt_pc[fi])
        any_ok += (gt_pc[fi] in pcs)
    na = len(active)
    print(f'\n== FRAME LEVEL (GT-active frames n={na}) ==')
    print(f'top-note pc accuracy: {top_ok / na:.1%}   '
          f'(baselines on demucs other: skyline 22%, bp+Viterbi 23%, CQT comb 31.5%)')
    print(f'any-note pc accuracy: {any_ok / na:.1%}')

    # ── note-event coverage (onset ±0.12s, pc match) ──
    hit = 0
    for g in gt:
        if any(abs(o['start'] - g['start']) <= 0.12
               and o['midi'] % 12 == g['midi'] % 12 for o in ours):
            hit += 1
    print(f'\n== NOTE LEVEL ==')
    print(f'GT-note coverage: {hit / len(gt):.1%}  '
          f'(other-stem poly draft baseline: Lead 61%)')
    amps = [o['amp'] for o in ours]
    if amps:
        print(f'ours n={len(ours)}, amp p50={np.median(amps):.2f} '
              f'(velocity=confidence in lines.mid)')


if __name__ == '__main__':
    main()
