const SOURCE_LABEL = {
  open_meteo: "Open-Meteo",
  gem: "GEM (Env Canada)",
  met_norway: "MET Norway",
};

function formatTime(iso) {
  return parseInt(iso.slice(11, 13), 10) + "h";
}

function degToCardinal(deg) {
  return ["N", "NE", "E", "SE", "S", "SO", "O", "NO"][Math.round(deg / 45) % 8];
}

function slugify(name) {
  return name.toLowerCase().replace(/[^a-z0-9]+/g, "-");
}

// Color category for a cell based on raw values (no consensus).
function cellClass(h) {
  if (h.wind == null) return "hour unknown";
  if (h.wind >= 12 && h.dir_ok) return "hour alert";
  if (h.wind >= 8 && h.dir_ok) return "hour marginal";
  return "hour low";
}

function summarizeAlerts(spot) {
  const total = Object.keys(spot.alerts.today).length;
  const todayCount = Object.values(spot.alerts.today).filter(Boolean).length;
  const tomCount = Object.values(spot.alerts.tomorrow).filter(Boolean).length;
  if (!todayCount && !tomCount) {
    return `<span class="alert-pill silent">Aucune alerte</span>`;
  }
  const pieces = [];
  if (todayCount) pieces.push(`<span class="alert-pill active">⚠ Auj : ${todayCount}/${total} sources</span>`);
  if (tomCount) pieces.push(`<span class="alert-pill active">⚠ Demain : ${tomCount}/${total} sources</span>`);
  return pieces.join(" ");
}

function renderSourceRow(src, hours, alertWindow) {
  const row = document.createElement("div");
  row.className = "source-row" + (alertWindow ? " source-active" : "");
  const header = document.createElement("div");
  header.className = "source-label";
  header.innerHTML = `<span class="src-name">${SOURCE_LABEL[src] || src}</span>` +
    (alertWindow
      ? `<span class="src-alert">⚠ ${alertWindow.start}–${alertWindow.end} · ${alertWindow.wind_min}-${alertWindow.wind_max} kn · ${alertWindow.dominant_dir}</span>`
      : `<span class="src-quiet">pas d'alerte</span>`);
  row.appendChild(header);

  const hoursEl = document.createElement("div");
  hoursEl.className = "hours";
  if (!hours.length) {
    hoursEl.innerHTML = `<div class="empty">Pas de données</div>`;
  } else {
    for (const h of hours) {
      const cell = document.createElement("div");
      cell.className = cellClass(h);
      cell.title = `${formatTime(h.time)} · ${h.wind} kn (rafales ${h.gust}) · vent de ${degToCardinal(h.dir)} (${h.dir}°)${h.dir_ok ? "" : " ⚠ off-shore"} · ${h.temp}°C · ${h.precip} mm/h`;
      cell.innerHTML = `
        <span class="time">${formatTime(h.time)}</span>
        <span class="wind">${h.wind.toFixed(0)}<small>/${h.gust.toFixed(0)}</small></span>
        <span class="dir">
          <span class="arrow ${h.dir_ok ? "ok" : "bad"}" style="--rot:${h.dir}deg"></span>${degToCardinal(h.dir)}
        </span>
        <span class="temp">${h.temp.toFixed(0)}°</span>
      `;
      hoursEl.appendChild(cell);
    }
  }
  row.appendChild(hoursEl);
  return row;
}

function render(data) {
  const gen = new Date(data.generated_at);
  document.getElementById("generated").textContent =
    "Mis à jour : " + gen.toLocaleString("fr-CA", { dateStyle: "short", timeStyle: "short" });

  const container = document.getElementById("spots");
  container.innerHTML = "";

  for (const spot of data.spots) {
    const card = document.createElement("article");
    card.className = "spot";
    card.id = "spot-" + slugify(spot.name);
    card.innerHTML = `
      <header class="spot-head">
        <h2>${spot.name}</h2>
        <div class="alert-pills">${summarizeAlerts(spot)}</div>
      </header>
      <p class="dirs">Directions kiteables : ${spot.allowed_dirs.join(", ")}</p>
      <div class="days"></div>
    `;
    const daysDiv = card.querySelector(".days");
    for (const [dayKey, label, dayIso] of [
      ["today", "Aujourd'hui", data.today],
      ["tomorrow", "Demain", data.tomorrow],
    ]) {
      const dayEl = document.createElement("div");
      dayEl.className = "day";
      dayEl.innerHTML = `<div class="day-label">${label} <span class="date">${dayIso.slice(5).replace("-", "/")}</span></div>`;
      for (const src of data.sources) {
        const hours = (spot.by_source[src] || []).filter(h => h.time.startsWith(dayIso));
        const alertWindow = spot.alerts[dayKey][src];
        dayEl.appendChild(renderSourceRow(src, hours, alertWindow));
      }
      daysDiv.appendChild(dayEl);
    }
    container.appendChild(card);
  }
}

async function load() {
  try {
    const res = await fetch("data.json?" + Date.now());
    if (!res.ok) throw new Error("data.json introuvable");
    const data = await res.json();
    render(data);
  } catch (err) {
    document.getElementById("generated").textContent =
      "Pas encore de données. Le script doit rouler une première fois.";
    console.error(err);
  }
}

load();
