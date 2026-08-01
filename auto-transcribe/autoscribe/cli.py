"""CLI orchestration: one command, cached stages, all outputs."""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog='transcribe',
        description='Local chord + melody transcription → ChordHUD project')
    p.add_argument('audio', nargs='?', help='input audio file (wav/flac/mp3/m4a/…)')
    p.add_argument('--out', default=None, help='output dir (default output\\<slug>)')
    p.add_argument('--title', default=None)
    p.add_argument('--bpm', type=float, default=None)
    p.add_argument('--key', default=None, help='e.g. "Eb Major", "C# Minor"')
    p.add_argument('--beats-per-bar', type=int, default=4)
    p.add_argument('--downbeat-shift', type=int, default=None, choices=range(8))
    p.add_argument('--grid-zero', action='store_true',
                   help='shift times so bar 1 beat 1 = 0.0')
    p.add_argument('--no-melody', action='store_true')
    p.add_argument('--melody-source', default='auto',
                   choices=['auto', 'vocals', 'other', 'none'])
    p.add_argument('--lead-floor', default='C4',
                   help='skyline floor pitch for instrumental lead (default C4)')
    p.add_argument('--vocal-gate', type=float, default=0.25,
                   help='drop vocal-melody notes outside sections where the '
                        'vocals stem carries this share of mix energy '
                        '(0 = off; default 0.25)')
    p.add_argument('--chroma-vocals', type=float, default=None,
                   help='mix vocals into harmony chroma at this weight (default: auto)')
    p.add_argument('--model', default='htdemucs',
                   choices=['htdemucs', 'htdemucs_ft'])
    p.add_argument('--stems', default=None,
                   help='乐器级分离 (逗号分隔): 6=六轨全套(人声/鼓/贝斯/吉他/钢琴/其他, '
                        'MVSEP 排行第一的 BS-Roformer-SW), synth, strings, eguitar, '
                        'aguitar, guitar, leadsynth, 或任意 MVSep Mega-53 乐器名 '
                        '(organ/saxophone/violin/brass/…)。CPU 上每个模型需要几分钟'
                        '到几十分钟, 结果缓存')
    p.add_argument('--stems-only', action='store_true',
                   help='只做乐器分离并导出 stems 音频, 跳过扒谱全流程')
    p.add_argument('--piano', action='store_true',
                   help='also run the ByteDance piano engine (velocity+pedal) '
                        '→ piano.mid; best on piano-led material')
    p.add_argument('--piano-stem', default='input',
                   choices=['input', 'other', 'piano'],
                   help='piano engine input: the full mix (default, for piano '
                        'recordings), the demucs other stem, or the dedicated '
                        'piano stem from "--stems 6" (best on band mixes)')
    p.add_argument('--lines-scale-snap', action='store_true',
                   help='drop out-of-key notes from lines.mid poly/lead tracks '
                        '(NeuralNote-style scale filter; off by default — '
                        'chromatic passages are real music)')
    p.add_argument('--click', action='store_true',
                   help='add beat clicks to preview.wav (downbeat = high pitch)')
    p.add_argument('--preview-melody', action='store_true',
                   help='add a sine render of the melody to preview.wav')
    p.add_argument('--force', default=None,
                   help='re-run a stage (separate/separate_ext/beats/key/chroma/'
                        'bass/chords/melody) or "all"')
    p.add_argument('--verify-install', action='store_true',
                   help='check environment and exit')
    return p


