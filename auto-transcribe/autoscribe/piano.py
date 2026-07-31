"""Piano transcription engine (ByteDance model via Melodfy's ONNX port).

Best for piano-led material: outputs full polyphony with velocities and
pedal events. Model file is reused from the installed Melodfy app when
present; otherwise downloaded once from Hugging Face.
"""
from __future__ import annotations

import json
import urllib.request
from pathlib import Path

import numpy as np

MELODFY_MODEL = Path(r'K:\DEV Tools\Melodfy\Melodfy\_internal\models\model.onnx')
LOCAL_MODEL = Path(__file__).resolve().parent.parent / 'models' / 'piano.onnx'
HF_URL = 'https://huggingface.co/krystv/piano_inference_onnx/resolve/main/model.onnx'


def model_path() -> Path:
    if MELODFY_MODEL.exists():
        return MELODFY_MODEL
    if not LOCAL_MODEL.exists():
        LOCAL_MODEL.parent.mkdir(parents=True, exist_ok=True)
        print(f'  downloading piano model (~130MB) from Hugging Face…')
        urllib.request.urlretrieve(HF_URL, LOCAL_MODEL)
    return LOCAL_MODEL


def _noop(*_a, **_k):
    pass


def transcribe(wav_path: Path, out_json: Path, midi_path: Path | None = None) -> dict:
    from onnxruntime import InferenceSession

    from .audio_io import load_mono
    from .melodfy_vendor import config
    from .melodfy_vendor.inference import PianoTranscription

    session = InferenceSession(str(model_path()),
                               providers=['CPUExecutionProvider'])
    # Melodfy's load_audio needs its patched audioread; ours is equivalent
    audio, _ = load_mono(wav_path, sr=config.sample_rate)
    pt = PianoTranscription(session.run)
    tmp_mid = str(midi_path) if midi_path else str(out_json.with_suffix('.mid'))
    result = pt.transcribe(audio, tmp_mid, _noop, _noop, _noop,
                           logUpdate=lambda *_: None)
    events = result['est_note_events']
    notes = [{'start': round(float(e['onset_time']), 4),
              'end': round(float(e['offset_time']), 4),
              'midi': int(e['midi_note']),
              'amp': round(float(e['velocity']) / 127.0, 3)}
             for e in events]
    notes.sort(key=lambda n: n['start'])
    pedal = [{'start': round(float(e['onset_time']), 4),
              'end': round(float(e['offset_time']), 4)}
             for e in result.get('est_pedal_events', [])]
    out = {'engine': 'bytedance-piano', 'notes': notes, 'pedal': pedal,
           'n_pedal': len(pedal)}
    out_json.write_text(json.dumps(out), encoding='utf-8')
    return out


def load(piano_json: Path) -> dict:
    return json.loads(piano_json.read_text(encoding='utf-8'))
