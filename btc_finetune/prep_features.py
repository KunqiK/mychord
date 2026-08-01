r"""Precompute BTC-format CQT features + frame labels for the chord fine-tune.

Reads  K:\Claude Projects\!!!ChordHUD\MIDIandMUSIC\dataset\manifest.json
       (per-song: audio_path, jsonl) and the per-song jsonl label files
       ({"t": seconds_in_audio, "chord": "<root_pc>:<quality>"|"N"}, 0.25 s grid).
Writes features\<base>.npz  with:
       feature : float32 (T, 144)  log-CQT, UNNORMALIZED (train.py applies the
                 pretrained checkpoint's mean/std)
       label   : int64 (T,)  BTC large_voca id 0..169, or -1 = no label
                 (audio frames past the end of the label grid)

Feature params mirror btc/utils/mir_eval_modules.audio_file_to_features and
run_config.yaml exactly: sr 22050 mono, CQT n_bins=144, bins_per_octave=24,
hop_length=2048, computed in 10-s chunks then concatenated, log(abs+1e-6).
Frame times: within each 10-s chunk, frame j is at chunk_start + j*2048/22050
(the chunked CQT restarts its frame clock each chunk).

Label mapping (our 8-quality vocab -> BTC large_voca, id = root_pc*14 + q):
    ours    -> voca quality (idx)     notes
    maj     -> maj   (1)
    min     -> min   (0)
    7       -> 7     (9)              our '7' folds 9/7b9/7#9
    maj7    -> maj7  (8)              our 'maj7' folds maj9
    m7      -> min7  (6)              our 'm7' folds m9
    dim     -> dim   (2)              our 'dim' folds dim7/m7b5 (hdim7 lost)
    sus     -> sus4  (13)             our 'sus' folds sus2/sus4/7sus4
    other   -> maj   (1)  FALLBACK    our 'other' = aug/augMaj7/mMaj7,
                                      unmappable -> maj per plan
    N       -> 169
(root_pc 0 = C, matching BTC's root_list order; large_voca id 168 'X' unused.)

Run with the auto-transcribe venv python:
  "K:\\Claude Projects\\!!!ChordHUD\\auto-transcribe\\.venv\\Scripts\\python.exe" prep_features.py
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import librosa

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

HERE = Path(__file__).resolve().parent
DATASET = Path(r'K:\Claude Projects\!!!ChordHUD\MIDIandMUSIC\dataset')
FEAT_DIR = HERE / 'features'

SR = 22050
INST_LEN = 10.0          # seconds per CQT chunk
N_BINS = 144
BINS_PER_OCTAVE = 24
HOP = 2048
LABEL_FRAME = 0.25       # jsonl grid

# our quality -> large_voca quality index (within the 14-per-root block)
# voca quality_list = ['min','maj','dim','aug','min6','maj6','min7','minmaj7',
#                      'maj7','7','dim7','hdim7','sus2','sus4']
QUALITY_TO_VOCA = {
    'maj': 1, 'min': 0, '7': 9, 'maj7': 8, 'm7': 6,
    'dim': 2, 'sus': 13, 'other': 1,   # 'other' -> maj fallback
}
N_ID = 169


def chord_to_id(chord: str) -> int:
    if chord == 'N':
        return N_ID
    root_s, qual = chord.split(':')
    root = int(root_s)                  # pitch class 0..11, 0 = C
    return root * 14 + QUALITY_TO_VOCA[qual]


def find_ffmpeg() -> str | None:
    exe = shutil.which('ffmpeg')
    if exe:
        return exe
    winget = (Path.home() / 'AppData/Local/Microsoft/WinGet/Packages')
    if winget.is_dir():
        for p in winget.glob('Gyan.FFmpeg*/**/bin/ffmpeg.exe'):
            return str(p)
    return None


def load_audio(path: Path) -> np.ndarray:
    try:
        wav, _ = librosa.load(str(path), sr=SR, mono=True)
        return wav
    except Exception as e:                                    # noqa: BLE001
        print(f'  librosa.load failed ({e!r}); trying ffmpeg decode')
        ff = find_ffmpeg()
        if not ff:
            raise
        r = subprocess.run(
            [ff, '-v', 'error', '-i', str(path), '-ac', '1', '-ar', str(SR),
             '-f', 'f32le', '-'],
            capture_output=True)
        if r.returncode != 0:
            raise RuntimeError(r.stderr.decode(errors='replace'))
        return np.frombuffer(r.stdout, dtype=np.float32).copy()


def audio_to_feature(wav: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Mirror btc audio_file_to_features; also return per-frame times (s)."""
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
    return feature.T.astype(np.float32), np.concatenate(times)   # (T,144), (T,)


def labels_for(times: np.ndarray, jsonl: Path) -> np.ndarray:
    ids = []
    for ln in jsonl.read_text(encoding='utf-8').splitlines():
        if ln.strip():
            ids.append(chord_to_id(json.loads(ln)['chord']))
    ids = np.asarray(ids, dtype=np.int64)
    idx = np.floor(times / LABEL_FRAME).astype(np.int64)
    lab = np.full(len(times), -1, dtype=np.int64)
    ok = idx < len(ids)
    lab[ok] = ids[idx[ok]]
    return lab


def main() -> None:
    only = sys.argv[1] if len(sys.argv) > 1 else None
    FEAT_DIR.mkdir(exist_ok=True)
    manifest = json.loads((DATASET / 'manifest.json').read_text(encoding='utf-8'))
    done = skipped = 0
    for base, info in sorted(manifest.items()):
        if only and base != only:
            continue
        out = FEAT_DIR / f'{base}.npz'
        if out.exists():
            print(f'[skip] {base} (exists)')
            skipped += 1
            continue
        audio = Path(info['audio_path'])
        jsonl = DATASET / info['jsonl']
        print(f'[feat] {base}')
        wav = load_audio(audio)
        feature, times = audio_to_feature(wav)
        label = labels_for(times, jsonl)
        np.savez_compressed(out, feature=feature, label=label)
        n_ok = int((label >= 0).sum())
        print(f'       T={len(label)} frames, labeled={n_ok} '
              f'({100.0 * n_ok / len(label):.1f}%), N={(label == N_ID).sum()}')
        done += 1
    print(f'\nbuilt {done}, skipped {skipped} (already present)')


if __name__ == '__main__':
    main()
