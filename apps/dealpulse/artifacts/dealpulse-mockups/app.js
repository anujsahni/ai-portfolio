// DealPulse clickable mockup: routing, persona rules and page rendering.
// Data: window.DEALPULSE_DATA (synthetic CRM + real model scores), window.DEALPULSE_BRIEFS (sample briefs).
(() => {
  const D = window.DEALPULSE_DATA;
  const BRIEFS = window.DEALPULSE_BRIEFS || {};
  const TRACE = window.DEALPULSE_TRACE || [];
  const PAGES = ["pipeline", "deal", "sources", "model", "architecture"];
  const TITLES = { pipeline: "Pipeline", deal: "Deal brief", sources: "Sources", model: "Model", architecture: "Architecture" };
  const FEATURED = "006DP0000000007"; // Northbeam Logistics Group: Commit, model 17%
  const dealsById = Object.fromEntries(D.deals.map((d) => [d.id, d]));
  const notesById = {};
  D.deals.forEach((d) => d.notes.forEach((n) => { notesById[n.id] = { ...n, dealId: d.id }; }));

  const store = {
    get(key, fallback) { try { return localStorage.getItem(`dealpulse:${key}`) ?? fallback; } catch { return fallback; } },
    set(key, value) { try { localStorage.setItem(`dealpulse:${key}`, value); } catch { /* storage unavailable */ } },
  };
  const defaultPersona = D.personas.find((p) => p.name === "Priya Raman")?.id || D.personas[0].id;
  const state = {
    persona: store.get("persona", defaultPersona),
    deal: store.get("deal", FEATURED),
    forecast: "All",
    flaggedOnly: false,
    owner: "All",
    driverMode: "actionable",
    highlight: null,
  };

  // ------------------------------------------------------------ helpers
  const $ = (sel) => document.querySelector(sel);
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const money = (n) => (n >= 1e6 ? `$${(n / 1e6).toFixed(2)}M` : `$${Math.round(n / 1000).toLocaleString("en-US")}k`);
  const moneyFull = (n) => `$${Math.round(n).toLocaleString("en-US")}`;
  const shortDate = (iso) => new Date(`${iso}T12:00:00Z`).toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" });
  const longDate = (iso) => new Date(`${iso}T12:00:00Z`).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric", timeZone: "UTC" });
  const persona = () => D.personas.find((p) => p.id === state.persona) || D.personas[0];
  const forecastPill = (f) => `<span class="pill ${f === "Commit" ? "commit" : f === "Best Case" ? "best" : "pipeline"}">${esc(f)}</span>`;
  const shortStage = (s) => s.replace("/Price Quote", "").replace("/Review", "");

  function visibleDeals() {
    const p = persona();
    return D.deals.filter((d) => (p.manager ? d.team === p.team : d.ownerId === p.id));
  }
  function canSee(deal) {
    const p = persona();
    return p.manager ? deal.team === p.team : deal.ownerId === p.id;
  }
  function toast(message) {
    const el = $("#toast");
    el.textContent = message;
    el.classList.add("show");
    clearTimeout(toast.timer);
    toast.timer = setTimeout(() => el.classList.remove("show"), 2200);
  }
  function citeChip(id) {
    const shared = id.startsWith("PB-") || id.startsWith("PO-");
    return `<a class="cite${shared ? " shared" : ""}" href="#sources" data-cite="${esc(id)}" title="${shared ? esc(D.knowledge[id]?.title) : "Activity note"}">${esc(id.startsWith("00") ? id.slice(-4) : id)}</a>`;
  }

  // ------------------------------------------------------------ routing
  function currentPage() {
    const name = location.hash.replace(/^#/, "");
    return PAGES.includes(name) ? name : "pipeline";
  }
  function route() {
    const page = currentPage();
    document.querySelectorAll(".screen").forEach((s) => s.classList.toggle("active", s.id === `screen-${page}`));
    document.querySelectorAll(".nav-item").forEach((a) => a.classList.toggle("active", a.dataset.nav === page));
    $("#topbar-title").textContent = TITLES[page];
    document.title = `${TITLES[page]} · DealPulse Mockup`;
    ({ pipeline: renderPipeline, deal: renderDeal, sources: renderSources, model: renderModel, architecture: () => {} })[page]();
    if (page !== "sources") window.scrollTo(0, 0);
  }

  // ------------------------------------------------------------ persona
  function renderPersona() {
    const select = $("#persona");
    const managers = D.personas.filter((p) => p.manager);
    const reps = D.personas.filter((p) => !p.manager);
    select.innerHTML = `<optgroup label="Sales managers">${managers.map((p) => `<option value="${p.id}">${esc(p.name)} · ${esc(p.team)}</option>`).join("")}</optgroup>`
      + `<optgroup label="Account executives">${reps.map((p) => `<option value="${p.id}">${esc(p.name)} · ${esc(p.team)}</option>`).join("")}</optgroup>`;
    select.value = state.persona;
    const p = persona();
    $("#persona-note").textContent = p.manager
      ? `Sees the ${p.team} team's ${visibleDeals().length} open deals. Simulated sign-in.`
      : `Sees only their own ${visibleDeals().length} open deals. Simulated sign-in.`;
  }
  $("#persona").addEventListener("change", (e) => {
    state.persona = e.target.value;
    state.owner = "All";
    store.set("persona", state.persona);
    renderPersona();
    route();
    toast(`Viewing as ${persona().name}`);
  });

  // ------------------------------------------------------------ pipeline
  function renderPipeline() {
    const p = persona();
    const all = visibleDeals();
    $("#pipeline-lead").textContent = p.manager
      ? `${all.length} open deals for the ${p.team} team this quarter, with each rep's forecast next to the model's win probability.`
      : `Your ${all.length} open deals this quarter, with your forecast next to the model's win probability.`;
    $("#gap-points").textContent = D.gapPoints;

    const owners = [...new Set(all.map((d) => d.owner))].sort();
    const ownerSel = $("#owner-filter");
    ownerSel.innerHTML = `<option value="All">All owners</option>${owners.map((o) => `<option${o === state.owner ? " selected" : ""}>${esc(o)}</option>`).join("")}`;
    ownerSel.parentElement.style.display = p.manager ? "" : "none";

    const total = all.reduce((s, d) => s + d.amount, 0);
    const stageWeighted = all.reduce((s, d) => s + d.amount * d.stageProbability / 100, 0);
    const modelWeighted = all.reduce((s, d) => s + d.amount * d.modelProbability / 100, 0);
    const flagged = all.filter((d) => d.flag);
    const commit = all.filter((d) => d.forecast === "Commit");
    $("#kpis").innerHTML = `
      <div class="kpi"><span class="kpi-label">Open pipeline</span><span class="kpi-value">${money(total)}</span><span class="kpi-sub">${all.length} deals · ${commit.length} in Commit</span></div>
      <div class="kpi"><span class="kpi-label">Forecast by stage</span><span class="kpi-value">${money(stageWeighted)}</span><span class="kpi-sub">Amount × Salesforce stage probability</span></div>
      <div class="kpi"><span class="kpi-label">Forecast by model</span><span class="kpi-value">${money(modelWeighted)}</span><span class="kpi-sub">${modelWeighted < stageWeighted ? `${money(stageWeighted - modelWeighted)} below` : `${money(modelWeighted - stageWeighted)} above`} the stage view</span></div>
      <div class="kpi risk"><span class="kpi-label">Model disagrees</span><span class="kpi-value">${flagged.length}</span><span class="kpi-sub">${money(flagged.reduce((s, d) => s + d.amount, 0))} forecast as Commit or Best Case</span></div>`;

    document.querySelectorAll("#forecast-filter .chip").forEach((c) => c.classList.toggle("active", c.dataset.forecast === state.forecast));
    $("#flagged-only").checked = state.flaggedOnly;
    const rows = all.filter((d) => (state.forecast === "All" || d.forecast === state.forecast)
      && (!state.flaggedOnly || d.flag) && (state.owner === "All" || d.owner === state.owner));
    $("#deal-table tbody").innerHTML = rows.length ? rows.map((d) => `
      <tr class="${d.flag ? "flagged" : ""}" data-deal="${d.id}" tabindex="0" aria-label="Open the brief for ${esc(d.account)}">
        <td><div class="deal-name">${esc(d.account)}</div><div class="deal-sub">${esc(d.product)} · ${esc(d.type)}</div></td>
        <td>${esc(d.owner)}</td>
        <td class="num">${moneyFull(d.amount)}</td>
        <td>${esc(shortStage(d.stage))}</td>
        <td class="mono">${shortDate(d.closeDate)}</td>
        <td>${forecastPill(d.forecast)}</td>
        <td>
          <div class="compare">
            <div class="compare-row"><span>Stage</span><div class="bar stage"><span style="width:${d.stageProbability}%"></span></div><span class="num">${d.stageProbability}%</span></div>
            <div class="compare-row"><span>Model</span><div class="bar model"><span style="width:${d.modelProbability}%"></span></div><span class="num">${d.modelProbability}%</span></div>
          </div>
        </td>
        <td>${d.flag ? `<span class="pill risk">Model disagrees</span><div class="risk-text">${esc(d.topRisk || "")}</div>` : `<span class="risk-text">${esc(d.topRisk || "—")}</span>`}</td>
      </tr>`).join("") : `<tr><td colspan="8" class="risk-text">No deals match these filters.</td></tr>`;
  }
  $("#forecast-filter").addEventListener("click", (e) => {
    const chip = e.target.closest(".chip");
    if (!chip) return;
    state.forecast = chip.dataset.forecast;
    renderPipeline();
  });
  $("#flagged-only").addEventListener("change", (e) => { state.flaggedOnly = e.target.checked; renderPipeline(); });
  $("#owner-filter").addEventListener("change", (e) => { state.owner = e.target.value; renderPipeline(); });
  function openDeal(id) {
    state.deal = id;
    store.set("deal", id);
    location.hash = "deal";
  }
  $("#deal-table").addEventListener("click", (e) => { const tr = e.target.closest("tr[data-deal]"); if (tr) openDeal(tr.dataset.deal); });
  $("#deal-table").addEventListener("keydown", (e) => {
    const tr = e.target.closest("tr[data-deal]");
    if (tr && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); openDeal(tr.dataset.deal); }
  });

  // ------------------------------------------------------------ deal brief
  function driverList(deal) {
    const list = deal.drivers.filter((d) => state.driverMode === "all" || d.actionable).slice(0, 6);
    const max = Math.max(0.01, ...deal.drivers.map((d) => Math.abs(d.effect)));
    return list.map((d) => {
      const width = Math.round(50 * Math.abs(d.effect) / max);
      return `<div class="driver"><span class="driver-text">${d.effect < 0 ? "↓" : "↑"} ${esc(d.text)}</span>
        <span class="driver-bar" title="${d.effect > 0 ? "Raises" : "Lowers"} the score (${d.effect.toFixed(2)} log-odds)"><span class="${d.effect < 0 ? "down" : "up"}" style="width:${width}%"></span></span></div>`;
    }).join("") || `<p class="hint">No strong factors you can act on; see all factors.</p>`;
  }

  function renderDeal() {
    const root = $("#deal-root");
    const deal = dealsById[state.deal] || dealsById[FEATURED];
    if (!canSee(deal)) {
      root.innerHTML = `<h1 id="deal-title">Deal not available</h1>
        <div class="notice block">${esc(persona().name)} can't view <b>${esc(deal.account)}</b>: it belongs to ${esc(deal.owner)}${persona().manager ? ` on the ${esc(deal.team)} team` : ""}.
        DealPulse checks access before it loads any notes or calls any model.</div>
        <p><a href="#pipeline">Back to your pipeline</a></p>`;
      return;
    }
    const brief = BRIEFS[deal.id];
    const gap = deal.modelProbability - deal.stageProbability;
    const p = persona();
    const trace = TRACE.map(([title, detail]) => `<li><div>${esc(title)}<small>${esc(detail
      .replace("{persona}", p.name).replace("{owner}", deal.owner).replace("{notes}", deal.notes.length)
      .replace("{model}", deal.modelProbability).replace("{stage}", deal.stageProbability))}</small></div></li>`).join("");
    const listItems = (items, cls) => `<ul class="brief-list ${cls}">${items.map((it) => `<li><span>${esc(it.text)}</span>
      <span class="item-meta">${it.owner ? `<span class="pill quiet">${esc(it.owner)}</span>` : ""}${it.driver ? `<span class="pill quiet">Driver: ${esc(it.driver)}</span>` : ""}${(it.citations || []).map(citeChip).join("")}</span></li>`).join("")}</ul>`;

    const briefHtml = brief ? `
      <div class="card brief">
        <div class="section-head"><h2>Deal brief</h2><span class="pill quiet">Sample · written by hand for the mockup</span></div>
        <p class="brief-summary">${esc(brief.summary)}</p>
        <h3>Risks</h3>${listItems(brief.risks, "risks")}
        ${brief.strengths ? `<h3 style="margin-top:14px">What's going well</h3>${listItems(brief.strengths, "strengths")}` : ""}
        <h3 style="margin-top:14px">Recommended next steps</h3>${listItems(brief.nextSteps, "steps")}
        <h3 style="margin-top:14px">Open questions</h3><ul class="facts-list">${brief.openQuestions.map((q) => `<li>${esc(q)}</li>`).join("")}</ul>
      </div>
      <div class="card crm-box">
        <div class="section-head"><h2>Draft Salesforce update</h2><span class="pill warn">Review before pasting</span></div>
        <div class="crm-field"><label for="crm-next">Next Step</label><textarea id="crm-next" rows="2" maxlength="255">${esc(brief.crmUpdate.nextStep)}</textarea><span class="char-count" id="crm-next-count"></span></div>
        <div class="crm-field"><label for="crm-desc">Description</label><textarea id="crm-desc" rows="4">${esc(brief.crmUpdate.description)}</textarea></div>
        <div class="button-row"><button class="primary-button" id="copy-crm">Copy both fields</button><span class="hint">DealPulse never writes to Salesforce. The rep pastes and saves.</span></div>
      </div>
      <div class="card">
        <h2>Ask about this deal</h2>
        <form class="ask-form" id="ask-form">
          <input id="ask-input" aria-label="Question about this deal" placeholder="e.g. ${esc(brief.qa[0].q)}" autocomplete="off" />
          <button class="primary-button" type="submit">Ask</button></form>
        <div class="suggestions">${brief.qa.map((x) => `<button class="suggestion" data-q="${esc(x.q)}">${esc(x.q)}</button>`).join("")}
          <button class="suggestion" data-q="Rank my reps by performance and tell me who to fire.">Rank my reps…</button></div>
        <div id="answer"></div>
      </div>` : `
      <div class="card empty-state">
        <h2>Deal brief</h2>
        <p class="lead">In the live app DealPulse writes a cited brief for this deal in about 15–25 seconds: summary, risks, next steps and a draft Salesforce update. This mockup includes sample briefs for three deals.</p>
        <div class="button-row">${["006DP0000000007", "006DP0000000001", "006DP0000000003"].filter((id) => canSee(dealsById[id]))
          .map((id) => `<button class="secondary-button" data-open="${id}">${esc(dealsById[id].account)}</button>`).join("") || `<span class="hint">Switch to Priya Raman (West) to see them.</span>`}</div>
      </div>`;

    root.innerHTML = `
      <div class="deal-head">
        <div>
          <div class="eyebrow">${esc(deal.industry)} · ${esc(deal.segment)} · ${esc(deal.type)}</div>
          <h1 id="deal-title">${esc(deal.account)}</h1>
          <div class="deal-facts">
            <span class="fact"><span>Amount</span><b class="mono">${moneyFull(deal.amount)}</b></span>
            <span class="fact"><span>Stage</span><b>${esc(deal.stage)}</b></span>
            <span class="fact"><span>Close</span><b class="mono">${longDate(deal.closeDate)}</b></span>
            <span class="fact"><span>Forecast</span>${forecastPill(deal.forecast)}</span>
            <span class="fact"><span>Owner</span><b>${esc(deal.owner)}</b></span>
            ${deal.competitor ? `<span class="fact"><span>Competitor</span><b>${esc(deal.competitor)}</b></span>` : ""}
            ${deal.discount ? `<span class="fact"><span>Discount</span><b class="mono">${deal.discount}%</b></span>` : ""}
          </div>
        </div>
      </div>
      <div class="deal-layout">
        <div class="deal-side">
          <div class="card score-card${deal.flag ? " flagged" : ""}">
            <div class="section-head"><h3>Win probability</h3>${deal.flag ? `<span class="pill risk">Model disagrees</span>` : gap >= 10 ? `<span class="pill good">Above stage</span>` : `<span class="pill quiet">Close to stage</span>`}</div>
            <div class="score-big"><span class="value">${deal.modelProbability}%</span><span class="vs">model<br />vs. <b class="mono">${deal.stageProbability}%</b> for ${esc(shortStage(deal.stage))}</span></div>
            <p class="score-note">An estimate from deals like this one, not a promise. It doesn't change the forecast category.</p>
            <div>
              <div class="section-head"><h3>Why</h3><span class="drivers-tabs">
                <button class="link-button" data-mode="actionable" ${state.driverMode === "actionable" ? 'aria-pressed="true" style="font-weight:600"' : ""}>What you can act on</button> ·
                <button class="link-button" data-mode="all" ${state.driverMode === "all" ? 'aria-pressed="true" style="font-weight:600"' : ""}>All factors</button></span></div>
              <div class="drivers" id="drivers">${driverList(deal)}</div>
            </div>
          </div>
          <div class="card"><h3>How this brief was made</h3><ol class="trace">${trace}</ol></div>
        </div>
        <div class="deal-main">
          ${briefHtml}
          <div class="card">
            <div class="section-head"><h2>Latest notes</h2><span class="hint">${deal.notes.length} on this deal</span></div>
            ${deal.notes.length ? `<ul class="notes-list">${deal.notes.slice(0, 5).map((n) => `<li><span class="item-meta"><span class="mono">${longDate(n.date)}</span> · ${esc(n.type)} · ${esc(n.author)} · ${esc(n.contact)}, ${esc(n.contactTitle)} ${citeChip(n.id)}</span><span>${esc(n.text)}</span></li>`).join("")}</ul>`
              : `<div class="notice">No activity notes on this deal yet. The brief would say evidence is missing rather than guess.</div>`}
          </div>
        </div>
      </div>`;

    const next = $("#crm-next");
    if (next) {
      const count = () => { $("#crm-next-count").textContent = `${next.value.length} / 255`; };
      next.addEventListener("input", count);
      count();
    }
  }

  $("#deal-root").addEventListener("click", (e) => {
    const mode = e.target.closest("[data-mode]");
    const open = e.target.closest("[data-open]");
    const suggestion = e.target.closest("[data-q]");
    const cite = e.target.closest("[data-cite]");
    if (mode) { state.driverMode = mode.dataset.mode; renderDeal(); }
    else if (open) { state.deal = open.dataset.open; store.set("deal", state.deal); renderDeal(); }
    else if (suggestion) { $("#ask-input").value = suggestion.dataset.q; answer(suggestion.dataset.q); }
    else if (cite) { state.highlight = cite.dataset.cite; }
    else if (e.target.id === "copy-crm") {
      const text = `Next Step: ${$("#crm-next").value}\n\nDescription: ${$("#crm-desc").value}`;
      navigator.clipboard.writeText(text).then(() => toast("Copied. Paste into the opportunity in Salesforce."),
        () => toast("Copy was blocked here; select the text and copy it instead."));
    }
  });
  $("#deal-root").addEventListener("submit", (e) => {
    if (e.target.id !== "ask-form") return;
    e.preventDefault();
    answer($("#ask-input").value.trim());
  });

  function answer(question) {
    const deal = dealsById[state.deal];
    const brief = BRIEFS[deal.id];
    const out = $("#answer");
    if (!question) { out.innerHTML = ""; return; }
    const q = question.toLowerCase();
    if (/\b(rank|fire|worst|weak|performance review)\b/.test(q) && /\b(rep|reps|executive|salesperson|marcus|elena|sam|grace|tom|aisha)\b/.test(q)) {
      out.innerHTML = `<div class="notice block"><b>Blocked by Guardrails.</b> DealPulse can't judge or rank individual employees. Ask about a deal instead.</div>`;
      return;
    }
    if (/ignore (all )?(prior|previous) instructions|system:/.test(q)) {
      out.innerHTML = `<div class="notice block"><b>Blocked by Guardrails.</b> This looks like an instruction aimed at the assistant. Rephrase the question about the deal.</div>`;
      return;
    }
    const match = brief?.qa.find((x) => x.q.toLowerCase() === q) || brief?.qa.find((x) => q.split(/\W+/).filter((w) => w.length > 4).some((w) => x.q.toLowerCase().includes(w)));
    out.innerHTML = match
      ? `<div class="answer">${esc(match.a)} <span class="item-meta">${match.citations.map(citeChip).join("")}</span></div>`
      : `<div class="answer">In the live app Claude answers from this deal's notes and the shared playbook only, with citations (MVP-08). This mockup has a sample answer for: <i>${esc(brief?.qa[0].q || "")}</i></div>`;
  }

  // ------------------------------------------------------------ sources
  function renderSources() {
    const root = $("#sources-root");
    const deal = dealsById[state.deal] || dealsById[FEATURED];
    const brief = BRIEFS[deal.id];
    if (!canSee(deal)) {
      root.innerHTML = `<h1 id="sources-title">Sources</h1><div class="notice block">${esc(persona().name)} can't view this deal's sources.</div>`;
      return;
    }
    const uses = {};
    if (brief) {
      const add = (list, label) => list?.forEach((it, i) => (it.citations || []).forEach((c) => { (uses[c] ||= []).push(`${label} ${i + 1}`); }));
      add(brief.risks, "Risk"); add(brief.strengths, "Strength"); add(brief.nextSteps, "Next step"); add(brief.qa, "Answer");
    }
    const ids = Object.keys(uses);
    const dealIds = ids.filter((id) => id.startsWith("00"));
    const sharedIds = ids.filter((id) => !id.startsWith("00"));
    const card = (id) => {
      if (id.startsWith("00")) {
        const n = notesById[id];
        return `<article class="card source-card${state.highlight === id ? " highlight" : ""}" id="src-${id}">
          <div class="source-top"><span class="type-badge">${esc(n.type)} note</span><span class="mono source-meta">${esc(id)}</span></div>
          <p class="source-text">${esc(n.text)}</p>
          <div class="source-meta">${longDate(n.date)} · ${esc(n.author)} · with ${esc(n.contact)}, ${esc(n.contactTitle)}</div>
          <div class="item-meta">Cited in: ${uses[id].map((u) => `<span class="pill quiet">${esc(u)}</span>`).join("")}</div></article>`;
      }
      const k = D.knowledge[id];
      return `<article class="card source-card${state.highlight === id ? " highlight" : ""}" id="src-${id}">
        <div class="source-top"><span class="type-badge ${k.kind}">${k.kind === "playbook" ? "Playbook" : "Pricing policy"}</span><span class="mono source-meta">${esc(id)}</span></div>
        <h3>${esc(k.title)}</h3>
        <p class="source-text">${esc(k.text.slice(0, 420))}${k.text.length > 420 ? "…" : ""}</p>
        <div class="item-meta">Cited in: ${uses[id].map((u) => `<span class="pill quiet">${esc(u)}</span>`).join("")}</div></article>`;
    };
    root.innerHTML = `
      <div class="page-head"><div>
        <div class="eyebrow">EVIDENCE BEHIND THE BRIEF</div>
        <h1 id="sources-title">Sources for ${esc(deal.account)}</h1>
        <p class="lead">Every claim in the brief links to one of these. Deal notes come only from this opportunity; shared guidance is the same for every deal. Sources are shown from the records themselves, never from the model's text.</p>
      </div></div>
      ${brief ? `<div class="source-groups">
        <div><h2>This deal's notes <span class="hint">(${dealIds.length})</span></h2><div class="source-grid">${dealIds.map(card).join("")}</div></div>
        <div><h2>Shared guidance <span class="hint">(${sharedIds.length})</span></h2><div class="source-grid">${sharedIds.map(card).join("")}</div></div>
      </div>` : `<div class="notice">This deal has no sample brief in the mockup, so nothing is cited yet. Open Northbeam Logistics Group, Harborline Freight or Silverpine Retail Group from the Pipeline.</div>`}`;
    if (state.highlight) {
      document.getElementById(`src-${state.highlight}`)?.scrollIntoView({ block: "center" });
      state.highlight = null;
    }
  }

  // ------------------------------------------------------------ model
  const FEATURE_LABELS = {
    stage_index: "Stage", days_to_close: "Days to close date", days_in_stage: "Days in current stage", deal_age_days: "Deal age",
    close_pushes: "Close-date slips", log_amount: "Deal size", competitor_present: "Competitor in deal",
    exec_meeting_last_30d: "Executive meeting (30 days)", champion_identified: "Champion identified",
    activities_last_30d: "Activities (30 days)", days_since_last_activity: "Days since last activity", activity_trend_30d: "Activity trend",
    contact_roles: "Contacts engaged", economic_buyer_identified: "Economic buyer identified", discount_pct: "Discount %",
    is_expansion: "Expansion deal", segment_enterprise: "Enterprise segment", open_severe_cases: "Open severe cases",
  };
  const featureLabel = (f) => FEATURE_LABELS[f] || f.replace(/^lead_/, "Lead source: ").replace(/^industry_/, "Industry: ")
    .replace(/^product_/, "Product: ").replace(/^segment_/, "Segment: ").replace(/_/g, " ");
  const TIMING = new Set(["stage_index", "days_to_close", "days_in_stage", "deal_age_days"]);

  function calibrationChart(model) {
    const W = 360, H = 260, L = 50, B = 34, T = 12, R = 14;
    const x = (v) => L + v * (W - L - R);
    const y = (v) => H - B - v * (H - B - T);
    const pts = (rows) => rows.filter((r) => r.n >= 20 && r.mean_predicted != null);
    const line = (rows) => pts(rows).map((r, i) => `${i ? "L" : "M"}${x(r.mean_predicted).toFixed(1)},${y(r.observed_rate).toFixed(1)}`).join(" ");
    const ticks = [0, 0.25, 0.5, 0.75, 1];
    return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Calibration chart: predicted probability against observed win rate on the held-out quarter, for the model and the stage-probability baseline">
      ${ticks.map((t) => `<line class="grid" x1="${x(0)}" x2="${x(1)}" y1="${y(t)}" y2="${y(t)}" /><text x="${L - 8}" y="${y(t) + 4}" text-anchor="end">${Math.round(t * 100)}%</text>
        <text x="${x(t)}" y="${H - B + 16}" text-anchor="middle">${Math.round(t * 100)}%</text>`).join("")}
      <line class="axis" x1="${x(0)}" x2="${x(1)}" y1="${y(0)}" y2="${y(0)}" /><line class="axis" x1="${x(0)}" x2="${x(0)}" y1="${y(0)}" y2="${y(1)}" />
      <line class="diag" x1="${x(0)}" y1="${y(0)}" x2="${x(1)}" y2="${y(1)}" />
      <path class="base-line" d="${line(model.baseline_calibration)}" />${pts(model.baseline_calibration).map((r) => `<circle class="base-dot" cx="${x(r.mean_predicted)}" cy="${y(r.observed_rate)}" r="3" />`).join("")}
      <path class="model-line" d="${line(model.calibration)}" />${pts(model.calibration).map((r) => `<circle class="model-dot" cx="${x(r.mean_predicted)}" cy="${y(r.observed_rate)}" r="3.5"><title>${Math.round(r.mean_predicted * 100)}% predicted, ${Math.round(r.observed_rate * 100)}% won (${r.n} rows)</title></circle>`).join("")}
      <text x="${(L + W - R) / 2}" y="${H - 4}" text-anchor="middle" class="label-strong">Predicted win probability</text>
      <text transform="translate(12 ${(T + H - B) / 2}) rotate(-90)" text-anchor="middle" class="label-strong">Actually won</text>
    </svg>`;
  }

  function renderModel() {
    const root = $("#model-root");
    const m = D.model;
    if (!m) { root.innerHTML = `<h1 id="model-title">Model</h1><div class="notice">No evaluation report found. Run make train, then rebuild the mockup data.</div>`; return; }
    const effects = m.feature_effects.slice(0, 12);
    const maxShap = effects[0].mean_abs_shap;
    root.innerHTML = `
      <div class="page-head"><div>
        <div class="eyebrow">MODEL CARD · VERSION 1</div>
        <h1 id="model-title">Can you trust the score?</h1>
        <p class="lead">An XGBoost model trained on SageMaker with ${m.rows.train.toLocaleString("en-US")} point-in-time snapshots of ${m.deals.train.toLocaleString("en-US")} closed deals, tested on the newest quarter it never saw (${esc(m.quarters.test[0])}, ${m.deals.test} deals). Synthetic data: these numbers show the method works, not how it would do on your pipeline.</p>
      </div></div>
      <div class="metric-tiles">
        <div class="kpi metric"><span class="kpi-label">Ranking (AUC)</span><span class="kpi-value">${m.model.auc.toFixed(3)}</span><span class="better">vs. ${m.baseline_stage_probability.auc.toFixed(3)} for stage probability</span></div>
        <div class="kpi metric"><span class="kpi-label">Probability error (Brier)</span><span class="kpi-value">${m.model.brier.toFixed(3)}</span><span class="better">vs. ${m.baseline_stage_probability.brier.toFixed(3)}; lower is better</span></div>
        <div class="kpi metric"><span class="kpi-label">Test quarter win rate</span><span class="kpi-value">${(m.test_win_rate * 100).toFixed(1)}%</span><span class="kpi-sub">${m.rows.test.toLocaleString("en-US")} snapshots</span></div>
        <div class="kpi metric"><span class="kpi-label">Status</span><span class="kpi-value" style="font-size:18px">Pending approval</span><span class="kpi-sub">A person approves before it serves</span></div>
      </div>
      <div class="model-grid">
        <div class="card chart">
          <div class="section-head"><h2>Does 30% mean 30%?</h2></div>
          ${calibrationChart(m)}
          <div class="legend"><span><i></i>Model</span><span><i class="base"></i>Salesforce stage probability</span><span>Dashed diagonal = perfect</span></div>
          <p class="score-note" style="margin-top:8px">Bands with fewer than 20 rows are hidden. One band (50–60%) under-predicts: 55% predicted, 66% won.</p>
        </div>
        <div class="card">
          <div class="section-head"><h2>What moves the score</h2><span class="hint">mean |SHAP|, held-out quarter</span></div>
          <div class="importance">${effects.map((e) => `<div class="importance-row"><span>${e.direction === -1 ? "↓" : e.direction === 1 ? "↑" : "·"} ${esc(featureLabel(e.feature))}</span>
            <div class="bar${TIMING.has(e.feature) ? " timing" : ""}"><span style="width:${(100 * e.mean_abs_shap / maxShap).toFixed(0)}%"></span></div><span class="num">${e.mean_abs_shap.toFixed(2)}</span></div>`).join("")}</div>
          <p class="score-note" style="margin-top:10px">Grey bars are stage and timing: a deal's progress partly reflects the other factors, so they rank first. Blue factors are what a rep can change.</p>
        </div>
        <div class="card">
          <h2>What it uses and what it doesn't</h2>
          <ul class="facts-list">
            <li>35 features from stage history, close-date changes, contact roles, activities, discounts, competitors and support cases, rebuilt as of each snapshot date.</li>
            <li><b>Not used:</b> the rep's name or win rate (the score rates the deal, not the person), Salesforce's probability and forecast category (the baseline it is compared with), and note text.</li>
            <li>Split by close quarter, so no deal appears in both training and testing.</li>
          </ul>
        </div>
        <div class="card">
          <h2>Limits</h2>
          <ul class="facts-list">
            <li>Trained on synthetic data with a known hidden rule; a real pipeline needs retraining on a Salesforce export.</li>
            <li>It weighs stage heavily: a late-stage deal with weak engagement can still score high. The brief's evidence is the check.</li>
            <li>Advisory only. It never changes a forecast category or writes to the CRM.</li>
          </ul>
        </div>
      </div>`;
  }

  // ------------------------------------------------------------ start
  document.addEventListener("click", (e) => {
    const cite = e.target.closest("[data-cite]");
    if (cite) state.highlight = cite.dataset.cite;
  }, true);
  window.addEventListener("hashchange", route);
  renderPersona();
  route();
})();
