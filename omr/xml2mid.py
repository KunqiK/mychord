"""musicxml -> midi step of the sheet-screenshot tool (robust, visible errors)."""
import os
import sys

img = sys.argv[1]
base = os.path.splitext(img)[0]
xml = base + '.musicxml'
if not os.path.exists(xml):
    print('没有找到 ' + xml + ' —— 上一步识谱失败, 看上面的报错')
    sys.exit(1)
import music21
music21.converter.parse(xml).write('midi', base + '.mid')
print('MIDI 已生成: ' + base + '.mid')
