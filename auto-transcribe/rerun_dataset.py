r"""Re-run the pipeline over every dataset song that already has a
transcription (cached stages skip; only stale stages run), then batch_eval.
The A/B workhorse: change something, run this, read the DATASET REPORT.

  .venv\Scripts\python.exe rerun_dataset.py
"""
import contextlib
import io
import json
import subprocess
import sys
import time
from pathlib import Path

AT = Path(__file__).resolve().parent
sys.path.insert(0, str(AT))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from autoscribe import cli                     # noqa: E402
from autoscribe.cache import song_slug         # noqa: E402

MM = Path(r'K:\Claude Projects\!!!ChordHUD\MIDIandMUSIC')
mani = json.loads((MM / 'dataset' / 'manifest.json').read_text(encoding='utf-8'))

t_all = time.time()
done = skipped = failed = 0
for base, info in sorted(mani.items()):
    audio = Path(info['audio_path'])
    cache = AT / 'cache' / song_slug(audio)
    if not (cache / 'chords.json').exists():
        skipped += 1
        continue
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            rc = cli.main([str(audio)])
        ok = rc in (0, None)
    except Exception:                                         # noqa: BLE001
        ok = False
    done += ok
    failed += not ok
    if not ok:
        tail = buf.getvalue().strip().splitlines()[-4:]
        print(f'[FAIL] {base}\n' + '\n'.join(f'  | {t}' for t in tail),
              flush=True)

print(f'rerun: {done} ok, {failed} failed, {skipped} skipped '
      f'in {(time.time() - t_all) / 60:.1f} min', flush=True)

r = subprocess.run([sys.executable, str(MM / 'batch_eval.py')],
                   capture_output=True, text=True, encoding='utf-8',
                   errors='replace')
print(r.stdout)
