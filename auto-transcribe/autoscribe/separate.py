"""Stem separation via Demucs (CPU).

demucs 4.0.1 (latest on PyPI) has no `demucs.api`, so we drive the lower-level
apply_model directly and do audio I/O ourselves with soundfile (this also
avoids demucs's internal ffmpeg dependency). Normalization mirrors
demucs.separate: subtract mean / divide std of the mono reference.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

STEMS = ('vocals', 'drums', 'bass', 'other')


def separate(input_wav: Path, out_dir: Path, model_name: str = 'htdemucs') -> None:
    import soundfile as sf
    import torch
    from demucs.apply import apply_model
    from demucs.pretrained import get_model

    try:
        torch.set_num_threads(8)
    except RuntimeError:
        pass

    model = get_model(model_name)
    model.cpu()
    model.eval()

    data, sr = sf.read(str(input_wav), always_2d=True, dtype='float32')
    if sr != model.samplerate:
        import librosa
        data = librosa.resample(data.T, orig_sr=sr, target_sr=model.samplerate).T
    if data.shape[1] == 1:
        data = np.repeat(data, 2, axis=1)
    wav = torch.from_numpy(data.T.copy())          # (channels, samples)

    ref = wav.mean(0)
    mean, std = ref.mean(), ref.std()
    std = std if float(std) > 1e-8 else torch.tensor(1.0)
    wav_n = (wav - mean) / std

    with torch.no_grad():
        sources = apply_model(model, wav_n[None], device='cpu', shifts=1,
                              split=True, overlap=0.25, progress=True)[0]
    sources = sources * std + mean

    out_dir.mkdir(parents=True, exist_ok=True)
    for name, tensor in zip(model.sources, sources):
        audio = tensor.cpu().numpy().T             # (samples, channels)
        peak = np.abs(audio).max()
        if peak > 0.999:
            audio = audio / peak * 0.999
        sf.write(str(out_dir / f'{name}.wav'), audio, model.samplerate,
                 subtype='PCM_16')
    missing = [s for s in STEMS if not (out_dir / f'{s}.wav').exists()]
    if missing:
        raise RuntimeError(f'demucs did not produce stems: {missing}')
