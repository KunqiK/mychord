# mychord (formerly ClaudeCodesTesting)

A workspace for projects built and refined with Claude Code.

## Workflow rules
- **Always commit with a clean message before starting new changes.**
- Push to GitHub after every meaningful change session.

## Design
- **`docs/claude-design-brief.md`** — the brief, paste‑ready prompts, and tutorial for redesigning the
  ChordHUD UI in **Claude Design** (Anthropic Labs, https://claude.ai/design). Captures the redesign
  goals (HUD: enlarged slash/bass note, 7 diatonic degrees as primary squares with accidentals offset
  below piano‑style, EN/中文 toggle), the hard constraints (1920×1080, pure‑black/Screen‑blend so the
  HUD output must avoid dark elements, single‑file HTML, DOM+canvas parity), and the design‑system
  tokens. The intended flow: design in Claude Design → export HTML → hand off to Claude Code to build
  `chord_hud_v12.html` (re‑implementing the look on the export canvas and wiring the language toggle).

---

## Projects

### chord_hud_v4.html
A browser-based chord/progression HUD designed for video overlay (1920×1080, black background, Screen blending mode).

**Features:**
- Displays current chord name, scale degrees, BPM, key, song title, composer, vocalist
- Timeline editor: set absolute start times (seconds) per chord, highlight active scale degrees
- Progress bar with scrubbing (click to seek during preview)
- WebM export at 60 fps, 8 Mbps

**Session history (2026-05-24):**
- Fixed chord timing bug: `getCurrentIdx` used `else break` which stopped scanning the timeline early if entries were out of order, causing chords to appear at wrong times.
- Added `syncTimelineFromDOM()`: reads all time/chord input values directly from the DOM before preview/export starts, so edits don't need to be committed (blurred) before clicking Preview.
- Added `timeline.sort()` before preview and export to guarantee correct order.
- Added progress bar click-to-seek during preview: adjusts `startTime` via `performance.now()` so the RAF loop jumps to the clicked position immediately.
- Expanded from 7-note diatonic to **12-tone chromatic** degree system (positions 0–11).
- Added ♭/♯ toggle: switches degree number labels (`1 b2 2 b3…` vs `1 #1 2 #2…`); does NOT auto-fill letter note names (user edits those manually).
- Added **per-chord annotation**: italic text field per timeline entry, displayed below the degree row on the HUD and in canvas export.
- Added **carry-forward degree highlighting**: each chord carries highlights from the previous N chords. Current chord's degrees = purple; carried degrees = amber; current takes priority on overlap.

**Key functions:**
| Function | Purpose |
|---|---|
| `syncTimelineFromDOM()` | Reads DOM inputs → updates `timeline[]` → sorts. Called before preview/export. |
| `getCurrentIdx(t)` | Returns the index of the active chord at time `t` (scans all entries, no early break). |
| `previewHUD()` | Hides editor, runs RAF animation loop with accurate elapsed-time tracking. |
| `startExport()` | Records a WebM via `MediaRecorder` + canvas at 60 fps. |
| `applyFrame(idx)` | Updates chord display, degree row, and active row highlight. |
| `renderHUDDegrees(idx)` | Builds 12 degree boxes with purple/amber/dim states based on active + carry. |
| `setAccidental(type)` | Switches `degreeLabels` between flat and sharp arrays; does not touch `globalNotes`. |

---

### chord_hud_v5.html
Built on v4 with two new features. **v4 was not modified.**

**Additional features over v4:**
- **发布时间 (Release Date)**: New input field in the left panel. Syncs to the top-right song-meta on the HUD and canvas export. Hidden automatically when blank.
- **Multi-chord group display**: Each timeline entry has a `group` string field. Chords sharing the same group string appear simultaneously on screen — the playing chord at 120px/full brightness, group peers at 44px/40% opacity, separated by `/`. Flash animation targets only the active chord. Solo chords (empty group) behave identically to v4.

**Key changes from v4:**
- `timeline[]` entries have a new `group: ''` field.
- `#chord-name` → `#chord-display` flex container.
- `renderHUDChord()` → `renderChordDisplay(idx, flash)`: handles both solo and grouped layout.
- `syncTimelineFromDOM()` reads the new `group-input` field per row.
- `drawCanvas()` renders grouped chords horizontally (measuring widths, centering the whole group) and draws the release date line.

**Key functions (v5 additions):**
| Function | Purpose |
|---|---|
| `renderChordDisplay(idx, flash)` | Solo: one large span. Grouped: flex row of all group members, current large, others small. |
| `applyStatic()` | Also syncs release date; shows/hides `#release-line` based on content. |

---

### chord_hud_v6.html
Built on v5. Adds audio/background media, emphasis animation, and a GitHub Pages landing page. **v5 was not modified.**

**Additional features over v5:**
- **背景音频**: Load MP3/WAV via file picker; audio plays during preview and is mixed into WebM export via `hudAudio.captureStream()`.
- **背景图片/视频**: Image or video drawn behind HUD via `ctx.drawImage()`; optional dark overlay toggle.
- **重要和弦强调**: Per-entry `emphasis` boolean; CSS `@keyframes pulse-glow` animates a purple glow on the chord name in DOM preview; canvas export animates via `pulse = 0.5+0.5*sin(...)`.
- **Annotation moved above degree row**: `#chord-annotation` now renders before `#degree-row` in HTML and at `cy+40` in canvas (degrees at `cy+80`).
- **index.html**: GitHub Pages landing page with feature cards, usage steps, and a chord preview mockup.

**Key changes from v5:**
- New globals: `let bgType = null; let bgImage = null;`
- Timeline entries gain `emphasis: false` field.
- `saveProject()` version bumped to 2.
- Background layer HTML: `<div id="bg-layer">` with nested `<video>` + `<img>` + overlay `<div>`.
- Hidden `<audio id="hud-audio">` element for playback and stream capture.

---

### chord_hud_v6.1.html
Built on v6. Redesigns emphasis color to **red** and adds clear buttons for media. **v6 was not modified.**

**Changes from v6:**
- Emphasis color changed from purple to red: `@keyframes pulse-glow` uses `#ff4444`/`#ff7070`; `.emph-btn.active` styled red; canvas export uses `rgb(255, 68+pulse*40, 68+pulse*30)` with `shadowColor='#ff1010'`.
- `.clear-btn` added: `✕` buttons next to audio and background file names; `clearAudio()` and `clearBackground()` functions reset src and hide the buttons.

---

### chord_hud_v7.html
Built on v6.1. Adds bar/beat timing mode as an alternative to seconds. **v6.1 was not modified.**

**Additional features over v6.1:**
- **小节/拍 输入模式**: Toggle button switches between seconds input and bar+beat inputs per timeline entry. Per-entry hint shows the computed seconds value.
- **BPM-driven auto-recalculate**: Changing BPM or beats-per-bar in bar mode auto-recalculates all entry `time` values.
- Internal `time` (seconds) is always kept in sync; preview/export are unaffected.

**New globals:** `let timingMode = 'seconds'`, `let beatsPerBar = 4`

**Key functions (v7 additions):**
| Function | Purpose |
|---|---|
| `barBeatToSeconds(bar, beat)` | Converts bar+beat to seconds using current BPM and beatsPerBar. |
| `secondsToBarBeat(secs)` | Inverse conversion for mode switch. |
| `toggleTimingMode()` | Converts all entries and re-renders the timeline list. |
| `updateBarHint(i)` | Refreshes the computed-seconds hint label for entry `i`. |

**saveProject() version:** 3 (adds `timingMode`, `beatsPerBar`).

---

### chord_hud_v8.html
Built on v7. Adds text paste import, MIDI file import, and undo/redo. **v7 was not modified.**

**Additional features over v7:**
- **📋 粘贴导入**: Modal with textarea; parses `Am G F C` or `| Am | G | F | C |` or multi-line text; converts to timeline entries using current BPM and a configurable beats-per-chord value; appends to existing timeline.
- **🎹 MIDI 导入**: Inline binary MIDI parser (no external dependencies); reads MThd/MTrk, variable-length deltas, running status, note-on events, and tempo map; groups simultaneous notes (within 10% of a beat), matches pitch-class sets against chord templates (major/minor/maj7/m7/dom7/dim/aug/sus2/sus4); deduplicates consecutive identical chords; unrecognised clusters become `???`.
- **撤销/重做 (Ctrl+Z / Ctrl+Y)**: 50-state JSON snapshot stack; ↩/↪ header buttons with disabled state feedback.

**pushHistory() call points:** `addRow`, `removeRow`, `sortTimeline` (covers all time edits), `changeCarry`, `toggleEmphasis`, `toggleTimingMode`, `doTextImport`, `importMidiFile`, `loadProject` (resets stack then pushes initial state). Also called once at INIT.

**Key functions (v8 additions):**
| Function | Purpose |
|---|---|
| `pushHistory()` | Slices stack to current position, pushes JSON snapshot, trims to MAX_UNDO=50. |
| `undo()` / `redo()` | Decrement/increment `undoIdx`, restore snapshot, re-render. |
| `updateUndoButtons()` | Enables/disables the ↩ ↪ header buttons based on stack position. |
| `showTextImportModal()` / `doTextImport()` | Opens modal, parses chord tokens (filter by `/^[A-Ga-g]/`), appends entries. |
| `parseMidi(buf)` | Pure-JS MIDI binary parser returning `{ticksPerBeat, tempoMap, noteOns}`. |
| `ticksToSeconds(tick, tempoMap, tpb)` | Walks tempo segments to convert tick position to seconds. |
| `detectChord(pitchClasses)` | Best-fit pitch-class template match; returns root+suffix string or `???`. |
| `importMidiFile(input)` | Reads file as ArrayBuffer, calls parseMidi, groups notes, detects chords, appends. |

---

### chord_hud_v9.html
Built on v8. Adds time signature preset buttons and fixes the delete bug. **v8 was not modified.**

**Additional features over v8:**
- **拍号快捷按钮**: Replaces the plain `每小节拍数` number input with a row of preset buttons (2/4, 3/4, 4/4✓, 5/4, 6/4, 7/4) plus a custom numeric field. `setTimeSig(n)` is the single update path; active button stays highlighted; loadProject and toggleTimingMode sync button state.
- **拍数输入上限**: Beat input in bar mode now has `max="${beatsPerBar}"` to prevent overflow (e.g. beat 4 in a 3/4 bar).
- **删除行 bug 修复**: `removeRow(i)` now calls `syncTimelineFromDOM()` first (capturing unsaved group/chord/annotation inputs), saves the entry reference, then re-locates it via `indexOf` after the sync+sort before splicing — prevents group data loss and wrong-entry deletion.

**Key functions (v9 additions):**
| Function | Purpose |
|---|---|
| `setTimeSig(n)` | Sets `beatsPerBar`, syncs number input, highlights active ts-btn, re-renders if in bars mode. |

---

### chord_hud_v10.html
Built on v9. Adds MP4 export via WebCodecs + mp4-muxer. **v9 was not modified.**

**Additional features over v9:**
- **⬇ MP4 导出**: Encodes 1920×1080@60fps H.264 (avc1.640033, 8 Mbps) using the browser WebCodecs `VideoEncoder` API and muxes into MP4 via `mp4-muxer@5.2.2` (loaded via dynamic `import()` from jsDelivr CDN). Progress shown as percentage. Requires Chrome 94+ / Edge 94+. Falls back gracefully with an alert on unsupported browsers.

**Key functions (v10 additions):**
| Function | Purpose |
|---|---|
| `startExportMp4()` | Async: checks WebCodecs support, loads mp4-muxer, encodes all frames, downloads `.mp4`. |

---

### chord_hud_v11.html
Built on v10. Expands MIDI chord vocabulary and improves detection accuracy. **v10 was not modified.**

**Additional features over v10:**
- **Extended CHORD_TEMPLATES**: 22 templates across 3 tiers — 5-note (maj9, m9, 9, 7b9, 7#9), 4-note (maj7, mMaj7, m7, m7b5, 7, 7sus4, augMaj7, dim7, 6, m6, add9), 3-note (aug, dim, sus4, sus2, major triad, minor triad). Replaces the 9-template set originally in v8.
- **mp4-muxer inlined**: Embeds mp4-muxer@5.2.2 directly (no CDN dependency) to fix export on browsers that block jsDelivr.

**Key functions (expanded template set; logic unchanged):**
| Function | Purpose |
|---|---|
| `detectChord(pitchClasses)` | Best-fit pitch-class match over all 22 templates; returns root+suffix or `???`. |

---

### chord_hud_v11.1.html
Built on v11. Adds multi-interpretation chord detection, bass/slash chords, alt chips in the editor, and a robust MP4 export with codec fallback. **v11 was not modified.**

**Additional features over v11:**
- **多解和弦检测 `detectChords(pitchClasses, bassPC)`**: Replaces `detectChord`. Returns up to 8 ranked `{name, score}` candidates. Scoring uses interval weights (`INTERVAL_WEIGHTS = [3,0.5,1,2.5,2.5,1,1.5,1.5,1,1.5,2,2]` indexed by semitone from root). Relaxed threshold: ≥75% of template notes required (was 100%).
- **Bass/slash chord notation**: `importMidiFile` tracks `minNote` (lowest raw MIDI pitch) per simultaneous group; if `minNote % 12 ≠ root`, appends `/BassNote` to all candidate names (e.g., `Am/E`).
- **备选和弦 alt chips**: Each timeline entry gains `alts: string[]` (top 4 alternatives after the selected chord). Rendered as teal `.alt-chip` buttons below the annotation field. `pickAlt(i, name)` swaps chord in-place and updates DOM without calling `renderList()`. `alts` persists in `saveProject()` JSON.
- **MP4 导出修复**: Codec fallback chain tries `avc1.640029` → `avc1.4D4029` → `avc1.42E029` → `avc1.42E01F`. Output callback and `encoder.flush()` wrapped in try/catch. 5-second per-frame queue timeout prevents hangs. `encoder.close()` called on all exit paths. Detailed error messages guide users to chrome://settings hardware acceleration.

**Key functions (v11.1 additions):**
| Function | Purpose |
|---|---|
| `detectChords(pitchClasses, bassPC)` | Returns `[{name, score}, …]` sorted descending; adds `/BassNote` when bass ≠ root. |
| `pickAlt(i, name)` | Swaps selected chord ↔ clicked alt in `timeline[i]`; updates chord input and alt chip row in-place. |

**saveProject() version:** 3 (unchanged; `alts` round-trips via `JSON.parse(JSON.stringify(timeline))`; old project files load fine).

---

### chord_hud_v11.2.html
Built on v11.1. Adds row copy-paste and in-browser WebM→MP4 conversion. **v11.1 was not modified.**

**Additional features over v11.1:**
- **⬜ 复制所选 / 📋 粘贴到末尾**: Per-row checkboxes (`.tl-checkbox`) select timeline entries; `copySelected()` snapshots the checked rows (reading checkbox indices *before* `syncTimelineFromDOM()` to avoid index drift), `pasteToEnd()` appends deep copies at the end with a time offset. The paste button shows the clipboard count and is disabled when empty.
- **🔄 WebM→MP4 转换**: `convertWebmToMp4()` loads `ffmpeg.wasm` (worker fetched via `toBlobURL` so it works from a `file://` origin), remuxes the last-recorded WebM blob to MP4, and downloads it. Button enabled only after a WebM has been recorded. `ffmpegInst` is assigned only after `load()` succeeds and reset on failure.

**Key functions (v11.2 additions):**
| Function | Purpose |
|---|---|
| `copySelected()` | Reads checked row indices, deep-copies those entries to an in-memory clipboard, updates paste button count/state. |
| `pasteToEnd()` | Appends clipboard entries to the end of `timeline` with a time offset; re-renders. |
| `convertWebmToMp4()` | Lazy-loads ffmpeg.wasm and remuxes the recorded WebM blob to MP4 in-browser. |

---

### chord_hud_v11.3.html
Built on v11.2. A **readability / usability pass**: adds a comprehensive in-app Help guide and reorganizes the editor chrome so new users aren't lost. **No feature logic, export, or save format changed. v11.2 was not modified.**

**Additional features over v11.2:**
- **❓ 帮助 (Help) modal**: New `#help-modal` (reuses the existing `.modal-overlay` / `.modal-box` pattern with a wider scrollable `.modal-help` variant). Seven scannable sections — 快速上手(4-step quick start), 时间轴字段说明, 时间模式, 导入, 导出格式选择, 快捷键, 小贴士 — written in Chinese to match the UI. Opened from a standout teal `❓ 帮助` button in the header.
- **Grouped / labeled toolbar**: The flat 12-button header row is wrapped into labeled clusters (`.tb-group` + `.tb-group-label`) — 播放/导出, 工程, 编辑, 导入和弦 — separated by `.tb-sep` dividers. All existing button `id`s/`onclick`s are untouched, so undo/redo/paste enable-state logic is unaffected.
- **Section hints**: One-line `.section-hint` captions under each left/right panel `<h3>` explaining what the block does.
- **Info tooltips**: `title=` tooltips + small `.info-dot` (ⓘ) affordances on the cryptic per-row controls (承接前, 分组), and clarified tooltips on ★ emphasis, ✕ delete, and 高亮音级.
- **Esc-to-close + first-visit nudge**: The keydown handler now closes any open modal on `Esc` (via `anyModalOpen()`); on first load (no `localStorage['chordhud_help_seen']`) the 帮助 button pulses via a `.nudge` animation until opened once. localStorage wrapped in try/catch for `file://`.

**Key functions (v11.3 additions):**
| Function | Purpose |
|---|---|
| `showHelpModal()` | Shows `#help-modal`, scrolls it to top, clears the nudge, sets the `chordhud_help_seen` flag. |
| `closeHelpModal()` | Hides `#help-modal`. |
| `anyModalOpen()` | Returns true if the help or text-import modal is visible; gates keyboard shortcuts and drives Esc handling. |

**saveProject() version:** 3 (unchanged; v11.3 adds no data fields — older/newer project files interoperate).
