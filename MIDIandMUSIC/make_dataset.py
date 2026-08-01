"""Build the chord fine-tuning dataset from the clean MIDI+audio pairs.

Per song -> dataset\\<midibase>.jsonl : one JSON per 0.25 s audio frame
  {"t": seconds_in_audio, "chord": "<root_pc>:<quality>"}  or  {"t":..,"chord":"N"}

Labels come from the GT harmony tracks (gt_tracks auto roles): whenever the
sounding harmony pcs at a frame reach >= 3, detect_chords (ChordHUD port)
top-1 gives root+quality; the label is carried until the next >=3-pc voicing
(or until the harmony span ends -> "N"). Quality is folded into a small
vocab {maj, min, 7, maj7, m7, dim, sus, other}.

Alignment (audio-minus-midi offset), per song:
  1. bass agreement (evaluate_gt.estimate_offset_bass) against the cached
     pyin bass track of the batch-transcribed audio, when a cache exists;
  2. fallback/validation: chroma agreement — cross-correlate the audio's
     CQT chroma with a GT harmony+bass pitch-class indicator (works with no
     cache and doubles as a wrong-audio detector for multi-download songs).

Skips: 'Dont Fight The Music_Edit.Playable' (no audio) and pairs whose audio
duration mismatches the MIDI span (check_pairs logic, ratio outside 0.8-1.35).

Run: "K:\\Claude Projects\\!!!ChordHUD\\auto-transcribe\\.venv\\Scripts\\python.exe" make_dataset.py
"""
from __future__ import annotations

import contextlib
import io
import json
import re
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

import numpy as np

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
HERE = Path(__file__).resolve().parent
AT = Path(r'K:\Claude Projects\!!!ChordHUD\auto-transcribe')
sys.path.insert(0, str(AT))
sys.path.insert(0, str(HERE))

from evaluate_gt import load_midi_notes, estimate_offset_bass   # noqa: E402
from gt_tracks import pick                                      # noqa: E402
from autoscribe.hud_port import detect_chords                   # noqa: E402
from autoscribe.cache import song_slug                          # noqa: E402
from autoscribe.audio_io import load_mono, ffmpeg_exe           # noqa: E402
from check_pairs import ALIAS                                   # noqa: E402

SKIP_STEMS = {'Dont Fight The Music_Edit.Playable'}
FRAME = 0.25
CACHE_ROOT = AT / 'cache'
OUT = HERE / 'dataset'

# detect_chords suffix -> small training vocab
QUAL_MAP = {
    '': 'maj', '6': 'maj', 'add9': 'maj',
    'maj7': 'maj7', 'maj9': 'maj7',
    'm': 'min', 'm6': 'min',
    'm7': 'm7', 'm9': 'm7',
    '7': '7', '9': '7', '7b9': '7', '7#9': '7',
    'sus2': 'sus', 'sus4': 'sus', '7sus4': 'sus',
    'dim': 'dim', 'dim7': 'dim', 'm7b5': 'dim',
    'aug': 'other', 'augMaj7': 'other', 'mMaj7': 'other',
}


def audio_seconds(path: Path) -> float:
    r = subprocess.run(
        ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
         '-of', 'default=noprint_wrappers=1:nokey=1', str(path)],
        capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def load_audio_22k(mp3: Path) -> tuple[np.ndarray, int]:
    """Audio for chroma: cached input.wav if the batch transcribed this file,
    else the mp3 (soundfile, ffmpeg-decode fallback)."""
    wav = CACHE_ROOT / song_slug(mp3) / 'input.wav'
    if wav.exists():
        return load_mono(wav)
    try:
        return load_mono(mp3)
    except Exception:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td) / 'a.wav'
            subprocess.run([ffmpeg_exe(), '-y', '-i', str(mp3), '-ac', '1',
                            '-ar', '22050', '-loglevel', 'error', str(tmp)],
                           check=True)
            return load_mono(tmp)


def pc_indicator(notes, t0: float, t1: float, fps: float) -> np.ndarray:
    """(12, n) binary sounding-pc indicator over midi time [t0, t1)."""
    n = max(1, int(round((t1 - t0) * fps)))
    ind = np.zeros((12, n), dtype=np.float32)
    for note in notes:
        i0 = max(0, int(np.ceil((note['start'] - t0) * fps)))
        i1 = min(n, int(np.ceil((note['end'] - t0) * fps)))
        if i1 > i0:
            ind[note['midi'] % 12, i0:i1] = 1.0
    return ind


