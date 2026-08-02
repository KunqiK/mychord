r"""Claude symbolic chord referee (user-authorized 2026-08-01, subscription
headless via `claude -p`).

The automation of the human transcriber's functional-harmony reasoning: for
DISPUTED segments only (low confidence, or the BTC posterior disagrees with
the chosen root), pack the symbolic evidence — key, pc strengths, bass,
neighbor chords, candidate list — into one prompt per song and let a Claude
model pick among the EXISTING candidates. Labels only; the timeline is never
touched (arXiv 2509.18700's ablation: their bass-fix / beat-align stages
could regress, the label referee held up).

Experiment mode (A/B on the labeled dataset):
  .venv\Scripts\python.exe referee.py --experiment [--limit N]
      writes cache\<slug>\chords_ref.json for every dataset song with
      disputes (chords.json untouched); then swap+eval via --measure:
  .venv\Scripts\python.exe referee.py --measure     (swap in refs, batch_eval,
                                                     restore originals)
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np

AT = Path(__file__).resolve().parent
sys.path.insert(0, str(AT))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from autoscribe.hud_port import _NOTE_PC            # noqa: E402

NOTE_SHARP = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
CONF_GATE = 0.6
MAX_SEGS = 40
MODEL = 'sonnet'
FT_MIX = 0.5


def parse_chord_name(name: str):
    """'Abmaj7/Db' -> (root_pc, 'maj7') or None."""
    head = name.split('/')[0]
    for ln in (2, 1):
        if head[:ln] in _NOTE_PC:
            return _NOTE_PC[head[:ln]], head[ln:]
    return None


def collect(cache: Path):
    segs = json.loads((cache / 'chords.json').read_text(encoding='utf-8'))['segments']
    key = json.loads((cache / 'key.json').read_text(encoding='utf-8'))
    ch = np.load(cache / 'chroma.npz')
    chroma, bounds = ch['chroma'], ch['bounds']
    btc = None
    if (cache / 'btc.npz').exists():
        d = np.load(cache / 'btc.npz')
        parts = [(1 - FT_MIX, 'probs_off'), (FT_MIX, 'probs_ft')]
        avail = [(w, d[k].astype(np.float32)) for w, k in parts if k in d.files]
        if avail:
            wsum = sum(w for w, _ in avail)
            btc = (d['times'], sum(w * p for w, p in avail) / wsum)

    disputes = []
    for i, s in enumerate(segs):
        if s['chord'] == 'N' or s.get('root_pc') is None:
            continue
        cands = [s['chord']] + [a for a in s.get('alts', [])]
        if len(cands) < 2:
            continue
        btc_root = None
        if btc is not None:
            a = int(np.searchsorted(btc[0], s['start']))
            b = int(np.searchsorted(btc[0], s['end']))
            if b > a:
                p = btc[1][a:b].mean(axis=0)[:168].reshape(12, 14).sum(axis=1)
                btc_root = (int(p.argmax()), float(p.max() / (p.sum() or 1)))
        disputed = s.get('conf', 1.0) < CONF_GATE or \
            (btc_root is not None and btc_root[0] != s['root_pc'])
        if not disputed:
            continue
        f0 = int(np.searchsorted(bounds, s['start']))
        f1 = max(int(np.searchsorted(bounds, s['end'])), f0 + 1)
        med = np.median(chroma[:, f0:f1], axis=1)
        med = med / (med.max() or 1.0)
        pc = {NOTE_SHARP[p]: round(float(med[p]), 2)
              for p in range(12) if med[p] >= 0.2}
        disputes.append({
            'i': i, 'seg': s, 'cands': cands[:5], 'pc': pc,
            'bass': NOTE_SHARP[s['bass_pc']] if s.get('bass_pc') is not None else None,
            'btc': (NOTE_SHARP[btc_root[0]], round(btc_root[1], 2))
            if btc_root else None,
            'prev': [x['chord'] for x in segs[max(0, i - 2):i]],
            'next': [x['chord'] for x in segs[i + 1:i + 3]],
        })
    return segs, key, disputes[:MAX_SEGS]


def build_prompt(key: dict, disputes) -> str:
    lines = [
        'You are an expert in functional harmony judging chord labels for an '
        'electronic / J-pop track.',
        f"Key: {key.get('name', '?')}.",
        'For each numbered segment pick the best chord FROM ITS cands list '
        'ONLY. Use: functional progressions (ii-V-I, IV-V-vi, circle of '
        'fifths...), the bass note, pitch-class strengths (0-1), the '
        'neighboring chords, and the btc hint (a neural root estimate with '
        'its confidence — often right about the root, blind to quality). '
        'If genuinely unsure, keep the first candidate. Never invent a chord '
        'not in the list.',
        '',
    ]
    for d in disputes:
        s = d['seg']
        lines.append(
            f"#{d['i']} [{s['start']:.1f}-{s['end']:.1f}s] "
            f"cands={d['cands']} bass={d['bass']} "
            f"prev={d['prev']} next={d['next']} pc={d['pc']}"
            + (f" btc_root={d['btc'][0]}({d['btc'][1]})" if d['btc'] else ''))
    lines += ['',
              'Respond with ONLY minified JSON, no prose: '
              '{"picks":[{"i":<n>,"chord":"<name from cands>"}...]} '
              'covering EVERY segment above.']
    return '\n'.join(lines)


def ask_claude(prompt: str) -> dict | None:
    r = subprocess.run(f'claude -p --model {MODEL}',
                       input=prompt, capture_output=True, text=True,
                       encoding='utf-8', errors='replace', timeout=300,
                       shell=True)
    out = (r.stdout or '').strip()
    m = re.search(r'\{.*\}', out, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def referee_song(cache: Path) -> tuple[int, int]:
    segs, key, disputes = collect(cache)
    if not disputes:
        return 0, 0
    resp = ask_claude(build_prompt(key, disputes))
    if not resp or 'picks' not in resp:
        print(f'  [{cache.name}] no valid response', flush=True)
        return len(disputes), 0
    by_i = {d['i']: d for d in disputes}
    changed = 0
    for p in resp['picks']:
        d = by_i.get(p.get('i'))
        if d is None:
            continue
        name = p.get('chord')
        if name not in d['cands'] or name == d['seg']['chord']:
            continue
        parsed = parse_chord_name(name)
        if parsed is None:
            continue
        s = d['seg']
        old = s['chord']
        s['chord'], (s['root_pc'], s['sfx']) = name, parsed
        s['alts'] = ([old] + [a for a in s.get('alts', []) if a != name])[:4]
        changed += 1
    (cache / 'chords_ref.json').write_text(json.dumps({'segments': segs}),
                                           encoding='utf-8')
    return len(disputes), changed


def experiment(limit: int | None) -> None:
    sys.path.insert(0, str(AT.parent / 'MIDIandMUSIC'))
    from autoscribe.cache import song_slug
    mani = json.loads((AT.parent / 'MIDIandMUSIC' / 'dataset' /
                       'manifest.json').read_text(encoding='utf-8'))
    n = 0
    for base, info in sorted(mani.items()):
        cache = AT / 'cache' / song_slug(Path(info['audio_path']))
        if not (cache / 'chords.json').exists():
            continue
        if limit and n >= limit:
            break
        nd, ch = referee_song(cache)
        n += 1
        print(f'[{n}] {base}: {nd} disputes, {ch} changed', flush=True)


def measure() -> None:
    from autoscribe.cache import song_slug
    mani = json.loads((AT.parent / 'MIDIandMUSIC' / 'dataset' /
                       'manifest.json').read_text(encoding='utf-8'))
    swapped = []
    for base, info in sorted(mani.items()):
        cache = AT / 'cache' / song_slug(Path(info['audio_path']))
        ref = cache / 'chords_ref.json'
        if ref.exists():
            (cache / 'chords.json').rename(cache / 'chords_orig.json')
            ref.rename(cache / 'chords.json')
            swapped.append(cache)
    print(f'{len(swapped)} songs swapped to refereed chords; evaluating...',
          flush=True)
    r = subprocess.run([sys.executable,
                        str(AT.parent / 'MIDIandMUSIC' / 'batch_eval.py')],
                       capture_output=True, text=True, encoding='utf-8',
                       errors='replace')
    print(r.stdout)
    for cache in swapped:
        (cache / 'chords.json').rename(cache / 'chords_ref.json')
        (cache / 'chords_orig.json').rename(cache / 'chords.json')
    print('originals restored')


if __name__ == '__main__':
    if '--experiment' in sys.argv:
        lim = None
        if '--limit' in sys.argv:
            lim = int(sys.argv[sys.argv.index('--limit') + 1])
        experiment(lim)
    elif '--measure' in sys.argv:
        measure()
    else:
        sys.exit('use --experiment [--limit N] or --measure')
