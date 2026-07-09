# ChordHUD — Claude Design Brief

Everything you need to hand to **Claude Design** (claude.ai/design) to redesign the ChordHUD **editor UI** — the Input page and the Design page — while leaving the exported video overlay untouched.

**How to use this file:**
1. Copy **§1 The Prompt** into a new Claude Design project.
2. Attach the assets in **§2** (the current HTML file + screenshots).
3. Keep **§3–§5** open as reference — paste any section in if Claude Design asks for detail.

---

## 1. The Prompt  *(copy the block below)*

```text
PROJECT: Redesign the ChordHUD editor UI (not the video output).

WHAT CHORDHUD IS
ChordHUD is a browser-based tool that generates an animated chord/harmony "HUD"
overlay for music-theory and songwriting videos. A creator enters a song's chords
and timing; the tool renders a 1920×1080 overlay (chord name, 12-tone scale-degree
highlights, BPM/key/title, a spinning album vinyl) that they export as MP4/WebM and
composite over their video in DaVinci Resolve / Premiere using "Screen" blend mode.
It is ONE self-contained HTML file that runs in the browser with no install and no
login. The interface is in Simplified Chinese.

WHAT I WANT YOU TO REDESIGN
Only the EDITOR INTERFACE — the control panels the creator works in. Reorganize it
into two clear screens/tabs:

1) INPUT PAGE — everything about WHAT the song is and WHAT PLAYS WHEN:
   BPM, key, time signature, title / composer / vocalist / release-date, and the
   CHORD TIMELINE (rows of: appearance time in seconds OR bar·beat, chord name,
   which scale degrees to highlight, an annotation, a group tag, a "carry-forward"
   count, an ★ emphasis flag, a select checkbox, delete). Plus chord-import actions
   (paste text, import MIDI) and project save / load / undo / redo.

2) DESIGN PAGE — everything about HOW the overlay looks:
   background audio; background image/video (+ a dark-overlay toggle); the rotating
   album cover / vinyl (+ spin-speed, synced to BPM); the global 12-semitone note
   names (with ♭/♯ toggle); and the chord's vertical position on screen.

DO NOT redesign the rendered overlay itself (the chord-name display, the two-row
scale-degree boxes, the vinyl disc, the exported 1920×1080 frame). That output is
carefully tuned for video and must stay pixel-identical. Treat it as a FIXED live
preview that I drop into your new editor.

GOALS
- Cut density and cognitive load. Today six sections are crammed into a 300px left
  rail and the timeline rows are busy. Give it clear hierarchy, grouping, and
  breathing room while staying efficient for power users who build long timelines.
- Make the primary flow obvious: enter song info → build timeline → preview → export.
- Keep a persistent, non-blocking LIVE PREVIEW of the overlay visible while editing.
- Design strong, legible controls: text inputs, selects, sliders, toggle-button
  groups (the time-signature presets 2/4…7/4), file pickers with a clear/loaded
  state, the per-row scale-degree highlight grid (which mirrors the overlay's
  piano-style two-row layout: 7 in-key degrees on top, 5 chromatic below), and the
  teal chord-"alternatives" chips shown under a row after MIDI import.

ART DIRECTION
Keep continuity with the overlay's identity: deep near-black background (#060410),
lavender/purple accent (#8c5aff → #b48cff → #c8b4ff) with soft glow, monospace for
technical labels/numbers (Space Mono) plus Noto Sans SC for Chinese text. Elevate it
from "generic dark dev tool" to a refined, pro-creator instrument — better type
scale, spacing, and state design — without losing its dark, focused, glowy
character. (If a different mood would serve better, propose it; see the alternative
directions I can share.)

HARD CONSTRAINTS (critical)
- Ships as ONE self-contained HTML file, runs from file://, no build step, and no
  heavy new external dependencies.
- PRESERVE every element id, input id, and inline handler name — the app's
  JavaScript is wired to them. Examples that must keep working: previewHUD(),
  startExport(), startExportMp4(), addRow(), applyStatic(), applyNotes(),
  setTimeSig(n), toggleTimingMode(), loadAudio(), loadBackground(), loadJacket(),
  setVinylSpeed(), setAccidental(), updatePos(), saveProject(), loadProject(),
  undo(), redo(), copySelected(), pasteToEnd(), showTextImportModal(),
  importMidiFile(), showHelpModal(); and ids like in-bpm, in-key, in-bpb, in-title,
  in-composer, in-vocalist, in-release, in-total, timeline-list, note-grid,
  pos-slider, live-panel, live-canvas. If you restructure the markup, keep these
  hooks intact. Prefer CSS / layout / component changes over renaming things.
- Dark theme only (used against black video). Target 1280×800+ laptop screens.
  Chinese is the primary language; keep the bilingual font stack.

DELIVERABLES
- Redesigned INPUT page and DESIGN page (desktop).
- The header/toolbar with its primary actions: ▶ 预览 (Preview), 🖥 实时预览 (Live
  preview), ⬇ MP4, ⬇ WebM, 💾 保存 (Save), 📂 导入 (Load), ↩/↪ Undo/Redo,
  📋 粘贴导入 (paste import), 🎹 MIDI 导入, ❓ 帮助 (Help).
- ONE chord-timeline row component shown in its states: default, active (currently
  playing), selected (checkbox), and ★ emphasized — including the two-row
  degree-highlight grid and the alt-chip row.
- The paste-import modal and the Help modal.
- The floating, draggable live-preview panel frame (header + canvas area + scrub
  slider + play/pop-out buttons) — frame only; the canvas content is the fixed
  overlay.
- A proposed information architecture: exactly how Input vs Design split (tabs? a
  segmented switch?) and what lives on each.
- The color / type / spacing tokens you land on, so this can be handed to Claude Code
  to implement back into the real file.

Start by reading the attached current version (chord_hud_v12.1.html) and the
screenshots to extract the existing design system, then propose the new direction
before producing full screens.
```

