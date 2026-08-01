"""Instrument-level separation via MSST + community BS/MelBand-Roformer models.

Runs ZFTurbo's Music-Source-Separation-Training inference in the dedicated
`.venv-sep` environment as a subprocess — its deps (numpy>=2, einops,
rotary-embedding-torch) conflict with the main venv pins, so the two never
share a process. Checkpoints download on first use from HuggingFace into
models/sep/ (~45MB-700MB each; not redistributed with the repo — several
community checkpoints carry no explicit license).

CPU cost: one roformer pass is minutes-to-tens-of-minutes per song vs
demucs' ~1 min. Everything is cached per song+model by the separate_ext
stage, so re-runs are free.

MSST writes float32 wavs; we convert to PCM_16 flac (peak-normalizing only
if clipped) and synthesize the complement stem (mix minus target) for
single-target models, LALAL.AI style.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
SEP_PY = ROOT / '.venv-sep' / 'Scripts' / 'python.exe'
MSST_INFER = ROOT / 'msst' / 'inference.py'
MODELS_DIR = ROOT / 'models' / 'sep'

_HF_MEGA = ('https://huggingface.co/noblebarkrr/BS-Roformer-MVSep-Mega-53-stems'
            '/resolve/main/v1/')


def _mega(stem: str) -> dict:
    """Registry entry for one MVSep Mega-53 single-stem checkpoint (~78MB)."""
    return {
        'model_type': 'bs_roformer',
        'ckpt': f'mega53_{stem}.ckpt',
        'config': f'mega53_{stem}.yaml',
        'urls': {
            f'mega53_{stem}.ckpt': f'{_HF_MEGA}bs_mega_53stem_{stem}_mvsep.ckpt',
            f'mega53_{stem}.yaml': f'{_HF_MEGA}bs_mega_53stem_{stem}_mvsep_config.yaml',
        },
        'stems': {stem: stem.replace('-', '_')},
        'complement': True,
        'desc': f'MVSep Mega-53 "{stem}" 单乐器 (draft 级, ZFTurbo 官方权重)',
    }


# key → spec. 'stems': {msst_output_name: export_name}. 'complement': also
# write minus_<export_name> = mix - stem (only meaningful for single-target
# models). Any Mega-53 stem name (53 total: organ, saxophone, violin, brass,
# kick, snare, …) works via _mega() — REGISTRY lists the requested presets,
# unknown keys fall back to _mega(key) so e.g. --stems organ just works.
REGISTRY: dict[str, dict] = {
    'sw6': {
        'model_type': 'bs_roformer',
        'ckpt': 'BS-Rofo-SW-Fixed.ckpt',
        'config': 'BS-Rofo-SW-Fixed.yaml',
        'urls': {
            'BS-Rofo-SW-Fixed.ckpt':
                'https://huggingface.co/enerjazzer/BS-ROFO-SW-Fixed/resolve/main/BS-Rofo-SW-Fixed.ckpt',
            'BS-Rofo-SW-Fixed.yaml':
                'https://huggingface.co/enerjazzer/BS-ROFO-SW-Fixed/resolve/main/BS-Rofo-SW-Fixed.yaml',
        },
        'stems': {s: s for s in
                  ('vocals', 'drums', 'bass', 'guitar', 'piano', 'other')},
        'complement': False,
        'desc': 'BS-Roformer-SW 6 轨 (MVSEP 排行钢琴/吉他双第一, 超 LALAL.AI)',
    },
    'synth': _mega('synth'),
    'strings': _mega('strings'),
    'eguitar': _mega('electric-guitar'),
    'aguitar': _mega('acoustic-guitar'),
    'guitar': {
        'model_type': 'mel_band_roformer',
        'ckpt': 'becruily_guitar.ckpt',
        'config': 'becruily_guitar.yaml',
        'urls': {
            'becruily_guitar.ckpt':
                'https://huggingface.co/becruily/mel-band-roformer-guitar/resolve/main/becruily_guitar.ckpt',
            'becruily_guitar.yaml':
                'https://huggingface.co/becruily/mel-band-roformer-guitar/resolve/main/config_guitar_becruily.yaml',
        },
        'stems': {'Guitar': 'guitar'},
        'complement': True,
        'desc': 'becruily 吉他 MelBand-Roformer (45MB, 最快)',
    },
    'leadsynth': {
        'model_type': 'bs_roformer',
        'ckpt': 'lead_synth.ckpt',
        'config': 'lead_synth.yaml',
        'urls': {
            'lead_synth.ckpt':
                'https://huggingface.co/oulianov/bsroformer-lead-synth/resolve/main/model_bs_roformer_ep_1_sdr_4.9869_fixed.ckpt',
            'lead_synth.yaml':
                'https://huggingface.co/oulianov/bsroformer-lead-synth/resolve/main/config_bs_roformer_synth_lead.yaml',
        },
        'stems': {'synth lead': 'lead_synth'},
        'complement': True,
        'desc': '社区 lead-synth 分离 (SDR 4.99, 草稿级实验模型)',
    },
}

# aliases accepted on the CLI
ALIASES = {'6': 'sw6', 'piano': 'sw6', 'all': 'sw6'}


def resolve(keys: list[str]) -> list[str]:
    """Normalize CLI stem keys; unknown keys become Mega-53 single stems."""
    out = []
    for k in keys:
        k = ALIASES.get(k.strip().lower(), k.strip().lower())
        if k and k not in out:
            out.append(k)
    return out


def spec_for(key: str) -> dict:
    if key in REGISTRY:
        return REGISTRY[key]
    return _mega(key)          # any of the 53 Mega stem names


def expected_outputs(ext_dir: Path, keys: list[str]) -> list[Path]:
    outs = []
    for k in keys:
        spec = spec_for(k)
        for export in spec['stems'].values():
            outs.append(ext_dir / k / f'{export}.flac')
        if spec['complement']:
            for export in spec['stems'].values():
                outs.append(ext_dir / k / f'minus_{export}.flac')
    return outs


def _ensure_env() -> None:
    if not SEP_PY.exists():
        raise RuntimeError(
            f'分离引擎环境缺失: {SEP_PY}\n'
            '运行 setup_sep.cmd 一次即可安装 (需要联网, ~1GB)。')
    if not MSST_INFER.exists():
        raise RuntimeError(
            f'MSST 引擎缺失: {MSST_INFER}\n'
            '运行 setup_sep.cmd 一次即可安装。')


# config keys written by other MSST forks that this MSST's model classes reject
_BAD_CONFIG_KEYS = ('sage_attention',)


def _sanitize_config(path: Path) -> None:
    """Drop fork-specific model kwargs (text-level: PyYAML would mangle the
    !!python/tuple tags these configs rely on)."""
    lines = path.read_text(encoding='utf-8').splitlines(keepends=True)
    kept = [ln for ln in lines
            if not any(ln.lstrip().startswith(f'{k}:') for k in _BAD_CONFIG_KEYS)]
    if len(kept) != len(lines):
        path.write_text(''.join(kept), encoding='utf-8')


def _ensure_model(spec: dict, log=print) -> None:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    for fname, url in spec['urls'].items():
        dst = MODELS_DIR / fname
        if dst.exists() and dst.stat().st_size > 1024:
            if dst.suffix == '.yaml':
                _sanitize_config(dst)
            continue
        log(f'    downloading {fname} …')
        tmp = dst.with_suffix(dst.suffix + '.part')
        req = urllib.request.Request(url, headers={'User-Agent': 'auto-transcribe'})
        with urllib.request.urlopen(req) as r, open(tmp, 'wb') as f:
            shutil.copyfileobj(r, f, length=1 << 20)
        tmp.replace(dst)
        if dst.suffix == '.yaml':
            _sanitize_config(dst)
        log(f'    downloaded {fname} ({dst.stat().st_size / 1e6:.0f} MB)')


def _read_audio(path: Path) -> tuple[np.ndarray, int]:
    import soundfile as sf
    data, sr = sf.read(str(path), always_2d=True, dtype='float32')
    return data, sr


def _write_flac(path: Path, data: np.ndarray, sr: int) -> None:
    import soundfile as sf
    peak = float(np.abs(data).max()) if data.size else 0.0
    if peak > 0.999:
        data = data / peak * 0.999
    sf.write(str(path), data, sr, subtype='PCM_16', format='FLAC')


def run_model(input_wav: Path, ext_dir: Path, key: str, log=print) -> None:
    """Run one separation model; leave <export>.flac files in ext_dir/<key>."""
    _ensure_env()
    spec = spec_for(key)
    _ensure_model(spec, log=log)

    out_dir = ext_dir / key
    raw_dir = ext_dir / f'_{key}_raw'
    in_dir = ext_dir / '_in'
    for d in (raw_dir, out_dir):
        if d.exists():
            shutil.rmtree(d)
    in_dir.mkdir(parents=True, exist_ok=True)
    mix_link = in_dir / 'mix.wav'
    if not mix_link.exists():
        shutil.copyfile(input_wav, mix_link)

    log(f'    [{key}] {spec["desc"]}')
    cmd = [str(SEP_PY), str(MSST_INFER),
           '--model_type', spec['model_type'],
           '--config_path', str(MODELS_DIR / spec['config']),
           '--start_check_point', str(MODELS_DIR / spec['ckpt']),
           '--input_folder', str(in_dir),
           '--store_dir', str(raw_dir),
           '--force_cpu',
           '--disable_detailed_pbar',
           '--filename_template', '{instr}']
    res = subprocess.run(cmd, cwd=str(MSST_INFER.parent),
                         capture_output=True, text=True, encoding='utf-8',
                         errors='replace')
    if res.returncode != 0:
        tail = '\n'.join((res.stderr or res.stdout or '').splitlines()[-25:])
        raise RuntimeError(f'MSST inference failed for {key}:\n{tail}')

    out_dir.mkdir(parents=True, exist_ok=True)
    mix = None
    for msst_name, export in spec['stems'].items():
        src = None
        for ext in ('wav', 'flac'):
            cand = raw_dir / f'{msst_name}.{ext}'
            if cand.exists():
                src = cand
                break
        if src is None:
            produced = [p.name for p in raw_dir.glob('*.*')]
            raise RuntimeError(
                f'{key}: expected stem "{msst_name}" not produced '
                f'(got {produced})')
        data, sr = _read_audio(src)
        _write_flac(out_dir / f'{export}.flac', data, sr)
        if spec['complement']:
            if mix is None:
                mix, mix_sr = _read_audio(input_wav)
            n = min(len(mix), len(data))
            comp = mix[:n] - data[:n]
            _write_flac(out_dir / f'minus_{export}.flac', comp, sr)
    shutil.rmtree(raw_dir, ignore_errors=True)


def separate_ext(input_wav: Path, ext_dir: Path, keys: list[str],
                 log=print) -> None:
    for key in keys:
        done = expected_outputs(ext_dir, [key])
        if done and all(p.exists() for p in done):
            log(f'    [{key}] already separated — skipping')
            continue
        run_model(input_wav, ext_dir, key, log=log)
    shutil.rmtree(ext_dir / '_in', ignore_errors=True)


def export_stems(ext_dir: Path, keys: list[str], dest: Path,
                 log=print) -> list[Path]:
    """Copy produced stems flat into dest, de-colliding names by model key."""
    dest.mkdir(parents=True, exist_ok=True)
    taken: dict[str, str] = {}
    copied = []
    for k in keys:
        for p in sorted((ext_dir / k).glob('*.flac')):
            name = p.stem
            if name in taken and taken[name] != k:
                name = f'{name}_{k}'
            taken[p.stem] = taken.get(p.stem, k)
            tgt = dest / f'{name}.flac'
            shutil.copyfile(p, tgt)
            copied.append(tgt)
    return copied
