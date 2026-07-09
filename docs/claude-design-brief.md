# ChordHUD — Claude Design Brief & Prompt Pack

Everything you need to redesign the ChordHUD UI in **Claude Design**, plus a step‑by‑step
tutorial. Copy the prompts verbatim; feed the context; iterate; export HTML; hand the result
back to Claude Code to wire into the real tool.

> **What Claude Design is** — Anthropic Labs' AI design/prototyping tool at **https://claude.ai/design**,
> powered by Claude Opus 4.7. It turns a text prompt (plus uploaded images/docs or your codebase)
> into an editable visual prototype, and exports to **standalone HTML**, PDF, PPTX, or Canva — with a
> **handoff to Claude Code**. Research preview for **Pro, Max, Team, Enterprise** (Enterprise admins
> must enable it in Organization settings).

---

## 0. TL;DR — the fastest path

1. Go to **https://claude.ai/design** and start a new design.
2. In onboarding, **point it at your repo** `KunqiK/mychord` (or upload `chord_hud_v11.3.html`) so it
   learns your colors, fonts, and components. Optionally **web‑capture** the live page
   `https://kunqik.github.io/mychord/chord_hud_v11.3.html`.
3. Paste **Prompt A (HUD overlay)** below. Iterate with the follow‑ups.
4. Then paste **Prompt B (editor UI)** for the control‑panel redesign.
5. **Export → HTML**, then use **Handoff to Claude Code** (or send me the exported file/URL) and I'll
   integrate it into a new `chord_hud_v12.html` — keeping the video‑export canvas in sync.

---

## 1. Product context (give this to Claude Design as background)

**ChordHUD** is a browser tool that generates a **transparent chord/scale overlay for music videos**.
A musician builds a timeline of chords; the tool renders a 1920×1080 layer showing the current chord,
scale degrees, key, BPM, and song info, and exports it as video (WebM/MP4). In an editor like DaVinci
Resolve the layer is composited over footage with **"Screen" blend mode**, so the **black background
becomes transparent** and only the glowing text/graphics show.

There are **two distinct surfaces** to design:

- **The HUD output** — what gets burned into the exported video (chord name, degree grid, metadata,
  progress bar). This is the priority redesign.
- **The editor UI** — the dark control panel where the user builds the timeline and settings.

**Audience:** musicians / arrangers making chord‑progression breakdown or "play‑along" videos.

---

## 2. Redesign goals

### HUD output (primary)
- **Bass note, enlarged & distinct.** For slash chords like `Am/E`, show the bass note (`E`) as its own
  larger element beneath the chord name — a clear "bass" section, much bigger than today (where it's just
  small text inside the chord string).
- **Scale degrees 1–7 are the primary focus.** Seven large squares in a row for the diatonic degrees,
  each showing the degree number + note name.
- **Accidentals below, piano‑style.** The chromatic alterations (`b2 b3 b5 b6 b7`, or sharps) as smaller
  squares offset *between* the seven primary squares, like a piano's black keys.
- **More readable at a glance** in fast‑moving video: bigger primary elements, clearer active/inactive
  states, less visual clutter.

### Editor UI (secondary)
- Make the dense, monospace, all‑dark control panel **friendlier and more scannable** for new users while
  keeping the professional dark aesthetic.

### Both surfaces
- **EN / 中文 language toggle.** All UI text (and the HUD's burned‑in labels 编曲/人声/发布 →
  Composer/Vocal/Released) switchable between English and Chinese, remembered across sessions.

---

## 3. Hard constraints (state these explicitly — they're easy for a design tool to violate)