def chroma_offset(mp3: Path, gt_notes) -> tuple[float, float, float]:
    """(offset, peak_cosine, peak_minus_median) via chroma cross-correlation.

    Searches audio-minus-midi offsets in [-2, +8] s like estimate_offset_bass.
    """
    import librosa
    y, sr = load_audio_22k(mp3)
    hop = 1024
    fps = sr / hop
    C = librosa.feature.chroma_cqt(y=y, sr=sr, hop_length=hop).astype(np.float32)
    Cn = C / (np.linalg.norm(C, axis=0, keepdims=True) + 1e-9)
    nf = Cn.shape[1]

    lo_k, hi_k = int(np.floor(-2.0 * fps)), int(np.ceil(8.0 * fps))
    # GT indicator over midi times we may query: [-8, audio_end + 2]
    g0 = -(hi_k / fps) - 1.0
    ind = pc_indicator(gt_notes, g0, nf / fps + 2.0, fps)
    ind_n = ind / (np.linalg.norm(ind, axis=0, keepdims=True) + 1e-9)
    has_gt = ind.any(axis=0)
    k0 = int(round(-g0 * fps))          # grid index of midi time 0

    scores = np.full(hi_k - lo_k + 1, np.nan)
    for j, k in enumerate(range(lo_k, hi_k + 1)):
        # audio frame i  <->  gt grid index i - k + k0
        gi = np.arange(nf) - k + k0
        ok = (gi >= 0) & (gi < ind.shape[1])
        gi = gi[ok]
        use = has_gt[gi]
        if use.sum() < 50:
            continue
        cos = np.einsum('ij,ij->j', Cn[:, ok][:, use], ind_n[:, gi][:, use])
        scores[j] = float(cos.mean())
    if np.all(np.isnan(scores)):
        return 0.0, 0.0, 0.0
    b = int(np.nanargmax(scores))
    peak = float(scores[b])
    sharp = peak - float(np.nanmedian(scores))
    # parabolic refinement
    off = (lo_k + b) / fps
    if 0 < b < len(scores) - 1 and not np.isnan(scores[b - 1]) \
            and not np.isnan(scores[b + 1]):
        s0, s1, s2 = scores[b - 1], scores[b], scores[b + 1]
        den = s0 - 2 * s1 + s2
        if abs(den) > 1e-9:
            off += float(0.5 * (s0 - s2) / den) / fps
    return float(off), peak, sharp


def bass_offset(bass_notes, cache: Path) -> tuple[float | None, float | None]:
    """Reuse estimate_offset_bass; capture the printed agreement %."""
    if not bass_notes or not (cache / 'bass.json').exists() \
            or not (cache / 'chroma.npz').exists():
        return None, None
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        off = estimate_offset_bass(bass_notes, cache)
    m = re.search(r'agreement ([\d.]+)%', buf.getvalue())
    return off, (float(m.group(1)) / 100 if m else None)


def label_frames(harm_notes, offset: float, adur: float):
    """Frame labels on the audio timeline. Returns list[(t, label)]."""
    n_frames = int(np.ceil(adur / FRAME))
    ts = np.arange(n_frames) * FRAME
    tm = ts - offset                      # midi time per frame
    harm_end = max(n['end'] for n in harm_notes)

    # per-frame sounding pc bitmask
    mask = np.zeros(n_frames, dtype=np.int32)
    for note in harm_notes:
        sel = (tm >= note['start']) & (tm < note['end'])
        mask[sel] |= 1 << (note['midi'] % 12)

    memo: dict[int, str | None] = {}
    out = []
    current = None
    for i in range(n_frames):
        m = int(mask[i])
        if bin(m).count('1') >= 3:
            if m not in memo:
                pcs = [pc for pc in range(12) if m >> pc & 1]
                cands = detect_chords(pcs)
                memo[m] = (f"{cands[0]['root']}:"
                           f"{QUAL_MAP.get(cands[0]['sfx'], 'other')}"
                           if cands else None)
            if memo[m] is not None:
                current = memo[m]
        if tm[i] > harm_end:
            current = None
        out.append((float(ts[i]), current if current else 'N'))
    return out


