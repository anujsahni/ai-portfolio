// WeekendWise web client (MVP-07). Talks only to this app's own server (/api/*).
// No credentials, model calls, or database calls happen in the browser.
"use strict";

const screenTitles = {
  plan: "Plan a trip",
  working: "Putting it together",
  itinerary: "Your itinerary",
  sources: "Sources & notes",
  architecture: "Architecture",
};
const DEFAULT_ROUTE = "plan";
const CLIENT_TIMEOUT_MS = 180000; // the server stops at 150 s; this is a safety net
const STORAGE_KEY = "weekendwise:last-plan";

const CITY_ART = {
  "san-francisco": { title: "City days,<br />coastal air." },
  portland: { title: "Coffee, books<br />&amp; gardens." },
  "santa-cruz": { title: "Boardwalk days,<br />redwood shade." },
  "napa-valley": { title: "Vines and<br />valley light." },
};
const CATEGORY_PIN = {
  "food-coffee": ["☕", "coffee-pin"],
  activities: ["◫", "art-pin"],
  stays: ["⌂", "local-pin"],
  "local-transit": ["↘", "food-pin"],
};
const STAGES = [
  { node: "normalize", label: "Getting a feel for your trip" },
  { node: "conditions", label: "Checking simulated local conditions", optional: true },
  { node: "retrieve", label: "Finding places you’ll love" },
  { node: "draft", label: "Putting your days together" },
  { node: "review", label: "Checking sources and budget" },
];

let config = null;
let current = null; // { request, response }
let inFlight = null;
let toastTimer;

// ------------------------------------------------------------------ helpers

const $ = (id) => document.getElementById(id);
const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const money = (n) => `$${Math.round(Number(n) || 0).toLocaleString("en-US")}`;
const parseDate = (iso) => new Date(`${iso}T12:00:00`);
const monthDay = (iso) => parseDate(iso).toLocaleDateString("en-US", { month: "short", day: "numeric" });

function dateRange(dates) {
  if (!dates?.length) return "";
  const first = parseDate(dates[0]);
  const last = parseDate(dates[dates.length - 1]);
  const month = first.toLocaleDateString("en-US", { month: "short" });
  const sameMonth = first.getMonth() === last.getMonth();
  const end = sameMonth ? last.getDate() : last.toLocaleDateString("en-US", { month: "short", day: "numeric" });
  return dates.length === 1 ? `${month} ${first.getDate()}, ${first.getFullYear()}` : `${month} ${first.getDate()}–${end}, ${last.getFullYear()}`;
}

function showToast(message) {
  const toast = $("toast");
  toast.textContent = message;
  toast.classList.add("visible");
  window.clearTimeout(toastTimer);
  toastTimer = window.setTimeout(() => toast.classList.remove("visible"), 3200);
}

function showAlert(title, items = [], tone = "error") {
  const box = $("form-alert");
  box.className = `form-alert ${tone}`;
  box.innerHTML = `<strong>${esc(title)}</strong>${items.length ? `<ul>${items.map((i) => `<li>${esc(i)}</li>`).join("")}</ul>` : ""}`;
  box.hidden = false;
  box.scrollIntoView({ behavior: "smooth", block: "center" });
}

const clearAlert = () => { $("form-alert").hidden = true; };

// ------------------------------------------------------------------ routing

const routeFor = (name) => (name === "working" ? DEFAULT_ROUTE : name);
const urlFor = (route) => `/${route}`;

function showScreen(name, { updateUrl = true } = {}) {
  if (!screenTitles[name]) return;
  document.querySelectorAll(".screen").forEach((screen) => screen.classList.remove("active"));
  $(`screen-${name}`)?.classList.add("active");
  document.querySelectorAll("[data-nav]").forEach((item) => {
    item.classList.toggle("active", item.dataset.nav === name || (name === "working" && item.dataset.nav === "plan"));
  });
  $("topbar-title").textContent = screenTitles[name];
  document.title = `${screenTitles[name]} · WeekendWise`;
  const url = urlFor(routeFor(name));
  if (updateUrl && window.location.pathname !== url) history.pushState(null, "", url);
  window.scrollTo({ top: 0, behavior: updateUrl ? "smooth" : "auto" });
}

