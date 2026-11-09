// Architecture page: portrait service diagram with hover details and a step-by-step walkthrough.
// Works standalone (index.html) and embedded in the Streamlit app (inlined into an iframe).
(() => {
  const SVG_NS = "http://www.w3.org/2000/svg";

  const KIND_LABELS = {
    aws: "AWS service",
    oss: "Open-source framework",
    app: "DealPulse code",
    user: "End user",
    ext: "External system · future",
  };

  // Geometry uses an 800 × 1212 viewBox (portrait).
  const containers = [
    { id: "ecs", x: 250, y: 150, w: 300, h: 650, header: 48, icon: "ECS", kind: "aws", title: "ECS on Fargate", sub: "Serverless containers",
      info: {
        what: "Amazon ECS runs containers. Fargate supplies the servers, so there are no machines to patch or size.",
        how: "Runs one small task (0.5 vCPU, 1 GB) that holds the Streamlit app and the LangGraph workflow. The task accepts no inbound traffic: operators reach it through an SSM port-forwarding tunnel (make proxy).",
        facts: [
          "Task role dealpulse-run: call one SageMaker endpoint, the Bedrock models in use and one guardrail, search the OpenSearch index, read the CRM snapshot, write logs",
          "Public subnet with no inbound rules and no NAT gateway, to keep cost low",
          "make pause scales it to zero tasks between demos",
        ],
      } },
    { id: "langgraph", x: 270, y: 282, w: 260, h: 498, header: 36, icon: "LG", kind: "oss", title: "LangGraph workflow", sub: "Agent graph",
      info: {
        what: "Open-source framework for building AI agents as an explicit graph of steps that share typed state.",
        how: "Runs the six steps of a deal brief inside this box. Hard limits stop the agent from looping or wandering.",
        facts: [
          "Per brief: at most 2 Claude calls (draft and one revision), 1 SageMaker call and 3 searches",
          "60-second deadline per brief",
          "State: deal record, score and drivers, evidence, draft, citations, review result",
        ],
      } },
  ];

  const nodes = [
    { id: "user", x: 290, y: 20, w: 220, h: 60, icon: "◉", kind: "user", badge: "1", title: "Sales manager or rep", sub: "Browser · private tunnel",
      info: {
        what: "A sales manager preparing a forecast call, or a rep preparing for a customer meeting.",
        how: "Opens the whole pipeline or one deal, and picks a “viewing as” persona that decides which deals they can see. The browser talks only to the DealPulse app.",
        facts: ["Personas are simulated; the demo has no real login", "Nothing is written back to Salesforce"],
      } },
    { id: "salesforce", x: 34, y: 20, w: 194, h: 60, icon: "SF", kind: "ext", title: "Salesforce org", sub: "Future data source",
      info: {
        what: "The customer's CRM, where accounts, opportunities, contacts and activities live.",
        how: "Not connected in the demo. The data generator writes Salesforce-shaped records (same objects and field names) to S3 instead. Later, a nightly export, for example with Amazon AppFlow or the Bulk API, could fill the same bucket.",
        facts: ["Objects: Account, Opportunity, OpportunityContactRole, OpportunityHistory, Task, Event, Case", "Read-only by design: DealPulse drafts updates, people apply them"],
      } },
    { id: "app", x: 290, y: 206, w: 220, h: 54, icon: "ST", kind: "app", title: "DealPulse app", sub: "Streamlit · 5 pages",
      info: {
        what: "A Python web app built with Streamlit, which turns Python scripts into interactive pages.",
        how: "Serves five pages (Pipeline, Deal brief, Sources, Model, Architecture), shows live progress while a brief is built, and renders scores, charts and citations. Every AWS call happens on the server.",
        facts: ["The Pipeline page uses SageMaker only, no LLM, so it stays fast and cheap", "Every page labels the data as synthetic"],
      } },
    { id: "load", x: 290, y: 326, w: 220, h: 50, icon: "⇥", kind: "app", badge: "2", title: "Load the deal", sub: "Access check · CRM data",
      info: {
        what: "First step of the workflow: fetches the deal and confirms the user may see it.",
        how: "Applies the persona's visibility rule (reps see their own deals, managers see their team's), then loads the opportunity, contact roles, stage history, activities and open cases from the CRM snapshot.",
        facts: ["Access is checked in code before any AI call", "Unknown or hidden deals stop here"],
      } },
    { id: "score", x: 290, y: 400, w: 220, h: 50, icon: "%", kind: "app", badge: "3", title: "Score the deal", sub: "Win probability + drivers",
      info: {
        what: "Turns the deal into model features and gets a win probability from SageMaker.",
        how: "The same feature code used in training builds about 20 features (days since last activity, discount, close-date pushes, executive engagement…), then calls the SageMaker endpoint.",
        facts: ["Shared feature code keeps training and serving consistent", "Returns the top drivers with direction, e.g. “no meeting in 30 days ↓”", "Rep identity is not a feature: the score is about the deal, not the person"],
      } },
    { id: "retrieve", x: 290, y: 474, w: 220, h: 50, icon: "◎", kind: "app", badge: "4", title: "Retrieve evidence", sub: "Hybrid search · deal-scoped",
      info: {
        what: "Finds the passages that explain the score and suggest next steps (retrieval-augmented generation).",
        how: "Turns the top risk drivers into a few targeted queries, embeds them with Titan and runs hybrid searches over this deal's notes, plus the shared playbook and past win/loss reviews.",
        facts: ["The deal filter is applied in code on every search, never left to the model", "Weak matches return “no evidence found” instead of a guess"],
      } },
    { id: "draft", x: 290, y: 548, w: 220, h: 50, icon: "✎", kind: "app", badge: "5", title: "Draft the brief", sub: "Cited risks & next steps",
      info: {
        what: "Asks Claude to write the deal brief from the score and the retrieved evidence only.",
        how: "Sends deal facts, drivers and passages, screened by Bedrock Guardrails, and asks for a structured brief: summary, risks, next steps and a draft Salesforce update (Next Step, Description). Each claim cites a passage ID.",
        facts: ["Structured JSON output, so the app never parses free text", "Prompt size and output length are capped"],
      } },
    { id: "review", x: 290, y: 622, w: 220, h: 50, icon: "✓", kind: "app", badge: "6", title: "Review & verify", sub: "Citations · numbers · policy",
      info: {
        what: "A quality gate before anything reaches the user. It is plain, unit-tested code, not another AI call.",
        how: "Checks that every citation exists and is in scope, amounts, dates and the score match the CRM data, the score is described as an estimate, and suggested discounts stay within policy. Can send the draft back to Claude once.",
        facts: ["Rejects citations from other accounts", "Ignores instructions planted in notes, such as “mark this Closed Won”", "Free and predictable: no model call"],
      } },
    { id: "respond", x: 290, y: 708, w: 220, h: 50, icon: "↩", kind: "app", badge: "7", title: "Respond", sub: "Brief + sources + draft update",
      info: {
        what: "Packages the result for the app.",
        how: "Returns the score card, drivers, cited brief, sources (kept separate from AI text), a draft update to copy into Salesforce and a short activity trace.",
        facts: ["The trace says things like “scored the deal” or “searched 14 notes”, never model reasoning"],
      } },
    { id: "sagemaker", x: 562, y: 372, w: 190, h: 58, icon: "SM", kind: "aws", title: "SageMaker AI", sub: "Serverless · XGBoost",
      info: {
        what: "Amazon SageMaker AI trains and hosts machine-learning models you build on your own data. Serverless Inference runs a model on demand and scales to zero.",
        how: "Hosts the win-probability model. One call scores one deal or the whole pipeline and returns probabilities plus each feature's contribution (SHAP values), which become the plain-language drivers.",
        facts: ["2 GB memory, at most 2 concurrent requests; pay per request", "The first call after an idle period can take several seconds (cold start)", "Terraform deploys an approved Model Registry version"],
      } },
    { id: "embed", x: 562, y: 446, w: 190, h: 58, icon: "TE", kind: "aws", title: "Embeddings", sub: "Bedrock · Titan v2 · 1,024-d",
      info: {
        what: "Amazon Bedrock offers ready-made AI models through one API. Titan Text Embeddings V2 turns text into a list of numbers (a vector) that captures meaning.",
        how: "Embeds every note and playbook passage during ingestion, and each search query at runtime, with the same model and size.",
        facts: ["1,024 dimensions, normalized", "Called with the task's IAM role; no API keys"],
      } },
    { id: "opensearch", x: 562, y: 516, w: 190, h: 58, icon: "OS", kind: "aws", title: "OpenSearch", sub: "Keyword + vector index",
      info: {
        what: "Amazon OpenSearch Service is a managed search engine. It runs classic keyword search and nearest-neighbor vector search in the same index.",
        how: "Stores each passage with its text, metadata (account, opportunity, document type, date) and vector. Hybrid queries mix keyword scores, good for names, products and competitors, with vector scores, good for meaning.",
        facts: ["One t3.small.search node: the cheapest option with vector search", "The app may only search; only the ingestion job can write", "OpenSearch Serverless is the scale-up path, at a higher minimum cost"],
      } },
    { id: "guardrails", x: 562, y: 590, w: 190, h: 58, icon: "GR", kind: "aws", title: "Guardrails", sub: "Bedrock · screens in & out",
      info: {
        what: "Amazon Bedrock Guardrails checks text going into and coming out of a model against rules you define.",
        how: "Checks retrieved notes and user questions for prompt attacks, and masks email addresses and phone numbers in the output. A denied topic blocks requests to judge individual employees.",
        facts: ["Called on its own (ApplyGuardrail) before and after each Claude call", "Its configuration is versioned in Terraform"],
      } },
    { id: "claude", x: 562, y: 664, w: 190, h: 58, icon: "C", kind: "aws", title: "Claude", sub: "Bedrock · Opus 5.5",
      info: {
        what: "Anthropic's Claude model, served through Amazon Bedrock.",
        how: "Writes the deal brief and the draft Salesforce update, and answers follow-up questions about the deal, using only the evidence it is given.",
        facts: ["Claude Opus 5.5, called with Anthropic's Python SDK (Bedrock client)", "At most 2 calls per brief: draft and one revision", "Uses the task's IAM role; no Anthropic API key"],
      } },
    { id: "s3", x: 34, y: 320, w: 194, h: 62, icon: "S3", kind: "aws", title: "Amazon S3", sub: "CRM snapshot · model data",
      info: {
        what: "Amazon S3 is object storage: files of any size, kept in buckets.",
        how: "Holds the CRM snapshot the app reads, the training data, the evaluation reports and the trained model files.",
        facts: ["The app can read only the snapshot folder", "Versioning on, all public access blocked"],
      } },
    { id: "cloudwatch", x: 34, y: 740, w: 194, h: 62, icon: "CW", kind: "aws", badge: "8", title: "CloudWatch Logs", sub: "Structured, no prompts",
      info: {
        what: "Amazon CloudWatch Logs stores and searches application logs.",
        how: "Receives one structured event per step: request ID, step, model or endpoint, latency and error category.",
        facts: ["No prompts, notes or contact details are logged", "Bedrock model-invocation logging stays off", "Logs expire after 14 days"],
      } },
    { id: "codebuild", x: 34, y: 870, w: 194, h: 62, icon: "CB", kind: "aws", badge: "D", title: "CodeBuild", sub: "Tests, then builds",
      info: {
        what: "AWS CodeBuild runs build jobs on demand, on machines that exist only for the job.",
        how: "Runs the tests, then builds the app's container image (make build).",
        facts: ["Runs as its own role, dealpulse-build"],
      } },
    { id: "ecr", x: 295, y: 870, w: 210, h: 62, icon: "ECR", kind: "aws", title: "ECR", sub: "Versioned images",
      info: {
        what: "Amazon Elastic Container Registry is a private store for container images.",
        how: "Keeps every DealPulse image version. ECS deploys from it.",
        facts: ["Images are scanned on push", "Earlier versions make rollback one command"],
      } },
    { id: "ingest", x: 562, y: 870, w: 190, h: 62, icon: "⇪", kind: "app", badge: "C", title: "Ingestion job", sub: "make seed · 1k passages",
      info: {
        what: "An offline script that loads the knowledge base.",
        how: "Splits activity notes, playbooks and win/loss reviews into passages, embeds them with Titan and bulk-loads them into OpenSearch.",
        facts: ["Runs as dealpulse-ingest, the only identity that can write the index", "Stable IDs and checksums make re-runs safe; new notes need no redeploy"],
      } },
    { id: "generator", x: 34, y: 990, w: 194, h: 62, icon: "⚙", kind: "app", badge: "A", title: "Data generator", sub: "Synthetic Salesforce data",
      info: {
        what: "A seeded Python script that creates realistic, fictional Salesforce data.",
        how: "Writes accounts, opportunities, contacts, activities, cases and notes for a fictional software vendor to S3, plus point-in-time training rows. A hidden rule decides which deals win, so we can check that the model learns the right drivers.",
        facts: ["Same seed, same data: results are reproducible", "Includes test traps: a planted prompt-injection email and look-alike accounts"],
      } },
    { id: "training", x: 295, y: 990, w: 210, h: 62, icon: "SM", kind: "aws", badge: "B", title: "SageMaker Training", sub: "XGBoost · point-in-time",
      info: {
        what: "SageMaker Training runs your training script on managed machines that exist only for the job.",
        how: "Trains XGBoost on about 12,000 point-in-time snapshots of closed deals. Older quarters train the model; the newest quarter tests it against Salesforce's stage-based probability.",
        facts: ["One ml.m5.large for a few minutes: cents per run", "Snapshots stop the model from “peeking” at how a deal ended"],
      } },
    { id: "registry", x: 562, y: 990, w: 190, h: 62, icon: "MR", kind: "aws", title: "Model Registry", sub: "Versions · approval gate",
      info: {
        what: "SageMaker Model Registry keeps each model version with its metrics and an approval status.",
        how: "Each training run registers a version as pending. After a person reads the evaluation report, make approve-model approves it and make deploy-model points the endpoint at it.",
        facts: ["Rollback means deploying the previous approved version"],
      } },
    { id: "iam", x: 34, y: 1110, w: 228, h: 62, icon: "IAM", kind: "aws", badge: "E", title: "IAM", sub: "Least-privilege roles",
      info: {
        what: "AWS Identity and Access Management controls who, or what, can do what.",
        how: "Separate roles for the running app, ingestion, builds, SageMaker training and ECS task start-up, each with only the access it needs.",
        facts: ["No access keys anywhere; operators use short-lived sign-in (aws sso login)", "The running app cannot write to OpenSearch or S3"],
      } },
    { id: "budget", x: 278, y: 1110, w: 228, h: 62, icon: "$", kind: "aws", title: "AWS Budgets", sub: "$60 / month · 4 alerts",
      info: {
        what: "Cost tracking with email alerts.",
        how: "A $60/month budget with alerts at 50%, 80% and 100% of actual spend and at 100% of forecast spend. make pause and make destroy-all keep idle cost down.",
        facts: ["A budget sends alerts; it does not cap spending"],
      } },
    { id: "terraform", x: 522, y: 1110, w: 230, h: 62, icon: "TF", kind: "oss", title: "Terraform", sub: "make apply · destroy-all",
      info: {
        what: "Infrastructure as code: every cloud resource is declared in version-controlled files.",
        how: "Two modules: bootstrap (state bucket, budget) and stack (network, IAM, S3, OpenSearch, SageMaker endpoint, guardrail, ECR, CodeBuild, ECS). One command removes everything.",
        facts: ["State in a versioned S3 bucket with native locking", "Model versions and image tags are Terraform inputs, so every deploy is reviewable"],
      } },
  ];

  const edges = [
    { id: "e_req", from: "user", to: "app", d: "M400,80 V206", both: true },
    { id: "e_sf_s3", from: "salesforce", to: "s3", d: "M200,80 V320", style: "optional" },
    { id: "e_in", from: "app", to: "load", d: "M400,260 V326" },
    { id: "e_load_s3", from: "load", to: "s3", d: "M290,351 H228" },
    { id: "e_l_s", from: "load", to: "score", d: "M400,376 V400" },
    { id: "e_s_sm", from: "score", to: "sagemaker", d: "M510,425 C536,425 536,401 562,401" },
    { id: "e_s_r", from: "score", to: "retrieve", d: "M400,450 V474" },
    { id: "e_r_emb", from: "retrieve", to: "embed", d: "M510,492 C536,492 536,475 562,475" },
    { id: "e_r_os", from: "retrieve", to: "opensearch", d: "M510,506 C536,506 536,545 562,545" },
    { id: "e_r_d", from: "retrieve", to: "draft", d: "M400,524 V548" },
    { id: "e_d_g", from: "draft", to: "guardrails", d: "M510,573 C536,573 536,619 562,619" },
    { id: "e_g_c", from: "guardrails", to: "claude", d: "M657,648 V664", both: true },
    { id: "e_d_rv", from: "draft", to: "review", d: "M400,598 V622" },
    { id: "e_loop", from: "review", to: "draft", d: "M290,654 C272,654 272,580 290,580", style: "loop" },
    { id: "e_rv_resp", from: "review", to: "respond", d: "M400,672 V708" },
    { id: "e_return", from: "respond", to: "app", d: "M290,733 H259 V233 H290" },
    { id: "e_log", from: "ecs", to: "cloudwatch", d: "M250,771 H228" },
    { id: "e_cb_ecr", from: "codebuild", to: "ecr", d: "M228,901 H295", style: "ops" },
    { id: "e_ecr_ecs", from: "ecr", to: "ecs", d: "M400,870 V800", style: "ops" },
    { id: "e_ing_emb", from: "ingest", to: "embed", d: "M752,901 H766 V475 H752", style: "ops" },
    { id: "e_emb_os", from: "embed", to: "opensearch", d: "M657,504 V516", style: "ops" },
    { id: "e_gen_s3", from: "generator", to: "s3", d: "M34,1021 H22 V351 H34", style: "ops" },
    { id: "e_gen_tr", from: "generator", to: "training", d: "M228,1021 H295", style: "ops" },
    { id: "e_tr_reg", from: "training", to: "registry", d: "M505,1021 H562", style: "ops" },
    { id: "e_reg_sm", from: "registry", to: "sagemaker", d: "M752,1021 H778 V401 H752", style: "ops" },
  ];

  const labels = [
    { x: 420, y: 136, text: "AWS ACCOUNT · dealpulse-demo · us-east-1", cls: "boundary-label" },
    { x: 562, y: 362, text: "AWS AI & DATA", cls: "column-label" },
    { x: 34, y: 308, text: "DATA & OPERATIONS", cls: "column-label" },
    { x: 34, y: 858, text: "BUILD & DEPLOY", cls: "column-label" },
    { x: 562, y: 858, text: "KNOWLEDGE BASE · OFFLINE", cls: "column-label" },
    { x: 34, y: 978, text: "ML PIPELINE · OFFLINE", cls: "column-label" },
    { x: 34, y: 1098, text: "PLATFORM FOUNDATION", cls: "column-label" },
    { x: 302, y: 614, text: "≤ 1 revision", cls: "loop-label" },
    { x: 408, y: 838, text: "deploy", cls: "edge-label" },
    { x: 122, y: 238, text: "nightly export", cls: "edge-label" },
    { x: 150, y: 251, text: "(future)", cls: "edge-label" },
  ];

  const steps = [
    { key: "1", group: "A deal review", title: "Open the pipeline or a deal",
      nodes: ["user", "ecs", "app"], edges: ["e_req"],
      text: "A sales manager opens the Pipeline page or picks one opportunity. The browser talks only to the DealPulse app; it never calls Bedrock, SageMaker or OpenSearch directly." },
    { key: "2", title: "Load the deal and check access",
      nodes: ["app", "langgraph", "load", "s3"], edges: ["e_in", "e_load_s3"],
      text: "The workflow checks that the selected persona may see the deal, then reads the opportunity, contact roles, stage history, activities and open cases from the CRM snapshot in S3." },
    { key: "3", title: "Score the deal",
      nodes: ["langgraph", "score", "sagemaker"], edges: ["e_l_s", "e_s_sm"],
      text: "Shared feature code turns the deal into about 20 numbers. The SageMaker endpoint returns a win probability and the drivers behind it. The Pipeline page scores every open deal in one batched call, with no LLM involved." },
    { key: "4", title: "Retrieve evidence (RAG)",
      nodes: ["langgraph", "retrieve", "embed", "opensearch"], edges: ["e_s_r", "e_r_emb", "e_r_os"],
      text: "The top risk drivers become targeted questions. Titan turns them into vectors, and OpenSearch runs hybrid keyword and vector searches over this deal's notes only, plus the shared playbook and win/loss reviews." },
    { key: "5", title: "Draft the brief",
      nodes: ["langgraph", "draft", "guardrails", "claude"], edges: ["e_r_d", "e_d_g", "e_g_c"],
      text: "Guardrails screen the evidence for prompt attacks. Claude writes the brief (summary, risks, next steps and a draft Salesforce update) and cites a passage for every claim. Guardrails screen the answer again and mask contact details." },
    { key: "6", title: "Review and verify",
      nodes: ["langgraph", "review", "draft"], edges: ["e_d_rv", "e_loop"],
      text: "Plain code, not another AI call, checks that every citation exists and belongs to this deal or the shared playbook, that amounts, dates and the score match the CRM data, and that no step promises a discount above policy. One revision at most." },
    { key: "7", title: "Return the brief",
      nodes: ["langgraph", "respond", "app", "ecs", "user"], edges: ["e_rv_resp", "e_return", "e_req"],
      text: "The manager sees the score and its drivers, the cited brief, the sources and a draft update to copy into Salesforce. Nothing is written back automatically." },
    { key: "8", title: "Observe every step",
      nodes: ["ecs", "cloudwatch"], edges: ["e_log"],
      text: "Each step writes a structured log: request ID, step, model or endpoint, latency and error type. Prompts, notes and contact details stay out of the logs." },
    { key: "A", group: "Behind the scenes", title: "Generate the CRM data",
      nodes: ["generator", "s3", "salesforce"], edges: ["e_gen_s3", "e_sf_s3"],
      text: "A seeded script creates Salesforce-shaped data for a fictional software vendor and writes it to S3. In production, a nightly export from Salesforce would fill the same bucket." },
    { key: "B", title: "Train and register the model",
      nodes: ["generator", "training", "registry", "sagemaker"], edges: ["e_gen_tr", "e_tr_reg", "e_reg_sm"],
      text: "SageMaker Training fits an XGBoost model on point-in-time snapshots of closed deals and tests it on the newest quarter. The version waits in the Model Registry until a person approves it; Terraform then points the serverless endpoint at it." },
    { key: "C", title: "Load the knowledge base",
      nodes: ["ingest", "embed", "opensearch"], edges: ["e_ing_emb", "e_emb_os"],
      text: "Offline, activity notes, playbooks and win/loss reviews are split into passages, embedded with Titan and loaded into OpenSearch. New notes need no redeploy." },
    { key: "D", title: "Build and deploy",
      nodes: ["codebuild", "ecr", "ecs"], edges: ["e_cb_ecr", "e_ecr_ecs"],
      text: "CodeBuild runs the tests and builds the container, ECR stores each version, and ECS runs it. Earlier versions allow a one-command rollback." },
    { key: "E", title: "Security and cost guardrails",
      nodes: ["iam", "budget", "terraform"], edges: [],
      text: "Least-privilege roles with no access keys, a $60/month budget with alerts, and every resource created and removed by Terraform." },
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
    // Keep the tooltip at the body level so fixed positioning uses the viewport.
    const tip = document.getElementById("arch-tip");
    if (tip) document.body.appendChild(tip);

    const defs = make("defs", {}, svg);
    [["arrow", "arrow-head"], ["arrow-on", "arrow-head on"]].forEach(([id, cls]) => {
      const marker = make("marker", { id, viewBox: "0 0 10 10", refX: 9, refY: 5, markerWidth: 7, markerHeight: 7, orient: "auto-start-reverse" }, defs);
      make("path", { d: "M0,1 L9,5 L0,9 z", class: cls }, marker);
    });

    make("rect", { x: 12, y: 108, width: 776, height: 1086, rx: 22, class: "account-boundary" }, svg);

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
      <div class="tip-block"><span>IN DEALPULSE</span><p>${item.info.how}</p></div>
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
      <p class="detail-text">Use <kbd>→</kbd> and <kbd>←</kbd>, or the buttons below, to walk through a deal review step by step.</p>`;
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

  const next = () => (currentStep === steps.length - 1 ? goTo(-1) : goTo(currentStep + 1));
  const prev = () => goTo(currentStep - 1);
  const reset = () => goTo(-1);
  const unpin = () => {
    pinnedId = null;
    svg.querySelectorAll(".pinned").forEach((element) => element.classList.remove("pinned"));
    renderDetail();
  };

  document.addEventListener("keydown", (event) => {
    // Only while the Architecture page is on screen (inside a multi-page shell it may be hidden).
    const screen = document.getElementById("screen-architecture");
    if (!screen || !screen.offsetParent) return;
    if (["INPUT", "SELECT", "TEXTAREA"].includes(document.activeElement?.tagName)) return;
    if (event.key === "ArrowRight") { event.preventDefault(); next(); }
    if (event.key === "ArrowLeft") { event.preventDefault(); prev(); }
    if (event.key === "Escape") reset();
  });
  window.addEventListener("scroll", hoverOff, { passive: true });

  // Panel buttons use data attributes instead of inline handlers (works under a strict CSP).
  document.getElementById("screen-architecture")?.addEventListener("click", (event) => {
    const go = event.target.closest("[data-arch-go]");
    const pinButton = event.target.closest("[data-arch-pin]");
    const action = event.target.closest("[data-arch-action]");
    if (go) goTo(Number(go.dataset.archGo));
    else if (pinButton) pin(pinButton.dataset.archPin);
    else if (event.target.closest("[data-arch-unpin]")) unpin();
    else if (action) ({ prev, next, reset })[action.dataset.archAction]?.();
  });

  render();
  goTo(-1);
})();
