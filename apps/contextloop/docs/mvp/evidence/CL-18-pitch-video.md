# CL-18 evidence — Narrated pitch video on the architecture page

**Date:** 11 Nov 2026 · **Rendered with:** `python scripts/render_pitch_video.py` (macOS voice *Samantha*, rate 172; no recorded takes yet)

## Output

| File | Check |
|---|---|
| `contextloop/ui/assets/video/contextloop-pitch.mp4` | 1920 × 1080, H.264 High, 30 fps, CRF 16; AAC 48 kHz; 5:03; 69 MB; `+faststart` |
| `contextloop/ui/assets/video/contextloop-pitch.vtt` | WebVTT captions, one or more cues per beat, timed from the measured audio |
| `contextloop/ui/assets/video/contextloop-pitch-poster.jpg` | Cover frame (frame 0 is the same title card, so the player's thumbnail is never black) |

Audio loudness (ffmpeg `loudnorm` summary): integrated **−16.0 LUFS**, true peak **−1.5 dBTP**.

## Structure (37 beats, 6 scenes)

1. Open: title card and agenda.
2. The problem: Northstar's four systems, then the COO's question and what a correct answer needs.
3. The confident wrong answer: real naive-agent answers from the recordings (11 accounts vs 9; 87.0% vs 86.1%; 26 vs 25), traps T1–T4 and T6, and the **2.7 / 6** average.
4. The solution: four layers, and 2.7 vs **6.0** of 6.
5. The architecture: the real `architecture/index.html` in an iframe, driven through `window.__arch` (new hooks `flowStep`, `setView`, `showCard`): the whole loop, Acts 1–5 with a camera that frames the active nodes and a detail card for a key node in each act, all eight request-flow steps, then the "At a customer" view.
6. Close: takeaways, next step (scoped pilot), disclaimer that the data is synthetic.

## Acceptance criteria

- [x] `make pitch-video` renders the MP4, captions and poster (above).
- [x] Covers the problem, the solution, every act, the request flow and the customer view; each cue is placed at a fraction of its own beat, so highlights follow the narration (checked on stills from the encoded file at 0 s, 150 s, 160 s, 205 s and 235 s).
- [x] Numbers come from the repository; `tests/test_ui.py::test_pitch_script_drives_the_real_architecture_page` checks the scores against `reports/latest.json` and every cue against the architecture page's nodes, acts and flow steps.
- [x] The Architecture page shows the video with English captions above the interactive diagram (AppTest: one video element, no exception) and falls back to a hint when the video hasn't been built.
- [x] Recorded takes in `recordings/voiceover/<beat id>.wav|m4a` replace the synthetic voice, and the timeline is rebuilt from their measured length.

## Notes

- Frames are captured deterministically: every visual on the stage is a function of time, and CSS transitions (including inside the architecture page) are paused and stepped through the Web Animations API, so no frame is dropped or rushed. About 8 minutes to render on an M-series Mac.
- The default macOS voice is serviceable; a Premium voice, or the presenter's own takes, is recommended before sending the video to a customer.
