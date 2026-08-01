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
force_ts = sys.argv[2] if len(sys.argv) > 2 and '/' in sys.argv[2] else None
import music21
score = music21.converter.parse(xml)
if bpm:
    score.insert(0, music21.tempo.MetronomeMark(number=bpm))
    print(f'识别到速度标记: BPM = {bpm}')
else:
    print('图里没找到「♩= 数字」速度标记, MIDI 用默认 120 (可在 DAW 改)')
if force_ts:
    # 强制拍号 + 压紧空拍: homr 的小节常常没填满名义拍号, MIDI 导出会在
    # 每小节尾垫静音。按各小节的实际内容时长(跨声部取最长, 保留显式
    # 休止符)重新首尾相接。
    parts = list(score.parts)
    measures = [list(p.getElementsByClass(music21.stream.Measure))
                for p in parts]
    n_m = max(len(ms) for ms in measures)
    slot = float(music21.meter.TimeSignature(force_ts).barDuration.quarterLength)
    new_score = music21.stream.Score()
    if bpm:
        new_score.insert(0, music21.tempo.MetronomeMark(number=bpm))
    for ms in measures:
        np_ = music21.stream.Part()
        np_.insert(0, music21.meter.TimeSignature(force_ts))
        for i, m in enumerate(ms):
            t = i * slot
            kept = [el for el in m.notesAndRests if el.offset < slot]
            for el in kept:
                # clip anything spilling past the barline (OMR overfull
                # errors), and extend the final sounding note to the
                # barline (OMR loses sustain; matches sheet preview)
                end = min(float(el.offset) + float(el.quarterLength), slot)
                el.quarterLength = max(end - float(el.offset), 0.125)
                np_.insert(t + el.offset, el)
            if kept and kept[-1].isNote or kept and hasattr(kept[-1], 'pitches'):
                last = kept[-1]
                last.quarterLength = max(slot - float(last.offset),
                                         float(last.quarterLength))
        new_score.insert(0, np_)
    score = new_score
    print(f'已强制拍号 = {force_ts} (每小节 {slot} 拍, 超出裁剪/结尾延音填满, {n_m} 小节)')
score.write('midi', base + '.mid')
print('MIDI 已生成: ' + base + '.mid')
