# mychord (formerly ClaudeCodesTesting)

A workspace for projects built and refined with Claude Code.

## Workflow rules
- **Always commit with a clean message before starting new changes.**
- Push to GitHub after every meaningful change session.

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
