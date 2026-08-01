r"""HookTheory/Sheet Sage dataset -> fine-tune fuel.

Pass 1 (this script, no network): read models\hooktheory\Hooktheory.json.gz,
keep annotations tagged AUDIO_AVAILABLE + HARMONY + REFINED_ALIGNMENT and
without TEMPO_CHANGES, convert each harmony event to our 8-quality vocab with
absolute audio times (piecewise-linear beat->time via the refined alignment),
group by YouTube id, and write:

  models\hooktheory\clips.jsonl   one line per youtube id:
      {yt, dur, t0, t1, ann_sec, events: [{t0, t1, chord: "<root_pc>:<qual>"}]}
      t0/t1 = union clip bounds (padded 3 s); events use ABSOLUTE video time
      (subtract the clip download offset later when building features)
  models\hooktheory\pilot.txt     top-N ids by annotated seconds (download queue)

Pass 2 (--download [N]): yt-dlp each pilot id's [t0, t1] section to
models\hooktheory\audio\<yt>.m4a (user-authorized 2026-08-01, personal
research use; rate-limited, resumable — already-downloaded ids are skipped).

License note: dataset CC BY-NC-SA 3.0, audio rights remain with the owners —
nothing under models\hooktheory\ is committed to git.
"""
from __future__ import annotations

import gzip
import json
import subprocess
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

HERE = Path(__file__).resolve().parent
HT_DIR = HERE.parent / 'auto-transcribe' / 'models' / 'hooktheory'
SRC = HT_DIR / 'Hooktheory.json.gz'
CLIPS = HT_DIR / 'clips.jsonl'
PILOT = HT_DIR / 'pilot.txt'
AUDIO_DIR = HT_DIR / 'audio'
PY = HERE.parent / 'auto-transcribe' / '.venv' / 'Scripts' / 'python.exe'

PILOT_N = 300
PAD = 3.0                 # clip padding around the annotated span (s)

# root_position_intervals -> our 8-quality vocab (prep_features folding rules:
# dim absorbs dim7/m7b5, sus absorbs sus2/sus4/7sus4, other -> maj at train)
_IV = {
    (4, 3): 'maj', (3, 4): 'min', (3, 3): 'dim', (4, 4): 'other',
    (5, 2): 'sus', (2, 5): 'sus',
    (4, 3, 3): '7', (4, 3, 4): 'maj7', (3, 4, 3): 'm7', (3, 4, 4): 'other',
    (3, 3, 3): 'dim', (3, 3, 4): 'dim', (5, 2, 3): 'sus',
}


def quality(intervals) -> str:
    t = tuple(intervals)
    if t in _IV:
        return _IV[t]
    for k in (3, 2):                       # extended chord: match the stack head
        if len(t) > k and t[:k] in _IV:
            return _IV[t[:k]]
    return 'other'


def build() -> None:
    with gzip.open(SRC, 'rt', encoding='utf-8') as f:
        data = json.load(f)
    by_yt: dict[str, dict] = {}
    kept = 0
    for v in data.values():
        tags = set(v.get('tags', []))
        if not {'AUDIO_AVAILABLE', 'HARMONY', 'REFINED_ALIGNMENT'} <= tags:
            continue
        if 'TEMPO_CHANGES' in tags:
            continue
        yt = v['youtube']['id']
        al = v['alignment']['refined']
        beats, times = al['beats'], al['times']
        if len(beats) < 2:
            continue

        def t_of(beat: float) -> float:
            # piecewise-linear, clamped extrapolation at the ends
            import bisect
            i = bisect.bisect_right(beats, beat) - 1
            i = max(0, min(i, len(beats) - 2))
            b0, b1 = beats[i], beats[i + 1]
            if b1 == b0:
                return times[i]
            a = (beat - b0) / (b1 - b0)
            return times[i] + a * (times[i + 1] - times[i])

        events = []
        for h in v['annotations'].get('harmony', []):
            q = quality(h.get('root_position_intervals', ()))
            t0, t1 = t_of(h['onset']), t_of(h['offset'])
            if t1 - t0 < 0.1:
                continue
            events.append({'t0': round(t0, 3), 't1': round(t1, 3),
                           'chord': f"{h['root_pitch_class'] % 12}:{q}"})
        if not events:
            continue
        kept += 1
        e = by_yt.setdefault(yt, {'yt': yt,
                                  'dur': v['youtube'].get('duration'),
                                  'events': []})
        e['events'].extend(events)

    lines = []
    for e in by_yt.values():
        e['events'].sort(key=lambda x: x['t0'])
        lo = max(0.0, e['events'][0]['t0'] - PAD)
        hi = e['events'][-1]['t1'] + PAD
        if e['dur']:
            hi = min(hi, float(e['dur']))
        e['t0'], e['t1'] = round(lo, 2), round(hi, 2)
        e['ann_sec'] = round(sum(x['t1'] - x['t0'] for x in e['events']), 1)
        lines.append(e)
    lines.sort(key=lambda x: -x['ann_sec'])
    with open(CLIPS, 'w', encoding='utf-8') as f:
        for e in lines:
            f.write(json.dumps(e, ensure_ascii=False) + '\n')
    PILOT.write_text('\n'.join(e['yt'] for e in lines[:PILOT_N]),
                     encoding='utf-8')
    total = sum(e['ann_sec'] for e in lines)
    pilot = sum(e['ann_sec'] for e in lines[:PILOT_N])
    print(f'{kept} annotations -> {len(lines)} youtube ids, '
          f'{total / 3600:.1f} h annotated ({CLIPS.name})')
    print(f'pilot {PILOT_N} ids = {pilot / 3600:.1f} h annotated ({PILOT.name})')


