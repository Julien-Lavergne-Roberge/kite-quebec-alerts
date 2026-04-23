const EMOJI = { green: "🟢", yellow: "🟡", red: "🔴", unknown: "⚪" };
const DIRS = ["N", "NE", "E", "SE", "S", "SO", "O", "NO"];

function degToDir(deg) {
  return DIRS[Math.round(deg / 45) % 8];
}

function formatTime(iso) {
  return iso.slice(11, 16);
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

function render(data) {
  const gen = new Date(data.generated_at);
  document.getElementById("generated").textContent =
    "Mis à jour : " + gen.toLocaleString("fr-CA", { dateStyle: "short", timeStyle: "short" });

  const container = document.getElementById("spots");
  container.innerHTML = "";

  for (const spot of data.spots) {
    const today = EMOJI[spot.today] || "⚪";
    const tom = EMOJI[spot.tomorrow] || "⚪";
    const card = document.createElement("article");
    card.className = "spot";
    card.innerHTML = `
      <header class="spot-head">
        <h2>${spot.name}</h2>
        <span class="status">${today}<small>→</small>${tom}</span>
      </header>
      <p class="dirs">Vents OK : ${spot.allowed_dirs.join(", ")}</p>
      <div class="days"></div>
    `;
    const daysDiv = card.querySelector(".days");
    for (const [dayKey, label] of [["today", "Aujourd'hui"], ["tomorrow", "Demain"]]) {
      const dayIso = data[dayKey];
      const hours = spot.hourly.filter(h => h.time.startsWith(dayIso));
      const dayEl = document.createElement("div");
      dayEl.className = "day";
      dayEl.innerHTML = `<div class="label">${label} (${dayIso.slice(5)})</div><div class="hours"></div>`;
      const hoursEl = dayEl.querySelector(".hours");
      if (hours.length === 0) {
        hoursEl.innerHTML = '<div class="empty">Pas de données</div>';
      } else {
        for (const h of hours) {
          const cell = document.createElement("div");
          cell.className = "hour " + (h.status || "unknown");
          cell.title = h.reason || "";
          cell.innerHTML = `
            <span class="time">${formatTime(h.time)}</span>
            <span class="wind">${h.wind.toFixed(0)}/${h.gust.toFixed(0)}</span>
            <span class="dir">${degToDir(h.dir)}</span>
            <span class="temp">${h.temp.toFixed(0)}°</span>
          `;
          hoursEl.appendChild(cell);
        }
      }
      daysDiv.appendChild(dayEl);
    }
    container.appendChild(card);
  }
}

load();