function routeFromUrl() {
  const fromHash = window.location.hash.replace(/^#\/?/, "");
  const raw = fromHash || window.location.pathname.replace(/^\/+/, "");
  const name = raw.split(/[/?]/)[0].toLowerCase();
  return screenTitles[name] && name !== "working" ? name : DEFAULT_ROUTE;
}

function showScreenFromUrl() {
  const target = routeFromUrl();
  showScreen(target, { updateUrl: false });
  if (window.location.pathname !== urlFor(target) || window.location.hash) history.replaceState(null, "", urlFor(target));
}

// ------------------------------------------------------------------ plan form

function selectedCity() {
  return config.cities.find((c) => c.id === $("destination").value) || config.cities[0];
}

function renderInspiration() {
  const city = selectedCity();
  const art = CITY_ART[city.id] || { title: esc(city.name) };
  $("inspiration").className = `inspiration-card city-${city.id}`;
  $("inspiration-caption").textContent = `${city.name}, ${city.state}`.toUpperCase();
  $("inspiration-image").setAttribute("aria-label", `Illustration of ${city.name}`);
  $("inspiration-title").innerHTML = art.title;
  $("inspiration-text").textContent = city.tagline;
  $("inspiration-meta").innerHTML = `<span>☀ ${esc(city.weatherShort)}</span><span>◷ 2–3 days is just right</span>`;
  const others = config.cities.filter((c) => c.id !== city.id);
  $("suggestions").innerHTML = `<span class="suggestion-label">${others.some((c) => c.trending) ? "TRENDING" : "ALSO TRY"}</span>`
    + others.map((c) => `<button type="button" class="suggestion-chip" data-city="${esc(c.id)}">${esc(c.name)}</button>`).join("");
}

function setInterests(ids) {
  document.querySelectorAll(".interest-chip").forEach((chip) => {
    const on = ids.includes(chip.dataset.id);
    chip.classList.toggle("selected", on);
    chip.setAttribute("aria-pressed", String(on));
  });
}

function setBudget(value) {
  $("budget").value = value;
  const range = $("budget-range");
  if (value >= Number(range.min) && value <= Number(range.max)) range.value = value;
}

function fillForm(req) {
  $("destination").value = req.cityId;
  $("start-date").value = req.startDate;
  $("end-date").value = req.endDate;
  $("travelers").value = String(req.travelers);
  setBudget(req.budget);
  setInterests(req.interestIds || []);
  $("notes").value = [...(req.constraints || []), req.notes || ""].filter(Boolean).join(" ");
  renderInspiration();
}

function readForm() {
  const city = selectedCity();
  const text = $("notes").value.trim();
  return {
    destination: city.name,
    cityId: city.id,
    startDate: $("start-date").value,
    endDate: $("end-date").value,
    travelers: Number($("travelers").value),
    budget: Number($("budget").value),
    currency: "USD",
    interestIds: Array.from(document.querySelectorAll(".interest-chip.selected")).map((c) => c.dataset.id),
    constraints: text ? [text.slice(0, 200)] : [],
    notes: text.length > 200 ? text : "",
  };
}

function validate(req) {
  const errors = [];
  if (!req.startDate || !req.endDate) errors.push("Choose a start and end date.");
  else {
    const days = Math.round((parseDate(req.endDate) - parseDate(req.startDate)) / 86400000) + 1;
    if (days < 1) errors.push("The end date is before the start date.");
    else if (days > config.limits.maxTripDays) errors.push(`Trips can be at most ${config.limits.maxTripDays} days.`);
  }
  if (!Number.isFinite(req.budget) || req.budget < config.limits.minBudget || req.budget > config.limits.maxBudget) {
    errors.push(`Budget must be between ${money(config.limits.minBudget)} and ${money(config.limits.maxBudget)}.`);
  }
  if (!req.interestIds.length) errors.push("Pick at least one interest so we can find matching guides.");
  return errors;
}

// ------------------------------------------------------------------ progress

function renderProgress(steps, { includeConditions }) {
  const stages = STAGES.filter((s) => !s.optional || includeConditions);
  const doneNodes = new Set(steps.map((s) => (s.node === "revise" ? "draft" : s.node)));
  const firstOpen = stages.findIndex((s) => !doneNodes.has(s.node));
  $("progress-list").innerHTML = stages.map((stage, index) => {
    const step = [...steps].reverse().find((s) => s.node === stage.node);
    let cls = "";
    let marker = '<span class="step-empty"></span>';
    let status = "";
    if (step) {
      const ok = step.status === "done";
      cls = ok ? " complete" : " warn";
      marker = ok ? '<span class="step-check">✓</span>' : '<span class="step-check warn">!</span>';
      status = ok ? "DONE" : step.status === "skipped" ? "SKIPPED" : "CHECK";
    } else if (index === firstOpen) {
      cls = " current";
      marker = '<span class="step-loader"></span>';
      status = "IN PROGRESS";
    }
    const detail = step && step.label !== stage.label ? `<em>${esc(step.label)}</em>` : "";
    return `<div class="progress-step${cls}">${marker}<span>${esc(stage.label)}${detail}</span><small>${status}</small></div>`;
  }).join("");
}

// ------------------------------------------------------------------ planning request

async function startPlanning(event) {
  event.preventDefault();
  clearAlert();
  const req = readForm();
  const errors = validate(req);
  if (errors.length) return showAlert("Please check your trip details", errors);

  const weatherRe = new RegExp(config.weatherPattern, "i");
  const includeConditions = weatherRe.test(req.constraints.join(" ") + " " + req.notes);
  const steps = [];
  $("working-destination").textContent = req.destination;
  $("working-dates").textContent = dateRange([req.startDate, req.endDate]);
  $("working-budget").textContent = money(req.budget);
  renderProgress(steps, { includeConditions });
  showScreen("working");
  $("submit-button").disabled = true;

  const controller = new AbortController();
  inFlight = controller;
  const timer = window.setTimeout(() => controller.abort("timeout"), CLIENT_TIMEOUT_MS);
  let response = null;
  let failure = null;
  let requestId = "";
  try {
    const res = await fetch("/api/plan", {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
      body: JSON.stringify(req),
      signal: controller.signal,
    });
    requestId = res.headers.get("X-Request-ID") || "";
    if (!res.ok || !res.body) {
      const body = await res.json().catch(() => ({}));
      requestId = body.requestId || requestId;
      failure = { title: body.message || "The planner couldn’t take this request.", items: body.errors || [] };
    } else {
      for await (const { event: name, data } of readEvents(res.body)) {
        if (name === "step") {
          steps.push(data);
          if (data.node === "conditions") renderProgress(steps, { includeConditions: true });
          else renderProgress(steps, { includeConditions: includeConditions || steps.some((s) => s.node === "conditions") });
        } else if (name === "result") {
          response = data;
        } else if (name === "error") {
          failure = { title: data.message || "Something went wrong.", items: data.hint ? [data.hint] : [] };
        }
      }
    }
  } catch (err) {
    if (controller.signal.aborted && controller.signal.reason === "edit") return; // user went back to edit
    failure = controller.signal.aborted
      ? { title: "The planner took too long to answer.", items: ["Please try again in a moment."] }
      : { title: "We couldn’t reach the planner.", items: ["Check your connection and try again."] };
  } finally {
    window.clearTimeout(timer);
    if (inFlight === controller) inFlight = null;
    $("submit-button").disabled = false;
  }
  if (response) response.requestId = requestId;
  if (failure && requestId) failure.items = [...failure.items, `Reference: ${requestId}`];
  handleResult(req, response, failure);
}

async function* readEvents(stream) {
  const reader = stream.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += value;
    let split;
    while ((split = buffer.indexOf("\n\n")) >= 0) {
      const block = buffer.slice(0, split);
      buffer = buffer.slice(split + 2);
      let name = "message";
      let data = "";
      for (const line of block.split("\n")) {
        if (line.startsWith("event:")) name = line.slice(6).trim();
        else if (line.startsWith("data:")) data += line.slice(5).trim();
      }
      if (data) yield { event: name, data: JSON.parse(data) };
    }
  }
}