def download(limit: int) -> None:
    AUDIO_DIR.mkdir(exist_ok=True)
    clips = {}
    with open(CLIPS, encoding='utf-8') as f:
        for ln in f:
            e = json.loads(ln)
            clips[e['yt']] = e
    ids = PILOT.read_text(encoding='utf-8').split()[:limit]
    ok = skip = fail = 0
    for i, yt in enumerate(ids, 1):
        out = AUDIO_DIR / f'{yt}.m4a'
        if out.exists() and out.stat().st_size > 30_000:
            skip += 1
            continue
        e = clips[yt]
        # full-song download on purpose: --download-sections streams through
        # ffmpeg and gets throttled by YouTube to a crawl; whole bestaudio via
        # the native downloader is ~10x faster and only 3-4 MB per song.
        # The [t0, t1] span is applied later when building features.
        cmd = [str(PY), '-m', 'yt_dlp',
               '-f', 'bestaudio[ext=m4a]/bestaudio',
               '-o', str(AUDIO_DIR / f'{yt}.%(ext)s'),
               '--no-playlist', '--retries', '2',
               '--sleep-interval', '2', '--max-sleep-interval', '6',
               '--quiet', '--no-warnings',
               f'https://www.youtube.com/watch?v={yt}']
        r = subprocess.run(cmd, capture_output=True, text=True,
                           encoding='utf-8', errors='replace')
        got = list(AUDIO_DIR.glob(f'{yt}.*'))
        if r.returncode == 0 and got:
            ok += 1
        else:
            fail += 1
            tail = (r.stderr or '').strip().splitlines()[-1:] or ['?']
            print(f'  [fail] {yt}: {tail[0][:100]}', flush=True)
        if i % 20 == 0:
            print(f'[{i}/{len(ids)}] ok {ok} skip {skip} fail {fail}',
                  flush=True)
        time.sleep(1.0)
    print(f'download done: ok {ok} skip {skip} fail {fail}', flush=True)


def features() -> None:
    """Pass 3: downloaded audio -> features_ht\\<yt>.npz (same schema as
    prep_features: unnormalized log-CQT + large_voca frame labels). Only the
    annotated [t0, t1] span is used; frames not covered by a harmony event
    stay -1 (unlabeled) — a gap means "not annotated", NOT "no chord"."""
    import numpy as np
    import prep_features as pf
    out_dir = HERE / 'features_ht'
    out_dir.mkdir(exist_ok=True)
    clips = {}
    with open(CLIPS, encoding='utf-8') as f:
        for ln in f:
            e = json.loads(ln)
            clips[e['yt']] = e
    done = skipped = failed = 0
    for audio in sorted(AUDIO_DIR.glob('*.*')):
        yt = audio.stem
        e = clips.get(yt)
        out = out_dir / f'{yt}.npz'
        if e is None or out.exists():
            skipped += 1
            continue
        try:
            wav = pf.load_audio(audio)
            a = int(e['t0'] * pf.SR)
            b = min(int(e['t1'] * pf.SR), len(wav))
            if b - a < pf.SR * 5:
                raise ValueError('clip too short (bad download?)')
            feat, times = pf.audio_to_feature(wav[a:b])
            times = times + e['t0']              # back to absolute video time
            ev_t0 = np.array([x['t0'] for x in e['events']])
            ev_t1 = np.array([x['t1'] for x in e['events']])
            ev_id = np.array([pf.chord_to_id(x['chord'])
                              for x in e['events']], dtype=np.int64)
            lab = np.full(len(times), -1, dtype=np.int64)
            idx = np.searchsorted(ev_t0, times, side='right') - 1
            ok = (idx >= 0) & (times < ev_t1[np.clip(idx, 0, None)])
            lab[ok] = ev_id[idx[ok]]
            np.savez_compressed(out, feature=feat, label=lab)
            done += 1
        except Exception as ex:                                # noqa: BLE001
            failed += 1
            print(f'  [fail] {yt}: {ex!r}', flush=True)
    print(f'features: {done} built, {skipped} skipped, {failed} failed '
          f'-> {out_dir.name}', flush=True)


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--download':
        n = int(sys.argv[2]) if len(sys.argv) > 2 else PILOT_N
        download(n)
    elif len(sys.argv) > 1 and sys.argv[1] == '--features':
        features()
    else:
        build()
