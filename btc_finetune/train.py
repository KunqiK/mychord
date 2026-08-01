r"""STANDALONE CPU fine-tune of BTC (large_voca, 170 chords) on the
MIDIandMUSIC chord dataset. Resume-capable; run indefinitely up to 50 epochs.

Inputs : features\<base>.npz  (from prep_features.py: feature (T,144) log-CQT
         unnormalized, label (T,) large_voca id or -1)
         pretrained ckpt btc\test\btc_model_large_voca.pt (model + mean/std)
Outputs: split.json            fixed train/val song lists (6 val songs)
         ckpt_epoch<N>.pt      one per epoch  (+ latest.pt, atomic-ish)
         stdout                one line per epoch with train/val loss + val acc
                               (the detached launcher appends stdout to train.log)

Resume : if latest.pt exists it is loaded (model+optimizer+epoch) and training
         continues from the next epoch. Baseline (pretrained, "epoch 0") val
         accuracy is evaluated and logged only on a fresh start.

Launch (detached, appending):
  cmd /c ""K:\...\.venv\Scripts\python.exe" -u train.py >> train.log 2>&1"
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import torch

HERE = Path(__file__).resolve().parent
BTC_DIR = Path(r'K:\Claude Projects\!!!ChordHUD\auto-transcribe\btc')
sys.path.insert(0, str(BTC_DIR))

from utils.hparams import HParams          # noqa: E402
from btc_model import BTC_model            # noqa: E402

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

FEAT_DIR = HERE / 'features'
SPLIT_JSON = HERE / 'split.json'
LATEST = HERE / 'latest.pt'
PRETRAINED = BTC_DIR / 'test' / 'btc_model_large_voca.pt'

TIMESTEP = 108
LR = 1e-4
BATCH = 8
EVAL_BATCH = 16
MAX_EPOCH = 50
TRAIN_STRIDE = 54          # 50% overlapping windows for training
VAL_STRIDE = 108           # non-overlapping for validation
SEED = 1337
NUM_THREADS = 8

# fixed 6-song validation set. Chosen standalone: none of these has a
# near-duplicate/variant in the training set (dup groups kept in train:
# 1f1e33[2025]/1fle33, And Revive The Meldoy/_playable edit,
# Alexandrite(1)/alexandrite, Aether Crest Astral/Celestial, ALTER EGO x2).
VAL_SONGS = ['0.0000034', '7 Wonders', 'AMARA ver2', 'Akasha', 'Altale_2',
             '[]dentity']


def log(msg: str) -> None:
    print(f'[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}', flush=True)


def load_split() -> tuple[list[str], list[str]]:
    bases = sorted(p.stem for p in FEAT_DIR.glob('*.npz'))
    if SPLIT_JSON.exists():
        sp = json.loads(SPLIT_JSON.read_text(encoding='utf-8'))
        return sp['train'], sp['val']
    val = [b for b in VAL_SONGS if b in bases]
    train = [b for b in bases if b not in val]
    SPLIT_JSON.write_text(
        json.dumps({'train': train, 'val': val}, ensure_ascii=False, indent=1),
        encoding='utf-8')
    return train, val


def load_windows(bases: list[str], stride: int, mean: float, std: float):
    """Return list of (feature_tensor(T,144) per song, window start idx)."""
    songs, windows = [], []
    for si, b in enumerate(bases):
        d = np.load(FEAT_DIR / f'{b}.npz')
        feat = (d['feature'] - mean) / std
        lab = d['label']
        songs.append((torch.from_numpy(feat.astype(np.float32)),
                      torch.from_numpy(lab)))
        T = len(lab)
        for s in range(0, T - TIMESTEP + 1, stride):
            if (lab[s:s + TIMESTEP] >= 0).all():
                windows.append((si, s))
    return songs, windows


def batch_of(songs, windows, idxs):
    xs, ys = [], []
    for i in idxs:
        si, s = windows[i]
        f, l = songs[si]
        xs.append(f[s:s + TIMESTEP])
        ys.append(l[s:s + TIMESTEP])
    return torch.stack(xs), torch.cat(ys)


@torch.no_grad()
def evaluate(model, songs, windows) -> tuple[float, float]:
    model.eval()
    tot_loss = tot_correct = tot_frames = 0
    for i in range(0, len(windows), EVAL_BATCH):
        idxs = range(i, min(i + EVAL_BATCH, len(windows)))
        x, y = batch_of(songs, windows, idxs)
        pred, loss, _, _ = model(x, y)
        n = y.numel()
        tot_loss += float(loss) * n
        tot_correct += int((pred == y).sum())
        tot_frames += n
    return tot_loss / max(tot_frames, 1), tot_correct / max(tot_frames, 1)


def save_ckpt(path: Path, model, optimizer, epoch, mean, std, extra=None):
    tmp = path.with_suffix('.tmp')
    payload = {'model': model.state_dict(), 'optimizer': optimizer.state_dict(),
               'epoch': epoch, 'mean': mean, 'std': std}
    if extra:
        payload.update(extra)
    torch.save(payload, tmp)
    os.replace(tmp, path)


def main() -> None:
    torch.set_num_threads(NUM_THREADS)
    torch.manual_seed(SEED)

    config = HParams.load(BTC_DIR / 'run_config.yaml')
    config.feature['large_voca'] = True
    config.model['num_chords'] = 170
    model = BTC_model(config=config.model)

    pre = torch.load(PRETRAINED, map_location='cpu', weights_only=False)
    mean, std = float(pre['mean']), float(pre['std'])

    optimizer = torch.optim.Adam(model.parameters(), lr=LR, weight_decay=0.0)

    start_epoch = 1
    if LATEST.exists():
        ck = torch.load(LATEST, map_location='cpu', weights_only=False)
        model.load_state_dict(ck['model'])
        optimizer.load_state_dict(ck['optimizer'])
        mean, std = ck['mean'], ck['std']
        start_epoch = ck['epoch'] + 1
        log(f'RESUME from latest.pt (epoch {ck["epoch"]} done) '
            f'-> continuing at epoch {start_epoch}')
    else:
        model.load_state_dict(pre['model'])
        log('FRESH start from pretrained btc_model_large_voca.pt')

    train_bases, val_bases = load_split()
    tr_songs, tr_windows = load_windows(train_bases, TRAIN_STRIDE, mean, std)
    va_songs, va_windows = load_windows(val_bases, VAL_STRIDE, mean, std)
    log(f'data: {len(train_bases)} train songs -> {len(tr_windows)} windows '
        f'(stride {TRAIN_STRIDE}), {len(val_bases)} val songs -> '
        f'{len(va_windows)} windows | lr {LR} batch {BATCH} '
        f'threads {NUM_THREADS}')

    if start_epoch == 1:
        v_loss, v_acc = evaluate(model, va_songs, va_windows)
        log(f'EPOCH 0/{MAX_EPOCH} (pretrained baseline) '
            f'val_loss {v_loss:.4f} val_acc {v_acc:.4f}')

    rng = np.random.default_rng(SEED + start_epoch)
    for epoch in range(start_epoch, MAX_EPOCH + 1):
        t0 = time.time()
        order = rng.permutation(len(tr_windows))
        model.train()
        run_loss, nb = 0.0, 0
        steps = (len(order) + BATCH - 1) // BATCH
        for bi in range(steps):
            idxs = order[bi * BATCH:(bi + 1) * BATCH]
            x, y = batch_of(tr_songs, tr_windows, idxs)
            optimizer.zero_grad()
            _, loss, _, _ = model(x, y)
            loss.backward()
            optimizer.step()
            run_loss += float(loss)
            nb += 1
            if nb % 25 == 0:
                log(f'  epoch {epoch} step {nb}/{steps} '
                    f'loss {run_loss / nb:.4f}')
        v_loss, v_acc = evaluate(model, va_songs, va_windows)
        save_ckpt(HERE / f'ckpt_epoch{epoch}.pt', model, optimizer, epoch,
                  mean, std, {'val_acc': v_acc, 'val_loss': v_loss})
        save_ckpt(LATEST, model, optimizer, epoch, mean, std,
                  {'val_acc': v_acc, 'val_loss': v_loss})
        log(f'EPOCH {epoch}/{MAX_EPOCH} train_loss {run_loss / max(nb, 1):.4f} '
            f'val_loss {v_loss:.4f} val_acc {v_acc:.4f} '
            f'elapsed {time.time() - t0:.0f}s')

    log('DONE: reached MAX_EPOCH')


if __name__ == '__main__':
    main()