---

## 2. Assets to attach

| # | Asset | Why | How to get it |
|---|-------|-----|----------------|
| 1 | **`chord_hud_v12.1.html`** (this repo) | Claude Design reads codebases to extract your existing colors/type/components. This is the single most useful asset. | Upload the file, **or** connect the GitHub repo `https://github.com/KunqiK/mychord` and point it at this file. |
| 2 | **Screenshot — Input zone** | Shows the current timeline rows + header toolbar. | Open `chord_hud_v12.1.html`; it opens straight into the editor. Screenshot the right panel (和弦时间轴) + top toolbar. |
| 3 | **Screenshot — Design zone** | Shows the current left-rail sections. | Screenshot the left panel (基本信息 → 背景音频 → 背景图片/视频 → 旋转唱片 → 音名 → 和弦垂直位置). |
| 4 | **Screenshot — rendered overlay** | So Claude Design knows what the FIXED output looks like and doesn't try to restyle it. | Click **▶ 预览**, screenshot a frame, press any key to stop. |
| 5 | *(optional)* Live-preview panel + Help/paste modals | Extra states to redesign the frame around. | Click **🖥 实时预览** and **❓ 帮助**, screenshot each. |

> Tip: Claude Design also has a **web-capture** tool and can pull a **design system straight from your codebase or a Figma file** during onboarding — pointing it at asset #1 does most of that work automatically.

---

## 3. Current information architecture (what exists today)

Single full-screen editor (`#editor`), dark overlay, two columns:

- **Header toolbar** — grouped clusters: `播放/导出` (Preview · Live · WebM · MP4) · `工程` (Save · Load) · `编辑` (Undo · Redo · Copy · Paste) · `导入和弦` (Paste import · MIDI) · `❓帮助`.
- **Left panel (`#panel-left`, 300px)** — the "Design" controls: 基本信息 (BPM/Key/拍号 presets/曲名/编曲/人声/发布时间 + 应用基本信息) · 背景音频 · 背景图片/视频 (+遮罩) · 旋转唱片(专辑封面) (+转速) · 音名 12半音 (♭/♯ + grid + 应用音名) · 和弦垂直位置 (slider).
- **Right panel (`#panel-right`, flex)** — the "Input" controls: 和弦时间轴 — 总时长, a list of `.tl-item` rows, `＋ 添加和弦`.
- **Floating live-preview panel (`#live-panel`)** — draggable, resizable; a CSS-scaled 1920×1080 `<canvas>` = the exact export renderer, plus a scrub slider, ▶ play, and ⧉ pop-out-to-OS-window.
- **Modals** — `#text-import-modal` (paste chords), `#help-modal` (7-section guide).

