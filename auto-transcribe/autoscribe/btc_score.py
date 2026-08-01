"""BTC chord-posterior second opinion for the chords stage.

Runs the official large_voca checkpoint (btc\\test\\btc_model_large_voca.pt,
trained on 471 annotated pop songs) and, when present, our fine-tuned
btc_finetune\\best.pt over the whole song, caching per-frame 170-class
posteriors to btc.npz. The chords stage folds segment-mean posteriors into
candidate rescoring — evidence that sees the full CQT context and is not
bound by the pitch-class-evidence ceiling (a masked root's harmonics still
shape the posterior).

Feature extraction mirrors btc/utils/mir_eval_modules.audio_file_to_features
(and btc_finetune/prep_features.py) exactly: sr 22050 mono, CQT n_bins=144,
bins_per_octave=24, hop 2048, computed in 10-s chunks, log(abs+1e-6). Frame
times come from the chunked clock (each chunk restarts at its own offset) —
never derive them as n*hop/sr over the whole song.

Fails soft by design: weights_stamp() returns None when no checkpoint is
available, and any load/inference error surfaces to the caller (cli.py wraps
the stage and proceeds without BTC).
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

AT_DIR = Path(__file__).resolve().parents[1]              # auto-transcribe\
BTC_DIR = AT_DIR / 'btc'
OFFICIAL = BTC_DIR / 'test' / 'btc_model_large_voca.pt'
FINETUNED = AT_DIR.parent / 'btc_finetune' / 'best.pt'

SR = 22050
INST_LEN = 10.0
N_BINS = 144
BINS_PER_OCTAVE = 24
HOP = 2048
TIMESTEP = 108
BATCH = 16

# large_voca layout: id = root_pc*14 + quality_idx, 168 = X, 169 = N
# quality_list = ['min','maj','dim','aug','min6','maj6','min7','minmaj7',
#                 'maj7','7','dim7','hdim7','sus2','sus4']
N_CHORDS = 170


def weights_stamp() -> str | None:
    """Cache identity for the available checkpoints (None = BTC unusable)."""
    if not OFFICIAL.exists():
        return None
    parts = []
    for p in (OFFICIAL, FINETUNED):
        if p.exists():
            st = p.stat()
            parts.append(f'{p.name}:{st.st_size}:{int(st.st_mtime)}')
    return '|'.join(parts)


def _audio_to_feature(wav: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    import librosa
    chunk = int(SR * INST_LEN)
    feats, times = [], []
    start = 0
    while start + chunk < len(wav):
        c = librosa.cqt(wav[start:start + chunk], sr=SR, n_bins=N_BINS,
                        bins_per_octave=BINS_PER_OCTAVE, hop_length=HOP)
        feats.append(c)
        times.append(start / SR + np.arange(c.shape[1]) * (HOP / SR))
        start += chunk
    c = librosa.cqt(wav[start:], sr=SR, n_bins=N_BINS,
                    bins_per_octave=BINS_PER_OCTAVE, hop_length=HOP)
    feats.append(c)
    times.append(start / SR + np.arange(c.shape[1]) * (HOP / SR))
    feature = np.concatenate(feats, axis=1)
    feature = np.log(np.abs(feature) + 1e-6)
    return feature.T.astype(np.float32), np.concatenate(times)


def _load_model(ckpt_path: Path):
    if str(BTC_DIR) not in sys.path:
        sys.path.insert(0, str(BTC_DIR))
    import torch
    from utils.hparams import HParams          # noqa: E402 (btc repo module)
    from btc_model import BTC_model            # noqa: E402
    config = HParams.load(BTC_DIR / 'run_config.yaml')
    config.feature['large_voca'] = True
    config.model['num_chords'] = N_CHORDS
    model = BTC_model(config=config.model)
    ck = torch.load(ckpt_path, map_location='cpu', weights_only=False)
    model.load_state_dict(ck['model'])
    model.eval()
    return model, float(ck['mean']), float(ck['std'])


def compute(input_wav: Path, out_npz: Path) -> None:
    import librosa
    import torch
    torch.set_num_threads(8)
    wav, _ = librosa.load(str(input_wav), sr=SR, mono=True)
    feat, times = _audio_to_feature(wav)
    n_frames = len(times)
    data: dict[str, np.ndarray] = {'times': times.astype(np.float32)}
    for tag, ckpt in (('off', OFFICIAL), ('ft', FINETUNED)):
        if not ckpt.exists():
            continue
        model, mean, std = _load_model(ckpt)
        x = (feat - mean) / std
        pad = (-n_frames) % TIMESTEP
        xp = np.pad(x, ((0, pad), (0, 0)))
        xt = torch.from_numpy(xp).reshape(-1, TIMESTEP, N_BINS)
        probs = []
        with torch.no_grad():
            for i in range(0, len(xt), BATCH):
                # bypass forward(): it demands labels; the two submodules are
                # the whole inference path (see btc_model.BTC_model.forward)
                hidden, _ = model.self_attn_layers(xt[i:i + BATCH])
                logits = model.output_layer.output_projection(hidden)
                probs.append(torch.softmax(logits, dim=-1))
        p = torch.cat(probs).reshape(-1, N_CHORDS)[:n_frames]
        data[f'probs_{tag}'] = p.numpy().astype(np.float16)
    if len(data) == 1:
        raise RuntimeError('no BTC checkpoint available')
    np.savez_compressed(out_npz, **data)


def load(npz_path: Path) -> dict | None:
    if not npz_path.exists():
        return None
    d = np.load(npz_path)
    out = {'times': d['times'].astype(np.float32)}
    for tag in ('off', 'ft'):
        key = f'probs_{tag}'
        out[key] = d[key].astype(np.float32) if key in d.files else None
    if out['probs_off'] is None and out['probs_ft'] is None:
        return None
    return out
