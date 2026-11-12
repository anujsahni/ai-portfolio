// ContextLoop interactive architecture: five bands, hover cards, act step-through, the Act 4 request flow, and two views.
(function () {
  const BANDS = [
    ["sources", "Sources · synthetic"], ["move", "Move · Fivetran"], ["trust", "Transform & trust · dbt"],
    ["context", "Context · MCP"], ["activate", "Activate"],
  ];
  // kind -> color family; laptop and customer views per node. `use` (Transform & trust, Context, Activate): how this demo uses it, shown on the laptop card.
  const N = [
    { id: "sap", band: "sources", kind: "source", ic: "SAP",
      laptop: ["SAP S/4HANA extract", "Change feed: VBAK · LIKP · VBRK", "An ODP-style change feed of eight SAP tables, with C/U/D change modes, written by the datagen job.", "The ERP holds orders, deliveries and billing, with cryptic names, two currencies and cancelled documents.", "Fivetran SAP connectors (simulated by the Connector SDK here)", "datagen job → data volume"],
      customer: ["SAP S/4HANA", "Fivetran native SAP connectors", "Fivetran's SAP ERP connectors, or a hybrid deployment agent inside the customer's network.", "Replicates ERP tables with deletes and history, without custom extract code.", "Fivetran SAP connectors · hybrid deployment", "Fivetran (SaaS or hybrid)"] },
    { id: "pg", band: "sources", kind: "source", ic: "PG",
      laptop: ["Carrier tracking", "Postgres container", "A real Postgres database with shipments and tracking events, seeded by the generator.", "The actual delivery time lives only here: the key to measuring on-time delivery.", "Database replication", "postgres:17.11-alpine"],
      customer: ["Operational Postgres", "Log-based CDC", "Fivetran's PostgreSQL connector reading the write-ahead log.", "Low-impact, near-real-time replication of a production database.", "Fivetran PostgreSQL connector", "Customer database"] },
    { id: "sf", band: "sources", kind: "source", ic: "SF",
      laptop: ["Salesforce", "Accounts · tiers · renewals", "Synthetic CRM data in the exact layout Fivetran lands it, with history mode on account tier.", "Account IDs don't match SAP; a look-alike duplicate; tiers change mid-quarter.", "Fivetran Salesforce connector (simulated landing)", "sync job"],
      customer: ["Salesforce org", "Fivetran Salesforce connector", "Fivetran's Salesforce connector with history mode on the fields that change.", "Keeps every version of a tier so metrics can use the tier at the time.", "Fivetran Salesforce connector · history mode", "Fivetran"] },
    { id: "zd", band: "sources", kind: "source", ic: "ZD",
      laptop: ["Zendesk", "Support tickets", "Synthetic tickets in Fivetran's Zendesk layout; the sync is held two days behind (trap T6).", "Shipping complaints are tagged inconsistently, and stale tickets mislead.", "Fivetran Zendesk connector (simulated landing)", "sync job"],
      customer: ["Zendesk", "Fivetran Zendesk connector", "Fivetran's Zendesk connector.", "Support signal joined to orders and accounts.", "Fivetran Zendesk connector", "Fivetran"] },
    { id: "sdk", band: "move", kind: "fivetran", ic: "SDK",
      laptop: ["Connector SDK", "SAP + Postgres connectors", "Real Fivetran Connector SDK code run by `fivetran debug`: schema(), update(), upserts, deletes, checkpoints.", "Incremental sync, soft deletes and schema changes, visible in code.", "Fivetran Connector SDK", "sync job · /opt/fivetran"],
      customer: ["Fivetran connectors", "Native or hybrid deployment", "Managed connectors in the Fivetran account, or the hybrid deployment agent for data that must stay on-premises.", "No pipeline code to own; deletes, history and schema drift handled.", "Fivetran managed connectors · hybrid deployment", "Fivetran"] },
    { id: "land", band: "move", kind: "fivetran", ic: "FT",
      laptop: ["Fivetran-shaped landing", "_fivetran_synced · _fivetran_deleted", "Every source lands with Fivetran's system columns; history-mode columns on account tier.", "One consistent raw layer: the columns a naive agent ignores and dbt relies on.", "Fivetran landing conventions", "sync job → warehouse volume"],
      customer: ["Fivetran pipelines", "System columns everywhere", "The same columns, written by Fivetran into the destination.", "Consistent, trustworthy raw data across hundreds of sources.", "Fivetran destinations", "Fivetran"] },
    { id: "log", band: "move", kind: "fivetran", ic: "LOG",
      laptop: ["Sync log", "Freshness · MAR estimate", "One row per sync per connection, plus an estimate of monthly active rows (fivetran_log schema).", "Tells people and agents how fresh each source is.", "Fivetran Platform Connector (shape)", "fivetran_log schema"],
      customer: ["Fivetran Platform Connector", "Logs, usage, MAR", "Fivetran's own metadata: sync history, schema changes and usage.", "Freshness and cost, queryable next to the data.", "Fivetran Platform Connector", "Fivetran"] },
    { id: "duck", band: "trust", kind: "open", ic: "DD", use: "<code>dbt build</code> writes every model into one DuckDB file: raw → staging → marts. Act 1's naive agent runs <code>run_sql</code> on the raw schemas here; the services open <code>serving.db</code>, a read-only copy swapped in after each build.",
      laptop: ["DuckDB warehouse", "Raw and staging", "A local DuckDB file holds the raw schemas and dbt's models; services read a published read-only copy.", "Free and embedded; the SQL patterns carry to any warehouse.", "Destination", "warehouse volume"],
      customer: ["Snowflake · Databricks · BigQuery", "The customer's warehouse", "Fivetran lands directly into the customer's warehouse or lakehouse.", "Use the platform the customer already runs.", "Fivetran destinations", "Customer cloud"] },
    { id: "dbt", band: "trust", kind: "dbt", ic: "dbt", use: "<code>make build</code> runs <code>dbt build</code> (dbt-duckdb): 16 staging, 5 intermediate and 6 mart models. Each trap is fixed in a named model (<code>int_delivery_actuals</code> for T2, <code>int_account_identity</code> for T4) and guarded by a test; marts have enforced contracts. <code>make break TRAP=T1</code> fails a test live.",
      laptop: ["dbt Core", "27 models · tests · contracts", "Staging, intermediate and mart models; every trap handled in a named model and guarded by a test.", "One tested, documented version of each business entity.", "dbt (transformation, tests, contracts, lineage)", "build job"],
      customer: ["dbt platform", "Jobs, CI, docs", "Scheduled jobs and CI on the dbt platform; the same project.", "Trust at scale: tested changes, shared docs and lineage.", "dbt platform", "dbt Labs (SaaS)"] },
    { id: "mf", band: "trust", kind: "dbt", ic: "MF", use: "<code>semantic_models.yml</code> defines five semantic models and eight metrics. The metrics MCP server runs <code>mf query --explain</code>, so MetricFlow writes the SQL; it then runs read-only on the serving copy.",
      laptop: ["Semantic layer", "MetricFlow · 9 metrics", "on_time_delivery_rate, net_revenue, account_risk_flag and more, defined once.", "Gives people and agents definitions instead of guesses.", "dbt Semantic Layer (MetricFlow)", "dbt project · mf"],
      customer: ["dbt Semantic Layer", "Hosted", "The hosted Semantic Layer serves governed metrics to BI tools and agents.", "One definition everywhere: BI and AI agree.", "dbt Semantic Layer", "dbt Labs"] },
    { id: "ice", band: "trust", kind: "open", ic: "IC", use: "After each build, PyIceberg publishes the six marts to <code>northstar.marts</code> through the Iceberg REST catalog; Parquet files land in a RustFS bucket. Every build is a new snapshot.",
      laptop: ["Iceberg lakehouse", "REST catalog + RustFS", "The marts published as Apache Iceberg tables, data files in S3-compatible storage.", "Store once in an open format; read from any engine.", "Open table formats", "iceberg-rest · rustfs"],
      customer: ["Managed Data Lake Service", "Iceberg on S3, ADLS or GCS", "Fivetran writes Iceberg (and Delta) to the customer's object storage, with a catalog.", "No lock-in: every engine reads the same tables.", "Fivetran Managed Data Lake Service", "Customer cloud storage"] },
    { id: "trino", band: "trust", kind: "open", ic: "TR", use: "<code>make lakehouse</code> runs the at-risk query twice on the same Iceberg table: DuckDB (iceberg + httpfs extensions) and Trino's Iceberg connector. Act 3 shows the rows match.",
      laptop: ["Trino", "Second engine", "Reads the same Iceberg tables as DuckDB and returns identical rows.", "Proves the any-engine claim live.", "Open lakehouse engines", "trino (profile lakehouse)"],
      customer: ["Any Iceberg engine", "Snowflake · Databricks · Athena · Trino", "Every engine the customer uses reads the same tables.", "Teams choose tools without copying data.", "Open table formats", "Customer cloud"] },
    { id: "dbtmcp", band: "context", kind: "dbt", ic: "MCP", use: "The official <code>dbt-mcp</code> over streamable HTTP, with only <code>list</code>, <code>get_node_details_dev</code> and <code>get_lineage_dev</code> on. It reads the manifest from the latest build; build, run and SQL tools are off.",
      laptop: ["dbt MCP server", "Models · docs · lineage", "The official dbt-mcp server with its local, read-only project tools.", "The agent can read what a model means and where it came from.", "dbt MCP server", "dbt-mcp container"],
      customer: ["dbt MCP server", "Connected to the dbt platform", "Local or remote dbt MCP with discovery and Semantic Layer tools.", "Model metadata becomes agent context through a standard protocol.", "dbt MCP", "dbt platform"] },
    { id: "mmcp", band: "context", kind: "app", ic: "MCP", use: "Two tools on the Python MCP SDK: <code>list_metrics</code> (definitions, dimensions, filter syntax) and <code>query_metric</code> (MetricFlow-compiled SQL, up to 200 rows, the SQL returned with the result).",
      laptop: ["Metrics MCP server", "list_metrics · query_metric", "Lists the governed definitions; MetricFlow compiles the SQL for every query.", "The agent never invents a metric or writes SQL against the marts.", "Semantic layer through MCP", "mcp-metrics container"],
      customer: ["Semantic Layer via MCP", "dbt MCP semantic tools", "The dbt MCP server's Semantic Layer tools against the hosted Semantic Layer.", "Governed numbers for every agent.", "dbt Semantic Layer · MCP", "dbt platform"] },
    { id: "fmcp", band: "context", kind: "app", ic: "MCP", use: "<code>check_freshness</code> reads the <code>fivetran_log</code> sync history: last success, age, rows and errors per source, against a 24-hour window. Zendesk is held two days behind, so the agent must warn.",
      laptop: ["Freshness MCP server", "check_freshness", "Reads the sync log: last successful sync, age and errors per source.", "The agent can say when data is too old to act on.", "Freshness as context", "mcp-freshness container"],
      customer: ["Freshness context", "Platform Connector · source freshness", "Freshness from the Fivetran Platform Connector and dbt source freshness, exposed to agents.", "Answers carry their own data-age warning.", "Fivetran Platform Connector · dbt", "Customer"] },
    { id: "agent", band: "context", kind: "ai", ic: "C", use: "Act 1: one tool, <code>run_sql</code>, on the raw tables. Act 4: a bridge (<code>mcp_bridge.py</code>) connects to the three MCP servers with the Python MCP client and hands their tools to Claude's tool use.",
      laptop: ["Agent · Claude", "claude-opus-5-5", "The same model in Act 1 (raw SQL) and Act 4 (MCP tools); only the context differs.", "A fair test: same model, same question, different data foundation.", "AI and context engineering", "app container"],
      customer: ["The customer's agent", "Claude via API, Bedrock or Vertex", "Any agent framework that speaks MCP.", "The data foundation is what makes it trustworthy.", "AI and context engineering", "Customer"] },
    { id: "rev", band: "activate", kind: "app", ic: "RE", use: "<code>activation/sync.py</code> reads <code>marts.account_risk</code>, diffs four risk fields against the CRM, shows a dry run, then writes only the changes. Next steps come from the agent's answer (AI-drafted) or the dbt playbook rule.",
      laptop: ["Reverse ETL sync", "Diff-based", "Reads marts.account_risk, compares with the CRM, writes only changes; dry run first.", "Closes the loop: the insight reaches the people who act on it.", "Activation", "app container"],
      customer: ["Fivetran Activations", "Reverse ETL", "Fivetran Activations syncs governed models to business tools.", "No custom sync code; audited, incremental activation.", "Fivetran Activations", "Fivetran"] },
    { id: "crm", band: "activate", kind: "app", ic: "SF", use: "A FastAPI container: accounts with <code>Delivery_Risk__c</code>, <code>Delivery_Risk_Drivers__c</code>, <code>Next_Step__c</code> and <code>Next_Step_Source__c</code>, plus an audit log of every write, shown in Act 5.",
      laptop: ["Mock Salesforce", "Audit log of every write", "A small FastAPI stand-in for the CRM with four delivery-risk fields.", "The account teams see the answer where they already work.", "Activation target", "mock-salesforce container"],
      customer: ["Salesforce org", "Delivery-risk fields", "The customer's real Salesforce org.", "Risk and next steps on the account record.", "Fivetran Activations", "Salesforce"] },
    { id: "slack", band: "activate", kind: "ext", ic: "SL", use: "With <code>SLACK_WEBHOOK_URL</code> set, one summary message is posted; without it, Act 5 shows the message preview and makes no network call.",
      laptop: ["Slack", "Optional webhook", "Posts one summary message if a webhook is set; otherwise shows a preview.", "Alerts the team without another dashboard.", "Activation target", "app container"],
      customer: ["Slack workspace", "Channel alerts", "Activations to Slack.", "Where the account teams already talk.", "Fivetran Activations", "Slack"] },
    { id: "app", band: "app", kind: "app", ic: "ST",
      laptop: ["Streamlit app · 127.0.0.1:8501", "Five acts · architecture · POV scorecard", "The story navigator, replay and live modes, and the side-by-side scores.", "Makes the before-and-after checkable by the audience.", "Presentation", "app container"],
      customer: ["Customer apps and BI", "Dashboards, copilots, CRM", "Wherever the customer consumes governed data and agent answers.", "The same definitions in every surface.", "BI and AI consumers", "Customer"] },
  ];
  const E = [
    ["sap", "sdk"], ["pg", "sdk"], ["sf", "land"], ["zd", "land"], ["sdk", "land"], ["land", "log"], ["land", "duck"],
    ["duck", "dbt"], ["dbt", "mf"], ["dbt", "ice"], ["trino", "ice"],
    ["dbtmcp", "dbt"], ["mmcp", "mf"], ["fmcp", "log"], ["agent", "dbtmcp"], ["agent", "mmcp"], ["agent", "fmcp"],
    ["dbt", "rev"], ["rev", "crm"], ["rev", "slack"], ["agent", "app"], ["rev", "app"], ["agent", "duck", "raw"],
  ];
  const STEPS = [
    { title: "The whole loop", nodes: null, text: "Four sources → <b>Move</b> → <b>Transform and trust</b> → <b>Context</b> → <b>Activate</b>. Use ← and → to walk the acts." },
    { title: "Act 1 · The confident wrong answer", nodes: ["sap", "pg", "sf", "zd", "land", "duck", "agent", "app"], edges: [["agent", "duck"], ["agent", "app"], ["land", "duck"]],
      text: "<b>Act 1.</b> Same model we'll use later, with SQL access to the raw tables. It's fluent, precise and wrong, and nothing in the answer tells you so." },
    { title: "Act 2 · Move", nodes: ["sap", "pg", "sf", "zd", "sdk", "land", "log", "duck"],
      text: "<b>Act 2.</b> Fivetran lands all four systems the same way: incremental, with deletes kept as flags rather than lost, and history kept for the fields that change." },
    { title: "Act 3 · Transform and trust", nodes: ["duck", "dbt", "mf", "ice", "trino"],
      text: "<b>Act 3.</b> dbt turns the raw tables into one tested model, the semantic layer defines each number once, and Iceberg lets any engine read the same data." },
    { title: "Act 4 · Context", nodes: ["dbtmcp", "mmcp", "fmcp", "agent", "dbt", "mf", "log", "app"],
      text: "<b>Act 4.</b> Same model, same question, through the dbt MCP server, a metrics tool and a freshness tool, so it uses Northstar's definitions and says how fresh the data is." },
    { title: "Act 5 · Activate", nodes: ["dbt", "rev", "crm", "slack", "app"],
      text: "<b>Act 5.</b> The at-risk list and next steps go back into the CRM and the channel where the account teams already work." },
    { title: "Act 4 request flow", flow: true, text: "<b>Request flow.</b> Press ▶ to animate the eight steps of the headline question." },
  ];
  const FLOW = [
    [["app", "agent"], "1 · The COO's question arrives from the app."],
    [["agent", "dbtmcp", "mmcp", "fmcp"], "2 · The agent lists its tools from three MCP servers."],
    [["agent", "mmcp", "mf"], "3 · <b>list_metrics</b> (metrics server): reads the definitions, including what “strategic” means."],
    [["agent", "fmcp", "log"], "4 · <b>check_freshness</b> (freshness server): Zendesk is two days behind; it will say so."],
    [["agent", "mmcp", "mf", "dbt"], "5 · <b>query_metric</b>: MetricFlow compiles governed SQL over the tested marts."],
    [["agent", "dbtmcp", "dbt"], "6 · <b>lineage</b> (dbt MCP): where on_time_delivery_rate comes from."],
    [["agent"], "7 · The agent writes the answer: accounts, drivers, next steps, definitions, freshness."],
    [["app"], "8 · The app scores it against the hidden truth, next to Act 1's score."],
  ];

  // Build-up mode: the act that adds each box. Act 1 starts with the sources, a raw copy and the agent; each act adds its layer
  // until Act 5 completes the loop. Every act page shows its own stage of this.
  const ACT_OF = { sap: 1, pg: 1, sf: 1, zd: 1, duck: 1, agent: 1, app: 1, sdk: 2, land: 2, log: 2, dbt: 3, mf: 3, ice: 3, trino: 3,
    dbtmcp: 4, mmcp: 4, fmcp: 4, rev: 5, crm: 5, slack: 5 };
  const BUILD = [
    { name: "Where we start", text: "<b>Act 1 · Where we start.</b> Four source systems, a raw copy of their tables and an AI agent with SQL access. No definitions, no tests, no freshness: the agent has to guess, and it guesses wrong." },
    { name: "+ Move", text: "<b>Act 2 adds Move.</b> Fivetran connectors land all four sources the same way, keeping deletes as flags and history on the fields that change; a sync log records how fresh each source is." },
    { name: "+ Transform and trust", text: "<b>Act 3 adds Transform and trust.</b> dbt turns the raw tables into tested models, the semantic layer defines each metric once, and Iceberg lets a second engine read the same data." },
    { name: "+ Context", text: "<b>Act 4 adds Context.</b> Three MCP servers hand the agent the definitions, the lineage and the freshness. It no longer reads the raw tables." },
    { name: "+ Activate · complete", text: "<b>Act 5 adds Activate, and the loop is complete.</b> A reverse ETL sync writes the at-risk list and next steps into Salesforce and posts to Slack. This is the full architecture." },
  ];

  let view = "laptop", step = 0, pinned = null, flowTimer = null, flowAt = 0;  // flowAt: next request-flow step to show
  let mode = "acts", buildAct = 1;  // mode: "acts" (highlight each act) or "build" (add each act's boxes until the whole loop)
  const root = document.getElementById("arch");
  const byId = Object.fromEntries(N.map((n) => [n.id, n]));

  function nodeHTML(n) {
    const [t, s] = n[view];
    return `<div class="node" id="n-${n.id}" data-id="${n.id}" style="border-color:var(--k-${n.kind})">
      <div class="ic" style="background:var(--b-${n.kind});color:var(--i-${n.kind})">${n.ic}</div>
      <div><div class="t">${t}</div><div class="s">${s}</div></div><div class="stepn"></div></div>`;
  }

  function build() {
    const bands = BANDS.map(([id, label]) => `<div class="band" id="b-${id}"><div class="blabel">${view === "customer" ? label.replace(" · synthetic", "") : label}</div>${N.filter((n) => n.band === id).map(nodeHTML).join("")}</div>`).join("");
    root.querySelector(".bands").innerHTML = bands;
    root.querySelector(".app-row").innerHTML = nodeHTML(byId.app);
    root.querySelector(".netnote").innerHTML = view === "laptop"
      ? "On this laptop: Docker Compose, one private network; only 127.0.0.1:8501 (app), :9001 (RustFS console) and :8080 (Trino) are published."
      : "At a customer: private networking via AWS PrivateLink, Azure Private Link or Google Private Service Connect, SSH tunnels, or hybrid deployment.";
    root.querySelectorAll(".node").forEach((el) => {
      el.addEventListener("mouseenter", () => { if (!pinned && !el.classList.contains("future")) showCard(el.dataset.id); });
      el.addEventListener("mouseleave", () => { if (!pinned) hideCard(); });
      el.addEventListener("click", (ev) => { ev.stopPropagation(); pinned = pinned === el.dataset.id ? null : el.dataset.id;
        root.querySelectorAll(".node").forEach((x) => x.classList.toggle("pinned", x.dataset.id === pinned));
        pinned ? showCard(pinned) : hideCard(); });
    });
    requestAnimationFrame(() => { drawEdges(); apply(); });
  }

  function center(id, side) {
    const c = root.querySelector(".canvas").getBoundingClientRect();
    const r = document.getElementById(`n-${id}`).getBoundingClientRect();
    const x = side === "l" ? r.left : side === "r" ? r.right : r.left + r.width / 2;
    const y = side === "t" ? r.top : side === "b" ? r.bottom : r.top + r.height / 2;
    return [x - c.left, y - c.top];
  }

  function drawEdges() {
    const svg = root.querySelector("svg.edges");
    const order = Object.fromEntries(BANDS.map(([b], i) => [b, i]).concat([["app", 2]]));
    svg.innerHTML = E.map(([a, b, cls]) => {
      if (cls === "raw" && !(mode === "build" ? buildAct <= 3 : step === 1)) return "";  // the agent reads raw tables until Act 4
      const ba = order[byId[a].band], bb = order[byId[b].band];
      let d;
      if (byId[b].band === "app" || byId[a].band === "app") {
        const [x1, y1] = center(a, byId[a].band === "app" ? "t" : "b"), [x2, y2] = center(b, byId[b].band === "app" ? "t" : "b");
        d = `M${x1},${y1} C${x1},${(y1 + y2) / 2} ${x2},${(y1 + y2) / 2} ${x2},${y2}`;
      } else if (ba === bb) {
        const [x1, y1] = center(a, "r"), [x2, y2] = center(b, "r");
        d = `M${x1},${y1} C${x1 + 26},${y1} ${x2 + 26},${y2} ${x2},${y2}`;
      } else {
        const fwd = ba < bb;
        const [x1, y1] = center(a, fwd ? "r" : "l"), [x2, y2] = center(b, fwd ? "l" : "r");
        const mx = (x1 + x2) / 2;
        d = `M${x1},${y1} C${mx},${y1} ${mx},${y2} ${x2},${y2}`;
      }
      return `<path data-a="${a}" data-b="${b}" class="${cls || ""}" d="${d}"/>`;
    }).join("");
  }

  function setHot(ids, edges) {
    const canvas = root.querySelector(".canvas");
    canvas.classList.toggle("dim", !!ids);
    root.querySelectorAll(".node").forEach((el) => el.classList.toggle("hot", !!ids && ids.includes(el.dataset.id)));
    root.querySelectorAll("svg.edges path").forEach((p) => {
      const a = p.dataset.a, b = p.dataset.b;
      const hot = ids && (edges ? edges.some(([x, y]) => (x === a && y === b) || (x === b && y === a)) : ids.includes(a) && ids.includes(b));
      p.classList.toggle("hot", !!hot);
    });
  }

  function applyBuild() {
    stopFlow();
    root.querySelector(".canvas").classList.remove("dim");
    root.querySelectorAll(".node").forEach((el) => {
      const a = ACT_OF[el.dataset.id];
      el.classList.remove("hot", "flow");
      el.classList.toggle("future", a > buildAct);
      el.classList.toggle("new", a === buildAct);
    });
    drawEdges();
    root.querySelectorAll("svg.edges path").forEach((p) => {
      const a = Math.max(ACT_OF[p.dataset.a], ACT_OF[p.dataset.b]);
      p.classList.toggle("future", a > buildAct);
      p.classList.toggle("hot", a === buildAct);
    });
    root.querySelector(".caption").innerHTML = BUILD[buildAct - 1].text;
    root.querySelector(".stepname").textContent = `Act ${buildAct}/5 · ${BUILD[buildAct - 1].name}`;
    root.querySelector(".play").style.display = "none";
  }

  function apply() {
    if (mode === "build") return applyBuild();
    const s = STEPS[step];
    stopFlow();
    root.querySelectorAll(".node").forEach((el) => el.classList.remove("flow", "future", "new"));
    root.querySelector(".caption").innerHTML = s.text;
    root.querySelector(".stepname").textContent = `${step}/${STEPS.length - 1} · ${s.title}`;
    root.querySelector(".play").style.display = s.flow ? "" : "none";
    flowAt = 0; playLabel("Play request flow");
    setHot(s.flow ? FLOW[0][0] : s.nodes, s.edges);
    drawEdges();
    setHot(s.flow ? FLOW[0][0] : s.nodes, s.edges);
  }

  function stopFlow() { if (flowTimer) { clearTimeout(flowTimer); flowTimer = null; } }
  function flowStep(i) {  // show step i (0-based) of the request flow
    const [ids, text] = FLOW[i];
    setHot(ids);
    root.querySelectorAll(".node").forEach((el) => el.classList.remove("flow"));
    ids.forEach((id) => { const el = document.getElementById(`n-${id}`); el.classList.add("flow"); el.querySelector(".stepn").textContent = i + 1; });
    root.querySelector(".caption").innerHTML = `${text} <span class="kbd">· step ${i + 1} of ${FLOW.length}</span>`;
  }
  // Each step stays up long enough to read its description: about 4 to 8 seconds, by length.
  const readMs = (text) => Math.min(8000, Math.max(4000, 1500 + text.replace(/<[^>]+>/g, "").length * 60));
  const PLAY_ICON = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M8 5.5v13l10.5-6.5z"/></svg>';
  const PAUSE_ICON = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><path d="M9 5.5v13M15 5.5v13"/></svg>';
  function playLabel(label, icon = PLAY_ICON) { root.querySelector(".play").innerHTML = `${icon} ${label}`; }
  function playFlow() {  // play from where it stopped; the button pauses, resumes and replays
    if (flowTimer) { stopFlow(); playLabel("Resume"); return; }
    if (flowAt >= FLOW.length) flowAt = 0;
    const tick = () => {
      flowStep(flowAt);
      const wait = readMs(FLOW[flowAt][1]);
      flowAt += 1;
      flowTimer = flowAt < FLOW.length ? setTimeout(tick, wait) : null;
      if (!flowTimer) playLabel("Replay request flow");
    };
    playLabel("Pause", PAUSE_ICON);
    tick();
  }
  function setView(v) {
    view = v; pinned = null; hideCard();
    root.querySelectorAll(".view button").forEach((x) => x.classList.toggle("on", x.dataset.view === v));
    build();
  }

  function showCard(id) {
    const n = byId[id], v = n[view], card = root.querySelector(".card");
    const use = view === "laptop" && n.use ? `<div class="use"><b>In this demo</b>${n.use}</div>` : "";
    card.innerHTML = `<h3>${v[0]}</h3><dl><dt>What</dt><dd>${v[2]}</dd><dt>Why</dt><dd>${v[3]}</dd><dt>Capability</dt><dd>${v[4]}</dd>
      <dt>${view === "laptop" ? "Runs in" : "Runs at"}</dt><dd>${v[5]}</dd></dl>${use}<div class="pin">${pinned ? "Pinned · click again to unpin" : "Click to pin"}</div>`;
    card.style.display = "block";  // shown before measuring, so offsetWidth is real
    const c = root.querySelector(".canvas").getBoundingClientRect(), r = document.getElementById(`n-${id}`).getBoundingClientRect();
    let left = r.right - c.left + 8;
    if (left + card.offsetWidth + 10 > c.width) left = r.left - c.left - card.offsetWidth - 8;
    card.style.left = `${Math.max(0, left)}px`;
    card.style.top = `${Math.max(0, r.top - c.top - 6)}px`;
  }
  function hideCard() { root.querySelector(".card").style.display = "none"; }

  root.querySelector(".prev").onclick = () => {
    if (mode === "build") buildAct = buildAct === 1 ? 5 : buildAct - 1; else step = (step + STEPS.length - 1) % STEPS.length;
    apply();
  };
  root.querySelector(".next").onclick = () => {
    if (mode === "build") buildAct = buildAct === 5 ? 1 : buildAct + 1; else step = (step + 1) % STEPS.length;
    apply();
  };
  function setMode(m) {
    mode = m;
    root.querySelectorAll(".mode button").forEach((x) => x.classList.toggle("on", x.dataset.mode === m));
    apply();
  }
  root.querySelectorAll(".mode button").forEach((b) => (b.onclick = () => setMode(b.dataset.mode)));
  root.querySelector(".play").onclick = playFlow;
  root.querySelectorAll(".view button").forEach((b) => (b.onclick = () => setView(b.dataset.view)));
  root.querySelector(".theme").onclick = () => {
    const html = document.documentElement, dark = html.dataset.theme === "dark" || (!html.dataset.theme && matchMedia("(prefers-color-scheme: dark)").matches);
    html.dataset.theme = dark ? "light" : "dark";
  };
  document.addEventListener("keydown", (e) => {
    if (e.key === "ArrowRight") root.querySelector(".next").click();
    if (e.key === "ArrowLeft") root.querySelector(".prev").click();
  });
  document.addEventListener("click", () => { if (pinned) { pinned = null; hideCard(); root.querySelectorAll(".node").forEach((x) => x.classList.remove("pinned")); } });
  window.addEventListener("resize", () => { drawEdges(); apply(); });
  const params = new URLSearchParams(location.search);
  if (params.get("step")) step = Math.min(STEPS.length - 1, +params.get("step"));
  if (params.get("view") === "customer") { view = "customer"; root.querySelectorAll(".view button").forEach((x) => x.classList.toggle("on", x.dataset.view === "customer")); }
  // ?build=N (or window.__ARCH_INIT = {build: N, embed: true} from an act page) opens the build-up at act N;
  // embed shows just that stage, without the controls.
  const init = Object.assign({}, window.__ARCH_INIT || {});
  if (params.get("build")) init.build = +params.get("build");
  if (params.has("embed")) init.embed = true;
  if (init.build) {
    buildAct = Math.min(5, Math.max(1, init.build)); mode = "build";
    root.querySelectorAll(".mode button").forEach((x) => x.classList.toggle("on", x.dataset.mode === "build"));
  }
  if (init.embed && init.build) {
    root.classList.add("embed");
    root.querySelector(".top h1 span").textContent = buildAct === 5 ? "The complete architecture"
      : buildAct === 1 ? "The architecture at Act 1: where we start" : `The architecture after Act ${buildAct}`;
  }
  build();
  // Hooks for scripted use (the pitch video drives the page frame by frame through these).
  window.__arch = { steps: STEPS.length, nodes: N.length, flowSteps: FLOW.length, setStep: (i) => { mode = "acts"; step = i; apply(); }, playFlow, flowStep,
    setBuild: (n) => { mode = "build"; buildAct = n; apply(); },
    setView, showCard: (id) => (id ? showCard(id) : hideCard()) };
})();
