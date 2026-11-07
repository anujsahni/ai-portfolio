const screenTitles = {
  plan: "Plan a trip",
  working: "Putting it together",
  itinerary: "Your itinerary",
  sources: "Sources & notes",
  architecture: "Architecture",
};

let planningTimer;
let toastTimer;
const localDemoTrip = {
  destination: "San Francisco",
  dates: "May 14 – 16, 2027",
  travelers: "2 travelers",
  budget: 600,
  interests: ["Coffee", "Art & design"],
  estimate: 486,
};

// Each page has its own bookmarkable address.
// Served over http (make mockups): clean paths like /architecture.
// Opened as a local file: hash addresses like index.html#/architecture, since a file can't have paths.
// "working" is a transient loading screen, so it keeps the plan address.
const DEFAULT_ROUTE = "plan";
const USE_PATHS = window.location.protocol.startsWith("http");
const routeFor = (name) => (name === "working" ? DEFAULT_ROUTE : name);
const urlFor = (route) => (USE_PATHS ? `/${route}` : `#/${route}`);
const currentUrl = () => (USE_PATHS ? window.location.pathname : window.location.hash);

function showScreen(name, { updateUrl = true } = {}) {
  if (!screenTitles[name]) return;
  document.querySelectorAll(".screen").forEach((screen) => screen.classList.remove("active"));
  const screen = document.getElementById(`screen-${name}`);
  if (screen) screen.classList.add("active");
  document.querySelectorAll("[data-nav]").forEach((item) => {
    item.classList.toggle("active", item.dataset.nav === name || (name === "working" && item.dataset.nav === "plan"));
  });
  document.getElementById("topbar-title").textContent = screenTitles[name];
  document.title = `${screenTitles[name]} · WeekendWise`;

  const url = urlFor(routeFor(name));
  if (updateUrl && currentUrl() !== url) history.pushState(null, "", url);
  window.scrollTo({ top: 0, behavior: updateUrl ? "smooth" : "auto" });
}

function routeFromUrl() {
  // Old #/page links still work when served over http.
  const fromHash = window.location.hash.replace(/^#\/?/, "");
  const raw = USE_PATHS && !fromHash ? window.location.pathname.replace(/^\/+/, "") : fromHash;
  const name = raw.split(/[/?]/)[0].toLowerCase();
  return screenTitles[name] && name !== "working" ? name : DEFAULT_ROUTE;
}

function showScreenFromUrl() {
  const target = routeFromUrl();
  showScreen(target, { updateUrl: false });
  // Normalize empty, unknown or old-style addresses without adding a history entry.
  const url = urlFor(target);
  if (currentUrl() !== url || (USE_PATHS && window.location.hash)) history.replaceState(null, "", url);
}

// Point sidebar links at the right address style, and switch pages without a full reload.
document.querySelectorAll("a[data-nav], a.brand").forEach((link) => {
  const route = link.dataset.nav || DEFAULT_ROUTE;
  link.setAttribute("href", urlFor(route));
  link.addEventListener("click", (event) => {
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || event.button !== 0) return;
    event.preventDefault();
    showScreen(route);
  });
});

window.addEventListener("hashchange", showScreenFromUrl);
window.addEventListener("popstate", showScreenFromUrl);

function setDestination(destination) {
  document.getElementById("destination").value = destination;
}

function syncBudget(value) {
  document.getElementById("budget").value = value;
}

function startPlanning(event) {
  event.preventDefault();
  const destination = document.getElementById("destination").value.trim() || "San Francisco";
  if (destination.toLocaleLowerCase() !== "san francisco") {
    showToast("Local sample guides are seeded for San Francisco. Choose it to preview the full flow.");
    return;
  }

  localDemoTrip.destination = destination;
  localDemoTrip.dates = document.getElementById("dates").value.trim() || "Weekend dates not set";
  localDemoTrip.travelers = document.getElementById("travelers").value;
  localDemoTrip.budget = Number(document.getElementById("budget").value) || 600;
  localDemoTrip.interests = Array.from(document.querySelectorAll(".interest-chip.selected"))
    .map((chip) => chip.textContent.replace(/^[^\p{L}\p{N}]+/u, "").trim());

  document.getElementById("working-destination").textContent = localDemoTrip.destination;
  document.getElementById("working-budget").textContent = `$${localDemoTrip.budget}`;
  renderLocalTripSummary();
  showScreen("working");
  runDemoProgress();
}

