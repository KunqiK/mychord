"""Evaluate pipeline output against a ground-truth multitrack MIDI.

Usage:
  .venv\\Scripts\\python.exe evaluate_gt.py --midi GT.mid --cache cache\\<slug> \
      [--harmony "Pad,Piano,String"] [--bass "Bass"] [--melody "Lead"] \
      [--drums "Drum,Drum #2,KICK"] [--details]

Alignment: MIDI drum-note impulse train is cross-correlated against the
audio drums-stem onset envelope to find the global time offset.
Chord metrics are frame-sampled (0.25 s) so segment boundaries don't bias.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, str(Path(__file__).resolve().parent))
from autoscribe.audio_io import load_mono          # noqa: E402
from autoscribe.hud_port import detect_chords      # noqa: E402

MINORISH = {'m', 'm7', 'm6', 'm9', 'mMaj7', 'dim', 'dim7', 'm7b5'}
NEUTRAL = {'sus2', 'sus4', '7sus4'}


def load_midi_notes(path: Path):
    import mido
    mid = mido.MidiFile(str(path))
    tpb = mid.ticks_per_beat
    # global tempo map from all tracks (type 1: usually track 0/1)
    tempo_events = []
    for tr in mid.tracks:
        t = 0
        for msg in tr:
            t += msg.time
            if msg.type == 'set_tempo':
                tempo_events.append((t, msg.tempo))
    tempo_events.sort()
    if not tempo_events:
        tempo_events = [(0, 500000)]

    def tick_to_sec(tick):
        sec, prev_tick, uspb = 0.0, 0, tempo_events[0][1]
        for et, tempo in tempo_events:
            if et >= tick:
                break
            sec += (et - prev_tick) / tpb * uspb / 1e6
            prev_tick, uspb = et, tempo
        return sec + (tick - prev_tick) / tpb * uspb / 1e6

    tracks = {}
    for tr in mid.tracks:
        name = next((m.name for m in tr if m.type == 'track_name'), '')
        t = 0
        active = {}
        notes = []
        for msg in tr:
            t += msg.time
            if msg.type == 'note_on' and msg.velocity > 0:
                active.setdefault(msg.note, []).append(t)
            elif msg.type in ('note_off', 'note_on'):
                if msg.note in active and active[msg.note]:
                    t0 = active[msg.note].pop(0)
                    notes.append({'start': tick_to_sec(t0),
                                  'end': tick_to_sec(t),
                                  'midi': msg.note})
        if notes:
            tracks.setdefault(name, []).extend(notes)
    bpm0 = 60e6 / tempo_events[0][1]
    return tracks, bpm0


def estimate_offset_bass(gt_bass_notes, cache: Path) -> float | None:
    """Best offset by agreement between GT bass pcs and our pyin bass pcs."""
    bassj = json.loads((cache / 'bass.json').read_text(encoding='utf-8'))
    bounds = np.load(cache / 'chroma.npz')['bounds']
    pc = np.array(bassj['pc'])
    conf = np.array(bassj['conf'])
    centers = (bounds[:-1] + bounds[1:]) / 2

    def gt_pc(t):
        s = [n for n in gt_bass_notes if n['start'] <= t < n['end']]
        return min(s, key=lambda n: n['midi'])['midi'] % 12 if s else None

    best = None
    for off in np.arange(-2.0, 8.01, 0.05):
        tot = ok = 0
        for i, tc in enumerate(centers):
            if conf[i] < 0.4 or pc[i] < 0:
                continue
            g = gt_pc(tc - off)
            if g is None:
                continue
            tot += 1
            ok += (g == pc[i])
        if tot > 50 and (best is None or ok / tot > best[0]):
            best = (ok / tot, float(off))
    if best:
        print(f'bass-agreement offset: {best[1]:+.2f}s (agreement {best[0]:.1%})')
        return best[1]
    return None


def estimate_offset(gt_drum_notes, drums_wav: Path) -> float:
    """Cross-correlate GT drum impulses with the audio drums onset envelope."""
    import librosa
    import scipy.signal
    y, sr = load_mono(drums_wav)
    env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=512,
                                       aggregate=np.median)
    fps = sr / 512
    n = len(env)
    imp = np.zeros(n)
    for note in gt_drum_notes:
        i = int(round(note['start'] * fps))
        if 0 <= i < n:
            imp[i] += 1.0
    imp = scipy.signal.convolve(imp, scipy.signal.windows.hann(5), mode='same')
    env_z = env - env.mean()
    imp_z = imp - imp.mean()
    corr = scipy.signal.correlate(env_z, imp_z, mode='full')
    lags = scipy.signal.correlation_lags(n, n, mode='full')
    # search reasonable offsets: -2s .. +8s (audio usually starts later)
    mask = (lags / fps >= -2.0) & (lags / fps <= 8.0)
    lag = lags[mask][np.argmax(corr[mask])]
    return float(lag / fps)


def sounding_pcs(notes, t, min_len=0.0):
    return sorted({n['midi'] % 12 for n in notes
                   if n['start'] <= t < n['end']
                   and n['end'] - n['start'] >= min_len})


def gt_chord_at(harm_notes, bass_notes, t):
    pcs = sounding_pcs(harm_notes, t)
    if len(pcs) < 2:
        return None
    bass_sounding = [n for n in bass_notes if n['start'] <= t < n['end']]
    bass_pc = min(bass_sounding, key=lambda n: n['midi'])['midi'] % 12 \
        if bass_sounding else None
    cands = detect_chords(pcs, bass_pc)
    return cands[0] if cands else None


def quality_family(sfx):
    if sfx in NEUTRAL:
        return 'sus'
    return 'min' if sfx in MINORISH else 'maj'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--midi', required=True)
    ap.add_argument('--cache', required=True, help='cache/<slug> dir')
    ap.add_argument('--harmony', default='Pad,Piano,String')
    ap.add_argument('--bass', default='Bass')
    ap.add_argument('--melody', default='Lead')
    ap.add_argument('--drums', default='Drum,Drum #2,KICK,Drums')
    ap.add_argument('--offset', type=float, default=None,
                    help='manual audio-minus-midi offset (skip drum alignment)')
    ap.add_argument('--auto', action='store_true',
                    help='auto-classify GT tracks into harmony/melody/bass/'
                         'drums (for full multitrack reference MIDIs)')
    ap.add_argument('--details', action='store_true')
    args = ap.parse_args()

    cache = Path(args.cache)
    tracks, gt_bpm = load_midi_notes(Path(args.midi))
    print(f'GT tracks: {sorted(tracks)}')
    print(f'GT BPM: {gt_bpm:.2f}')

    if args.auto:
        from gt_tracks import pick
        sel = pick(tracks)
        args.harmony = ','.join(sel['harmony'])
        args.melody = ','.join(sel['melody'][:1])
        args.bass = ','.join(sel['bass'])
        args.drums = ','.join(sel['drums'])
        print(f"auto tracks: harmony=[{args.harmony}] melody=[{args.melody}] "
              f"bass=[{args.bass}] drums=[{args.drums}]")

    def collect(namelist):
        out = []
        for nm in namelist.split(','):
            out.extend(tracks.get(nm.strip(), []))
        return sorted(out, key=lambda n: n['start'])

    harm = collect(args.harmony)
    bass = collect(args.bass)
    mel = collect(args.melody)
    drums = collect(args.drums)
    if not harm:
        sys.exit('no harmony notes — check --harmony track names')

    beats = json.loads((cache / 'beats.json').read_text(encoding='utf-8'))
    segments = json.loads((cache / 'chords.json').read_text(encoding='utf-8'))['segments']
    melody = json.loads((cache / 'melody.json').read_text(encoding='utf-8')) \
        if (cache / 'melody.json').exists() else None

    if args.offset is not None:
        offset = args.offset
    else:
        offset = estimate_offset_bass(bass, cache) if bass else None
        if offset is None:
            offset = estimate_offset(drums, cache / 'stems' / 'drums.wav') \
                if drums else 0.0
    print(f'audio-minus-midi offset: {offset:+.3f}s')
    print(f'our BPM: {beats["bpm"]}  (GT {gt_bpm:.2f})  '
          f'grid={"fit" if beats.get("grid_fitted") else "raw"} '
          f'lock={beats.get("grid_lock")}')

    # ── chord frame accuracy (0.25 s sampling on the GT window) ──
    from autoscribe.hud_port import CHORD_TEMPLATES
    tmpl_by_sfx = dict(CHORD_TEMPLATES)

    gt_end = max(n['end'] for n in harm)
    ts = np.arange(0.0, gt_end, 0.25)
    tot = root_ok = fam_ok = exact_ok = compat_ok = 0
    alts_ok = [0]
    mism = []
    our_by_t = segments
    for t in ts:
        gt = gt_chord_at(harm, bass, t)
        if gt is None:
            continue
        ta = t + offset
        seg = next((s for s in our_by_t if s['start'] <= ta < s['end']), None)
        if seg is None or seg['chord'] == 'N' or seg.get('root_pc') is None:
            tot += 1
            mism.append((t, gt['name'], seg['chord'] if seg else '—'))
            continue
        tot += 1
        # harmonic compatibility: are our chord tones a reading of what sounds?
        gt_pcs = set(sounding_pcs(harm, t))
        bass_sounding = [n for n in bass if n['start'] <= t < n['end']]
        if bass_sounding:
            gt_pcs.add(min(bass_sounding, key=lambda n: n['midi'])['midi'] % 12)
        our_pcs = {(seg['root_pc'] + iv) % 12
                   for iv in tmpl_by_sfx.get(seg.get('sfx', ''), (0, 4, 7))}
        if seg.get('bass_pc') is not None:
            our_pcs.add(seg['bass_pc'] % 12)
        if our_pcs and len(our_pcs & gt_pcs) / len(our_pcs) >= 0.75:
            compat_ok += 1
        alt_roots = set()
        for a in seg.get('alts', []):
            for ln in (2, 1):
                head = a[:ln]
                from autoscribe.hud_port import _NOTE_PC
                if head in _NOTE_PC:
                    alt_roots.add(_NOTE_PC[head])
                    break
        if seg['root_pc'] == gt['root'] or gt['root'] in alt_roots:
            alts_ok[0] += 1
        if seg['root_pc'] == gt['root']:
            root_ok += 1
            if quality_family(seg.get('sfx', '')) == quality_family(gt['sfx']) \
                    or 'sus' in (quality_family(seg.get('sfx', '')), quality_family(gt['sfx'])):
                fam_ok += 1
            if seg.get('sfx', '') == gt['sfx']:
                exact_ok += 1
        else:
            mism.append((t, gt['name'], seg['chord']))
    print(f'\n== CHORDS (frames n={tot}) ==')
    print(f'root accuracy:        {root_ok / tot:.1%}')
    print(f'root+family accuracy: {fam_ok / tot:.1%}')
    print(f'exact-name accuracy:  {exact_ok / tot:.1%}')
    print(f'harmonic-compat:      {compat_ok / tot:.1%}   '
          f'(our tones ⊆ sounding GT harmony — a defensible reading)')
    print(f'root in top1+alts:    {alts_ok[0] / tot:.1%}   '
          f'(GT root reachable via ChordHUD alt chips)')
    if args.details and mism:
        print('mismatch regions (midi-time, GT, ours):')
        last = -10
        for t, g, o in mism:
            if t - last > 1.0:
                print(f'  {int(t) // 60}:{t % 60:05.2f}  GT={g:12s} ours={o}')
            last = t

    # ── multi-line coverage: skyline lead + full poly draft vs GT ──
    if melody and mel:
        def cover(ours_notes, tol=0.12):
            hit = 0
            for g in mel:
                if any(abs(o['start'] - offset - g['start']) <= tol
                       and o['midi'] % 12 == g['midi'] % 12 for o in ours_notes):
                    hit += 1
            return hit / len(mel)
        if melody.get('lead_line'):
            print(f"\nlead_line (skyline) covers {cover(melody['lead_line']):.1%} "
                  f"of GT {args.melody} notes (n={len(melody['lead_line'])})")
        if melody.get('poly'):
            print(f"poly draft covers {cover(melody['poly']):.1%} "
                  f"of GT {args.melody} notes (n={len(melody['poly'])}, over-detects by design)")

    # ── melody note-level P/R (onset ±0.1 s) ──
    if melody and melody.get('notes') and mel:
        ours = [{'start': n['start'] - offset, 'midi': n['midi']}
                for n in melody['notes']]
        used = set()
        hit = hit_oct = 0
        for g in mel:
            best = None
            for i, o in enumerate(ours):
                if i in used or abs(o['start'] - g['start']) > 0.1:
                    continue
                if best is None or abs(o['start'] - g['start']) < abs(ours[best]['start'] - g['start']):
                    if o['midi'] % 12 == g['midi'] % 12:
                        best = i
            if best is not None:
                used.add(best)
                hit_oct += 1
                if ours[best]['midi'] == g['midi']:
                    hit += 1
        p = hit_oct / len(ours) if ours else 0
        r = hit_oct / len(mel) if mel else 0
        f1 = 2 * p * r / (p + r) if p + r else 0
        print(f'\n== MELODY (GT n={len(mel)}, ours n={len(ours)}) ==')
        print(f'recall(pitch-class,±100ms): {r:.1%}   precision: {p:.1%}   F1: {f1:.2f}')
        print(f'exact-octave among matches: {hit}/{hit_oct}')


if __name__ == '__main__':
    main()
