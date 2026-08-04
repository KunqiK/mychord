r"""Self-consistency check on the HookTheory clips: does each clip's AUDIO
actually match its ANNOTATION?

HookTheory annotations are tied to one specific recording. yt-dlp may have
fetched a cover, a remix, a sped-up upload or a live take — in which case the
labels are pure noise and the clip poisons training. run4 (723 clips) beat
both run5 (1085, user x2) and run6 (1085, user x4), so the 362-clip increment
is the prime suspect; the weighting explanation is already falsified.

Method: run the deployed checkpoint over each clip's features and measure
frame-level ROOT agreement with its stored labels. A well-matched clip lands
far above chance; a mismatched one hovers at chance (~1/12 for roots). This
uses the model only as a detector of gross misalignment, so its own accuracy
ceiling doesn't matter — we compare clips against each other, not to a bar.

Writes features_ht_agree.json: {yt: {"root": float, "exact": float, "n": int}}

  .venv\Scripts\python.exe verify_ht.py [--limit N]
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import torch

HERE = Path(__file__).resolve().parent
AT = HERE.parent / 'auto-transcribe'
BTC_DIR = AT / 'btc'
sys.path.insert(0, str(BTC_DIR))

from utils.hparams import HParams          # noqa: E402
from btc_model import BTC_model            # noqa: E402

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

FEAT = HERE / 'features_ht'
# The judge must be a model that trained on NONE of these clips. best.pt
# (run4) memorised most of them — measured 0.86 median root agreement, i.e.
# it scores recall, not alignment. The official pretrained checkpoint never
# saw our corpus, so its agreement reflects only whether the audio really
# matches the annotation.
CKPT = BTC_DIR / 'test' / 'btc_model_large_voca.pt'
OUT = HERE / 'features_ht_agree.json'
TIMESTEP = 108
BATCH = 8
N_CHORDS = 170


def load_model():
    torch.set_num_threads(int(os.environ.get('BTC_NUM_THREADS', '4')))
    config = HParams.load(BTC_DIR / 'run_config.yaml')
    config.feature['large_voca'] = True
    config.model['num_chords'] = N_CHORDS
    config.model['probs_out'] = False
    model = BTC_model(config=config.model)
    ck = torch.load(CKPT, map_location='cpu', weights_only=False)
    model.load_state_dict(ck['model'])
    model.eval()
    return model, float(ck['mean']), float(ck['std'])


@torch.no_grad()
def agreement(model, mean, std, npz: Path):
    d = np.load(npz)
    feat, lab = d['feature'], d['label']
    ok = lab >= 0
    if ok.sum() < TIMESTEP * 2:
        return None
    x = (feat - mean) / std
    pad = (-len(x)) % TIMESTEP
    xp = np.pad(x, ((0, pad), (0, 0)))
    xt = torch.from_numpy(xp.astype(np.float32)).reshape(-1, TIMESTEP, 144)
    preds = []
    for i in range(0, len(xt), BATCH):
        chunk = xt[i:i + BATCH]
        dummy = torch.zeros(len(chunk) * TIMESTEP, dtype=torch.long)
        p, _, _, _ = model(chunk, dummy)
        preds.append(p)
    pred = torch.cat(preds).numpy()[:len(lab)]
    m = ok & (lab < 168) & (pred < 168)       # compare real chords only
    if m.sum() < 100:
        return None
    root_p, root_l = pred[m] // 14, lab[m] // 14
    return {'root': float((root_p == root_l).mean()),
            'exact': float((pred[m] == lab[m]).mean()),
            'n': int(m.sum())}


def main() -> None:
    limit = None
    if '--limit' in sys.argv:
        limit = int(sys.argv[sys.argv.index('--limit') + 1])
    model, mean, std = load_model()
    files = sorted(FEAT.glob('*.npz'))[:limit]
    done = json.loads(OUT.read_text(encoding='utf-8')) if OUT.exists() else {}
    t0 = time.time()
    for i, f in enumerate(files, 1):
        if f.stem in done:
            continue
        try:
            r = agreement(model, mean, std, f)
        except Exception as e:                                # noqa: BLE001
            print(f'  [fail] {f.stem}: {e!r}', flush=True)
            r = None
        done[f.stem] = r
        if i % 25 == 0:
            OUT.write_text(json.dumps(done), encoding='utf-8')
            vals = [v['root'] for v in done.values() if v]
            print(f'[{i}/{len(files)}] 已验 {len(vals)} 首, '
                  f'root 一致率中位 {np.median(vals):.3f}, '
                  f'{(time.time() - t0) / 60:.0f} 分钟', flush=True)
    OUT.write_text(json.dumps(done), encoding='utf-8')
    vals = np.array([v['root'] for v in done.values() if v])
    print(f'\n完成 {len(vals)} 首 (总 {len(done)})')
    for q in (5, 10, 25, 50, 75, 90):
        print(f'  {q:2d}% 分位: root 一致率 {np.percentile(vals, q):.3f}')
    for thr in (0.15, 0.20, 0.25, 0.30):
        print(f'  门槛 >{thr:.2f} 留存 {int((vals > thr).sum())} 首 '
              f'({100 * (vals > thr).mean():.0f}%)')


if __name__ == '__main__':
    main()