function renderLocalTripSummary() {
  document.getElementById("result-destination").textContent = localDemoTrip.destination;
  document.getElementById("result-dates").textContent = `▦ ${localDemoTrip.dates.toLocaleUpperCase()}`;
  document.getElementById("result-travelers").textContent = `♧ ${localDemoTrip.travelers.toLocaleUpperCase()}`;
  document.getElementById("result-city").textContent = `⌖ ${localDemoTrip.destination.toLocaleUpperCase()}`;
  document.getElementById("result-estimate").textContent = `$${localDemoTrip.estimate}`;
  document.getElementById("result-budget").textContent = `of $${localDemoTrip.budget}`;

  const percentage = Math.min(100, Math.round((localDemoTrip.estimate / localDemoTrip.budget) * 100));
  const budgetStatus = document.getElementById("result-budget-status");
  budgetStatus.textContent = localDemoTrip.estimate <= localDemoTrip.budget ? "ON TRACK" : "OVER BUDGET";
  budgetStatus.classList.toggle("over-budget", localDemoTrip.estimate > localDemoTrip.budget);
  document.getElementById("result-budget-meter").style.width = `${percentage}%`;

  const interests = localDemoTrip.interests;
  document.getElementById("result-interests").textContent = interests.length
    ? `You picked ${interests.join(" and ")}. This fixed sample leaves open space between stops.`
    : "You asked for a relaxed plan. This fixed sample leaves open space between stops.";
}

function runDemoProgress() {
  window.clearInterval(planningTimer);
  const list = document.getElementById("progress-list");
  const labels = [
    "Getting a feel for your trip",
    "Finding places you’ll love",
    "Checking the little details",
    "Putting your days together",
  ];
  let current = 1;
  renderProgress(list, labels, current);
  planningTimer = window.setInterval(() => {
    current += 1;
    renderProgress(list, labels, current);
    if (current >= labels.length) {
      window.clearInterval(planningTimer);
      window.setTimeout(() => showScreen("itinerary"), 550);
    }
  }, 850);
}

function renderProgress(list, labels, current) {
  list.innerHTML = labels.map((label, index) => {
    let state = "";
    let marker = '<span class="step-empty"></span>';
    let status = "";
    if (index < current) {
      state = " complete";
      marker = '<span class="step-check">✓</span>';
      status = "DONE";
    } else if (index === current) {
      state = " current";
      marker = '<span class="step-loader"></span>';
      status = "IN PROGRESS";
    }
    return `<div class="progress-step${state}">${marker}<span>${label}</span><small>${status}</small></div>`;
  }).join("");
}

function selectDay(button, dayId) {
  document.querySelectorAll(".day-tab").forEach((tab) => tab.classList.remove("active"));
  document.querySelectorAll(".day-plan").forEach((day) => day.classList.remove("active"));
  button.classList.add("active");
  document.getElementById(dayId)?.classList.add("active");
}

function openSources() {
  showScreen("sources");
}

function showToast(message) {
  const toast = document.getElementById("toast");
  toast.textContent = message;
  toast.classList.add("visible");
  window.clearTimeout(toastTimer);
  toastTimer = window.setTimeout(() => toast.classList.remove("visible"), 2400);
}

document.querySelectorAll(".interest-chip").forEach((chip) => {
  chip.addEventListener("click", () => {
    const selected = chip.classList.toggle("selected");
    chip.setAttribute("aria-pressed", String(selected));
  });
});

document.getElementById("budget").addEventListener("input", (event) => {
  const range = document.querySelector(".budget-range");
  const value = Number(event.target.value);
  if (value >= Number(range.min) && value <= Number(range.max)) range.value = value;
});

showScreenFromUrl();
