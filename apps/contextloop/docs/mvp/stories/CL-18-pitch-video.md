# CL-18 — Narrated pitch video on the architecture page

**Phase:** 4 · Experience  
**Type:** UI, video and documentation  
**Priority:** P1  
**Estimate:** 4–6 hours  
**Story points:** 5  
**Target day:** Wed 11 Nov

## User story

As the presenter, I want a short, narrated 16:9 video that briefs a customer on ContextLoop (the problem, the solution, then a walk through each phase of the architecture diagram), playable from the app's Architecture page, so that the pitch can be sent ahead of a meeting or played when no presenter is free.

## Scope

- A scripted pitch in beats (`contextloop/ui/pitch/script.json`): opening, the problem (Northstar's four systems and the COO's question), the confident wrong answer, the solution in four layers, a walk through the real architecture diagram (the whole loop, Acts 1 to 5, the eight-step request flow, and the customer view), and the close.
- A pitch stage (`contextloop/ui/pitch/pitch.html`) at 1920 × 1080 whose every visual is a function of time. The architecture walkthrough drives the real architecture page in an iframe, so the video always matches the diagram.
- A renderer (`scripts/render_pitch_video.py`, `make pitch-video`) that:
  - voices each beat (a recorded take from `recordings/voiceover/<beat>.wav` when present, otherwise the best macOS voice installed);
  - captures every frame deterministically (CSS transitions are stepped through the Web Animations API, so nothing is dropped or rushed);
  - encodes H.264 High at 1080p 30 fps, CRF 16, with AAC audio, plus WebVTT captions and a poster frame.
- The Architecture page plays the video (16:9, with captions) above the interactive diagram.

**Out of scope:** filming a presenter on camera; background music (optional `--music` flag only).

## Acceptance criteria

- [ ] `make pitch-video` renders `contextloop/ui/assets/video/contextloop-pitch.mp4` (1920 × 1080, H.264, AAC), `.vtt` captions and a poster frame.
- [ ] The video covers the problem, the solution, every act on the diagram, the request flow and the customer view, with each highlight in step with its narration.
- [ ] Every number in the narration comes from the repository (the evaluation report or the narrative).
- [ ] The Architecture page shows the video with captions; the page still renders when the video hasn't been built yet.
- [ ] Dropping in a recorded take for a beat replaces the synthetic voice, and the timing follows the new take.

## Dependencies and deliverables

**Dependencies:** CL-13 (architecture page), CL-11 (evaluation report).
