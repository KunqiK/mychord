"""Per-song, per-stage caching.

Song identity = sha1(abspath|size|mtime)[:8]. Each expensive stage writes a
sidecar `<stage>.stage.json` holding a hash of its parameters; if the sidecar
matches and the stage's outputs exist, the stage is skipped on re-run.
Cheap output stages (hud_json/midi/preview/report) always re-run.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path

# stage → stages that must be invalidated when it re-runs
DOWNSTREAM = {
    'separate': ['beats', 'key', 'chroma', 'bass', 'chords', 'melody'],
    'separate_ext': [],   # instrument-level stems (additive; nothing consumes them yet)
    'beats':    ['key', 'chroma', 'bass', 'chords', 'melody'],
    'chroma':   ['key', 'chords'],
    'bass':     ['chords'],
    'key':      ['chords'],
    'btc':      ['chords'],   # BTC posterior feeds chord candidate rescoring
    'chords':   [],
    'melody':   [],
    'piano':    ['chords'],   # piano notes feed chord labeling when the stem exists
}
STAGES = list(DOWNSTREAM.keys())


def song_slug(audio_path: Path) -> str:
    st = audio_path.stat()
    ident = f'{audio_path.resolve()}|{st.st_size}|{int(st.st_mtime)}'
    h = hashlib.sha1(ident.encode('utf-8')).hexdigest()[:8]
    stem = re.sub(r'[^\w\-]+', '_', audio_path.stem)[:40].strip('_') or 'song'
    return f'{stem}-{h}'


def params_hash(params: dict) -> str:
    return hashlib.sha1(json.dumps(params, sort_keys=True).encode('utf-8')).hexdigest()[:12]


class SongCache:
    def __init__(self, cache_root: Path, audio_path: Path):
        self.dir = cache_root / song_slug(audio_path)
        self.dir.mkdir(parents=True, exist_ok=True)

    def path(self, name: str) -> Path:
        return self.dir / name

    def _sidecar(self, stage: str) -> Path:
        return self.dir / f'{stage}.stage.json'

    def is_fresh(self, stage: str, params: dict, outputs: list[Path]) -> bool:
        sc = self._sidecar(stage)
        if not sc.exists():
            return False
        try:
            meta = json.loads(sc.read_text(encoding='utf-8'))
        except (json.JSONDecodeError, OSError):
            return False
        if meta.get('params_hash') != params_hash(params):
            return False
        return all(p.exists() for p in outputs)

    def mark_done(self, stage: str, params: dict) -> None:
        self._sidecar(stage).write_text(json.dumps({
            'params_hash': params_hash(params),
            'done_at': time.strftime('%Y-%m-%d %H:%M:%S'),
            'params': params,
        }, indent=2), encoding='utf-8')

    def invalidate(self, stage: str) -> None:
        for s in [stage] + DOWNSTREAM.get(stage, []):
            sc = self._sidecar(s)
            if sc.exists():
                sc.unlink()

    def run_stage(self, stage: str, params: dict, outputs: list[Path], fn, log=print):
        if self.is_fresh(stage, params, outputs):
            log(f'  [{stage}] cached — skipping')
            return
        t0 = time.time()
        log(f'  [{stage}] running…')
        fn()
        self.mark_done(stage, params)
        log(f'  [{stage}] done in {time.time() - t0:.1f}s')
