"""Drag-and-drop entry: run the pipeline on the dropped file, then open the
output folder and explain the results. All user-facing text lives here
(cmd files mangle non-ASCII)."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

ROOT = Path(__file__).resolve().parent


def newest_output() -> Path | None:
    out = ROOT / 'output'
    dirs = [d for d in out.iterdir() if d.is_dir()] if out.exists() else []
    return max(dirs, key=lambda d: d.stat().st_mtime) if dirs else None


def main() -> int:
    if len(sys.argv) < 2:
        print()
        print('  用法: 把歌曲文件 (flac / mp3 / wav) 用鼠标拖到「拖歌扒谱」图标上,')
        print('  松手后自动扒谱, 完成后自动打开结果文件夹。')
        print()
        return 0

    song = Path(sys.argv[1])
    print()
    print(f'  正在扒谱: {song.name}')
    print('  (第一次处理一首歌需要几分钟, 大头是 AI 分离人声/鼓/贝斯;')
    print('   同一首歌再跑第二次只要几秒)')
    print()

    from autoscribe.cli import main as run
    rc = run([str(song), '--click'])
    if rc != 0:
        print()
        print('  出错了 —— 请把上面的错误信息发给 Claude')
        return rc

    out = newest_output()
    if out:
        os.startfile(str(out))  # noqa: S606
    print()
    print('  完成! 结果文件夹已打开。文件说明:')
    print('    preview.wav       - 先听这个! 和弦垫混在原曲下, 错和弦一听就打架')
    print('    *.chordhud.json   - ChordHUD 里点「载入工程」选它, 和弦全部预填好')
    print('    report.md         - 扒谱报告, 低置信度和弦排最前 (先修这些)')
    print('    melody.mid        - 人声主旋律 (已对齐节拍), 拖进 DAW')
    print('    lines.mid         - 多轨旋律草稿 (含伴奏复音), 在 DAW 里删修')
    print()
    return 0


if __name__ == '__main__':
    sys.exit(main())
