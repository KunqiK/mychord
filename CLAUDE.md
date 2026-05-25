# ClaudeCodesTesting

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
