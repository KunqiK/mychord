"""Krumhansl-Schmuckler key detection on aggregate chroma."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from .hud_port import key_spelling

KS_MAJOR = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09,
                     2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
KS_MINOR = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53,
                     2.54, 4.75, 3.98, 2.69, 3.34, 3.17])


def detect(chroma: np.ndarray, energy: np.ndarray, out_json: Path,
           key_override: str | None = None) -> dict:
    if key_override:
        best = _parse_key(key_override)
        cands = [dict(best, corr=1.0)]
    else:
        w = np.clip(energy, 0, 2)
        agg = (chroma * w).sum(axis=1)
        agg = agg / (np.linalg.norm(agg) or 1)
        cands = []
        for mode, profile in (('maj', KS_MAJOR), ('min', KS_MINOR)):
            for tonic in range(12):
                rolled = np.roll(profile, tonic)
                corr = float(np.corrcoef(agg, rolled)[0, 1])
                cands.append({'tonic_pc': tonic, 'mode': mode, 'corr': round(corr, 4)})
        cands.sort(key=lambda c: -c['corr'])
        best = cands[0]

    root, active_key, dir_sharp, root_names = key_spelling(
        best['tonic_pc'], best['mode'])
    result = {
        'tonic_pc': best['tonic_pc'],
        'mode': best['mode'],
        'root': root,
        'active_key': active_key,
        'dir_sharp': dir_sharp,
        'name': f"{root} {'Minor' if best['mode'] == 'min' else 'Major'}",
        'top3': [
            {**c, 'name': _pretty(c)} for c in cands[:3]
        ],
    }
    out_json.write_text(json.dumps(result), encoding='utf-8')
    return result


def _pretty(c) -> str:
    root, _, _, _ = key_spelling(c['tonic_pc'], c['mode'])
    return f"{root} {'Minor' if c['mode'] == 'min' else 'Major'}"


def _parse_key(text: str) -> dict:
    from .hud_port import _NOTE_PC
    parts = text.replace('大调', ' Major').replace('小调', ' Minor').split()
    root = parts[0]
    mode = 'min' if (len(parts) > 1 and parts[1].lower().startswith('min')) else 'maj'
    if root not in _NOTE_PC:
        raise SystemExit(f'Unrecognized key root: {text!r} (use e.g. "Eb Major", "C# Minor")')
    return {'tonic_pc': _NOTE_PC[root], 'mode': mode}


def load(key_json: Path) -> dict:
    return json.loads(key_json.read_text(encoding='utf-8'))
