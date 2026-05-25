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

**Key functions:**
| Function | Purpose |
|---|---|
| `syncTimelineFromDOM()` | Reads DOM inputs → updates `timeline[]` → sorts. Called before preview/export. |
| `getCurrentIdx(t)` | Returns the index of the active chord at time `t` (scans all entries, no early break). |
| `previewHUD()` | Hides editor, runs RAF animation loop with accurate elapsed-time tracking. |
| `startExport()` | Records a WebM via `MediaRecorder` + canvas at 60 fps. |
| `applyFrame(idx)` | Updates chord name, degree row, and active row highlight. |
