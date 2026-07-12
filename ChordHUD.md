# ChordHUD

A browser-based chord/progression HUD designed for video overlay (1920×1080, black background, Screen blending mode). Each version is a single self-contained HTML file; new features are always built into a **new** file (`chord_hud_vN.html`) — the previous version is never modified.

**Current version: `chord_hud_v17.html`**

All ChordHUD documentation lives in this file (moved out of CLAUDE.md on 2026-07-01). Record all future ChordHUD changes here.

---

## Version history

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

---

### chord_hud_v12.html
Built on v11.3. Adds a rotating vinyl/jacket layer, a redesigned two-row degree display, and a draggable realtime preview panel. **v11.3 was not modified.**

**Session history (2026-07-01):**
- Restored the working folder from `origin/master` (remote had v11.3 merged via PR #1; local tree had deleted the tracked HTML files).
- Moved all ChordHUD documentation from CLAUDE.md into this file.
- Second pass after user feedback: live panel enlarged (720px) + **⧉ pop-out to a real OS window**; defaults changed to bars mode / 175 BPM / C Major / sample 4-chord group with a generated placeholder cover; vinyl redesigned to be cover-dominant.
- Third pass after user feedback: default highlights = root degree only with carry 0/1/2/3; **auto 承接前 for grouped chords**; 高亮音级 editor grid now mirrors the HUD's two-row layout; disc speed synced to BPM (revolutions per bar); cover + new generated background in dark purples (pentagons/glitch/distortion); emphasis pulse minimized. Also fixed a **latent v4–v11.3 bug**: inline `onchange="timeline[i].x=…"` handlers never worked because `document.timeline` (Web Animations API) shadows the global array inside inline-handler scope chains — all silently threw, masked by `syncTimelineFromDOM()`; replaced with `setEntry*()` setter functions.

**Additional features over v11.3:**
- **旋转唱片 (rotating vinyl / jacket layer)**: New left-panel section loads an album-cover image; a 280px disc renders below the degree rows. **Cover-dominant design**: the jacket fills ~78% of the disc (cover-fit, clipped to a circle); vinyl black shows only as an outer ring with grooves, plus spindle hole, rim highlight, and a static sheen (the light source does not rotate with the disc). Speed is BPM-synced (see below; default 1 rev / 2 bars). The DOM preview spins via CSS `@keyframes vinyl-spin`; canvas export rotates deterministically by `elapsed × vinylRPMNow() / 60 × 2π`, so exports are frame-accurate. Nothing is drawn when no jacket is loaded.
- **内置示例封面 (generated placeholder cover)**: `makeSampleCover()` draws an 800×800 canvas — diagonal stripes in dark purple hues + "Album Cover" in big type — and loads it as the default jacket at INIT (regenerated once webfonts load). Generated locally on a canvas (never from a `file://` image) so the export canvas is never tainted. Replaced the moment the user picks a real cover; a standalone copy is saved as `sample_album_cover.jpg` in the repo.
- **内置示例背景 (generated placeholder background)**: `makeSampleBackground()` draws a 1920×1080 dark-purple scene — ~70 filled + 26 outlined pentagons, wavy vertical distortion bands, horizontal glitch slice shifts, RGB-split patches, scanline patches, and a vignette. Seeded PRNG (identical image every launch); auto-loaded as the default background at INIT (clearable with ✕). Standalone copy: `sample_background.jpg`.
- **New defaults (sample project)**: bars mode (小节) is the default timing mode; BPM 175, Key "C Major", 曲名 "Song Name", 编曲 "Composer", 人声 "Vocal", 发布 "0000.00.00", 总时长 6s. Timeline: FMaj7 → Gsus4 → AbDim7(★ emphasis) → Amin7, one bar each, all in group "1" (grouped slash display), each highlighting its **root degree only** (4, 5, b6, 6) with 承接前 = 0/1/2/3. Entry times are recomputed from bar/beat at INIT so they always match the default BPM.
- **承接前自动计算 (auto-carry for groups)**: `recomputeGroupCarries()` sets each grouped entry's carry to the number of consecutive immediately-preceding entries in the same group; runs whenever a group name is edited (`setEntryGroup`), after paste-to-end, and after re-sorting. Ungrouped entries keep their manual carry; manual ± still works on grouped entries until the next group edit.
- **高亮音级 grid mirrors the HUD**: `renderHLGrid()` now lays the 12 cells out exactly like the HUD — a 14-column CSS grid where the 7 diatonic cells span 2 columns each on row 1 and the 5 chromatic cells straddle the gaps on row 2.
- **BPM-synced disc rotation**: the RPM slider is replaced by a 转速 select — 1 revolution per 1/2/4/8 bars, or 静止. `vinylRPMNow()` derives RPM as `bpm / (beatsPerBar × vinylBarsPerRev)`; DOM spin duration re-applied on BPM/time-signature changes; canvas rotation uses the same formula, so exports stay beat-locked.
- **音级双行显示 (stacked degree rows)**: The single 12-box row (72px) is replaced by two stacked rows — the 7 in-key degrees at 96px on top, the 5 chromatic (not-in-key) degrees at 80px below, each centered in the gap between its diatonic neighbours (piano black-key layout, inverted). Fonts enlarged (degree label 15/13px, note name 26/21px). A shared `DEG_LAYOUT` table drives both the DOM (`#degree-rows`, absolutely positioned boxes) and the canvas renderer, so preview and export match exactly.
- **🖥 实时预览 (realtime preview panel)**: Floating, draggable (by its header), horizontally resizable panel (default 720px wide) containing a 1920×1080 canvas (CSS-scaled) rendered by `drawCanvas()` — the exact export renderer, so it is WYSIWYG. A scrub slider (0.01s steps) jumps to any time; ▶ plays from the scrub position with background audio/video; every edit anywhere in the editor re-renders the panel on the next animation frame (capture-phase `input`/`change`/`click` delegation on `#editor`, so the render happens after inline handlers mutate state). Panel visibility persists in `localStorage['chordhud_live_panel']`; toggled from the toolbar button or the panel's ✕.
- **⧉ 弹出 (pop-out preview window)**: `popOutLive()` opens a real OS window — draggable outside the browser, onto another monitor — that mirrors `#live-canvas` via `captureStream(30)` into a `<video>`. The popup has its own ▶ button and scrub slider wired back to the opener's `toggleLivePlay()` / `onLiveScrub()`; `renderLive()` mirrors scrub position, time, and current chord into it. The in-page panel hides while popped out and is restored when the window closes (500ms watcher).
- **Emphasis pulse export fix + minimized**: `drawCanvas` computed the red emphasis pulse as `sin((elapsed/1000)·…)` — but `elapsed` is already in seconds, so exported emphasis chords never visibly pulsed (period ≈ 25 minutes). Now `sin(elapsed·π·2/1.5)`, matching the DOM's 1.5s CSS animation. Per user feedback the pulse is also much subtler: CSS glow reduced from up-to-200px multi-layer shadows to 16–44px, canvas `shadowBlur` from `30+130·pulse` to `16+14·pulse`, and the color swing narrowed.

**Key implementation notes:**
- `readTimelineForDisplay()` is a **non-mutating** variant of `syncTimelineFromDOM()`: it overlays current DOM input values onto a sorted deep copy. The live panel renders from this copy by temporarily swapping the global `timeline` reference around the synchronous `drawCanvas()` call, so editor state (row order, unsaved inputs, undo history) is never disturbed by live rendering.
- `stopLivePlay()` is called at the top of `previewHUD()`, `startExport()`, and `startExportMp4()` so live playback never fights the fullscreen preview or export for the shared `<audio>`/`<video>` elements.

**Key functions (v12 additions):**
| Function | Purpose |
|---|---|
| `DEG_LAYOUT` (const) | Precomputed box layout: 7 diatonic (96px, y=0) + 5 chromatic (80px, y=110, gap-centered). Drives DOM + canvas. |
| `drawVinyl(ctx,cx,cy,elapsed)` | Draws glow, disc gradient, grooves, cover-fit jacket label, spindle hole, rim, static sheen; rotation from elapsed·RPM. |
| `loadJacket(input)` / `clearJacket()` | Loads/clears the jacket image; toggles `#vinyl-wrap` visibility and the clear button. |
| `setVinylRPM(v)` / `applyVinylSpin()` | Sets RPM, syncs slider + label, updates the CSS spin duration (`none` at 0 RPM). |
| `readTimelineForDisplay()` | Non-mutating DOM→timeline overlay onto a sorted deep copy, for live rendering. |
| `renderLive()` | Renders `drawCanvas()` into `#live-canvas` at `liveScrubT` using the copy; updates scrub max, time and chord labels. |
| `scheduleLive()` | rAF-debounced `renderLive()`; safe to call from anywhere, deduplicates per frame. |
| `onLiveScrub(v)` | Scrub handler: seeks bg-video (throttled while paused), resyncs `liveT0` + audio/video during playback. |
| `startLivePlay()` / `stopLivePlay()` / `toggleLivePlay()` | RAF playback loop from the scrub position with audio/video; auto-stops at total duration. |
| `toggleLivePanel()` | Shows/hides the panel; persists the choice to localStorage; focuses the popup if one is open. |
| `popOutLive()` / `isLiveWinOpen()` | Opens the pop-out OS window (canvas `captureStream` → `<video>`), hides the in-page panel, restores it on close. |
| `syncPopoutPlayBtn()` | Mirrors the ▶/⏸ state into the popup on play/stop. |
| `makeSampleCover()` / `loadSampleCover()` | Generates the striped "Album Cover" placeholder on a canvas and installs it as the default jacket (`jacketIsSample` flag). |
| `makeSampleBackground()` / `loadSampleBackground()` | Generates the pentagon/glitch dark-purple background (seeded PRNG) and installs it as the default background. |
| `setEntry{Time,Bar,Beat,Chord,Group,Annotation}(i,v)` | Per-row field setters used by the timeline inputs (fixes the `document.timeline` shadowing bug that broke all inline `timeline[i].x=` handlers since v4). |
| `recomputeGroupCarries()` | Auto-sets carry for every grouped entry = count of consecutive preceding same-group entries; updates carry displays in place. |
| `vinylRPMNow()` / `setVinylSpeed(v)` | Disc RPM derived from BPM: `bpm / (beatsPerBar × vinylBarsPerRev)`; select offers 1/2/4/8 bars per revolution or static. |

**saveProject() version:** 4 (adds `vinylBarsPerRev`; the jacket/background images themselves are not persisted — same policy as background media and audio; v3 and older project files load fine).

---

### chord_hud_v12.1.html
Built on v12. An **export-correctness release**: fixes the silently-broken MP4 export (broken since v10), muxes background audio into the MP4, and removes the ffmpeg.wasm converter. **v12 was not modified.**

**Session history (2026-07-02):**
- **Root cause of the MP4 failure (v10–v12)**: the inlined mp4-muxer requires an explicit `fastStart` option; `new Muxer(...)` in `startExportMp4()` never passed one and threw `'fastStart' option must be false, 'in-memory', 'fragmented' or an object`. The throw happened inside an async function *before* any try/catch or UI change, so it became an unhandled promise rejection — the button appeared to do nothing. All the v11.1 codec-fallback work was fixing the wrong layer.
- The 🔄 WebM→MP4 converter was separately broken: it fetched `@ffmpeg/core-st@0.12.6`, a package that does not exist on jsDelivr (404), and `@ffmpeg/ffmpeg@0.12.6` builds its main worker from the CDN URL internally (the `workerURL` load option only overrides the *core* worker), which a `file://` page cannot do (`cannot be accessed from origin 'null'`). Even fully working, its `-c copy` remux would emit VP9-in-MP4, which DaVinci rejects just like WebM — only a transcode helps (that is why cloudconvert worked).
- Verified in headless Chromium **and real Edge**: 6s 1080p60 H.264 exports in ~4s (faster than realtime, unlike the WebM path), valid `ftyp isom/avc1` container, plays end-to-end; with a loaded 背景音频 the MP4 contains an audible AAC track (`webkitAudioDecodedByteCount` > 0 during playback). Deliberate-failure test confirms errors now alert + show in the status strip with the editor restored.

**Changes from v12:**
- **⬇ MP4 修复**: `fastStart: 'in-memory'` added to the Muxer options (correct mode for `ArrayBufferTarget`); the whole of `startExportMp4()` is wrapped in try/catch/finally — any failure alerts, shows in `#export-status`, and always restores the editor UI and closes the encoder.
- **MP4 含音频**: `loadAudio()` stashes the picked `File` in `hudAudioFile`; export decodes it via `AudioContext.decodeAudioData`, AAC-encodes with `AudioEncoder` (`mp4a.40.2`, 192 kbps, ≤2 ch, 1-second planar `AudioData` slices), and muxes it as an MP4 audio track trimmed to the export duration. Falls back to video-only with a visible note when AAC encoding is unsupported.
- **🔄 WebM→MP4 removed**: button, `convertWebmToMp4()`, and the `ffmpegInst`/`lastWebmBlob` state deleted; help bullet dropped (see root-cause notes above for why it could never work).
- **Export hygiene**: shared `EXPORT_W/H/FPS/BITRATE` constants used by both exporters; `exportStatusShow()/exportStatusHide()` helpers are the single write path for `#export-status` (it contains the `#export-timer` span — the old converter's `textContent` writes destroyed it); `URL.revokeObjectURL()` after WebM/MP4 downloads; the pointless keep-alive `setInterval` removed.
- **Help ⑤ rewritten**: MP4 = recommended, notes audio inclusion and faster-than-realtime export; converter bullet removed.
- **Inline-handler audit**: all generated row handlers already route through `setEntry*()`/named functions (v12's `document.timeline` fix); no bare `timeline[...]` references remain in HTML attributes or generated markup.

**Key functions (v12.1 additions/changes):**
| Function | Purpose |
|---|---|
| `exportStatusShow(html)` / `exportStatusHide()` | Single write path for `#export-status`; each export re-creates its own `#export-timer` span. |
| `startExportMp4()` | Rewritten: fastStart fix, full-body error guard, optional AAC audio track, try/finally UI restore. |
| `loadAudio(input)` / `clearAudio()` | Also set / clear `hudAudioFile` so the MP4 exporter can encode the audio offline. |

**saveProject() version:** 4 (unchanged — v12 project files interoperate).

---

### chord_hud_v13.html
Built on v12.1. A **UI redesign of the editor**, imported from **Claude Design** (project "ChordHUD editor UI redesign", the **"编辑部 · 静 / Editorial-calm"** direction, option `1c` in `Editor Redesign Explorations.dc.html`). Reorganizes the editor into two pages with a row-detail editing model. **The HUD output renderer, export, MIDI/paste import, undo/redo, and save format are all unchanged. v12.1 was not modified.**

**Session history (2026-07-09):**
- Imported the Claude Design exploration doc via the design MCP (`DesignSync.get_file`), chose direction **1c**, and implemented it — fixing the doc's minor inconsistencies (a duplicated 应用基本信息 button, a malformed 发布时间 field) and wiring every Claude Design `{{ noop }}` placeholder to the real `onclick` / id handlers.
- Layout refined after user feedback: the live preview is a full-height right column (was pushed down under the header/song-info); the 时间模式 button label shortened to 秒数模式 / 小节模式 and the 曲名 label simplified.
- Second feedback pass: **responsive layout** (header wraps, the preview column narrows at breakpoints, Design cards collapse to one column) so high browser-zoom / narrow windows no longer cram or overflow; the default **white scrollbars replaced with thin, theme-matched** ones (scroll preserved); header tightened (icon-only 🖥 live toggle, ⬇ MP4) to stay one line; docked-preview controls shrink instead of overflowing.
- Added **实时预览快捷键**: 空格 播放/暂停；← / → 定位前后 5 秒，Shift ±25 秒，Ctrl ±2 秒 (handled in the global keydown listener, skipped while typing in a text field; documented in the ❓ 帮助 快捷键 section and the scrub/play tooltips).
- The **Design page was not part of the exploration doc** (it only covered the Input page); it was built to match the chosen direction, reusing the existing media/notes/position controls and their ids.

**Additional features / changes over v12.1:**
- **两页信息架构 (two-page IA)**: a top pill switch splits the editor into **输入** (song info + chord timeline + import + project/undo) and **设计** (background audio / image·video / vinyl cover / note names / vertical position). New `switchPage('input'|'design')`.
- **歌曲信息头 (inline song header)**: BPM / Key / 拍号 / 时间模式 / 曲名 / 编曲 / 人声 / 发布 are inline-editable fields in the Input-page header (ids unchanged: `in-bpm`, `in-key`, `in-title`, …); `应用基本信息` still calls `applyStatic()`.
- **精简时间轴行 + 行详情 (summary rows + row-detail editor)**: `#timeline-list` now renders compact summary rows (小节·拍 / 秒 · chord · active-degree chips · 承 carry chip · group tag · 备选 flag · ★). Full editing moved to a persistent **行详情** panel on the right that edits the selected row (`selIdx`). New: `renderRows()`, `renderDetail()`, `renderDetailGrid()`, `selectRow(i)`, and detail handlers `detChord / detGroup / detAnnot / detTimeEdit / detToggleDeg / detCarry / detEmph / detPickAlt / detDelete`. `renderList()` = `renderRows()` + `renderDetail()` + `scheduleLive()`, so every existing caller keeps working.
- **停靠式实时预览 (docked live preview)**: the v12 floating preview panel (`#live-panel`, all child ids preserved) is docked at the top of a **full-height right-hand column** that is visible on **both** the 输入 and 设计 pages (so background/cover/position edits preview live); the header actions and song-info sit in the left column beside it. The ⧉ pop-out window and scrub/play controls still work. The 行详情 detail editor sits below the preview and is hidden on the 设计 page.
- **Sync model change**: `syncTimelineFromDOM()` and `readTimelineForDisplay()` now flush / overlay the single detail panel for `selIdx` (edits already commit to `timeline[]` through the detail handlers), instead of iterating per-row inputs. `refreshAllHLGrids()` now refreshes summary rows + the detail grid + the HUD.
- **多选复制保留 (copy-select preserved)**: each summary row keeps a subtle `.tl-checkbox` (`data-idx`) so `复制所选 / 粘贴到末尾` still works; clicking the checkbox no longer selects the row.

**Key functions (v13 additions):**
| Function | Purpose |
|---|---|
| `switchPage(p)` | Toggles the 输入 / 设计 pages and the header pill. |
| `renderRows()` | Builds the compact summary rows in `#timeline-list` and marks `selIdx` / the live-scrub 播放 row. |
| `renderDetail()` / `renderDetailGrid()` | Builds the 行详情 editor (and its two-row degree grid) for `timeline[selIdx]`. |
| `selectRow(i)` | Selects a row for the detail panel. |
| `detChord/detGroup/detAnnot/detTimeEdit/detToggleDeg/detCarry/detEmph/detPickAlt/detDelete` | Detail-panel edit handlers; operate on `selIdx`, keep `timeline[]` authoritative, re-render rows + HUD + live. |
| `degChipsHtml(item)` / `esc(s)` | Summary-chip markup helper; HTML/attribute escaper. |

**Preserved contract:** every element id, input id, and inline handler name from v12.1 is unchanged; the HUD output (`drawCanvas`, `drawVinyl`, `DEG_LAYOUT`, `renderHUDDegrees`, WebM/MP4 export) is byte-for-byte identical. Single self-contained `file://` HTML, no new external dependencies.

**saveProject() version:** 4 (unchanged; v12 project files interoperate).

---

### chord_hud_v14.html
Built on v13. Adds a **中文 / English UI language toggle**. **The rendered HUD output is unchanged** — including the on-screen `编曲：/ 人声：/ 发布：` meta labels, which are deliberately left as-is so exported videos are unaffected. v13 was not modified.

**Session (2026-07-09):**
- New **EN / 中文 toggle** button in the header (`toggleLang()`); the choice persists in `localStorage['chordhud_lang']` and defaults to **中文** (English is opt-in, restored at INIT).
- i18n mechanism (no per-element markup surgery): a compact `I18N_PAIRS` dictionary drives a **text-node walk** in `setLang()` that swaps every static label / button / hint / tooltip / `<select>` option across the header, song-info, timeline tools, Design page, live-panel and the paste-import modal. `tr(zh, en)` handles all **JS-generated** text — summary rows (组 / 承 / 备选), the 行详情 detail editor, the timing / paste buttons, `alert()`s, MIDI and export-status messages. Rich blocks (`#d-intro`, the paste note) swap via `innerHTML` (`I18N_RICH`); the **Help modal** toggles between a Chinese `#help-zh` and a fully-translated English `#help-en`.
- All element ids / handlers preserved. Verified a clean **en ↔ zh round-trip** across every panel and both modals with no console errors; the realtime-preview keyboard shortcuts still work.

**Key functions (v14 additions):**
| Function | Purpose |
|---|---|
| `setLang(lang)` | Switches the whole editor to `'zh'` / `'en'`: text-node walk + attribute/rich swaps + Help dual-div toggle, then re-renders dynamic content and persists the choice. |
| `toggleLang()` | Flips between 中文 and English (the header EN / 中文 button). |
| `tr(zh, en)` | Returns the string for the current `LANG`; used by all JS-generated UI text. |
| `applyTimingBtnText()` / `applyPasteBtnText()` | Re-apply the JS-set timing-mode and paste-button labels in the current language. |

**Data:** `I18N_PAIRS` (static zh↔en pairs), `I18N_RICH` (innerHTML blocks).

**saveProject() version:** 4 (unchanged; UI language is a local preference, not stored in the project file).

---

### chord_hud_v15.html
Built on v14. Adds a **Key quick-select** to the 音名 / Note-names section: pick a major or minor key and the 12 note-name cells auto-fill with correct, traditionally-spelled note names — no more hand-typing. v14 was not modified.

**Session (2026-07-09):**
- New `<select id="key-select">` in the note-names card (Design page): grouped **Major** (C, Db, D, Eb, E, F, F#, Gb, G, Ab, A, Bb, B) and **Minor** (Cm…Bm), plus a 自定义 / Custom entry. `applyKeyPreset('root|mode')` fills `globalNotes`, syncs the ♭ / ♯ degree labels to the key's direction, and reflects the key on the HUD (sets the KEY field + `applyStatic()`). Editing any note cell resets the selector to Custom.
- **Spelling engine** `keyNotes(root, mode)` (verified in Node across all 25 keys — no double accidentals):
  - **Diatonic 7 notes** spelled from the key signature — one letter per degree, accidental computed — so flat keys keep proper spelling (**F major → Bb**, not A#; Gb major legitimately → Cb) and no key is mis-named (**Bb major uses Bb/Eb**, never "A# major").
  - **Chromatic 5 notes** take the minimal accidental: natural where the pitch is a white key (so F major's tritone reads **B**, not Cb), otherwise a single sharp/flat leaning the key's flat/sharp side. Minor keys raise the 6th/7th (A minor → **F# / G#**); leading tones use a clean natural rather than B#/F##.
- The label is bilingual (i18n `调（快速填充音名）` / "Key (quick-fill notes)"); options are language-neutral. All element ids / handlers preserved; the HUD output renderer is unchanged.

**Key functions (v15 additions):** `keyNotes(root, mode)`, `applyKeyPreset(val)`, `_accStr(letter, pc)`; data `_KEY_SHARPS`, `_NOTE_PC`, `_SHARP_PC` / `_FLAT_PC`.

**saveProject() version:** 4 (unchanged).

---

### chord_hud_v16.html
Built on v15. **UI polish of the note-names / key section**: the note-name editor now uses the same two-row piano layout as 高亮音级 (7 in-key on top, 5 chromatic in the gaps below), and the outdated native `<select>` key dropdown is replaced by a themed picker. v15 was not modified.

**Session (2026-07-09):**
- **Two-row note editor** — `renderNoteGrid()` now lays the 12 editable cells out like the HUD / 高亮音级 grid: a 14-column grid with the 7 diatonic degrees spanning 2 columns on row 1 and the 5 chromatic degrees straddling the gaps on row 2 (diatonic cells purple, chromatic amber).
- **Themed key picker** (replaces the native dropdown that rendered as an OS-styled list): a **大调 / 小调** (Major / Minor) segmented toggle + a 7-column grid of key buttons. The active key is highlighted; editing any note cell clears it to Custom. New: globals `keyMode` / `activeKey` / `KEY_ROOTS`; functions `setKeyMode()`, `renderKeyBtns()`, `onNoteEdit()`. `applyKeyPreset()` and the v15 spelling engine are unchanged. The mode-toggle labels are bilingual (i18n `大调`/`小调` ↔ Major/Minor).
- All element ids / handlers preserved; the note spelling and HUD output are unchanged.

**Key functions (v16 additions):** `setKeyMode(m)`, `renderKeyBtns()`, `onNoteEdit()` (+ rewritten `renderNoteGrid()`).

**saveProject() version:** 4 (unchanged).

---

### chord_hud_v17.html
Built on v16. Adds a **数拍子 (beat-counter) HUD element** and support for **mid-song time-signature changes (拍号变化 / meter map)**. v16 was not modified.

**Session (2026-07-12):**
- **数拍子 beat counter (new HUD element)**: a metronome-style row of beat pips at the **top centre** of the HUD, drawn by `drawBeatCounter(ctx, elapsed)` inside `drawCanvas` — so preview, the docked/pop-out live panel, and both WebM/MP4 exports all show it identically. The current beat is enlarged and **pulses on each onset** (`pulse = (1 − beatPhase·1.8)^1.5`); **beat 1 (the downbeat) is amber** so bar boundaries read at a glance; past beats in the bar are dimly filled, upcoming beats outlined. A label line below reads `N/4 · 小节 <bar> · 第 <beat> 拍` (bilingual). Toggle with the **显示数拍子** checkbox on the Design page (`beatCounterOn`, default on). All light-on-black so it survives the Screen-blend export.
- **拍号变化 meter map (mid-song time-signature changes)**: `meterMap = [{startBar, beatsPerBar}, …]` — a sorted list of meter segments; the first always starts at bar 1 (the opening metre, mirrored into the global `beatsPerBar`). `barBeatToSeconds` / `secondsToBarBeat` are now **meter-map aware** (they walk the segments), so a song that switches e.g. 4/4 → 3/4 from bar 9 converts bar·beat ↔ seconds correctly. **Backward compatible**: with a single default segment the math is byte-identical to v16, and old project files (no `meterMap`) fall back to one segment built from `beatsPerBar`. BPM is still a single global (beat duration = 60/BPM); only the beat grouping changes per segment.
- **Meter-change editor** (Design page card "数拍子 / 拍号变化"): a checkbox to show/hide the beat counter, plus a list of segments — each row is "从第 N 小节起 · 每小节 X 拍" with a ✕ delete (the opening bar-1 row is fixed and set by the header 拍号 buttons). `＋ 添加拍号变化` appends a segment. Editing any segment recomputes all timeline entry times (in bars mode), refreshes the disc speed, the row list and the live preview.
- The header **拍号 buttons** (2/4–7/4) now set the **opening** segment (`meterMap[0]`); `setTimeSig`, `toggleTimingMode`, and `loadProject` keep `meterMap[0].beatsPerBar` in sync with the global `beatsPerBar`. Meter edits are **not** part of the timeline undo stack (undo is timeline-only, unchanged).
- i18n: new static strings added to `I18N_PAIRS`; `renderMeterList()` uses `tr()` and is re-run by `setLang()`; the beat-counter label reads `LANG` live. Help sections ③ (zh + en) document the feature.

**Key functions (v17 additions):**
| Function | Purpose |
|---|---|
| `beatStateAt(t)` | Returns `{bar, beatIndex, beatPhase, beatsPerBar}` at time `t`, walking `meterMap`. Drives the beat counter. |
| `drawBeatCounter(ctx, elapsed)` | Renders the top-centre beat-pip row + label; no-op when `beatCounterOn` is false. |
| `beatsBeforeBar(bar)` / `meterAtBar(bar)` | Meter-map helpers: total beats before a bar's downbeat / beats-per-bar in effect at a bar. |
| `sortMeterMap()` | Normalises `meterMap` (sort, guarantee bar-1 segment, dedupe, mirror opening metre into `beatsPerBar`). |
| `renderMeterList()` | Builds the meter-change editor rows. |
| `addMeterChange()` / `removeMeterChange(i)` / `setMeterBar(i,v)` / `setMeterBpb(i,v)` | Editor handlers; each ends in `commitMeter()`. |
| `commitMeter()` | Re-sorts, recomputes entry times (bars mode), re-syncs 拍号 buttons/disc/row list/live. |
| `toggleBeatCounter(on)` | Shows/hides the beat counter. |
| `barBeatToSeconds` / `secondsToBarBeat` | Rewritten to be meter-map aware (single-segment behaviour identical to v16). |

**saveProject() version:** 4 (unchanged; adds `meterMap` + `beatCounterOn` additively — v16 and older project files load fine, and v17 files load in older versions ignoring the new fields).
