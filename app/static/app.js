const state = {
  running: true,
  scenario: "baseline",
  interval: null,
};

const kpiDefinitions = [
  ["OEE", "oee", "%", "Availability × performance × quality"],
  ["Availability", "availability", "%", "Run time versus planned time"],
  ["Scrap rate", "scrap_rate", "%", "Rejected units versus total units"],
  ["Downtime", "downtime_minutes", " min", "Accumulated recorded downtime"],
  ["MTBF", "mtbf_minutes", " min", "Mean run time between failures"],
  ["MTTR", "mttr_minutes", " min", "Mean repair time for failures"],
  ["Good output", "good_units", "", "Accepted units"],
  ["Rejects", "reject_units", "", "Rejected units"],
];

async function request(url, options = {}) {
  const response = await fetch(url, {
    headers: {"Content-Type": "application/json"},
    ...options,
  });
  if (!response.ok) {
    const message = await response.text();
    throw new Error(`${response.status}: ${message}`);
  }
  return response.json();
}

function renderKpis(kpis) {
  document.querySelector("#kpiGrid").innerHTML = kpiDefinitions.map(([label, key, suffix, note]) => `
    <article class="kpi">
      <span>${label.toUpperCase()}</span>
      <strong>${kpis[key]}${suffix}</strong>
      <small>${note}</small>
    </article>
  `).join("");
}

function renderAlerts(alerts) {
  const container = document.querySelector("#alerts");
  document.querySelector("#alertCount").textContent = alerts.length;
  if (!alerts.length) {
    container.innerHTML = `
      <div class="alert info">
        <div class="alert-top"><strong>No active threshold alerts</strong><em>HEALTHY</em></div>
        <p>Current rolling windows remain inside the configured operating limits.</p>
      </div>`;
    return;
  }
  container.innerHTML = alerts.map(alert => `
    <div class="alert ${alert.severity}">
      <div class="alert-top">
        <strong>${alert.title}</strong>
        <em>${alert.severity.toUpperCase()}</em>
      </div>
      <p>${alert.evidence}</p>
      <p class="recommendation"><b>Next action:</b> ${alert.recommendation}</p>
    </div>
  `).join("");
}

function renderPareto(selector, rows) {
  const container = document.querySelector(selector);
  if (!rows.length) {
    container.innerHTML = `<p class="empty">No losses recorded in the current window.</p>`;
    return;
  }
  const max = Math.max(...rows.map(row => row.count));
  container.innerHTML = rows.map(row => `
    <div class="bar-row">
      <div class="bar-label"><span>${row.name}</span><strong>${row.count}</strong></div>
      <div class="bar-track"><div class="bar-fill" style="width:${(row.count/max)*100}%"></div></div>
    </div>
  `).join("");
}

function renderEvents(events) {
  document.querySelector("#eventsTable").innerHTML = events.map(event => `
    <tr>
      <td><strong>${event.machine}</strong></td>
      <td>${event.product}</td>
      <td>${event.good_units}</td>
      <td>${event.reject_units}</td>
      <td>${event.downtime_seconds}s</td>
      <td>${event.pressure} bar</td>
      <td><span class="pill">${event.stop_reason !== "None" ? event.stop_reason : event.defect_type}</span></td>
    </tr>
  `).join("");
}

function renderDependency(dependency) {
  const status = document.querySelector("#dependencyStatus");
  const text = document.querySelector("#dependencyText");
  status.textContent = dependency.status === "healthy" ? "Healthy" : "Degraded";
  status.classList.toggle("degraded", dependency.status !== "healthy");
  text.textContent = dependency.status === "healthy"
    ? "Production database is responding."
    : "Readiness is failing by design. The simulated dependency will recover automatically.";
}

async function refresh() {
  const overview = await request("/api/overview");
  renderKpis(overview.kpis);
  renderAlerts(overview.alerts);
  renderPareto("#stopPareto", overview.stop_pareto);
  renderPareto("#defectPareto", overview.defect_pareto);
  renderEvents(overview.recent_events);
  renderDependency(overview.dependency);
}

async function tick() {
  if (!state.running) return;
  await request("/api/simulator/tick", {method:"POST"});
  await refresh();
}

function setRunning(running) {
  state.running = running;
  document.querySelector("#liveDot").classList.toggle("paused", !running);
  document.querySelector("#liveLabel").textContent = running ? "LIVE SIMULATION" : "SIMULATION PAUSED";
  document.querySelector("#toggleButton").textContent = running ? "Pause" : "Resume";
}

document.querySelectorAll("[data-scenario]").forEach(button => {
  button.addEventListener("click", async () => {
    document.querySelectorAll("[data-scenario]").forEach(item => item.classList.remove("active"));
    button.classList.add("active");
    state.scenario = button.dataset.scenario;
    await request("/api/scenarios", {
      method:"POST",
      body:JSON.stringify({scenario:state.scenario}),
    });
    setRunning(true);
    await tick();
  });
});

document.querySelector("#toggleButton").addEventListener("click", async () => {
  const updated = await request("/api/simulator/toggle", {method:"POST"});
  setRunning(updated.running);
});

document.querySelector("#resetButton").addEventListener("click", async () => {
  await request("/api/reset", {method:"POST"});
  document.querySelectorAll("[data-scenario]").forEach(item => {
    item.classList.toggle("active", item.dataset.scenario === "baseline");
  });
  state.scenario = "baseline";
  setRunning(true);
  await refresh();
});

(async function start() {
  const current = await request("/api/state");
  state.running = current.running;
  state.scenario = current.scenario;
  setRunning(current.running);
  await refresh();
  state.interval = setInterval(tick, 2400);
})();