- **Canvas is exactly 1920×1080.** Design the HUD to that frame.
- **HUD sits on pure black `#000` and is composited with Screen blend.** Therefore in the HUD output:
  **no dark fills, no dark/opaque panels, no dark text** — they disappear when black turns transparent.
  Everything must be **bright and luminous** (white + colored glows). (This constraint applies to the HUD
  *output* only; the *editor* panel can stay dark since it's not exported.)
- **Legible at video scale** and when the layer is semi‑transparent over busy footage.
- **Single self‑contained HTML file.** The real tool is one `.html` with inline CSS/JS. Fonts load from
  Google Fonts; keep the concept implementable inline with no heavy runtime frameworks.
- **The HUD is rendered twice** — a live DOM preview **and** a `<canvas>` used for video export — and the
  two must match pixel‑for‑pixel. (Claude Design produces the visual/HTML concept; reproducing it on the
  export canvas is an engineering step for the Claude Code handoff — call it out so nothing gets designed
  that can't be drawn on a canvas.)

### Current design system (so the redesign stays on‑brand)
| Token | Value |
|---|---|
| Fonts | `Space Mono` (numbers/Latin, mono) · `Noto Sans SC` (Chinese) |
| Purple (primary accent) | `#8c5aff`, `#b48cff`, `#c8b4ff`, `#e8e0ff` |
| Amber (carry / secondary) | `#ffb83c`, `#ff9f6a`, `#ffcc70` |
| Teal (tertiary) | `#7fe8d0` |
| Emphasis red | `#ff4444` / `#ff7070` |
| Background | `#000` (HUD) · `rgba(6,4,16,0.97)` (editor) |
| Chord name | 120px, white, purple glow · group peers 44px @ 40% · emphasis = red pulsing glow |

### Scale‑degree reference (the exact model to visualize)
- 12 chromatic positions `0…11`. **Diatonic (major) degrees** live at positions `[0,2,4,5,7,9,11]` →
  labels `1 2 3 4 5 6 7`. **Accidentals** live at `[1,3,6,8,10]` → `b2 b3 b5 b6 b7` (flat mode) or
  `#1 #2 #4 #5 #6` (sharp mode). Note there is **no accidental between 3 and 4** and **between 7 and 1** —
  so the piano‑style offset row has gaps there.
- **States:** current chord's active degrees = **purple glow**; carried‑forward degrees from previous
  chords = **amber glow**; everything else = **dim**.

---

## 4. Current UI inventory (what already exists — redesign these, don't invent net‑new)

**HUD output:** top‑left `BPM 191 | Key = Gb Major`; top‑right song title + `编曲/人声/发布` lines;
center chord name (solo, or a `/`-separated group with one large + peers small; optional red emphasis
pulse); a one‑line italic annotation; the 12‑cell degree grid; a bottom progress bar (purple→orange
gradient) with `mm:ss / mm:ss`.

**Editor UI:** grouped header toolbar (播放/导出 · 工程 · 编辑 · 导入和弦 · ❓帮助); **left panel**
(基本信息: BPM/Key/拍号/曲名/编曲/人声/发布 · 背景音频 · 背景图片/视频 · 音名 · 和弦垂直位置);
**right panel** (和弦时间轴 rows: 时间 · 和弦名 · 承接前 · 分组 · 高亮音级 · 解说 · ★ · ✕); a Help modal.

---

## 5. PROMPT A — HUD overlay (paste into Claude Design)

```
I'm redesigning the visual output of ChordHUD, a browser tool that generates a transparent
chord/scale overlay for music videos. The overlay is a 1920×1080 layer rendered on a PURE
BLACK (#000) background and composited over footage with "Screen" blend mode, so black becomes
transparent and only bright elements show. HARD RULE: never use dark fills, dark panels, or dark
text anywhere — every element must be bright/white with colored glows, or it will vanish.

Design the on-screen HUD with this content and hierarchy:

1. CENTER — the current chord name, very large (~120px), white with a soft purple glow. If it's a
   slash chord like "Am/E", render the bass note ("E") as its own DISTINCT, ENLARGED element just
   below the chord name — clearly a separate "bass" section, much bigger and bolder than a normal
   inline slash. Make the bass note feel important.

2. SCALE-DEGREE GRID — make the 7 diatonic degrees (1 2 3 4 5 6 7) the PRIMARY focus: seven large
   rounded squares in a row, each showing the big degree number and, smaller, its note name (e.g.
   1=Gb, 2=Ab …). BELOW that row, show the chromatic accidentals (b2 b3 b5 b6 b7) as SMALLER
   rounded squares, offset horizontally to sit BETWEEN the primary squares like a piano's black
   keys. Note: there is no accidental between 3–4 or between 7–1, so leave those gaps.

3. STATES — the current chord's active degrees glow PURPLE (#8c5aff); degrees "carried" from the
   previous chord glow AMBER (#ffb83c); all other degrees are dim/low-contrast outlines.

4. TOP-LEFT — "BPM 191 | Key = Gb Major" in Space Mono. TOP-RIGHT — song title large, with three
   smaller metadata lines (composer, vocal, release date).

5. ABOVE the degree grid — one line of italic annotation text (chord analysis).

6. BOTTOM — a thin full-width progress bar, purple→orange gradient, with "1:23 / 3:45" time text.

Style: fonts "Space Mono" (numbers/Latin) + "Noto Sans SC" (Chinese). Accents: purple
#8c5aff/#b48cff, amber #ffb83c, teal #7fe8d0, emphasis red #ff4444. Luminous, clean, glanceable
at video speed. Frame is exactly 1920×1080.

START SIMPLE: first give me ONLY the centered chord name + enlarged bass note + the two-row degree
grid (7 big diatonic + accidentals offset below), on black. We'll layer in the metadata, annotation,
and progress bar after that looks right.
```

**Follow‑up prompts (send one at a time, after the base looks right):**
- `Now add the top-left BPM/Key and the top-right title + composer/vocal/release metadata.`
- `Add the bottom progress bar (purple→orange) and the italic annotation line above the grid.`
- `Show all three degree states together: some squares purple (active), some amber (carried), rest dim — so I can see the contrast.`
- `Make a variant where the current chord has an "emphasis" red pulsing glow.`
- `Give me an English and a Chinese version of the metadata labels (Composer/Vocal/Released vs 编曲/人声/发布).`
- `Tighten spacing so nothing clips at 1920×1080 and the grid stays centered.`

---

## 6. PROMPT B — editor / control‑panel UI (paste after the HUD is done)

```
Now redesign the ChordHUD EDITOR interface — the dark control panel where users build the overlay
(this panel is NOT exported to video, so a dark theme is fine here). Keep the professional dark look
but make it far more readable and approachable for first-time users.

Layout: a top toolbar of grouped actions (Playback/Export, Project save/load, Edit undo/redo/copy,
Import chords, Help), a LEFT settings panel (song info: BPM, Key, time signature, title, composer,
vocal, release; background audio; background image/video; custom note names; chord vertical position),
and a RIGHT "chord timeline" — a scrollable list of chord rows. Each row has: time, chord name, a
"carry previous N" stepper, a group field, a clickable 12-cell degree highlighter, an annotation
field, an emphasis ★ toggle, and a delete ✕.

Goals: clearer visual grouping and hierarchy, obvious primary actions (Preview, Export), readable
labels with short helper hints, and a prominent EN/中文 language toggle in the header. Keep the
palette: dark background rgba(6,4,16,0.97), purple #8c5aff/#b48cff accents, teal #7fe8d0, amber
#ffb83c; fonts Space Mono + Noto Sans SC.

Start with the toolbar + the timeline row design; then the left settings panel.
```

---

## 7. How to feed ChordHUD's real context to Claude Design

Pick any (more context = more on‑brand output):
- **Codebase:** in onboarding, connect the GitHub repo **`KunqiK/mychord`** so Claude Design reads the
  real code and derives your design system (colors, type, components). Or **upload
  `chord_hud_v11.3.html`** directly.
- **Web capture:** use the web‑capture tool on the live page
  **`https://kunqik.github.io/mychord/chord_hud_v11.3.html`** to grab actual components so the prototype
  matches the real product.
- **Screenshots:** open the tool, click **▶ 预览** to see the HUD, and drag a screenshot into the prompt.
  A screenshot of the current 12‑box degree row is the single most useful reference for the grid redesign.

---

## 8. Tutorial — using Claude Design end‑to‑end

1. **Access.** Go to **https://claude.ai/design** (sign in with your Claude Pro/Max/Team/Enterprise
   account). On Enterprise, an admin must enable it in Organization settings. It runs on Claude Opus 4.7.
2. **Onboarding / design system.** On first use, let it **read your codebase/design files** so every
   project reuses your colors, typography, and components. Connect `KunqiK/mychord` or upload the HTML.
3. **Start a project.** New design → paste **Prompt A**. Good prompts name four things: **goal** (what
   you're building), **layout** (how it's arranged), **content** (what to show), **audience** (who uses
   it) — Prompt A already covers all four. **Start simple, then layer complexity**; Claude Design responds
   best to incremental requests.
4. **Iterate visually.**
   - **Comment inline** on a specific element ("make this bass note 2× bigger").
   - **Edit text directly** on the canvas.
   - **Adjustment knobs** tweak spacing/color/layout live.
   - Then **"apply across the full design"** to propagate a change everywhere.
   Use the follow‑up prompts in §5.
5. **Add states & variants.** Ask for the active/carried/dim degree states and the emphasis‑glow variant
   so you can compare (§5 follow‑ups).
6. **Export.** Use the export menu → **HTML** (standalone) for the cleanest handoff (also PDF/PPTX/Canva,
   or share an internal URL / save as folder).
7. **Handoff to Claude Code.** Use Claude Design's **Handoff to Claude Code**, or just send me the
   exported HTML file (or the design URL). I'll integrate the approved look into a new
   **`chord_hud_v12.html`** — importantly, re‑implementing the new HUD on the **export `<canvas>`** so the
   recorded video matches the preview, wiring the **EN/中文 toggle**, and keeping every existing feature
   working. Then I'll open a PR.

### Tips
- Redesign the **HUD first**, editor second — the HUD is the higher‑value, more constrained surface.
- Keep repeating the **black‑background / Screen‑blend / no‑dark‑elements** rule; a design tool's instinct
  is to add dark cards, which would render invisible in the exported overlay.
- Ask for **both light‑on‑black states and the three degree states** in one board so you can judge contrast.
- Give it a **screenshot of the current degree row** as the anchor for the "7 big + accidentals below" grid.

### Good to know / limitations
- **Research preview** — expect rough edges; not on Free.
- Exported HTML is a **visual concept**, not the wired app: the chord‑detection, timeline, MIDI import,
  and video export are existing ChordHUD engineering that the Claude Code handoff must preserve.
- Claude Design is **vision/layout**‑oriented; it won't reproduce the canvas‑export pipeline — that's why
  the final integration goes through Claude Code.

---

## 9. Handoff checklist (what to send back to Claude Code)

- [ ] Exported **HTML** (or Claude Design share URL) of the approved **HUD** design.
- [ ] Exported **HTML** of the approved **editor** design (if redesigned).
- [ ] Any color/spacing/type changes you settled on that differ from §3's tokens.
- [ ] Confirmation of the **degree layout** (7 big + accidentals offset below) and the **bass‑note**
      treatment you chose.
- [ ] Whether the **EN/中文 toggle** should also switch the HUD's burned‑in metadata labels.