def main():
    OUT.mkdir(exist_ok=True)
    manifest, table = {}, []
    skipped = []
    for mid in sorted(HERE.glob('*.mid')):
        if mid.stem in SKIP_STEMS:
            skipped.append((mid.stem, 'excluded (no audio / not a clean pair)'))
            continue
        base = ALIAS.get(mid.stem, mid.stem)
        hits = [p for p in sorted((HERE / 'audio').iterdir())
                if p.name.startswith(f'{base} === ') and p.suffix == '.mp3']
        if not hits:
            skipped.append((mid.stem, 'no audio file'))
            continue

        tracks, _ = load_midi_notes(mid)
        allnotes = [n for tr in tracks.values() for n in tr]
        mdur = max(n['end'] for n in allnotes) - min(n['start'] for n in allnotes)
        cands = []
        for h in hits:
            adur = audio_seconds(h)
            ratio = adur / mdur if mdur else 0
            if 0.8 <= ratio <= 1.35:
                cands.append((h, adur))
        if not cands:
            skipped.append((mid.stem, 'audio duration mismatch (check_pairs)'))
            continue

        sel = pick(tracks)
        harm = [n for nm in sel['harmony'] for n in tracks.get(nm, [])]
        bass = [n for nm in sel['bass'] for n in tracks.get(nm, [])]
        if not harm:
            skipped.append((mid.stem, 'no harmony tracks classified'))
            continue

        print(f'\n=== {mid.stem} ===')
        # score every duration-consistent candidate by chroma agreement;
        # this both aligns and catches wrong-download audio
        scored = []
        for h, adur in cands:
            off_c, peak, sharp = chroma_offset(h, harm + bass)
            scored.append((h, adur, off_c, peak, sharp))
            print(f'  chroma  {peak:.3f} (sharp {sharp:+.3f}) '
                  f'off {off_c:+.2f}s  {h.name[:60]}')
        audio, adur, off_chroma, peak, sharp = max(scored, key=lambda s: s[3])

        cache = CACHE_ROOT / song_slug(audio)
        off_bass, agree = bass_offset(bass, cache)
        if off_bass is not None:
            print(f'  bass    agreement {agree:.1%}  off {off_bass:+.2f}s')

        flags = []
        if off_bass is not None and agree is not None and agree >= 0.45:
            offset, method = off_bass, 'bass'
        elif sharp >= 0.03:
            offset, method = off_chroma, 'chroma'
            if off_bass is not None:
                flags.append(f'bass agreement weak ({agree:.0%})')
        elif off_bass is not None and agree is not None and agree >= 0.35:
            offset, method = off_bass, 'bass'
            flags.append(f'both weak (bass {agree:.0%}, chroma sharp {sharp:.3f})')
        else:
            offset, method = off_chroma, 'chroma'
            flags.append(f'UNRELIABLE (chroma sharp {sharp:.3f}, '
                         f'bass {f"{agree:.0%}" if agree is not None else "n/a"})')
        if off_bass is not None and abs(off_bass - off_chroma) > 0.15 \
                and method == 'bass':
            flags.append(f'methods disagree (bass {off_bass:+.2f} vs '
                         f'chroma {off_chroma:+.2f})')

        frames = label_frames(harm, offset, adur)
        jsonl = OUT / f'{mid.stem}.jsonl'
        with jsonl.open('w', encoding='utf-8') as f:
            for t, lab in frames:
                f.write(json.dumps({'t': round(t, 2), 'chord': lab}) + '\n')

        labs = [lab for _, lab in frames]
        hist = Counter('N' if lab == 'N' else lab.split(':')[1] for lab in labs)
        n_chords = sum(1 for i, lab in enumerate(labs)
                       if lab != 'N' and (i == 0 or labs[i - 1] != lab))
        n_labeled = sum(1 for lab in labs if lab != 'N')
        manifest[mid.stem] = {
            'audio_path': str(audio),
            'jsonl': jsonl.name,
            'midi_path': str(mid),
            'offset': round(float(offset), 3),
            'offset_method': method,
            'bass_agreement': round(agree, 3) if agree is not None else None,
            'bass_offset': round(float(off_bass), 3) if off_bass is not None else None,
            'chroma_offset': round(float(off_chroma), 3),
            'chroma_peak': round(peak, 3),
            'chroma_sharp': round(sharp, 3),
            'flags': flags,
            'harmony_tracks': sel['harmony'],
            'n_frames': len(frames),
            'n_labeled': n_labeled,
            'n_chords': n_chords,
            'label_histogram': dict(hist),
        }
        print(f'  -> {jsonl.name}: {len(frames)} frames, {n_labeled} labeled, '
              f'{n_chords} chord segments, offset {offset:+.2f}s ({method})'
              + (f'  [{"; ".join(flags)}]' if flags else ''))
        table.append((mid.stem, len(frames), n_labeled, n_chords, offset,
                      method, agree, sharp, flags))

    (OUT / 'manifest.json').write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')

    # ── summary ──
    print(f'\n{"=" * 100}')
    print(f'{"song":42s} {"frames":>6s} {"labeled":>7s} {"chords":>6s} '
          f'{"offset":>7s} {"method":>6s} {"bassagr":>7s} {"sharp":>6s}  flags')
    for name, nf, nl, nc, off, meth, agree, sharp, flags in table:
        print(f'{name:42s} {nf:6d} {nl:7d} {nc:6d} {off:+7.2f} {meth:>6s} '
              f'{(f"{agree:.0%}" if agree is not None else "-"):>7s} '
              f'{sharp:6.3f}  {"; ".join(flags)}')
    total = Counter()
    for e in manifest.values():
        total.update(e['label_histogram'])
    n_all = sum(total.values())
    n_lab = n_all - total.get('N', 0)
    print(f'\nsongs: {len(manifest)} written, {len(skipped)} skipped')
    for name, why in skipped:
        print(f'  skipped: {name} — {why}')
    print(f'frames: {n_all} total, {n_lab} labeled ({n_lab / n_all:.1%})')
    print('label distribution (frames):')
    for lab, c in total.most_common():
        print(f'  {lab:6s} {c:7d}  {c / n_all:6.1%}')


if __name__ == '__main__':
    main()
