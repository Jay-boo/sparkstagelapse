const container = document.getElementById("container");
const statusEl = document.getElementById("status");
const statusText = document.getElementById("status-text");
const emptyState = document.getElementById("empty-state");
const countEl = document.getElementById("table-count");
const clearBtn = document.getElementById("clear-btn");

let tableCount = 0;

function updateCount() {
  countEl.textContent = tableCount + (tableCount === 1 ? " table" : " tables");
}

function relativeTime(ts) {
  if (!ts) return "";
  const diffSec = Math.max(0, Math.floor(Date.now() / 1000 - ts));
  if (diffSec < 5) return "à l'instant";
  if (diffSec < 60) return diffSec + "s";
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return diffMin + " min";
  const diffH = Math.floor(diffMin / 60);
  if (diffH < 24) return diffH + " h";
  return Math.floor(diffH / 24) + " j";
}

function refreshRelativeTimes() {
  document.querySelectorAll(".card-time").forEach((el) => {
    const ts = parseFloat(el.dataset.ts || "0");
    el.textContent = ts ? "il y a " + relativeTime(ts) : "";
  });
}
setInterval(refreshRelativeTimes, 15000);

function clearLatestPills() {
  document.querySelectorAll(".latest-pill").forEach((el) => el.remove());
}

// Renders payload.plot (a Plotly {data, layout} spec) inside the given
// .spark-table container, appended below the table. Requires plotly.js to
// already be loaded on the page (see templates/index.html).
function renderPlot(sparkTableEl, plotSpec) {
  const plotDiv = document.createElement("div");
  plotDiv.className = "spark-plot";
  sparkTableEl.appendChild(plotDiv);
  const layout = Object.assign({ autosize: true, margin: { t: 30, r: 20, b: 40, l: 50 } }, plotSpec.layout || {});
  Plotly.newPlot(plotDiv, plotSpec.data || [], layout, { responsive: true, displaylogo: false });
}

// Wires the tree / dag / raw view switcher on a .spark-plan block
// (see rendering/plan_html.py for the markup it expects).
function wirePlanToggle(planEl) {
  if (!planEl) return;
  const buttons = planEl.querySelectorAll('[data-role="plan-viewsw"] .plan-view-btn');
  if (!buttons.length) return;
  const views = {
    tree: planEl.querySelector('[data-role="plan-tree"]'),
    dag: planEl.querySelector('[data-role="plan-dag-scroll"]'),
    raw: planEl.querySelector('[data-role="plan-raw"]'),
  };
  buttons.forEach((btn) => {
    btn.addEventListener("click", () => {
      buttons.forEach((b) => b.classList.toggle("active", b === btn));
      Object.entries(views).forEach(([name, el]) => {
        if (el) el.hidden = name !== btn.dataset.view;
      });
    });
  });
}

// Wires click-and-drag panning on the DAG's scroll container, so people
// can grab the canvas directly instead of hunting for scrollbars. Uses
// Pointer Events so mouse, touch, and pen all work through one path;
// panning is just scrollLeft/scrollTop math, so it composes fine with the
// container's native overflow:auto (still scrollable with a wheel/trackpad
// or scrollbar when not actively dragging).
function wireDagPan(scrollEl) {
  if (!scrollEl) return;
  let dragging = false;
  let startX = 0, startY = 0, startLeft = 0, startTop = 0;

  scrollEl.addEventListener("pointerdown", (e) => {
    if (e.button !== 0) return; // left-click / primary touch only
    dragging = true;
    startX = e.clientX;
    startY = e.clientY;
    startLeft = scrollEl.scrollLeft;
    startTop = scrollEl.scrollTop;
    scrollEl.classList.add("dragging");
    scrollEl.setPointerCapture(e.pointerId);
  });
  scrollEl.addEventListener("pointermove", (e) => {
    if (!dragging) return;
    scrollEl.scrollLeft = startLeft - (e.clientX - startX);
    scrollEl.scrollTop = startTop - (e.clientY - startY);
  });
  const stopDrag = () => {
    dragging = false;
    scrollEl.classList.remove("dragging");
  };
  scrollEl.addEventListener("pointerup", stopDrag);
  scrollEl.addEventListener("pointercancel", stopDrag);
  scrollEl.addEventListener("pointerleave", stopDrag);
}


function addCard(payload) {
  if (document.getElementById("card_" + payload.id)) return;
  emptyState.style.display = "none";

  const card = document.createElement("div");
  card.className = "table-card";
  card.id = "card_" + payload.id;

  const meta = document.createElement("div");
  meta.className = "card-meta";
  const pill = document.createElement("span");
  pill.className = "latest-pill";
  pill.textContent = "PLUS RÉCENT";
  const time = document.createElement("span");
  time.className = "card-time";
  time.dataset.ts = payload.ts || "";
  time.title = payload.ts ? new Date(payload.ts * 1000).toLocaleString() : "";
  meta.appendChild(pill);
  meta.appendChild(time);
  card.appendChild(meta);

  // table_html is plain semantic markup now (no inline <script> to smuggle
  // through innerHTML) — insert it, then wire behavior via SparkTable.
  card.insertAdjacentHTML("beforeend", payload.table_html);
  const sparkTableEl = card.querySelector(".spark-table");
  new SparkTable(sparkTableEl);

  if (payload.plot) {
    renderPlot(sparkTableEl, payload.plot);
  }

  if (payload.plan_html) {
    card.insertAdjacentHTML("beforeend", payload.plan_html);
    const planEl = card.querySelector(".spark-plan");
    wirePlanToggle(planEl);
    wireDagPan(planEl.querySelector('[data-role="plan-dag-scroll"]'));
  }

  clearLatestPills();
  container.prepend(card);
  refreshRelativeTimes();

  tableCount++;
  updateCount();
}

clearBtn.addEventListener("click", () => {
  container.innerHTML = "";
  tableCount = 0;
  updateCount();
  emptyState.style.display = "block";
});

function connect() {
  const ws = new WebSocket("ws://" + location.host + "/ws");
  ws.onopen = () => {
    statusEl.classList.add("connected");
    statusText.textContent = "connecté";
  };
  ws.onclose = () => {
    statusEl.classList.remove("connected");
    statusText.textContent = "déconnecté, reconnexion…";
    setTimeout(connect, 1000);
  };
  ws.onerror = () => ws.close();
  ws.onmessage = (event) => addCard(JSON.parse(event.data));
}
connect();