r"""Rank candidate checkpoints by the metric that actually matters: the
end-to-end 34-song chord evaluation — not val_acc.

Why: val_acc is measured on 6 songs / 92 windows and swings 1.24pp between
adjacent epochs of the SAME model, so differences under ~2.5pp are noise.
Worse, "best epoch val_acc" is a maximum over ~50 noisy draws, which rewards
longer runs by luck alone. The dataset eval samples ~34 songs of real
pipeline output, so it can separate what val_acc cannot.

Each candidate is swapped into best.pt (the btc stage keys its cache on the
file's mtime+size, so posteriors recompute automatically), the dataset is
re-run, and the original checkpoint is restored at the end — always, even
on Ctrl-C.

  .venv\Scripts\python.exe compare_ckpts.py ckptA.pt ckptB.pt ...
  (no args = every run*_best_*.pt plus the current best.pt)
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
AT = HERE.parent / 'auto-transcribe'
BEST = HERE / 'best.pt'
BACKUP = HERE / '_best_backup_compare.pt'
sys.stdout.reconfigure(encoding='utf-8', errors='replace')


def run_dataset() -> tuple | None:
    r = subprocess.run([sys.executable, str(AT / 'rerun_dataset.py')],
                       capture_output=True, text=True, encoding='utf-8',
                       errors='replace')
    out = r.stdout or ''
    m = re.search(r'root:\s+mean ([\d.]+)%\s+median ([\d.]+)%', out)
    c = re.search(r'compat: mean ([\d.]+)%', out)
    if not m:
        print('   eval failed:', (out.strip().splitlines() or ['?'])[-1])
        return None
    return float(m.group(1)), float(m.group(2)), float(c.group(1)) if c else 0.0


def main() -> None:
    args = sys.argv[1:]
    cands = [Path(a) if Path(a).is_absolute() else HERE / a for a in args]
    if not cands:
        cands = [BEST] + sorted(HERE.glob('run*_best_*.pt'))
    cands = [c for c in cands if c.exists()]
    if not cands:
        sys.exit('no checkpoints found')

    shutil.copy(BEST, BACKUP)
    results = []
    try:
        for c in cands:
            print(f'[{c.name}] 换入并重跑数据集…', flush=True)
            if c.resolve() != BEST.resolve():
                shutil.copy(c, BEST)
            res = run_dataset()
            if res:
                results.append((c.name, *res))
                print(f'   root 均值 {res[0]}%  中位 {res[1]}%  兼容 {res[2]}%',
                      flush=True)
    finally:
        shutil.copy(BACKUP, BEST)
        BACKUP.unlink(missing_ok=True)
        print('\n原 best.pt 已还原', flush=True)

    if results:
        print('\n== 端到端排名 (34 首, 票权固定) ==')
        print(f"{'checkpoint':22} {'root均值':>8} {'root中位':>8} {'兼容':>7}")
        for n, a, b, cc in sorted(results, key=lambda r: -r[1]):
            print(f'{n:22} {a:7.1f}% {b:7.1f}% {cc:6.1f}%')


if __name__ == '__main__':
    main()
