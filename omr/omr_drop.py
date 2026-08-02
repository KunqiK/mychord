"""Drag-and-drop entry for sheet-screenshot -> MIDI. All user-facing text
lives HERE — cmd files mangle non-ASCII and flash-crash (learned twice)."""
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

HERE = Path(__file__).resolve().parent
VENV = HERE / 'venv' / 'Scripts'


def hold(code: int) -> int:
    try:
        input('\n  按回车键关闭窗口...')
    except EOFError:
        pass
    return code


def main() -> int:
    if len(sys.argv) < 2:
        print()
        print('  用法: 把五线谱截图 (png/jpg) 拖到「谱图转MIDI」图标上, 不要双击。')
        print('  生成的 .mid 会出现在图片旁边 (同文件夹同名)。')
        return hold(0)

    img = Path(sys.argv[1])
    if not img.exists():
        print(f'  找不到文件: {img}')
        return hold(1)

    print()
    print(f'  谱图: {img.name}')
    try:
        ts = input('  拍号: 直接回车=按谱子上的, 或输入正确拍号如 4/4 : ').strip()
    except EOFError:
        ts = ''
    print()
    print('  正在识谱 (每页约 15-30 秒)...')
    r = subprocess.run([str(VENV / 'homr.exe'), str(img)])
    if r.returncode != 0:
        print('  识谱失败 —— 请把上面的错误信息发给 Claude')
        return hold(r.returncode)
    args = [str(VENV / 'python.exe'), str(HERE / 'xml2mid.py'), str(img)]
    if '/' in ts:
        args.append(ts)
    r = subprocess.run(args)
    if r.returncode != 0:
        print('  转 MIDI 失败 —— 请把上面的错误信息发给 Claude')
        return hold(r.returncode)
    print()
    print('  提示: MIDI 速度若没识别到谱面标记则默认 120, 可在 DAW 改;')
    print('        三连音/复杂节奏可能被简化。')
    return hold(0)


if __name__ == '__main__':
    sys.exit(main())
