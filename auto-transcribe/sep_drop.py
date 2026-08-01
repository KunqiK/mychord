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
        print('  拆成: 人声 / 鼓 / 贝斯 / 吉他 / 钢琴 / 木吉他 / 弦乐 / 木管。')
        print()
        print('  还想要别的乐器 (synth / 电吉他 / 管风琴 / 萨克斯 / 小提琴 / 铜管…共53种),')
        print('  让 Claude 帮你跑, 例如: transcribe.cmd "歌" --stems synth,organ --stems-only')
        print()
        return 0

    song = Path(sys.argv[1])
    print()
    print(f'  正在拆乐器: {song.name}')
    print('  人声/鼓/贝斯/吉他/钢琴 用 MVSEP 排行榜第一的模型 (超 LALAL.AI),')
    print('  木吉他/弦乐/木管 用 MVSep Mega-53 单乐器模型。')
    print('  注意: 纯 CPU 第一次要跑 1~2 小时 (4 个 AI 模型轮流过一遍),')
    print('  跑完永久缓存, 同一首歌第二次秒开。先去干别的吧 ~')
    print()

    from autoscribe.cli import main as run
    rc = run([str(song), '--stems', '6,aguitar,strings,woodwind', '--stems-only'])
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
    print('    vocals / drums / bass / guitar / piano / acoustic_guitar / strings / woodwind')
    print('  直接拖进 FL Studio / NeuralNote 用。')
    print()
    return 0


if __name__ == '__main__':
    sys.exit(main())
