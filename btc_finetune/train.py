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
HT_DIR = HERE / 'features_ht'      # HookTheory clips (optional, auto-detected)
USER_REPEAT = int(os.environ.get('BTC_USER_REPEAT', '2'))
                                   # upweight the user's own songs vs HT volume
HT_MIN_ANN_SEC = float(os.environ.get('BTC_HT_MIN_ANN_SEC', '0'))
                                   # quality gate on HookTheory clips: drop any
                                   # with less than this many annotated seconds
                                   # (run5 lesson — clips ranked 300-2000 by
                                   # annotation length diluted val 33.5 -> 32.1;
                                   # more data only helps if it is not thinner)
SPLIT_JSON = HERE / 'split.json'
LATEST = HERE / 'latest.pt'
PRETRAINED = BTC_DIR / 'test' / 'btc_model_large_voca.pt'

TIMESTEP = 108
LR = 1e-4
BATCH = 8
EVAL_BATCH = 16
MAX_EPOCH = 50
PATIENCE = 12              # early stop: epochs without a new val_acc best
TRAIN_STRIDE = 54          # 50% overlapping windows for training
VAL_STRIDE = 108           # non-overlapping for validation
SEED = 1337
NUM_THREADS = 8
# pitch-shift augmentation (BTC-paper standard, -5..+6 semitones): the CQT has
# 24 bins/octave = 2 bins/semitone, so a semitone shift is a pure bin roll —
# no audio re-rendering. Train-time only; validation stays unaugmented so val
# curves compare across runs. Labels move with the roll (root_pc + k mod 12).
AUG_SEMIS = np.arange(-5, 7)
BINS_PER_SEMI = 2

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


def load_windows(entries, stride: int, mean: float, std: float):
    """entries = [(dir, base, repeat)] -> (songs, windows). `repeat`
    duplicates a song's windows to upweight it in the epoch mix (the user's
    own 38 songs must not drown in HookTheory volume)."""
    songs, windows = [], []
    for si, (root, b, rep) in enumerate(entries):
        d = np.load(root / f'{b}.npz')
        feat = (d['feature'] - mean) / std
        lab = d['label']
        songs.append((torch.from_numpy(feat.astype(np.float32)),
                      torch.from_numpy(lab)))
        T = len(lab)
        for s in range(0, T - TIMESTEP + 1, stride):
            if (lab[s:s + TIMESTEP] >= 0).all():
                windows.extend([(si, s)] * rep)
    return songs, windows


def batch_of(songs, windows, idxs, aug_rng=None, pad_val=0.0):
    xs, ys = [], []
    for i in idxs:
        si, s = windows[i]
        f, l = songs[si]
        x = f[s:s + TIMESTEP]
        y = l[s:s + TIMESTEP]
        if aug_rng is not None:
            k = int(AUG_SEMIS[aug_rng.integers(len(AUG_SEMIS))])
            if k:
                b = k * BINS_PER_SEMI
                x2 = torch.full_like(x, pad_val)
                if b > 0:                     # pitch up: content moves to higher bins
                    x2[:, b:] = x[:, :-b]
                else:                         # pitch down
                    x2[:, :b] = x[:, -b:]
                x = x2
                chord = (y >= 0) & (y < 168)  # 168 X / 169 N / -1 unlabeled stay put
                y = torch.where(
                    chord, ((y // 14 + k) % 12) * 14 + y % 14, y)
        xs.append(x)
        ys.append(y)
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
    ht_bases = sorted(p.stem for p in HT_DIR.glob('*.npz')) \
        if HT_DIR.is_dir() else []
    if ht_bases and HT_MIN_ANN_SEC > 0:
        clips = HERE.parent / 'auto-transcribe' / 'models' / 'hooktheory' / 'clips.jsonl'
        ann = {}
        with open(clips, encoding='utf-8') as f:
            for ln in f:
                e = json.loads(ln)
                ann[e['yt']] = e['ann_sec']
        before = len(ht_bases)
        ht_bases = [b for b in ht_bases if ann.get(b, 0) >= HT_MIN_ANN_SEC]
        log(f'HT quality gate >={HT_MIN_ANN_SEC}s annotated: '
            f'{before} -> {len(ht_bases)} clips')
    tr_entries = [(FEAT_DIR, b, USER_REPEAT if ht_bases else 1)
                  for b in train_bases] \
        + [(HT_DIR, b, 1) for b in ht_bases]
    tr_songs, tr_windows = load_windows(tr_entries, TRAIN_STRIDE, mean, std)
    va_songs, va_windows = load_windows(
        [(FEAT_DIR, b, 1) for b in val_bases], VAL_STRIDE, mean, std)
    log(f'data: {len(train_bases)} user + {len(ht_bases)} hooktheory songs '
        f'-> {len(tr_windows)} windows (stride {TRAIN_STRIDE}, '
        f'user x{USER_REPEAT if ht_bases else 1}), {len(val_bases)} val '
        f'songs -> {len(va_windows)} windows | lr {LR} batch {BATCH} '
        f'threads {NUM_THREADS}')

    if start_epoch == 1:
        v_loss, v_acc = evaluate(model, va_songs, va_windows)
        log(f'EPOCH 0/{MAX_EPOCH} (pretrained baseline) '
            f'val_loss {v_loss:.4f} val_acc {v_acc:.4f}')

    # silence floor after per-song normalization — what a padded CQT bin
    # (rolled in from beyond the spectrum) should look like
    pad_val = float((np.log(1e-6) - mean) / std)
    rng = np.random.default_rng(SEED + start_epoch)
    aug_rng = np.random.default_rng(SEED * 2 + start_epoch)
    best_acc, best_epoch = -1.0, 0
    for epoch in range(start_epoch, MAX_EPOCH + 1):
        t0 = time.time()
        order = rng.permutation(len(tr_windows))
        model.train()
        run_loss, nb = 0.0, 0
        steps = (len(order) + BATCH - 1) // BATCH
        for bi in range(steps):
            idxs = order[bi * BATCH:(bi + 1) * BATCH]
            x, y = batch_of(tr_songs, tr_windows, idxs, aug_rng, pad_val)
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
        if v_acc > best_acc:
            best_acc, best_epoch = v_acc, epoch
        elif epoch - best_epoch >= PATIENCE:
            log(f'DONE: early stop (no val improvement since epoch '
                f'{best_epoch}, best {best_acc:.4f})')
            return

    log('DONE: reached MAX_EPOCH')


if __name__ == '__main__':
    main()
