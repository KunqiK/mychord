"""Batch-evaluate all MIDI+audio pairs: auto track roles, auto offset,
chord scoring. Aggregates root / compat across the whole dataset."""
import re
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
HERE = Path(__file__).resolve().parent
AT = Path(r'K:\Claude Projects\!!!ChordHUD\auto-transcribe')
sys.path.insert(0, str(AT))
from autoscribe.cache import song_slug  # noqa: E402
from check_pairs import ALIAS           # noqa: E402

PY = str(AT / '.venv' / 'Scripts' / 'python.exe')

results = []
for mid in sorted(HERE.glob('*.mid')):
    base = ALIAS.get(mid.stem, mid.stem)
    hits = list((HERE / 'audio').glob(f'{base} === *.mp3'))
    if not hits:
        continue
    slug = song_slug(hits[0])
    cache = AT / 'cache' / slug
    if not (cache / 'chords.json').exists():
        results.append((mid.stem, None, None, 'no-transcription'))
        continue
    r = subprocess.run(
        [PY, str(AT / 'evaluate_gt.py'), '--midi', str(mid),
         '--cache', str(cache), '--auto'],
        capture_output=True, text=True, encoding='utf-8', errors='replace',
        cwd=str(AT))
    out = r.stdout or ''
    root = re.search(r'root accuracy:\s+([\d.]+)%', out)
    compat = re.search(r'harmonic-compat:\s+([\d.]+)%', out)
    alts = re.search(r'root in top1\+alts:\s+([\d.]+)%', out)
    off = re.search(r'offset: ([+\-\d.]+)s', out)
    if root:
        results.append((mid.stem, float(root.group(1)),
                        float(compat.group(1)),
                        f'alts {alts.group(1)}% off {off.group(1) if off else "?"}'))
    else:
        tail = (r.stderr or out).strip().splitlines()[-1:] or ['?']
        results.append((mid.stem, None, None, f'EVAL-FAIL {tail[0][:60]}'))

ok = [(n, ro, c) for n, ro, c, _ in results if ro is not None]
print(f'\n===== DATASET REPORT: {len(ok)}/{len(results)} evaluated =====')
if ok:
    import numpy as np
    roots = [r for _, r, _ in ok]
    compats = [c for _, _, c in ok]
    print(f'root:   mean {np.mean(roots):.1f}%  median {np.median(roots):.1f}%  '
          f'min {min(roots):.1f}%  max {max(roots):.1f}%')
    print(f'compat: mean {np.mean(compats):.1f}%  median {np.median(compats):.1f}%')
print()
for name, root, compat, note in sorted(results,
                                       key=lambda x: -(x[1] or -1)):
    rs = f'{root:5.1f}%' if root is not None else '  ----'
    cs = f'{compat:5.1f}%' if compat is not None else '  ----'
    print(f'{rs} root  {cs} compat  {name:42s} {note}')
