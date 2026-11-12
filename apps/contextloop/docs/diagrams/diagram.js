// Tiny renderer for the ContextLoop README diagrams.
// Each page calls draw(spec); scripts/render_diagrams.py screenshots the .canvas element.
// Coordinates are in CSS pixels. Edges route orthogonally; pass `via` points for exact routes.

const KINDS = {  // ContextLoop brand palette (contextloop/ui/brand.py)
  source:   { label: "Synthetic source",          stroke: "#A7B0C2", bg: "#EEF1F6", ink: "#5B6478", dash: true },
  fivetran: { label: "Fivetran pattern",          stroke: "#8E99EC", bg: "#ECEEFD", ink: "#3341B8" },
  dbt:      { label: "dbt",                        stroke: "#FFAA95", bg: "#FFEFEA", ink: "#B8432A" },
  open:     { label: "Open source / public image", stroke: "#78D3C8", bg: "#E3F7F4", ink: "#0B7A70" },
  app:      { label: "ContextLoop code",           stroke: "#86D4B2", bg: "#E2F6EE", ink: "#13734F" },
  ai:       { label: "Claude",                     stroke: "#F0C35C", bg: "#FFF5DC", ink: "#8A5A00" },
  ext:      { label: "Outside the stack",          stroke: "#CDD3DF", bg: "#F5F7FC", ink: "#18203A" },
  volume:   { label: "Named volume",               stroke: "#A7B0C2", bg: "#EEF1F6", ink: "#18203A" },
  bad:      { label: "Wrong answer",               stroke: "#F2A3A6", bg: "#FDECEC", ink: "#B4282D" },
  good:     { label: "Governed answer",            stroke: "#86D4B2", bg: "#E2F6EE", ink: "#13734F" },
};

const esc = (s) => String(s).replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));

function anchor(box, side = "b", off = 0) {
  const { x, y, w, h } = box;
  if (side === "t") return [x + w / 2 + off, y];
  if (side === "b") return [x + w / 2 + off, y + h];
  if (side === "l") return [x, y + h / 2 + off];
  return [x + w, y + h / 2 + off];
}

function route(s, fs, e, ts) {
  const v = (k) => k === "t" || k === "b";
  if (v(fs) && v(ts)) {
    if (Math.abs(s[0] - e[0]) < 1) return [];
    const m = (s[1] + e[1]) / 2;
    return [[s[0], m], [e[0], m]];
  }
  if (!v(fs) && !v(ts)) {
    if (Math.abs(s[1] - e[1]) < 1) return [];
    const m = (s[0] + e[0]) / 2;
    return [[m, s[1]], [m, e[1]]];
  }
  return v(fs) ? [[s[0], e[1]]] : [[e[0], s[1]]];
}

function pathD(pts, r = 9) {
  let d = `M${pts[0][0]},${pts[0][1]}`;
  for (let i = 1; i < pts.length - 1; i++) {
    const [px, py] = pts[i - 1], [cx, cy] = pts[i], [nx, ny] = pts[i + 1];
    const l1 = Math.hypot(cx - px, cy - py), l2 = Math.hypot(nx - cx, ny - cy);
    const rr = Math.min(r, l1 / 2, l2 / 2);
    const ax = cx - ((cx - px) / l1) * rr, ay = cy - ((cy - py) / l1) * rr;
    const bx = cx + ((nx - cx) / l2) * rr, by = cy + ((ny - cy) / l2) * rr;
    d += ` L${ax},${ay} Q${cx},${cy} ${bx},${by}`;
  }
  const last = pts[pts.length - 1];
  return d + ` L${last[0]},${last[1]}`;
}