function handleResult(req, response, failure) {
  if (failure || !response) {
    showScreen("plan");
    return showAlert(failure?.title || "The planner didn’t return a plan.", failure?.items || ["Please try again."]);
  }
  if (response.status === "complete") {
    current = { request: req, response };
    try { sessionStorage.setItem(STORAGE_KEY, JSON.stringify(current)); } catch { /* storage full or disabled */ }
    renderItinerary();
    renderSources();
    return showScreen("itinerary");
  }
  showScreen("plan");
  if (response.status === "invalid_request") return showAlert("Please check your trip details", response.errors || []);
  if (response.status === "needs_clarification") return showAlert("We need a little more to go on", [response.question], "info");
  return showAlert(response.message || "The planner couldn’t finish this plan.", ["Please try again."]);
}

// ------------------------------------------------------------------ itinerary

// One card per guide: several cited passages from the same guide are shown together.
function sourceGroups() {
  const groups = [];
  const byId = {};
  (current?.response.citations || []).forEach((c) => {
    let g = byId[c.sourceId];
    if (!g) {
      g = byId[c.sourceId] = { number: groups.length + 1, sourceId: c.sourceId, title: c.title, contentType: c.contentType,
        lastReviewed: c.lastReviewed, excerpts: [], usedFor: [], chunkIds: [] };
      groups.push(g);
    }
    g.excerpts.push(c.excerpt);
    g.chunkIds.push(c.chunkId);
    c.usedFor.split(", ").forEach((u) => { if (u && !g.usedFor.includes(u)) g.usedFor.push(u); });
  });
  return groups;
}

