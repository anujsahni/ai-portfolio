// ContextLoop pitch stage. Everything on screen is a function of time t (seconds): window.__render(t).
// scripts/render_pitch_video.py calls __init(durations) with the measured length of each voiced beat, then renders frame by frame.
// CSS transitions (inside the architecture page too) are stepped through the Web Animations API, so frames are deterministic.
(function () {
  const T = { lead: 0.9, firstLead: 1.4, gap: 0.42, tail: 0.8, xfade: 0.7, endHold: 1.2 };
  const ease = (x) => (x <= 0 ? 0 : x >= 1 ? 1 : 1 - Math.pow(1 - x, 3));
  const easeIO = (x) => (x <= 0 ? 0 : x >= 1 ? 1 : x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2);
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];

  let TL = null;            // timeline: { total, scenes, beats, cues }
  let arch = null, adoc = null, archH = 0;
  const seen = new WeakMap();
  const S = { key: "", cap: "", capT: -9, cam: null, camFrom: null, camTo: null, camT0: 0, label: "", labelT: -9 };

  // ---- timeline -------------------------------------------------------------------------------------------------------
  function build(script, durations) {
    let t = 0;
    const scenes = [], beats = {}, cues = [];
    script.scenes.forEach((sc, i) => {
      const start = t;
      t += i === 0 ? T.firstLead : T.lead;
      sc.beats.forEach((b, j) => {
        const dur = durations[b.id] ?? Math.max(1.6, b.text.split(/\s+/).length / 2.6);
        beats[b.id] = { start: t, dur, scene: sc.id, text: b.text };
        (b.cues || []).forEach((c) => cues.push({ ...c, t: t + (c.at || 0) * dur }));
        t += dur + (b.pause_after || 0) + (j < sc.beats.length - 1 ? T.gap : 0);
      });
      t += i === script.scenes.length - 1 ? T.endHold : T.tail;
      scenes.push({ id: sc.id, chapter: sc.chapter, start, end: t });
    });
    cues.sort((a, b) => a.t - b.t);
    return { total: t, scenes, beats, cues };
  }

  // ---- architecture iframe --------------------------------------------------------------------------------------------
  function archReady() {
    return new Promise((resolve) => {
      const f = $("#arch");
      const check = () => {
        try {
          if (f.contentWindow.__arch && f.contentDocument.querySelector(".node")) return resolve();
        } catch (e) { /* not loaded yet */ }
        setTimeout(check, 50);
      };
      check();
    });
  }

  function setupArch() {
    const f = $("#arch");
    adoc = f.contentDocument; arch = f.contentWindow.__arch;
    adoc.documentElement.dataset.theme = "dark";
    const st = adoc.createElement("style");
    st.textContent = `html,body{background:transparent!important;overflow:hidden}
      .top,.caption,.legend .kbd,.card .pin,.card .use{display:none!important}
      .arch{padding-top:4px}
      .caption{font-size:15.5px;min-height:50px}`;
    adoc.head.appendChild(st);
    f.style.width = "1272px";
    measure();
  }
  function measure() {  // fit the iframe to the page (the customer view is taller)
    const f = $("#arch");
    f.style.height = "2000px";
    archH = adoc.querySelector(".arch").getBoundingClientRect().height + 8;
    f.style.height = `${archH}px`;
    f.contentWindow.dispatchEvent(new Event("resize"));
  }

  function vp() { const v = $("#viewport"); return { w: v.clientWidth, h: v.clientHeight }; }
  function baseScale() { const { w, h } = vp(); return Math.min(w / 1272, h / archH); }

  function camFor(mode) {
    const { w, h } = vp(), s0 = baseScale();
    let rect = { x: 0, y: 0, w: 1272, h: archH }, s = s0;
    if (mode === "focus") {
      const els = $$(".node.hot", adoc).concat($$(".card", adoc).filter((c) => c.style.display === "block"));
      if (els.length) {
        const rs = els.map((e) => e.getBoundingClientRect());
        const x0 = Math.min(...rs.map((r) => r.left)) - 28, y0 = Math.min(...rs.map((r) => r.top)) - 28;
        const x1 = Math.max(...rs.map((r) => r.right)) + 28, y1 = Math.max(...rs.map((r) => r.bottom)) + 28;
        rect = { x: x0, y: y0, w: x1 - x0, h: y1 - y0 };
        s = Math.max(s0, Math.min(w / rect.w, h / rect.h, s0 * 1.5));
      }
    }
    const cx = rect.x + rect.w / 2, cy = rect.y + rect.h / 2;
    const clamp = (pos, size, view) => (size * s <= view ? (view - size * s) / 2 : Math.min(0, Math.max(view - size * s, pos)));
    return { s, x: clamp(w / 2 - cx * s, 1272, w), y: clamp(h / 2 - cy * s, archH, h) };
  }

  function camAt(t) {
    if (!S.camTo) return null;
    const k = easeIO((t - S.camT0) / 1.15);
    const a = S.camFrom || S.camTo, b = S.camTo;
    return { s: a.s + (b.s - a.s) * k, x: a.x + (b.x - a.x) * k, y: a.y + (b.y - a.y) * k };
  }

  function archState(t) {
    const st = { view: "laptop", step: 0, flow: null, card: null, cam: "full", label: "" };
    let since = 0, labelAt = 0;
    for (const c of TL.cues) {
      if (c.t > t) break;
      since = c.t;
      if (c.label && c.label !== st.label) labelAt = c.t;
      if (c.view) st.view = c.view;
      if (c.step !== undefined) { st.step = c.step; st.flow = null; st.card = null; }
      if (c.flow !== undefined) st.flow = c.flow;
      if (c.card !== undefined) st.card = c.card;
      if (c.cam) st.cam = c.cam;
      if (c.label) st.label = c.label;
    }
    return [st, since, labelAt];
  }

  let applied = { view: "laptop", step: -1, flow: null, card: null };
  function applyArch(t) {
    const [st, since, labelAt] = archState(t);
    const key = JSON.stringify(st);
    if (key !== S.key) {
      if (st.view !== applied.view) { arch.setView(st.view); measure(); }
      if (st.step !== applied.step || st.view !== applied.view) { arch.setStep(st.step); arch.showCard(null); applied.flow = null; applied.card = null; }
      if (st.flow !== null && st.flow !== applied.flow) arch.flowStep(st.flow);
      if (st.card !== applied.card) arch.showCard(st.card);
      // the page's caption is shown on the stage (outside the camera); keyboard hints make no sense in a video
      const cap = adoc.querySelector(".caption").innerHTML.replace(/\s*Use ← and → to walk the acts\./, "");
      if (cap !== S.cap) { S.cap = cap; S.capT = since; $("#archcap").innerHTML = cap; }
      applied = { view: st.view, step: st.step, flow: st.flow, card: st.card };
      const target = camFor(st.cam);
      S.camFrom = camAt(since) || target; S.camTo = target; S.camT0 = since; S.key = key;
      if (st.label !== S.label) { S.label = st.label; S.labelT = labelAt; $("#actlabel").textContent = st.label; }
    }
    const c = camAt(t);
    $("#cam").style.transform = `translate(${c.x.toFixed(2)}px, ${c.y.toFixed(2)}px) scale(${c.s.toFixed(4)})`;
    const lk = ease((t - S.labelT) / 0.5);
    $("#actlabel").style.opacity = lk;
    $("#actlabel").style.transform = `translateX(${(1 - lk) * -14}px)`;
    const ck = ease((t - S.capT) / 0.45);
    $("#archcap").style.opacity = 0.15 + 0.85 * ck;
  }

  // ---- render ---------------------------------------------------------------------------------------------------------
  function appearTime(el) {
    const b = TL.beats[el.dataset.at];
    return b ? b.start + (parseFloat(el.dataset.frac || 0) * b.dur) : Infinity;
  }

  function renderScene(sc, t) {
    const el = $(`.scene[data-scene="${sc.id}"]`);
    const half = T.xfade / 2;
    const fin = sc.start === 0 ? 1 : ease((t - sc.start + half) / T.xfade);
    const op = Math.min(fin, 1 - ease((t - sc.end + half) / T.xfade));
    el.style.opacity = op;
    el.style.visibility = op > 0.001 ? "visible" : "hidden";
    if (op <= 0.001) return 0;
    $$("[data-at]", el).forEach((n) => {
      const a = appearTime(n);
      let k = ease((t - a) / (n.classList.contains("pane") ? 0.6 : 0.75));
      if (n.dataset.out) { const o = TL.beats[n.dataset.out]; if (o) k *= 1 - ease((t - o.start + 0.15) / 0.55); }
      const fx = n.dataset.fx || (n.classList.contains("pane") ? "fade" : "rise");
      n.style.opacity = k;
      n.style.visibility = k > 0.001 ? "visible" : "hidden";
      if (fx === "rise") n.style.transform = `translateY(${(1 - k) * 28}px)`;
      if (fx === "pop") n.style.transform = `scale(${0.82 + 0.18 * k})`;
      if (n.dataset.grow) {
        const g = easeIO((t - a - 0.15) / 1.3) * parseFloat(n.dataset.grow);
        n.style.transform = `scaleX(${g})`; n.style.opacity = 1;
      }
    });
    return op;
  }

  function stepAnimations(t, docs) {
    for (const d of docs) {
      for (const a of d.getAnimations()) {
        if (!seen.has(a)) seen.set(a, t);
        a.pause();
        a.currentTime = Math.max(0, (t - seen.get(a)) * 1000);
      }
    }
  }

  function chapters(t) {
    const names = [...new Set(TL.scenes.map((s) => s.chapter).filter(Boolean))];
    const cur = TL.scenes.find((s) => t >= s.start && t < s.end) || TL.scenes[TL.scenes.length - 1];
    const ci = names.indexOf(cur.chapter);
    $("#chapters").innerHTML = names.map((n, i) => `<span class="${i === ci ? "on" : i < ci ? "done" : ""}">${n}</span>`).join("");
  }

  function render(t, step = true) {
    let chrome = 0;
    for (const sc of TL.scenes) {
      const op = renderScene(sc, t);
      if (sc.chapter && sc.id !== "close") chrome = Math.max(chrome, op);
      if (sc.id === "arch" && op > 0.001) applyArch(t);
    }
    $("#chrome").style.opacity = chrome;
    chapters(t);
    $("#bar").style.width = `${(100 * t / TL.total).toFixed(3)}%`;
    $(".g1").style.transform = `translate(${Math.sin(t * 0.07) * 90}px, ${Math.cos(t * 0.05) * 60}px)`;
    $(".g2").style.transform = `translate(${Math.cos(t * 0.06) * 80}px, ${Math.sin(t * 0.045) * 70}px)`;
    // no fade in: frame 0 is the title card, so it doubles as the video's thumbnail; fade to black at the end
    $("#fade").style.opacity = ease((t - (TL.total - 0.9)) / 0.9);
    if (step) stepAnimations(t, [document, adoc]);
  }

  // ---- entry points ---------------------------------------------------------------------------------------------------
  window.__init = async (durations = {}) => {
    const script = await (await fetch("script.json")).json();
    TL = build(script, durations);
    await archReady();
    setupArch();
    await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
    return { total: TL.total, beats: TL.beats, scenes: TL.scenes };
  };
  window.__render = async (t) => {
    render(t, false);
    await new Promise((r) => requestAnimationFrame(r));  // let the architecture page's own rAF work run, then freeze transitions
    render(t, true);
  };

  if (new URLSearchParams(location.search).has("play")) {   // real-time preview in a browser (no audio)
    window.__init().then(() => {
      const t0 = performance.now(), from = +new URLSearchParams(location.search).get("t") || 0;
      const loop = () => { const t = from + (performance.now() - t0) / 1000; render(t, false); if (t < TL.total) requestAnimationFrame(loop); };
      loop();
    });
  }
})();
