// Architecture tab: portrait service diagram with hover details and a step-by-step walkthrough.
(() => {
  const SVG_NS = "http://www.w3.org/2000/svg";

  const KIND_LABELS = {
    gcp: "Google Cloud service",
    oss: "Open-source framework",
    app: "WeekendWise code",
    user: "End user",
  };

  // Geometry uses an 800 × 1064 viewBox (portrait).
  const containers = [
    { id: "cloudrun", x: 250, y: 150, w: 300, h: 650, header: 48, icon: "CR", kind: "gcp", title: "Cloud Run", sub: "Serverless runtime",
      info: {
        what: "Runs a containerized web app without servers to manage, and scales to zero when nobody is using it.",
        how: "Hosts the web UI and the Python + LangGraph backend in one container behind an HTTPS URL.",
        facts: ["Runs as service account weekendwise-run: Vertex AI user, Firestore read-only, log writer", "Conservative instance limits keep demo costs low", "No service-account keys inside the image"],
      } },
    { id: "langgraph", x: 270, y: 282, w: 260, h: 498, header: 36, icon: "LG", kind: "oss", title: "LangGraph workflow", sub: "Agent graph",
      info: {
        what: "Open-source framework for building AI agents as an explicit graph of steps that share typed state.",
        how: "Coordinates the six steps inside this box. Hard limits stop the agent from looping or wandering.",
        facts: ["At most 3 model calls (draft, one revision, one format repair), 1 tool call and 1 revision per trip", "150-second planning deadline; 45 seconds per model call", "State: constraints, evidence, tool result, draft, citations, budget, review result"],
      } },
  ];

  const nodes = [
    { id: "traveler", x: 290, y: 20, w: 220, h: 60, icon: "◉", kind: "user", badge: "1", title: "Traveler", sub: "Web browser · HTTPS",
      info: {
        what: "The person planning a weekend away.",
        how: "Enters destination, dates, party size, budget and interests. Talks only to the app's HTTPS endpoint, never directly to the database or the AI models.",
        facts: ["No login in the MVP", "No bookings or payments are made"],
      } },
    { id: "streamlit", x: 290, y: 206, w: 220, h: 54, icon: "PY", kind: "app", title: "WeekendWise app", sub: "Form · itinerary · sources",
      info: {
        what: "A small Python web server (Starlette + Uvicorn) that serves the screens and one /api/plan endpoint.",
        how: "Serves the trip form, streams live progress from the planner, and renders the itinerary, budget and source cards. All AI and database calls happen on the server.",
        facts: ["Progress shows safe step summaries, not model reasoning", "Every screen labels demo data and simulated conditions"],
      } },
    { id: "normalize", x: 290, y: 326, w: 220, h: 50, icon: "⇥", kind: "app", badge: "2", title: "Understand request", sub: "Validate & normalize",
      info: {
        what: "First step of the workflow: makes sure the request is valid and in scope.",
        how: "Maps the city to a supported ID (San Francisco, Portland, Santa Cruz, Napa Valley) and checks dates (up to 3 days), party size and budget.",
        facts: ["Unsupported requests fail early and clearly", "Prompt size capped at 24,000 characters"],
      } },
    { id: "retrieve", x: 290, y: 474, w: 220, h: 50, icon: "◎", kind: "app", badge: "4", title: "Retrieve evidence", sub: "Embed query → vector search",
      info: {
        what: "Finds the destination-guide passages most relevant to this trip (retrieval-augmented generation).",
        how: "Embeds the request with Vertex AI, then asks Firestore for the closest guide chunks in the chosen city.",
        facts: ["Returns 4 chunks by default, never more than 5", "Weak matches return “insufficient evidence” instead of a guess"],
      } },
    { id: "conditions", x: 290, y: 400, w: 220, h: 50, icon: "☁", kind: "app", badge: "3", title: "Check conditions", sub: "Optional · max 1 tool call",
      info: {
        what: "Optional step: decides whether the plan needs a local-conditions check, such as a rainy-day request.",
        how: "Calls the single allowlisted tool with schema-validated arguments. Ordinary requests skip this step.",
        facts: ["At most one tool call per request", "Invalid city or date fails closed"],
      } },
    { id: "plan", x: 290, y: 548, w: 220, h: 50, icon: "✎", kind: "app", badge: "5", title: "Draft itinerary", sub: "Grounded, cited plan",
      info: {
        what: "Asks Gemini to write a day-by-day plan using only the retrieved evidence.",
        how: "Sends the traveler's constraints, retrieved passages and any conditions to Gemini. Each guide-based claim must cite a chunk ID.",
        facts: ["Prompt size and output length are capped", "Budget estimated across 4 categories with a 10% buffer"],
      } },
    { id: "review", x: 290, y: 622, w: 220, h: 50, icon: "✓", kind: "app", badge: "6", title: "Review & verify", sub: "Citations · budget · caveats",
      info: {
        what: "A quality gate before anything reaches the traveler. It is plain, unit-tested code, not another AI call.",
        how: "Checks that every citation matches a retrieved chunk, the budget adds up (±$1), dates and constraints are met and simulated conditions are flagged. Can send the draft back to Gemini once.",
        facts: ["Predictable and free: no model call", "Rejects made-up citation IDs and claims that something was booked", "Adds a drink-driving caveat when a plan mentions alcohol"],
      } },
    { id: "respond", x: 290, y: 708, w: 220, h: 50, icon: "↩", kind: "app", badge: "7", title: "Respond", sub: "Itinerary + sources + trace",
      info: {
        what: "Packages the final answer for the web app.",
        how: "Returns the itinerary, budget summary, citations (kept separate from generated text) and a short activity trace.",
        facts: ["The trace says things like “searched guides” and “reviewed sources”, never private model reasoning"],
      } },
    { id: "embed", x: 572, y: 418, w: 194, h: 62, icon: "VA", kind: "gcp", title: "Embeddings", sub: "Vertex AI · 768-d",
      info: {
        what: "Turns text into a vector, a list of numbers that captures meaning, so similar ideas end up close together.",
        how: "Embeds the traveler's query at runtime and every guide chunk during ingestion, with the same model and size for both.",
        facts: ["Model gemini-embedding-001, 768 dimensions, us-central1", "Called only from the server, authorized by IAM"],
      } },
    { id: "firestore", x: 572, y: 500, w: 194, h: 62, icon: "FS", kind: "gcp", title: "Firestore", sub: "Vector search store",
      info: {
        what: "Google's managed document database, with built-in nearest-neighbor vector search.",
        how: "Stores each guide chunk with its text, metadata (city, source, active flag) and embedding in guide_chunks, then returns the closest chunks for a query.",
        facts: ["Cosine distance, filtered by city and active flag on the server", "The app can only read; only the ingestion job can write", "Right-sized for a small corpus; Vertex AI Vector Search is the scale-up path"],
      } },
    { id: "gemini", x: 572, y: 592, w: 194, h: 64, icon: "G", kind: "gcp", title: "Gemini", sub: "Vertex AI · 3.8 Flash",
      info: {
        what: "Google's generative AI model, called through Vertex AI.",
        how: "Writes the itinerary draft from the retrieved passages, and rewrites it once if the reviewer finds problems.",
        facts: ["Model gemini-3.8-flash, global endpoint, low thinking level for speed and cost", "At most 3 calls per trip, with one retry on a temporary error", "Uses the Cloud Run service identity; no API keys"],
      } },
    { id: "mocktool", x: 34, y: 394, w: 194, h: 62, icon: "☂", kind: "app", title: "Conditions tool", sub: "Simulated · read-only",
      info: {
        what: "check_local_conditions: a fixed data set that returns sample conditions for a seeded city and date.",
        how: "Shows safe agent tool use without depending on a live weather or maps API.",
        facts: ["No network calls, bookings, payments or writes", "Output is always labeled as sample data"],
      } },
    { id: "logging", x: 34, y: 740, w: 194, h: 62, icon: "CL", kind: "gcp", badge: "8", title: "Cloud Logging", sub: "Structured, privacy-safe",
      info: {
        what: "Google's managed service for storing and searching logs.",
        how: "Receives one structured event per step: request ID, step, model, latency and error category.",
        facts: ["No full prompts or personal details logged by default", "Used to troubleshoot the live demo"],
      } },
    { id: "cloudbuild", x: 34, y: 858, w: 194, h: 62, icon: "CB", kind: "gcp", badge: "B", title: "Cloud Build", sub: "Builds the container",
      info: {
        what: "Google's managed build service. It runs a series of build steps.",
        how: "Turns the source code into the app's container image (make build).",
        facts: ["Runs as its own service account, weekendwise-build"],
      } },
    { id: "registry", x: 295, y: 858, w: 210, h: 62, icon: "AR", kind: "gcp", title: "Artifact Registry", sub: "Versioned images",
      info: {
        what: "A private repository for container images.",
        how: "Stores each WeekendWise image version. Cloud Run deploys from it.",
        facts: ["The handoff point between build and run", "Earlier versions make rollback quick"],
      } },
    { id: "ingest", x: 572, y: 858, w: 194, h: 62, icon: "⇪", kind: "app", badge: "A", title: "Ingestion job", sub: "make seed · 47 guides",
      info: {
        what: "An offline script that loads the destination knowledge base.",
        how: "Reads 47 synthetic Markdown guides for 4 cities, splits them into 95 chunks, embeds them with Vertex AI and writes chunks and vectors to Firestore.",
        facts: ["Runs as weekendwise-ingest, the only identity that can write Firestore", "Stable IDs and checksums make re-runs safe", "Updating content needs no app redeploy"],
      } },
    { id: "iam", x: 34, y: 966, w: 234, h: 62, icon: "IAM", kind: "gcp", badge: "C", title: "IAM", sub: "3 least-privilege identities",
      info: {
        what: "Controls who, or what, can use each resource.",
        how: "Three service accounts: run (Vertex AI, Firestore read, logs), ingest (Vertex AI, Firestore write) and build (image push, logs).",
        facts: ["No downloadable keys; operators impersonate service accounts", "The running app cannot write to the database"],
      } },
    { id: "budget", x: 283, y: 966, w: 234, h: 62, icon: "$", kind: "gcp", title: "Billing budget", sub: "$20 / month · 4 alerts",
      info: {
        what: "Cost visibility and alerts for the project.",
        how: "A $20/month budget with four alert thresholds. Scale-to-zero and per-request limits keep spend around $5–$30 a month.",
        facts: ["A budget sends alerts; it is not a hard spending cap"],
      } },
    { id: "terraform", x: 532, y: 966, w: 234, h: 62, icon: "TF", kind: "oss", title: "Terraform", sub: "make apply · destroy-all",
      info: {
        what: "Infrastructure as code: every cloud resource is declared in version-controlled files.",
        how: "Two modules (bootstrap and stack) create the project, APIs, IAM, database and services. One command removes everything.",
        facts: ["No manual console changes", "State kept in a versioned Cloud Storage bucket"],
      } },
  ];

  const edges = [
    { id: "e_req", from: "traveler", to: "streamlit", d: "M400,80 V206", both: true },
    { id: "e_in", from: "streamlit", to: "normalize", d: "M400,260 V326" },
    { id: "e_n_c", from: "normalize", to: "conditions", d: "M400,376 V400" },
    { id: "e_r_emb", from: "retrieve", to: "embed", d: "M510,492 C541,492 541,449 572,449" },
    { id: "e_r_fs", from: "retrieve", to: "firestore", d: "M510,506 C541,506 541,531 572,531" },
    { id: "e_c_r", from: "conditions", to: "retrieve", d: "M400,450 V474" },
    { id: "e_c_tool", from: "conditions", to: "mocktool", d: "M290,425 H228", style: "optional" },
    { id: "e_r_p", from: "retrieve", to: "plan", d: "M400,524 V548" },
    { id: "e_p_g", from: "plan", to: "gemini", d: "M510,573 C541,573 541,624 572,624" },
    { id: "e_p_r", from: "plan", to: "review", d: "M400,598 V622" },
    { id: "e_loop", from: "review", to: "plan", d: "M290,654 C272,654 272,580 290,580", style: "loop" },
    { id: "e_r_resp", from: "review", to: "respond", d: "M400,672 V708" },
    { id: "e_return", from: "respond", to: "streamlit", d: "M290,733 H259 V233 H290" },
    { id: "e_log", from: "cloudrun", to: "logging", d: "M250,771 H228" },
    { id: "e_cb_ar", from: "cloudbuild", to: "registry", d: "M228,889 H295", style: "ops" },
    { id: "e_ar_cr", from: "registry", to: "cloudrun", d: "M400,858 V800", style: "ops" },
    { id: "e_ing_emb", from: "ingest", to: "embed", d: "M766,880 H780 V449 H766", style: "ops" },
    { id: "e_emb_fs", from: "embed", to: "firestore", d: "M669,480 V500", style: "ops" },
  ];

  const labels = [
    { x: 30, y: 136, text: "GOOGLE CLOUD PROJECT · weekendwise-demo", cls: "boundary-label" },
    { x: 572, y: 406, text: "GOOGLE AI & DATA", cls: "column-label" },
    { x: 34, y: 382, text: "TOOL & OPERATIONS", cls: "column-label" },
    { x: 34, y: 846, text: "BUILD & DEPLOY", cls: "column-label" },
    { x: 572, y: 846, text: "KNOWLEDGE BASE · OFFLINE", cls: "column-label" },
    { x: 34, y: 954, text: "PLATFORM FOUNDATION", cls: "column-label" },
    { x: 302, y: 614, text: "≤ 1 revision", cls: "loop-label" },
    { x: 408, y: 834, text: "deploy", cls: "edge-label" },
  ];

  const steps = [
    { key: "1", group: "A traveler's request", title: "Traveler submits a trip",
      nodes: ["traveler", "cloudrun", "streamlit"], edges: ["e_req"],
      text: "The browser sends the trip form to the Cloud Run URL over HTTPS. It never talks to Vertex AI or Firestore directly." },
    { key: "2", title: "Understand the request",
      nodes: ["streamlit", "langgraph", "normalize"], edges: ["e_in"],
      text: "The web server hands the request to the LangGraph workflow, which validates city, dates, party size and budget and stops early on anything out of scope." },
    { key: "3", title: "Check local conditions",
      nodes: ["langgraph", "conditions", "mocktool"], edges: ["e_n_c", "e_c_tool"],
      text: "Only when it's needed, for example a rainy-day trip, the agent calls one allowlisted, read-only tool. Arguments are validated, and the agent gets at most one call." },
    { key: "4", title: "Retrieve evidence (RAG)",
      nodes: ["langgraph", "retrieve", "embed", "firestore"], edges: ["e_c_r", "e_r_emb", "e_r_fs"],
      text: "Vertex AI turns the request into a 768-number vector. Firestore returns the 4 closest guide passages for that city. Weak matches come back as “insufficient evidence”, not a guess." },
    { key: "5", title: "Draft the itinerary",
      nodes: ["langgraph", "plan", "gemini"], edges: ["e_r_p", "e_p_g"],
      text: "Gemini writes a day-by-day plan from the retrieved passages only. It cites a chunk ID for every guide-based claim and adds a budget estimate." },
    { key: "6", title: "Review and verify",
      nodes: ["langgraph", "review", "plan"], edges: ["e_p_r", "e_loop"],
      text: "Plain code, not another AI call, checks every citation, the budget math (±$1), dates and safety caveats. If something is off, the draft goes back to Gemini for one revision at most." },
    { key: "7", title: "Return a cited plan",
      nodes: ["langgraph", "respond", "streamlit", "cloudrun", "traveler"], edges: ["e_r_resp", "e_return", "e_req"],
      text: "The traveler gets the itinerary, budget, clickable sources and a short activity trace. Sources are kept separate from AI-generated text." },
    { key: "8", title: "Observe every step",
      nodes: ["cloudrun", "logging"], edges: ["e_log"],
      text: "Each step writes a structured log: request ID, step, model, latency and error type. Prompts and personal details stay out of the logs." },
    { key: "A", group: "Behind the scenes", title: "Load the knowledge base",
      nodes: ["ingest", "embed", "firestore"], edges: ["e_ing_emb", "e_emb_fs"],
      text: "Offline, 47 synthetic guides for 4 cities are split into chunks, embedded with Vertex AI and written to Firestore. Updating content needs no redeploy." },
    { key: "B", title: "Build and deploy",
      nodes: ["cloudbuild", "registry", "cloudrun"], edges: ["e_cb_ar", "e_ar_cr"],
      text: "Cloud Build packages the container, Artifact Registry stores each version and Cloud Run deploys it. Earlier versions allow a quick rollback." },
    { key: "C", title: "Security and cost guardrails",
      nodes: ["iam", "budget", "terraform"], edges: [],
      text: "Three least-privilege service accounts with no keys, a $20/month budget with alerts, and every resource created and removed by Terraform." },
  ];

  const byId = Object.fromEntries([...containers, ...nodes].map((item) => [item.id, item]));
  let currentStep = -1;
  let pinnedId = null;
  let svg;

  function make(tag, attrs = {}, parent) {
    const element = document.createElementNS(SVG_NS, tag);
    Object.entries(attrs).forEach(([key, value]) => element.setAttribute(key, value));
    if (parent) parent.appendChild(element);
    return element;
  }

  function addText(parent, x, y, text, cls) {
    const element = make("text", { x, y, class: cls }, parent);
    element.textContent = text;
    return element;
  }

  function addInfoDot(group, cx, cy) {
    const dot = make("g", { class: "info-dot" }, group);
    make("circle", { cx, cy, r: 8 }, dot);
    addText(dot, cx, cy + 3.6, "i", "info-dot-text");
  }

  function addIcon(group, x, cy, icon, size = 30) {
    make("rect", { x, y: cy - size / 2, width: size, height: size, rx: 8, class: "node-icon-bg" }, group);
    addText(group, x + size / 2, cy + 4, icon, `node-icon-text${icon.length > 2 ? " small" : ""}`);
  }

  function addBadge(group, x, y, text) {
    make("circle", { cx: x, cy: y, r: 10, class: "step-badge" }, group);
    addText(group, x, y + 3.6, text, "step-badge-text");
  }

  function makeInteractive(group, item) {
    group.setAttribute("tabindex", "0");
    group.setAttribute("role", "button");
    group.setAttribute("aria-label", `${item.title}: ${item.info.what}`);
    group.dataset.id = item.id;
    group.addEventListener("pointerenter", () => hoverOn(item.id, group));
    group.addEventListener("pointerleave", hoverOff);
    group.addEventListener("focus", () => hoverOn(item.id, group));
    group.addEventListener("blur", hoverOff);
    group.addEventListener("click", () => pin(item.id));
    group.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        pin(item.id);
      }
    });
  }

  function render() {
    svg = document.getElementById("arch-svg");
    if (!svg) return;
    // Keep the tooltip outside the animated screen so fixed positioning uses the viewport.
    const tip = document.getElementById("arch-tip");
    if (tip) document.body.appendChild(tip);

    const defs = make("defs", {}, svg);
    [["arrow", "arrow-head"], ["arrow-on", "arrow-head on"]].forEach(([id, cls]) => {
      const marker = make("marker", { id, viewBox: "0 0 10 10", refX: 9, refY: 5, markerWidth: 7, markerHeight: 7, orient: "auto-start-reverse" }, defs);
      make("path", { d: "M0,1 L9,5 L0,9 z", class: cls }, marker);
    });

    make("rect", { x: 12, y: 108, width: 776, height: 942, rx: 22, class: "project-boundary" }, svg);

    containers.forEach((box) => {
      const group = make("g", { class: `arch-container kind-${box.kind}`, id: `node-${box.id}` }, svg);
      make("rect", { x: box.x, y: box.y, width: box.w, height: box.h, rx: 16, class: "container-body" }, group);
      const header = make("g", { class: "container-header arch-target" }, group);
      make("rect", { x: box.x, y: box.y, width: box.w, height: box.header, rx: 16, class: "container-hit" }, header);
      const cy = box.y + box.header / 2;
      addIcon(header, box.x + 12, cy, box.icon, 26);
      addText(header, box.x + 46, cy + 1, box.title, "container-title");
      addText(header, box.x + 46, cy + 13, box.sub, "container-sub");
      addInfoDot(header, box.x + box.w - 18, cy);
      makeInteractive(header, box);
    });

    const edgeLayer = make("g", { class: "edge-layer" }, svg);
    edges.forEach((edge) => {
      const path = make("path", { d: edge.d, class: `arch-edge${edge.style ? ` ${edge.style}` : ""}`, id: `edge-${edge.id}`, "marker-end": "url(#arrow)" }, edgeLayer);
      if (edge.both) path.setAttribute("marker-start", "url(#arrow)");
    });

    nodes.forEach((node) => {
      const group = make("g", { class: `arch-node arch-target kind-${node.kind}`, id: `node-${node.id}` }, svg);
      make("rect", { x: node.x, y: node.y, width: node.w, height: node.h, rx: 12, class: "node-body" }, group);
      const cy = node.y + node.h / 2;
      addIcon(group, node.x + 12, cy, node.icon);
      addText(group, node.x + 52, cy - 2, node.title, "node-title");
      addText(group, node.x + 52, cy + 13, node.sub, "node-sub");
      addInfoDot(group, node.x + node.w - 15, node.y + 15);
      if (node.badge) addBadge(group, node.x, node.y, node.badge);
      makeInteractive(group, node);
    });

    labels.forEach((label) => addText(svg, label.x, label.y, label.text, label.cls));

    renderStepList();
    renderDetail();
  }

  // Hover tooltip ---------------------------------------------------------

  function infoMarkup(item, { full = false } = {}) {
    const facts = item.info.facts.map((fact) => `<li>${fact}</li>`).join("");
    return `
      <div class="tip-kind kind-${item.kind}"><i></i>${KIND_LABELS[item.kind]}</div>
      <h4>${item.title}</h4>
      <p class="tip-what">${item.info.what}</p>
      <div class="tip-block"><span>IN WEEKENDWISE</span><p>${item.info.how}</p></div>
      <ul class="tip-facts">${facts}</ul>
      ${full ? "" : '<div class="tip-foot">Click to pin in the side panel</div>'}`;
  }

  function hoverOn(id, target) {
    const item = byId[id];
    const tip = document.getElementById("arch-tip");
    tip.innerHTML = infoMarkup(item);
    tip.classList.add("visible");

    const box = target.getBoundingClientRect();
    const tipBox = tip.getBoundingClientRect();
    const gap = 14;
    let left = box.right + gap;
    if (left + tipBox.width > window.innerWidth - 12) left = box.left - tipBox.width - gap;
    if (left < 12) left = Math.max(12, box.left + box.width / 2 - tipBox.width / 2);
    let top = box.top + box.height / 2 - tipBox.height / 2;
    top = Math.min(Math.max(12, top), window.innerHeight - tipBox.height - 12);
    tip.style.left = `${left}px`;
    tip.style.top = `${top}px`;

    svg.classList.add("hovering");
    document.getElementById(`node-${id}`)?.classList.add("hover");
    edges.filter((edge) => edge.from === id || edge.to === id)
      .forEach((edge) => document.getElementById(`edge-${edge.id}`)?.classList.add("hover"));
  }

  function hoverOff() {
    document.getElementById("arch-tip")?.classList.remove("visible");
    if (!svg) return;
    svg.classList.remove("hovering");
    svg.querySelectorAll(".hover").forEach((element) => element.classList.remove("hover"));
  }

  // Side panel ------------------------------------------------------------

  function pin(id) {
    pinnedId = id;
    svg.querySelectorAll(".pinned").forEach((element) => element.classList.remove("pinned"));
    document.getElementById(`node-${id}`)?.classList.add("pinned");
    renderDetail();
  }

  function renderStepList() {
    const list = document.getElementById("arch-steps");
    list.innerHTML = steps.map((step, index) => `
      ${step.group ? `<li class="step-group">${step.group}</li>` : ""}
      <li><button class="arch-step" data-index="${index}" data-arch-go="${index}">
        <span class="arch-step-key">${step.key}</span><span>${step.title}</span>
      </button></li>`).join("");
  }

  function renderDetail() {
    const detail = document.getElementById("arch-detail");
    if (pinnedId) {
      detail.innerHTML = `<div class="detail-eyebrow">SELECTED SERVICE<button class="detail-close" data-arch-unpin aria-label="Close details">×</button></div>${infoMarkup(byId[pinnedId], { full: true })}`;
      return;
    }
    if (currentStep >= 0) {
      const step = steps[currentStep];
      const chips = step.nodes.map((id) => `<button class="detail-chip" data-arch-pin="${id}">${byId[id].title}</button>`).join("");
      detail.innerHTML = `
        <div class="detail-eyebrow">STEP ${step.key}</div>
        <h4>${step.title}</h4>
        <p class="detail-text">${step.text}</p>
        <div class="detail-chips">${chips}</div>`;
      return;
    }
    detail.innerHTML = `
      <div class="detail-eyebrow">HOW TO USE THIS VIEW</div>
      <p class="detail-text">Hover over any service, or its <span class="inline-i">i</span>, to see what it does. Click a service to pin its details here.</p>
      <p class="detail-text">Use <kbd>→</kbd> and <kbd>←</kbd>, or the buttons below, to walk the panel through a request step by step.</p>`;
  }

  function goTo(index) {
    currentStep = Math.max(-1, Math.min(steps.length - 1, index));
    pinnedId = null;
    hoverOff();
    svg.querySelectorAll(".on, .pinned").forEach((element) => element.classList.remove("on", "pinned"));
    svg.classList.toggle("focus-mode", currentStep >= 0);
    svg.querySelectorAll(".arch-edge").forEach((path) => {
      path.setAttribute("marker-end", "url(#arrow)");
      if (path.hasAttribute("marker-start")) path.setAttribute("marker-start", "url(#arrow)");
    });

    if (currentStep >= 0) {
      const step = steps[currentStep];
      step.nodes.forEach((id) => document.getElementById(`node-${id}`)?.classList.add("on"));
      step.edges.forEach((id) => {
        const path = document.getElementById(`edge-${id}`);
        if (!path) return;
        path.classList.add("on");
        path.setAttribute("marker-end", "url(#arrow-on)");
        if (path.hasAttribute("marker-start")) path.setAttribute("marker-start", "url(#arrow-on)");
      });
    }

    document.querySelectorAll(".arch-step").forEach((button) => {
      button.classList.toggle("active", Number(button.dataset.index) === currentStep);
    });
    document.getElementById("arch-counter").textContent = currentStep >= 0
      ? `Step ${currentStep + 1} of ${steps.length}`
      : "Overview";
    document.getElementById("arch-prev").disabled = currentStep < 0;
    document.getElementById("arch-next").textContent = currentStep < 0 ? "Start walkthrough →" : currentStep === steps.length - 1 ? "Finish ✓" : "Next →";
    renderDetail();
  }

  window.archGoTo = goTo;
  window.archNext = () => (currentStep === steps.length - 1 ? goTo(-1) : goTo(currentStep + 1));
  window.archPrev = () => goTo(currentStep - 1);
  window.archReset = () => goTo(-1);
  window.archPin = pin;
  window.archUnpin = () => {
    pinnedId = null;
    svg.querySelectorAll(".pinned").forEach((element) => element.classList.remove("pinned"));
    renderDetail();
  };

  document.addEventListener("keydown", (event) => {
    if (!document.getElementById("screen-architecture")?.classList.contains("active")) return;
    if (["INPUT", "SELECT", "TEXTAREA"].includes(document.activeElement?.tagName)) return;
    if (event.key === "ArrowRight") { event.preventDefault(); window.archNext(); }
    if (event.key === "ArrowLeft") { event.preventDefault(); window.archPrev(); }
    if (event.key === "Escape") window.archReset();
  });
  window.addEventListener("scroll", hoverOff, { passive: true });

  // Buttons rendered into the panel use data attributes instead of inline handlers (strict CSP).
  document.getElementById("screen-architecture")?.addEventListener("click", (event) => {
    const go = event.target.closest("[data-arch-go]");
    const pinButton = event.target.closest("[data-arch-pin]");
    const action = event.target.closest("[data-arch-action]");
    if (go) goTo(Number(go.dataset.archGo));
    else if (pinButton) pin(pinButton.dataset.archPin);
    else if (event.target.closest("[data-arch-unpin]")) window.archUnpin();
    else if (action) ({ prev: window.archPrev, next: window.archNext, reset: window.archReset })[action.dataset.archAction]?.();
  });

  render();
  goTo(-1);
})();
