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
    # val_acc swings ~1.24pp between adjacent epochs of the same model, so a
    # single max is a lucky draw, not a score. Report the top-5 mean beside it
    # and treat gaps under ~2.5pp as ties to be settled by compare_ckpts.py
    # (the 34-song end-to-end eval), never by val_acc alone.
    top5 = sorted(a for _, a in epochs)[-5:]
    robust = sum(top5) / len(top5)
    print(f'best epoch {best_e} val_acc {best_acc:.4f} '
          f'(top-5 mean {robust:.4f}, {len(epochs)} epochs trained)')

    ck = HERE / f'ckpt_epoch{best_e}.pt'
    if not ck.exists():
        sys.exit(f'{ck.name} missing')
    old = HERE / 'best.pt'
    if old.exists():
        # deploy only when this run actually beats the incumbent (run5
        # lesson: more data can regress — thin batch-2 clips diluted val
        # 33.5 -> 32.1; blind deployment would have shipped the worse model)
        import torch
        inc = torch.load(old, map_location='cpu',
                         weights_only=False).get('val_acc', -1.0)
        if best_acc <= inc + 0.025:      # inside the val-noise floor: archive
                                         # and let compare_ckpts.py decide
            shutil.copy(ck, HERE / f'{tag}_best_ep{best_e}.pt')
            for p in HERE.glob('ckpt_epoch*.pt'):
                p.unlink()
            if (HERE / 'latest.pt').exists():
                shutil.move(HERE / 'latest.pt', HERE / f'{tag}_latest.pt')
            shutil.move(log_file, HERE / f'train_{tag}.log')
            print(f'NOT deployed: {best_acc:.4f} <= incumbent {inc:.4f}; '
                  f'run archived, best.pt unchanged, sweep skipped')
            return
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
