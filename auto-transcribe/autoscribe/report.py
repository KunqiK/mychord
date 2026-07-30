"""report.md — key/BPM/segments + a worst-first review list."""
from __future__ import annotations

from pathlib import Path

from .beats import bar_beat_at
from .hud_json import CONF_FLAG_BELOW, roman_for


def _t(seconds: float) -> str:
    m, s = divmod(seconds, 60)
    return f'{int(m)}:{s:05.2f}'


def write(out_path: Path, *, title: str, beats: dict, key: dict,
          segments: list[dict], melody: dict | None, duration: float):
    lines = [f'# 扒谱报告 — {title}', '']
    lines += ['## 全局', '']
    key_line = f"- **调性**: {key['name']}"
    if key.get('top3'):
        cands = ', '.join('{} r={}'.format(c['name'], c['corr'])
                          for c in key['top3'])
        key_line += f'  (候选: {cands})'
    lines.append(key_line)
    alt = f" — 半/双倍候选 {beats['bpm_alt']}" if beats.get('bpm_alt') else ''
    grid_desc = (f"恒速网格,锁定强度 {beats.get('grid_lock', 0):.1f}"
                 if beats.get('grid_fitted') else '逐拍跟踪(周期性弱)')
    lines.append(f"- **BPM**: {beats['bpm']:.2f}{alt}  ({grid_desc})")
    lines.append(f"- **拍号**: {beats['beats_per_bar']}/4,强拍相位 {beats['downbeat_phase']}"
                 f" — 首强拍 @ {_t(beats.get('first_downbeat', 0.0))}"
                 f"(如 click 试听相位不对,用 `--downbeat-shift 0..3` 重跑)")
    if beats.get('phase_scores'):
        lines.append(f"- 相位得分: {[round(s, 3) for s in beats['phase_scores']]}")
    lines.append(f"- **时长**: {_t(duration)},和弦段数 {len([s for s in segments if s['chord'] != 'N'])}")
    if melody:
        lines.append(f"- **旋律**: 来源 {melody['source']} · 引擎 {melody['engine']}"
                     f" · {len(melody['notes'])} 音符")
    lines.append('')

    low = sorted((s for s in segments
                  if s['chord'] != 'N' and s.get('conf', 1) < CONF_FLAG_BELOW),
                 key=lambda s: s.get('conf', 1))
    lines += ['## ⚠ 低置信度段(最差优先,先听这些)', '']
    if low:
        lines.append('| 时间 | 小节 | 和弦 | 置信度 | 备选 |')
        lines.append('|---|---|---|---|---|')
        for s in low:
            bar, beat = bar_beat_at(s['start'], beats)
            lines.append(f"| {_t(s['start'])} | {bar}.{beat} | {s['chord']} "
                         f"| {s.get('conf', 0):.2f} | {', '.join(s.get('alts', [])) or '—'} |")
    else:
        lines.append('(无 — 所有段置信度均在阈值以上)')
    lines.append('')

    lines += ['## 全部和弦段', '']
    lines.append('| 时间 | 小节 | 和弦 | 级数 | 置信度 |')
    lines.append('|---|---|---|---|---|')
    for s in segments:
        if s['chord'] == 'N':
            continue
        bar, beat = bar_beat_at(s['start'], beats)
        roman = roman_for(s['root_pc'], s.get('sfx', ''), key) \
            if s.get('root_pc') is not None else ''
        flag = ' ⚠' if s.get('conf', 1) < CONF_FLAG_BELOW else ''
        lines.append(f"| {_t(s['start'])} | {bar}.{beat} | {s['chord']}{flag} "
                     f"| {roman} | {s.get('conf', 0):.2f} |")
    lines.append('')
    lines += ['## 使用', '',
              '1. 打开 `preview.wav` A/B 试听 — 和弦垫混在原曲下,错和弦会明显打架',
              '2. ChordHUD → 📂 载入工程 → `*.chordhud.json`,低置信度段的备选和弦点 chip 即换',
              '3. `melody.mid`(已量化)/ `melody_raw.mid`(原始)导入 DAW 校对',
              '']
    out_path.write_text('\n'.join(lines), encoding='utf-8')
