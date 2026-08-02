r"""One-command post-training harvest ("收丹"):

  1. parse train.log for the best-val_acc epoch
  2. archive this run's latest.pt / train.log under a run tag
  3. best.pt <- ckpt_epoch<best>.pt (old best.pt archived), prune the rest
  4. run sweep_btc_weights.py --apply (vote-weight re-sweep + dataset eval)

  .venv\Scripts\python.exe harvest.py <run_tag>      e.g. harvest.py run4
"""
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
AT = HERE.parent / 'auto-transcribe'
sys.stdout.reconfigure(encoding='utf-8', errors='replace')


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit('usage: harvest.py <run_tag>')
    tag = sys.argv[1]
    log_file = HERE / 'train.log'
    txt = log_file.read_text(encoding='utf-8', errors='replace')
    if 'DONE' not in txt:
        sys.exit('train.log has no DONE marker — training still running?')
    epochs = [(int(m.group(1)), float(m.group(2))) for m in
              re.finditer(r'EPOCH (\d+)/\d+ .*val_acc ([\d.]+)', txt)]
    if not epochs:
        sys.exit('no epochs in train.log')
    best_e, best_acc = max(epochs, key=lambda x: x[1])
    print(f'best epoch {best_e} val_acc {best_acc:.4f} '
          f'({len(epochs)} epochs trained)')

    ck = HERE / f'ckpt_epoch{best_e}.pt'
    if not ck.exists():
        sys.exit(f'{ck.name} missing')
    old = HERE / 'best.pt'
    if old.exists():
        shutil.move(old, HERE / f'best_pre_{tag}.pt')
    shutil.copy(ck, HERE / 'best.pt')
    for p in HERE.glob('ckpt_epoch*.pt'):
        if p != ck:
            p.unlink()
    if (HERE / 'latest.pt').exists():
        shutil.move(HERE / 'latest.pt', HERE / f'{tag}_latest.pt')
    shutil.move(log_file, HERE / f'train_{tag}.log')
    print(f'best.pt = {tag} epoch {best_e}; run archived; ckpts pruned')

    print('re-sweeping BTC vote weights (this evaluates the dataset too)...',
          flush=True)
    r = subprocess.run([sys.executable, str(AT / 'sweep_btc_weights.py'),
                        '--apply'])
    sys.exit(r.returncode)


if __name__ == '__main__':
    main()