def verify_install() -> int:
    print(f'python: {sys.executable}')
    if 'mingw' in sys.executable.lower() or 'msys' in sys.executable.lower():
        print('FATAL: running under MSYS2/MinGW python — use the .venv CPython '
              '(transcribe.cmd does this automatically).')
        return 1
    ok = True
    for mod in ('numpy', 'scipy', 'librosa', 'soundfile', 'torch', 'demucs',
                'mido', 'onnxruntime'):
        try:
            __import__(mod)
            print(f'  {mod}: OK')
        except Exception as e:  # noqa: BLE001
            print(f'  {mod}: FAIL — {e}')
            ok = False
    try:
        import basic_pitch
        from basic_pitch import ICASSP_2022_MODEL_PATH
        p = str(ICASSP_2022_MODEL_PATH)
        print(f'  basic-pitch model: {p}')
        if not p.lower().endswith('.onnx') and 'onnx' not in p.lower():
            print('  WARN: basic-pitch did not select the ONNX backend')
    except Exception as e:  # noqa: BLE001
        print(f'  basic-pitch: unavailable ({e}) — pyin melody fallback will be used')
    from .audio_io import ffmpeg_exe
    print(f"  ffmpeg: {ffmpeg_exe() or 'NOT FOUND (wav/flac input only)'}")
    if ok:
        import numpy as np
        import soundfile as sf
        import tempfile
        # basic-pitch smoke test on a 2s A4 sine
        try:
            from basic_pitch.inference import predict
            with tempfile.TemporaryDirectory() as td:
                t = np.arange(2 * 22050) / 22050
                y = 0.5 * np.sin(2 * np.pi * 440 * t)
                wav = Path(td) / 'sine.wav'
                sf.write(str(wav), y, 22050, subtype='PCM_16')
                _, _, events = predict(str(wav))
                pitches = {e[2] for e in events}
                print(f'  basic-pitch sine test: notes={sorted(pitches)} '
                      f"{'OK (A4=69 found)' if 69 in pitches else 'UNEXPECTED'}")
        except Exception as e:  # noqa: BLE001
            print(f'  basic-pitch sine test: FAIL — {e}')
    print('verify done.')
    return 0 if ok else 1


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    if args.verify_install:
        return verify_install()
    if not args.audio:
        build_parser().print_help()
        return 2

    import numpy as np  # noqa: F401  (fail fast if env is broken)
    from . import (audio_io, bassline, beats as beats_mod, cache,
                   chords as chords_mod, chroma as chroma_mod, hud_json,
                   keydetect, melody as melody_mod, midi_out, report,
                   separate as separate_mod, synthesize)

    audio_path = Path(args.audio).resolve()
    if not audio_path.exists():
        print(f'input not found: {audio_path}')
        return 2
    title = args.title or audio_path.stem

    sc = cache.SongCache(ROOT / 'cache', audio_path)
    out_dir = Path(args.out) if args.out else ROOT / 'output' / sc.dir.name
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f'cache: {sc.dir}')
    print(f'output: {out_dir}')

    if args.force:
        if args.force == 'all':
            for s in cache.STAGES:
                sc.invalidate(s)
        elif args.force in cache.STAGES:
            sc.invalidate(args.force)
        else:
            print(f'unknown stage for --force: {args.force}')
            return 2

    t_start = time.time()
    input_wav = sc.path('input.wav')
    if not input_wav.exists():
        print('  [decode] → input.wav')
        audio_io.decode_to_wav(audio_path, input_wav)
    duration = audio_io.duration_seconds(input_wav)

    if args.stems:
        from . import separate_ext as sepext_mod
        stem_keys = sepext_mod.resolve(args.stems.split(','))
        ext_dir = sc.path('stems_ext')
        sc.run_stage('separate_ext', {'models': stem_keys, 'v': 1},
                     sepext_mod.expected_outputs(ext_dir, stem_keys),
                     lambda: sepext_mod.separate_ext(input_wav, ext_dir,
                                                     stem_keys))
        copied = sepext_mod.export_stems(ext_dir, stem_keys, out_dir / 'stems')
        print(f'    {len(copied)} stem files → {out_dir / "stems"}')
        if args.stems_only:
            # 新模式: every stem gets its own MIDI so the user can pick the
            # chord/melody tracks in the DAW (pass --bpm for grid alignment)
            from . import stems_midi
            print('  [stems-midi] transcribing each stem…')
            stems_midi.transcribe_stems(out_dir / 'stems', bpm=args.bpm,
                                        cache_dir=sc.dir)
            print(f'all done in {time.time() - t_start:.0f}s → {out_dir}')
            return 0
    elif args.stems_only:
        print('--stems-only 需要配合 --stems (例如 --stems 6)')
        return 2

    stems_dir = sc.path('stems')
    sc.run_stage('separate', {'model': args.model},
                 [stems_dir / f'{s}.wav' for s in separate_mod.STEMS],
                 lambda: separate_mod.separate(input_wav, stems_dir, args.model))

    beats_json = sc.path('beats.json')
    beat_params = {'bpm': args.bpm, 'bpb': args.beats_per_bar,
                   'shift': args.downbeat_shift}
    sc.run_stage('beats', beat_params, [beats_json],
                 lambda: beats_mod.estimate(
                     stems_dir / 'drums.wav', stems_dir / 'other.wav',
                     stems_dir / 'bass.wav', beats_json, duration,
                     bpm_override=args.bpm, beats_per_bar=args.beats_per_bar,
                     downbeat_shift=args.downbeat_shift))
    beats = beats_mod.load(beats_json)
    print(f"    BPM {beats['bpm']}  phase {beats['downbeat_phase']}"
          f"  grid={'fit' if beats['grid_fitted'] else 'raw'}")

    grid = beats_mod.frame_grid(beats)

    # vocals hurt harmony chroma on tested material (pitched chops); opt-in only
    voc_w = args.chroma_vocals if args.chroma_vocals is not None else 0.0
    # NOTE (measured vs the correct-chord chart): stem-based chroma does NOT
    # beat the demucs other stem — the roformer piano/synth stems go quiet in
    # busy sections and max-normalization inflates residual noise into fake
    # pitch classes. Chroma stays other-based; the piano stem enters at the
    # LABELING level instead, as note-level evidence (see chords stage).
    ext_dir = sc.path('stems_ext')
    harm_wavs: list = []
    chroma_npz = sc.path('chroma.npz')
    sc.run_stage('chroma', {'voc_w': voc_w, 'beats': beat_params,
                            'harm': [f'{p.parent.name}/{p.name}' for p in harm_wavs],
                            'v': 2},
                 [chroma_npz],
                 lambda: chroma_mod.compute(
                     stems_dir / 'other.wav', stems_dir / 'vocals.wav',
                     grid['bounds'], chroma_npz, vocals_weight=voc_w,
                     bass_wav=stems_dir / 'bass.wav',
                     harm_wavs=harm_wavs or None))
    chroma_data = chroma_mod.load(chroma_npz)

    bass_json = sc.path('bass.json')
    sc.run_stage('bass', {'beats': beat_params}, [bass_json],
                 lambda: bassline.analyze(stems_dir / 'bass.wav',
                                          grid['bounds'], bass_json))
    bass = bassline.load(bass_json)

    key_json = sc.path('key.json')
    sc.run_stage('key', {'override': args.key, 'voc_w': voc_w}, [key_json],
                 lambda: keydetect.detect(chroma_data['chroma'],
                                          chroma_data['energy'], key_json,
                                          key_override=args.key))
    key = keydetect.load(key_json)
    print(f"    key: {key['name']}")

    from .hud_port import key_spelling
    _, _, _, note_names = key_spelling(key['tonic_pc'], key['mode'])

    # melody runs BEFORE chords: its synth-stem poly draft doubles as pad
    # evidence for chord labeling (folded under the piano evidence)
    melody = None
    if not args.no_melody and args.melody_source != 'none':
        import librosa
        floor_midi = int(librosa.note_to_midi(args.lead_floor))
        melody_json = sc.path('melody.json')
        synth_stem = sc.path('stems_ext') / 'synth' / 'synth.flac'
        has_synth = synth_stem.exists()
        sc.run_stage('melody',
                     {'source': args.melody_source, 'floor': floor_midi,
                      'gate': args.vocal_gate, 'synth': has_synth, 'v': 3},
                     [melody_json],
                     lambda: melody_mod.extract(stems_dir, melody_json,
                                                source=args.melody_source,
                                                lead_floor_midi=floor_midi,
                                                vocal_gate=args.vocal_gate,
                                                synth_wav=synth_stem if has_synth
                                                else None))
        melody = melody_mod.load(melody_json)
        print(f"    melody: {melody['source']}/{melody['engine']} "
              f"{len(melody['notes'])} notes"
              + (f" + poly {len(melody.get('poly', []))}" if melody.get('poly') else ''))

    # piano stage runs BEFORE chords when a dedicated piano stem exists (from
    # --stems 6): its note-level voicings are the primary chord evidence —
    # the reference chart that defines "correct" is the comping instrument.
    # --piano-stem 'input' auto-upgrades to the dedicated stem when available.
    piano_data = None
    piano_flac = ext_dir / 'sw6' / 'piano.flac'
    piano_stem_id = args.piano_stem
    if piano_stem_id == 'input' and piano_flac.exists():
        piano_stem_id = 'piano'
    if piano_stem_id == 'piano' and not piano_flac.exists():
        print('    --piano-stem piano 需要先跑 --stems 6 (无缓存的钢琴轨)')
        return 2
    if args.piano or piano_stem_id == 'piano':
        from . import piano as piano_mod
        piano_json = sc.path('piano.json')
        piano_src = {'piano': piano_flac, 'other': stems_dir / 'other.wav',
                     'input': input_wav}[piano_stem_id]
        sc.run_stage('piano', {'stem': piano_stem_id, 'v': 1}, [piano_json],
                     lambda: piano_mod.transcribe(piano_src, piano_json))
        piano_data = piano_mod.load(piano_json)
        print(f"    piano: {len(piano_data['notes'])} notes, "
              f"{piano_data['n_pedal']} pedal events ({piano_stem_id} stem)")

    piano_evidence = piano_data['notes'] \
        if piano_data and piano_data['notes'] and piano_stem_id == 'piano' \
        else None
    synth_evidence = melody.get('synth_poly') if melody else None

    # BTC posterior second opinion (official large_voca + fine-tuned best.pt).
    # Soft-fails: any error just drops the evidence and the pipeline proceeds.
    from . import btc_score
    btc_data = None
    btc_stamp = btc_score.weights_stamp()
    if btc_stamp:
        btc_npz = sc.path('btc.npz')
        try:
            sc.run_stage('btc', {'w': btc_stamp, 'v': 1}, [btc_npz],
                         lambda: btc_score.compute(input_wav, btc_npz))
            btc_data = btc_score.load(btc_npz)
        except Exception as e:                                    # noqa: BLE001
            print(f'    btc scorer unavailable ({e!r}) — chords run without it')
    if btc_data:
        models = [t for t in ('off', 'ft') if btc_data.get(f'probs_{t}') is not None]
        print(f"    btc: {len(btc_data['times'])} frames x {'+'.join(models)}")

    chords_json = sc.path('chords.json')
    sc.run_stage('chords', {'key': key['active_key'], 'voc_w': voc_w,
                            'harm': [f'{p.parent.name}/{p.name}' for p in harm_wavs],
                            'pev': bool(piano_evidence),
                            'sev': bool(synth_evidence),
                            'btc': btc_stamp if btc_data else None,
                            'nnls': None, 'prog': None, 'v': 12},
                 [chords_json],
                 lambda: chords_mod.recognize(chroma_data, bass, grid, key,
                                              note_names, chords_json,
                                              piano_notes=piano_evidence,
                                              synth_notes=synth_evidence,
                                              btc=btc_data,
                                              nnls_wavs=(stems_dir / 'other.wav',
                                                         stems_dir / 'bass.wav')))
    segments = chords_mod.load(chords_json)['segments']
    n_chords = len([s for s in segments if s['chord'] != 'N'])
    print(f'    {n_chords} chord segments')

    if not args.key:   # user override wins; otherwise settle relative maj/min
        new_key = keydetect.disambiguate_relative(key, segments, key_json)
        if new_key['name'] != key['name']:
            print(f"    key revised by chord evidence: {key['name']} → {new_key['name']}")
            key = new_key

    # ── outputs (always regenerated) ──
    print('  [outputs]')
    mapper = midi_out.BeatMapper(beats['beat_times'])
    hud_json.emit(segments, beats, key, duration, title,
                  out_dir / f'{title}.chordhud.json', grid_zero=args.grid_zero)
    midi_out.write_chords(segments, mapper, beats['bpm'],
                          out_dir / 'chords.mid')
    if melody and melody['notes']:
        midi_out.write_melody(melody['notes'], mapper, beats['bpm'],
                              out_dir / 'melody.mid', quantize=True)
        midi_out.write_melody(melody['notes'], mapper, beats['bpm'],
                              out_dir / 'melody_raw.mid', quantize=False)
    if piano_data and piano_data['notes']:
        from .melodfy_vendor.utilities import write_events_to_midi
        write_events_to_midi(
            0,
            [{'midi_note': n['midi'], 'onset_time': n['start'],
              'offset_time': n['end'],
              'velocity': int(round(n['amp'] * 127))}
             for n in piano_data['notes']],
            [{'onset_time': p['start'], 'offset_time': p['end']}
             for p in piano_data.get('pedal', [])],
            str(out_dir / 'piano.mid'))

    if melody and (melody.get('poly') or melody.get('lead_line')
                   or melody.get('synth_poly')):
        def scale_snap(notes):
            if not args.lines_scale_snap:
                return notes
            steps = (0, 2, 3, 5, 7, 8, 10) if key['mode'] == 'min' \
                else (0, 2, 4, 5, 7, 9, 11)
            scale = {(key['tonic_pc'] + iv) % 12 for iv in steps}
            return [n for n in notes if n['midi'] % 12 in scale]
        tracks = []
        if melody['notes']:
            tracks.append((f"Primary ({melody['source']})", melody['notes']))
        if melody.get('lead_line'):
            tracks.append(('Lead candidate (skyline)', scale_snap(melody['lead_line'])))
        if melody.get('poly'):
            tracks.append(('Other stem (full poly draft)', scale_snap(melody['poly'])))
        if melody.get('synth_poly'):
            tracks.append(('Synth stem draft (cleaner)', scale_snap(melody['synth_poly'])))
        if piano_data and piano_data['notes']:
            tracks.append(('Piano (ByteDance, quantized)', piano_data['notes']))
        midi_out.write_lines(tracks, mapper, beats['bpm'],
                             out_dir / 'lines.mid', quantize=True)
    synthesize.write_preview(
        input_wav, segments, beats, out_dir / 'preview.wav', click=args.click,
        melody_notes=(melody['notes'] if (melody and args.preview_melody) else None))
    report.write(out_dir / 'report.md', title=title, beats=beats, key=key,
                 segments=segments, melody=melody, duration=duration)

    print(f'all done in {time.time() - t_start:.0f}s → {out_dir}')
    return 0
