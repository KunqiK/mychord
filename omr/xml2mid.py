"""musicxml -> midi step of the sheet-screenshot tool.

Also OCRs the screenshot for a tempo marking (quarter-note = NNN) and
writes it into the MIDI — homr itself does not capture tempo."""
import os
import re
import sys

img = sys.argv[1]
base = os.path.splitext(img)[0]
xml = base + '.musicxml'
if not os.path.exists(xml):
    print('没有找到 ' + xml + ' —— 上一步识谱失败, 看上面的报错')
    sys.exit(1)


def find_bpm(image_path):
    """OCR the image; a tempo mark like '♩ = 140' survives as '=140' /
    'J=140' / 'd = 140' in OCR text. Accept 40-260."""
    texts = []
    try:
        from rapidocr import RapidOCR
        res = RapidOCR()(image_path)
        texts = list(getattr(res, 'txts', None) or [])
    except Exception:
        try:
            from rapidocr_onnxruntime import RapidOCR
            res, _ = RapidOCR()(image_path)
            texts = [t[1] for t in (res or [])]
        except Exception:
            return None
    for t in texts:
        m = re.search(r'[=＝]\s*(\d{2,3})', str(t))
        if m and 40 <= int(m.group(1)) <= 260:
            return int(m.group(1))
    return None


bpm = find_bpm(img)
import music21
score = music21.converter.parse(xml)
if bpm:
    score.insert(0, music21.tempo.MetronomeMark(number=bpm))
    print(f'识别到速度标记: BPM = {bpm}')
else:
    print('图里没找到「♩= 数字」速度标记, MIDI 用默认 120 (可在 DAW 改)')
score.write('midi', base + '.mid')
print('MIDI 已生成: ' + base + '.mid')