A single **timeline row** currently packs: select checkbox · time (秒 or 小节·拍) · chord name · group tag · carry-forward ±（承接前）· ★ emphasis · ✕ delete · annotation field · a two-row 12-cell degree-highlight grid · teal alt-chips (after MIDI). This row is the densest thing in the app and the prime candidate for a cleaner component.

---

## 4. Current design tokens (so the redesign can evolve them, not fight them)

- **Background:** `#000` stage; editor overlay `rgba(6,4,16,0.97)` (≈ `#060410`); panels/inputs use translucent white fills `rgba(255,255,255,0.03–0.07)`.
- **Accent (purple/lavender):** `#8c5aff`, `#b48cff`, `#c8b4ff`, `#d4b8ff`; glows `rgba(140,90,255,·)`.
- **Semantic button colors:** purple = primary; **orange** `#ffb890` = export (WebM/MP4); **green** `#7fe8a0` = project save/load; **teal** `#9ff4dd` / `rgba(80,200,180,·)` = copy/paste & alt-chips & help; **red** `rgba(220,80,80,·)` = clear/delete; **amber** `#ffcc70` = carry-forward highlight.
- **Type:** `Space Mono` (monospace — labels, numbers, buttons, technical) + `Noto Sans SC` (Chinese body/annotations). Both already loaded from Google Fonts.
- **Shape:** small radii (5–8px inputs/buttons, 8px cards, 12px on the landing page), 1px translucent borders, 0.12–0.2s transitions, thin dividers `rgba(255,255,255,0.07)`.

---

## 5. Do-NOT-touch list & preservation contract

**Leave the rendered overlay exactly as-is** (this is the video output, not the editor):
- `previewHUD()` full-screen preview and the `#stage` / `#hud` DOM it shows.
- `drawCanvas()` and everything it paints: chord-name display, the two-row degree layout (`DEG_LAYOUT`), the vinyl (`drawVinyl`), background layer, song-meta text, annotation, emphasis pulse.
- `#live-canvas` **content** (it renders via `drawCanvas` — WYSIWYG with the export). You may restyle the panel FRAME around it, not the picture inside.
- The WebM/MP4 export path.

**Preservation contract for whoever implements the new design (likely Claude Code):**
- Keep all element `id`s, input `id`s, and inline handler names listed in the prompt.
- Keep the structure that JavaScript generates for timeline rows (`renderList()` builds `.tl-item`s that reference specific classes and `setEntry*()` / `pickAlt()` / `changeCarry()` / `toggleEmphasis()` handlers).
- Stay a single `file://`-openable HTML file (fonts from CDN are fine; the app already inlines its heavy deps).

---

## 6. Art-direction options (swap into the "ART DIRECTION" paragraph)

Default = **A**. Tell Claude Design which one, or blend.

- **A — Continuity / elevated (recommended).** Keep the dark + purple-glow identity; just refine type scale, spacing, and states. Lowest risk, strongest tie to the overlay.
- **B — Studio console.** Inspired by pro audio DAWs/synths (Ableton, Serum): darker neutral greys, tactile knob/fader controls, one confident accent, less web-glow, more "instrument."
- **C — Editorial / calm.** More whitespace, larger type, softer contrast, fewer glows — a modern dark-SaaS look that reduces fatigue on long editing sessions.
- **D — Neon / retro-futurist.** Lean into the music-video vibe: richer gradients and subtle grid/scanline motifs echoing the overlay's generated background.

---

## 7. After Claude Design — implementation loop

Claude Design produces the **design**; it does not run your app's JavaScript. To ship it:
1. Export from Claude Design as **standalone HTML** and/or use the **"hand off to Claude Code"** bundle.
2. Have Claude Code implement the new skin into a **new** file — `chord_hud_v13.html` (this repo's rule: never modify a previous version; always create the next `vN`). Record the change in `ChordHUD.md`.
3. Verify: the redesigned editor drives all the same functions, and the exported overlay frame is byte-for-byte the same as v12.1's.
