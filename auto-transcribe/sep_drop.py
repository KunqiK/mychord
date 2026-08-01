"""Drag-and-drop entry for INSTRUMENT SEPARATION only (LALAL.AI style):
drop a song → get vocals/drums/bass/guitar/piano/other stems as audio files.
All user-facing text lives here (cmd files mangle non-ASCII)."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

ROOT = Path(__file__).resolve().parent


def main() -> int:
    if len(sys.argv) < 2:
        print()
        print('  用法: 把歌曲文件 (flac / mp3 / wav) 拖到「拆乐器」图标上。')
        print('  默认拆成 6 轨: 人声 / 鼓 / 贝斯 / 吉他 / 钢琴 / 其他。')
        print()
        print('  想要更多乐器 (synth / 弦乐 / 电吉他 / 木吉他 / 管风琴 / 萨克斯…),')
        print('  让 Claude 帮你跑, 例如: transcribe.cmd "歌" --stems synth,strings --stems-only')
        print()
        return 0

    song = Path(sys.argv[1])
    print()
    print(f'  正在拆乐器: {song.name}')
    print('  用的是 MVSEP 排行榜第一的 BS-Roformer-SW 模型 (钢琴/吉他分离超过 LALAL.AI)。')
    print('  注意: 这个模型比普通四轨分离重得多, 纯 CPU 可能要跑十几到几十分钟,')
    print('  跑完会缓存, 同一首歌第二次是秒开。先去干点别的吧 ~')
    print()

    from autoscribe.cli import main as run
    rc = run([str(song), '--stems', '6', '--stems-only'])
    if rc != 0:
        print()
        print('  出错了 —— 请把上面的错误信息发给 Claude')
        return rc

    out_dirs = [d for d in (ROOT / 'output').iterdir() if d.is_dir()]
    out = max(out_dirs, key=lambda d: d.stat().st_mtime) if out_dirs else None
    if out and (out / 'stems').exists():
        os.startfile(str(out / 'stems'))  # noqa: S606
    print()
    print('  完成! stems 文件夹已打开:')
    print('    vocals.flac  drums.flac  bass.flac  guitar.flac  piano.flac  other.flac')
    print('  直接拖进 FL Studio / NeuralNote 用。')
    print()
    return 0


if __name__ == '__main__':
    sys.exit(main())
