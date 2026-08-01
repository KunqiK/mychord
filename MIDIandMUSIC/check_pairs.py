"""Cross-check MIDI <-> downloaded audio pairs by duration.

A correct match should have audio duration close to the MIDI note span
(audio may add a few seconds of intro/outro/silence). Big mismatches mean
the YouTube search grabbed the wrong video.

Run: "K:\\Claude Projects\\!!!ChordHUD\\auto-transcribe\\.venv\\Scripts\\python.exe" check_pairs.py
"""
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
HERE = Path(__file__).resolve().parent
sys.path.insert(0, r'K:\Claude Projects\!!!ChordHUD\auto-transcribe')
from evaluate_gt import load_midi_notes  # noqa: E402

# midi filename stem -> download base used (versions share one download)
ALIAS = {
    '1f1e33 [2025]': '1f1e33', '1fle33': '1f1e33',
    'Alexandrite(1)': 'alexandrite',
    'And Revive The Meldoy_playable edit': 'And Revive The Meldoy',
}


def audio_seconds(path: Path) -> float:
    r = subprocess.run(
        ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
         '-of', 'default=noprint_wrappers=1:nokey=1', str(path)],
        capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


rows = []
for mid in sorted(HERE.glob('*.mid')):
    base = ALIAS.get(mid.stem, mid.stem)
    try:
        tracks, _ = load_midi_notes(mid)
        notes = [n for tr in tracks.values() for n in tr]
        mdur = max(n['end'] for n in notes) - min(n['start'] for n in notes)
    except Exception as e:
        rows.append((mid.stem, 0, 0, f'MIDI-ERROR {e}'))
        continue
    hits = [p for p in (HERE / 'audio').iterdir()
            if p.name.startswith(f'{base} === ') and p.suffix == '.mp3']
    if not hits:
        rows.append((mid.stem, mdur, 0, 'MISSING'))
        continue
    adur = audio_seconds(hits[0])
    ratio = adur / mdur if mdur else 0
    verdict = 'OK' if 0.8 <= ratio <= 1.35 else f'MISMATCH ({hits[0].name[:60]})'
    rows.append((mid.stem, mdur, adur, verdict))

okc = sum(1 for r in rows if r[3] == 'OK')
print(f'{okc}/{len(rows)} midis have duration-consistent audio\n')
for name, mdur, adur, verdict in rows:
    mark = 'v' if verdict == 'OK' else 'X'
    print(f'{mark} {name:42s} midi {mdur:6.1f}s  audio {adur:6.1f}s  {verdict}')
