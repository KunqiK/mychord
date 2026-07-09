# How to Use Claude Design — a practical tutorial

A step-by-step guide for redesigning the ChordHUD editor with **Claude Design**. Pair this with **`CLAUDE_DESIGN_BRIEF.md`** (the prompt + assets).

---

## What Claude Design is

Claude Design is an Anthropic Labs tool (launched **April 17, 2026**, powered by Claude Opus 4.7) for producing polished visual work — UI mockups, prototypes, landing pages, slides, one-pagers — by working conversationally with Claude. It can **read your codebase or a Figma file to extract your design system**, let you refine with inline comments / direct edits / adjustment sliders, and **hand a design off to Claude Code** for implementation.

## Access (check this first)

- Available on **Claude Pro, Max, Team, and Enterprise** plans (currently a **research preview**). Not on the Free tier.
- Open it at **`claude.ai/design`**, or click the **palette icon** in the left sidebar on claude.ai.
- On **Enterprise**, an admin must enable it in Organization settings first.
- Usage is included with your plan (with extra usage available beyond limits).

> **No access?** The same brief works with **Claude.ai Artifacts** or directly with **Claude Code** — you lose the design-specific refinement UI but keep the core capability. See "Fallback" at the end.

---

## Step by step

### 1. Prepare (2 min)
Have ready: the **prompt** (§1 of the brief) and the **assets** (§2) — `chord_hud_v12.1.html` and 3–5 screenshots. Decide your **art direction** (default A — see §6 of the brief).

### 2. Start a project
Go to `claude.ai/design` → **new project** → paste the prompt from the brief.

### 3. Give it your existing design to learn from
This is what makes the result *yours* instead of generic:
- **Upload `chord_hud_v12.1.html`** (or connect the GitHub repo `KunqiK/mychord` and point at it). Claude Design extracts your colors, type, and components from it.
- **Attach the screenshots** so it sees the live layout and the fixed overlay it must not restyle.
- Optionally use the **web-capture** tool on anything you like the look of for reference.

### 4. Get the plan before the pixels
Ask it to **propose the information architecture first** — how it will split **Input** vs **Design** (tabs? a segmented switch?) and what lives where — plus a moodboard/direction. Approve or steer before it generates full screens. This avoids a beautiful design built on the wrong structure.

### 5. Generate, then refine
When it produces screens, refine with any of Claude Design's four tools:
- **Chat** — "make the timeline row 20% shorter and move the ★ next to the chord name."
- **Inline comments** — click an element, leave a note pinned to it.
- **Direct edits** — click text to edit it in place.
- **Adjustment sliders** — Claude-generated knobs for spacing / color / layout; nudge live, then ask it to **apply the change across the whole design**.

### 6. Explore variations
Ask for **2–3 directions** of the hardest components — the **timeline row** and the **Design page** — side by side, then pick and merge. Exploring alternatives is where this tool shines.

### 7. Export / hand off
When happy, export as any of: **standalone HTML**, **PDF / PPTX** (for review/sharing), **Canva**, an **internal URL**, a **ZIP/folder**, or the **"hand off to Claude Code"** bundle. For ChordHUD, use **standalone HTML + the Claude Code handoff** — then have Claude Code implement the skin into a **new `chord_hud_v13.html`** (never edit the previous version), preserving every id/handler, and log it in `ChordHUD.md`.

---

## Prompting tips (for good results)

- **Be specific about audience, purpose, and style.** "Pro-creator tool for music-theory YouTubers; dense but calm; dark; keep the purple." Beats "make it nicer."
- **Feed it the real file.** With `chord_hud_v12.1.html` attached it reuses your actual tokens instead of inventing a palette.
- **Name the states.** Explicitly ask for default / active / selected / emphasized on the timeline row, and loaded/empty on file pickers — otherwise you get one state.
- **Guard the output every iteration.** Keep repeating that the rendered 1920×1080 overlay is off-limits; it's tempting for the model to "improve" it.
- **Lead with the preservation rule.** The "keep all ids and handler names" constraint is what makes implementation painless later — keep it visible.
- **Use knobs for taste, chat for structure.** Fine-tune spacing/color with sliders; make layout/IA changes in chat.

## Watch-outs

- **It designs; it doesn't run your JS.** You still need Claude Code (or a hand edit) to wire the new look back into the working tool.
- **Research-preview limits.** Expect usage caps and occasional rough edges.
- **Verify parity after re-skinning.** Confirm the exported overlay frame is identical to v12.1's and that Preview / Export / Save-Load / Undo-Redo / MIDI-import all still fire.

## Fallback without Claude Design access

Paste the **same prompt** into **Claude Code** in this repo (attach nothing — it can read the file directly) and ask it to redesign the editor chrome into `chord_hud_v13.html` under the same constraints, or into **Claude.ai** as an **Artifact** for a visual mockup first. You keep 90% of the value.

---

### Sources
- [Introducing Claude Design — Anthropic](https://www.anthropic.com/news/claude-design-anthropic-labs)
- [Claude Design guide — buildfastwithai](https://www.buildfastwithai.com/blogs/claude-design-anthropic-guide-2026)
- [Claude Design 2026 guide — agence-scroll](https://agence-scroll.com/en/blog/claude-design-anthropic-2026-guide)