function sourceIndex() {
  const map = {};
  sourceGroups().forEach((g) => g.chunkIds.forEach((id) => { map[id] = g; }));
  return map;
}

function renderItinerary() {
  const { request: req, response: r } = current;
  const idx = sourceIndex();
  $("itinerary-empty").hidden = true;
  $("itinerary-content").hidden = false;
  $("result-destination").textContent = r.tripSummary.destination;
  $("result-headline").textContent = r.headline;
  $("result-dates").textContent = `▦ ${dateRange(r.tripSummary.dates).toUpperCase()}`;
  $("result-travelers").textContent = `♧ ${r.tripSummary.travelers} TRAVELER${r.tripSummary.travelers === 1 ? "" : "S"}`;
  $("result-city").textContent = `⌖ ${r.tripSummary.destination.toUpperCase()}`;
  const condDay = r.days.find((d) => d.conditions);
  const toolCall = r.toolCalls?.[0];
  $("result-conditions").textContent = condDay
    ? `☁ Simulated conditions for ${monthDay(condDay.date)} · not a forecast`
    : toolCall ? "☁ Conditions couldn’t be checked for that date" : "☁ No conditions check requested";

  const banner = $("review-banner");
  const review = r.review || {};
  if (review.outcome === "approved_with_warnings") {
    banner.className = "review-banner warn";
    banner.innerHTML = `<strong>Our reviewer still had concerns.</strong> Double-check these before relying on the plan:<ul>${review.issues.map((i) => `<li>${esc(i)}</li>`).join("")}</ul>`;
    banner.hidden = false;
  } else if (review.outcome === "approved_after_revision") {
    banner.className = "review-banner info";
    banner.innerHTML = `<strong>Reviewed and revised once.</strong> The first draft had ${review.issues.length || "a few"} issue(s), which were fixed.`;
    banner.hidden = false;
  } else banner.hidden = true;

  $("day-tabs").innerHTML = r.days.map((d, i) => {
    const day = parseDate(d.date);
    return `<button class="day-tab${i === 0 ? " active" : ""}" role="tab" data-day="${i}" aria-selected="${i === 0}"><span>${day.toLocaleDateString("en-US", { weekday: "short" }).toUpperCase()}</span><strong>${day.getDate()}</strong></button>`;
  }).join("") + `<span class="day-tabs-caption">${r.days.length} thoughtfully unhurried day${r.days.length === 1 ? "" : "s"}</span>`;

  $("day-plans").innerHTML = r.days.map((d, i) => {
    const cond = d.conditions;
    const intro = cond
      ? `<span class="day-weather">${esc(cond.label)}</span><h2>${esc(d.title)}</h2><p>${esc(cond.summary)} (simulated)</p>`
      : `<h2>${esc(d.title)}</h2><p>${esc(parseDate(d.date).toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric" }))}</p>`;
    const acts = d.activities.length ? d.activities.map((a) => activityCard(a, idx)).join("")
      : '<p class="lead compact empty-day">No sourced activities for this day. Leave it open, or edit your trip.</p>';
    return `<div class="day-plan${i === 0 ? " active" : ""}" data-day-plan="${i}"><div class="day-intro">${intro}</div>${acts}</div>`;
  }).join("");

  const notes = [
    ["Couldn’t answer from the guides", r.unansweredRequests],
    ["Worth double-checking", r.uncertainties],
    ["We assumed", r.assumptions],
  ].filter(([, items]) => items?.length);
  $("plan-notes").innerHTML = notes.map(([title, items]) => `<div><strong>${esc(title)}</strong><ul>${items.map((i) => `<li>${esc(i)}</li>`).join("")}</ul></div>`).join("");
  $("plan-notes").hidden = !notes.length;

  const b = r.budget;
  const over = b.status === "over-budget";
  $("result-budget-status").textContent = b.statusLabel;
  $("result-budget-status").classList.toggle("over-budget", over);
  $("result-estimate").textContent = money(b.total);
  $("result-budget").textContent = `of ${money(b.limit)}`;
  $("result-budget-meter").style.width = `${Math.min(100, Math.round((b.total / b.limit) * 100))}%`;
  $("result-budget-meter").classList.toggle("over", over);
  const labels = Object.fromEntries(config.budgetCategories.map((c) => [c.id, c.label]));
  $("budget-rows").innerHTML = b.lineItems.map((li) => `<div title="${esc(li.note)}"><span>${esc(labels[li.categoryId] || li.categoryId)}${li.categoryId === "stays" ? " <small>estimate</small>" : ""}</span><strong>${money(li.amountUsd)}</strong></div>`).join("");
  $("substitutions").innerHTML = b.substitutions?.length ? `<strong>Ways to bring it under budget</strong><ul>${b.substitutions.map((s) => `<li>${esc(typeof s === "string" ? s : s.suggestion || s.description || JSON.stringify(s))}</li>`).join("")}</ul>` : "";
  $("substitutions").hidden = !b.substitutions?.length;
  $("budget-footnote").textContent = `${b.footnote} · for ${r.tripSummary.travelers} traveler${r.tripSummary.travelers === 1 ? "" : "s"}`;
  $("result-why").textContent = r.whyThisFits;

  $("trace-items").innerHTML = r.trace.map((t) => `<div class="trace-item"><span class="trace-check${t.status === "done" ? "" : " warn"}">${t.status === "done" ? "✓" : "!"}</span><span>${esc(t.label)}</span></div>`).join("");
  const u = r.usage;
  $("trace-foot").textContent = `Gemini on Vertex AI · ${u.modelCalls} model call${u.modelCalls === 1 ? "" : "s"} · ${u.toolCalls} tool call${u.toolCalls === 1 ? "" : "s"} · ${u.retrievalQueries} searches · ${(u.elapsedMs / 1000).toFixed(1)} s${r.requestId ? ` · ref ${r.requestId}` : ""}`;
}