function draw(spec) {
  const canvas = document.querySelector(".canvas");
  canvas.style.width = spec.width + "px";
  canvas.style.height = spec.height + "px";
  const boxes = {};
  let html = "";
  let groupLabels = "";

  html += `<div class="head"><div class="title">${esc(spec.title)}</div><div class="subtitle">${esc(spec.subtitle || "")}</div></div>`;

  for (const g of spec.groups || []) {
    if (g.id) boxes[g.id] = g;
    const k = KINDS[g.kind] || {};
    const style = `left:${g.x}px;top:${g.y}px;width:${g.w}px;height:${g.h}px;` +
      (g.kind ? `border-color:${k.stroke};background:${g.fill || "transparent"};` : "");
    html += `<div class="group ${g.dash ? "dash" : ""} ${g.solid ? "solid" : ""}" style="${style}">` +
      `</div>`;
    if (g.label) groupLabels += `<div class="glabel" style="left:${g.x + 14}px;top:${g.y + 8}px;${g.labelColor ? `color:${g.labelColor}` : ""}">${g.label}</div>`;
  }

  for (const n of spec.nodes) {
    n.h = n.h || 64;
    boxes[n.id] = n;
    const k = KINDS[n.kind] || KINDS.ext;
    const border = `border-color:${k.stroke};${(k.dash || n.dash) ? "border-style:dashed;" : ""}${n.bg ? `background:${n.bg};` : ""}`;
    html += `<div class="node ${n.cls || ""}" style="left:${n.x}px;top:${n.y}px;width:${n.w}px;height:${n.h}px;${border}">` +
      (n.badge ? `<div class="badge" style="background:${k.bg};color:${k.ink}">${n.badge}</div>` : "") +
      `<div class="txt"><div class="ntitle ${n.mono ? "mono" : ""}">${n.title}</div>` +
      (n.sub ? `<div class="nsub">${n.sub}</div>` : "") +
      (n.body ? `<div class="nbody">${n.body}</div>` : "") +
      `</div>` +
      (n.step ? `<div class="step">${n.step}</div>` : "") +
      `</div>`;
  }

  let svg = `<svg class="edges" width="${spec.width}" height="${spec.height}"><defs>` +
    `<marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,1 L9,5 L0,9 z" fill="#8E98B0"/></marker>` +
    `<marker id="arrA" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,1 L9,5 L0,9 z" fill="#4B5BDC"/></marker>` +
    `</defs>`;
  let labels = "";
  for (const e of spec.edges || []) {
    const a = boxes[e.from], b = boxes[e.to];
    if (!a || !b) { throw new Error(`edge ${e.from}->${e.to}: unknown box`); }
    const fs = e.fs || "b", ts = e.ts || "t";
    const s = anchor(a, fs, e.fo || 0), t = anchor(b, ts, e.too || 0);
    const pts = [s, ...(e.via || route(s, fs, t, ts)), t];
    const accent = e.accent;
    const m = accent ? "url(#arrA)" : "url(#arr)";
    const color = accent ? "#4B5BDC" : "#8E98B0";
    const dash = e.dash ? `stroke-dasharray="6 5"` : e.dot ? `stroke-dasharray="2 4"` : "";
    const ends = e.arrow === "none" ? "" : e.arrow === "both" ? `marker-start="${m}" marker-end="${m}"` : `marker-end="${m}"`;
    svg += `<path d="${pathD(pts)}" fill="none" stroke="${color}" stroke-width="${accent ? 2 : 1.6}" ${dash} ${ends}/>`;
    if (e.label) {
      let at = e.at;
      if (!at) {
        let best = 0;
        for (let i = 0; i < pts.length - 1; i++) {
          const L = Math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1]);
          if (L > best) { best = L; at = [(pts[i][0] + pts[i + 1][0]) / 2, (pts[i][1] + pts[i + 1][1]) / 2]; }
        }
      }
      labels += `<div class="elabel ${accent ? "accent" : ""}" style="left:${at[0]}px;top:${at[1]}px">${e.label}</div>`;
    }
  }
  svg += `</svg>`;

  let legend = "";
  if (spec.legend) {
    legend = `<div class="legend" style="top:${spec.height - (spec.legendH || 52)}px">` +
      spec.legend.map((item) => {
        if (typeof item === "string") {
          const k = KINDS[item];
          return `<span><i class="sw" style="border-color:${k.stroke};background:${k.bg};${k.dash ? "border-style:dashed;" : ""}"></i>${k.label}</span>`;
        }
        return `<span><i class="ln ${item.line}"></i>${item.label}</span>`;
      }).join("") + `</div>`;
  }

  for (const n of spec.notes || []) {
    labels += `<div class="note" style="left:${n.x}px;top:${n.y}px;width:${n.w || 300}px;text-align:${n.align || "left"}">${n.text}</div>`;
  }

  canvas.innerHTML = html + svg + groupLabels + labels + legend;
  // nodes above edges, labels above all
  canvas.querySelector("svg.edges").style.zIndex = 1;
}
