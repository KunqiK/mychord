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

### ChordHUD
A browser-based chord/progression HUD designed for video overlay (1920×1080, black background, Screen blending mode). Latest version: **`chord_hud_v17.3.html`**.

Full documentation — version history (v4 → v12), features, and key-function reference — lives in **[ChordHUD.md](ChordHUD.md)**. Record all ChordHUD changes there, not here.