function activityCard(a, idx) {
  const [icon, pin] = CATEGORY_PIN[a.categoryId] || ["✳", "coffee-pin"];
  const label = (config.budgetCategories.find((c) => c.id === a.categoryId)?.label || "Activity").toUpperCase();
  const time = String(a.time || "").match(/^(\d{1,2}:\d{2})\s*(AM|PM)?$/i);
  const timeHtml = time ? `${esc(time[1])} <small>${esc((time[2] || "").toUpperCase())}</small>` : `<small>${esc(a.time)}</small>`;
  const cost = a.estimatedCostUsd > 0 ? `≈ ${money(a.estimatedCostUsd)} total` : "Free / no cost listed";
  const groups = [...new Map(a.citations.filter((c) => idx[c]).map((c) => [idx[c].number, idx[c]])).values()];
  const sources = groups.map((g) => `<button data-source="${esc(g.sourceId)}" title="${esc(g.title)}">Source ${g.number} ↗</button>`).join("");
  return `<article class="activity-card"><div class="activity-time">${timeHtml}</div><div class="activity-pin ${pin}">${icon}</div><div class="activity-content"><div class="activity-type">${esc(label)}${a.area ? ` · ${esc(a.area.toUpperCase())}` : ""}</div><h3>${esc(a.title)}</h3><p>${esc(a.description)}</p><div class="activity-tags">${a.area ? `<span>⌖ ${esc(a.area)}</span>` : ""}<span>${cost} · estimate</span>${sources}</div></div></article>`;
}

