# gt/ — 常驻评测基准 (勿删)

- `S.A.T.E.L.L.I.T.E.mid` — 用户人工全曲扒谱 (24 轨: Pad/Piano/String 和声, Lead/Vocal 旋律, 150 BPM)。
  这是管线所有精度指标的对照标准。
  音频: `D:\!!!Production\Reference Tracks\Camellia\[C95] かめるかめりあ — heart of android {CTCD-0018} [CD-FLAC]\07. S.A.T.E.L.L.I.T.E..flac`
  对齐偏移 +2.04s (音频减 MIDI)。
  评测: `.venv\Scripts\python.exe evaluate_gt.py --midi gt\S.A.T.E.L.L.I.T.E.mid --cache cache\<slug> --offset 2.04`

历史: 原存放在 `C:\Users\kunqi\Downloads`, 2026-07-31 发现被清理进了回收站, 抢救回来改存这里并入 git。
"correct chord.mid" (202 和弦事件) 回收站里已无, 未能找回; "correct vocal melody.mid" 的内容等同
GT 里的 Vocal 轨 (154 音符), 无损失。
