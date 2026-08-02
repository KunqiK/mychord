r"""Sweep the BTC vote weights on the full dataset and (optionally) apply
the winner to models\btc_weights.json. Run after EVERY retrain — a stronger
checkpoint earns a bigger vote (measured 2026-08-01: same model went from
+0.1pp at the old weights to +1.0pp at the swept ones).

  .venv\Scripts\python.exe sweep_btc_weights.py [--apply] [rw/qw rw/qw ...]

Each config spawns rerun_dataset.py with AS_BTC_ROOT_W/AS_BTC_QUAL_W set
(fresh process; the chords cache keys include the weights, so each config
recomputes only the chords stage — the BTC posteriors stay cached).
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

AT = Path(__file__).resolve().parent
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

DEFAULT_GRID = [(4.0, 1.5), (6.0, 2.0), (8.0, 2.5), (10.0, 3.0), (12.0, 3.5)]


def run_config(rw: float, qw: float):
    env = dict(os.environ)
    env['AS_BTC_ROOT_W'] = str(rw)
    env['AS_BTC_QUAL_W'] = str(qw)
    r = subprocess.run([sys.executable, str(AT / 'rerun_dataset.py')],
                       capture_output=True, text=True, encoding='utf-8',
                       errors='replace', env=env)
    out = r.stdout or ''
    m_root = re.search(r'root:\s+mean ([\d.]+)%\s+median ([\d.]+)%', out)
    m_comp = re.search(r'compat: mean ([\d.]+)%', out)
    if not m_root:
        tail = out.strip().splitlines()[-3:]
        print(f'  [{rw}/{qw}] EVAL FAILED: {tail}', flush=True)
        return None
    return (float(m_root.group(1)), float(m_root.group(2)),
            float(m_comp.group(1)) if m_comp else 0.0)


def main() -> None:
    args = sys.argv[1:]
    apply = '--apply' in args
    pairs = [a for a in args if '/' in a]
    grid = [tuple(map(float, p.split('/'))) for p in pairs] or DEFAULT_GRID
    results = []
    for rw, qw in grid:
        print(f'[sweep] root_w={rw} qual_w={qw} ...', flush=True)
        res = run_config(rw, qw)
        if res:
            results.append(((rw, qw), res))
            print(f'  -> root mean {res[0]}% median {res[1]}% '
                  f'compat {res[2]}%', flush=True)
    if not results:
        sys.exit('no successful configs')
    print('\n== SWEEP TABLE (root mean / median / compat) ==')
    for (rw, qw), (a, b, c) in results:
        print(f'  {rw:5.1f}/{qw:4.1f}   {a:5.1f}  {b:5.1f}  {c:5.1f}')
    best = max(results, key=lambda x: (x[1][0], x[1][1]))
    (rw, qw), (a, b, c) = best
    print(f'\nBEST: root_w={rw} qual_w={qw} '
          f'(root mean {a}% median {b}% compat {c}%)')
    if apply:
        cfg = AT / 'models' / 'btc_weights.json'
        cfg.write_text(json.dumps({'root_w': rw, 'qual_w': qw}),
                       encoding='utf-8')
        print(f'applied -> {cfg}')
        # leave the dataset caches on the winning config
        run_config(rw, qw)


if __name__ == '__main__':
    main()