function selectDay(index) {
  document.querySelectorAll(".day-tab").forEach((tab) => {
    const on = tab.dataset.day === String(index);
    tab.classList.toggle("active", on);
    tab.setAttribute("aria-selected", String(on));
  });
  document.querySelectorAll(".day-plan").forEach((day) => day.classList.toggle("active", day.dataset.dayPlan === String(index)));
}

// ------------------------------------------------------------------ sources

function renderSources() {
  const r = current.response;
  const groups = sourceGroups();
  const kind = (t) => (t || "guide").split("-")[0].toUpperCase();
  const clip = (t) => `${esc(t)}${t.length >= 240 ? "…" : ""}`;
  $("source-list").innerHTML = groups.length ? groups.map((g) => `
    <article class="source-card" id="src-${esc(g.sourceId)}"><div class="source-number">${String(g.number).padStart(2, "0")}</div>
      <div class="source-content"><div class="source-category">SAMPLE ${esc((g.contentType || "guide").replace(/-/g, " ").toUpperCase())} · REVIEWED ${esc(g.lastReviewed)}</div>
        <h2>${esc(g.title)}</h2>${g.excerpts.map((e) => `<p>${clip(e)}</p>`).join("")}
        <div class="source-meta"><span>Used for: ${esc(g.usedFor.join("; "))}</span><span class="source-score">${esc(g.sourceId)}</span></div></div>
      <span class="source-kind">${esc(kind(g.contentType))}</span></article>`).join("")
    : '<p class="lead">This plan has no cited sources.</p>';
  const notes = [...(r.notes || []), ...(r.caveats || [])];
  $("source-limits").innerHTML = `<p>Recommendations come only from the ${groups.length} sample guide${groups.length === 1 ? "" : "s"} listed here, found by meaning-based search in Firestore and written up by Gemini. Our reviewer checks that every suggestion cites one of them.</p><ul>${notes.map((n) => `<li>${esc(n)}</li>`).join("")}</ul>`;
}

function openSource(sourceId) {
  showScreen("sources");
  const card = document.getElementById(`src-${sourceId}`);
  if (!card) return;
  document.querySelectorAll(".source-card.highlight").forEach((c) => c.classList.remove("highlight"));
  card.classList.add("highlight");
  window.setTimeout(() => card.scrollIntoView({ behavior: "smooth", block: "center" }), 120);
}

