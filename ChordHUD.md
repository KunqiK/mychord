# ChordHUD

A browser-based chord/progression HUD designed for video overlay (1920×1080, black background, Screen blending mode). Each version is a single self-contained HTML file; new features are always built into a **new** file (`chord_hud_vN.html`) — the previous version is never modified.

**Current version: `chord_hud_v12.1.html`**

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