function itineraryText() {
  const r = current.response;
  const lines = [`${r.tripSummary.destination}: ${r.headline}`, dateRange(r.tripSummary.dates), ""];
  r.days.forEach((d) => {
    lines.push(`${parseDate(d.date).toDateString()}: ${d.title}`);
    d.activities.forEach((a) => lines.push(`  ${a.time} ${a.title} (${a.area}), about ${money(a.estimatedCostUsd)}`));
  });
  lines.push("", `Estimated total ${money(r.budget.total)} of ${money(r.budget.limit)} (${r.budget.statusLabel}).`, ...r.caveats);
  return lines.join("\n");
}

// ------------------------------------------------------------------ wiring

document.addEventListener("click", (event) => {
  const nav = event.target.closest("a[data-nav], a.brand");
  if (nav && !(event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || event.button !== 0)) {
    event.preventDefault();
    return showScreen(nav.dataset.nav || DEFAULT_ROUTE);
  }
  const target = event.target.closest("[data-action], [data-city], [data-source], [data-day], .interest-chip, [data-sample]");
  if (!target) return;
  if (target.dataset.city) { $("destination").value = target.dataset.city; renderInspiration(); return; }
  if (target.dataset.source) return openSource(target.dataset.source);
  if (target.dataset.day) return selectDay(Number(target.dataset.day));
  if (target.dataset.sample) {
    const sample = config.samples.find((s) => s.id === target.dataset.sample);
    if (sample) { fillForm(sample.request); clearAlert(); showToast(`Loaded sample: ${sample.title}`); }
    return;
  }
  if (target.classList.contains("interest-chip")) {
    const on = target.classList.toggle("selected");
    target.setAttribute("aria-pressed", String(on));
    return;
  }
  switch (target.dataset.action) {
    case "edit":
      if (inFlight) inFlight.abort("edit");
      if (current) fillForm(current.request);
      return showScreen("plan");
    case "sources": return showScreen("sources");
    case "itinerary": return showScreen("itinerary");
    case "help": return showToast("Sample guides and simulated conditions only. Plans come from Gemini on Vertex AI. No bookings are made.");
    case "copy":
      navigator.clipboard?.writeText(itineraryText()).then(() => showToast("Itinerary copied as text"), () => showToast("Couldn’t copy. Your browser blocked clipboard access."));
  }
});

window.addEventListener("popstate", showScreenFromUrl);
window.addEventListener("hashchange", showScreenFromUrl);
$("trip-form").addEventListener("submit", startPlanning);
$("destination").addEventListener("change", renderInspiration);
$("budget-range").addEventListener("input", (e) => { $("budget").value = e.target.value; });
$("budget").addEventListener("input", (e) => setBudget(Number(e.target.value)));

async function init() {
  showScreenFromUrl();
  try {
    const res = await fetch("/api/config");
    if (!res.ok) throw new Error(String(res.status));
    config = await res.json();
  } catch {
    showAlert("The app couldn’t load its settings.", ["Refresh the page in a moment."]);
    $("submit-button").disabled = true;
    return;
  }
  $("destination").innerHTML = config.cities.map((c) => `<option value="${esc(c.id)}">${esc(c.name)}</option>`).join("");
  $("interest-chips").innerHTML = config.interests.map((i) => `<button type="button" class="interest-chip${i.selectedByDefault ? " selected" : ""}" aria-pressed="${i.selectedByDefault}" data-id="${esc(i.id)}">${esc(i.icon)} ${esc(i.label)}</button>`).join("");
  $("sample-chips").innerHTML = config.samples.map((s) => `<button type="button" class="suggestion-chip" data-sample="${esc(s.id)}" title="${esc(s.title)}">${esc(s.short)}</button>`).join("");
  $("start-date").value = config.defaults.startDate;
  $("end-date").value = config.defaults.endDate;
  renderInspiration();
  try {
    const saved = JSON.parse(sessionStorage.getItem(STORAGE_KEY) || "null");
    if (saved?.response?.status === "complete") { current = saved; renderItinerary(); renderSources(); fillForm(saved.request); }
  } catch { /* ignore a corrupt saved plan */ }
}

init();
