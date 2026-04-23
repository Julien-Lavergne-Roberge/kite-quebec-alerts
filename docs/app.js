const EMOJI = { green: "🟢", yellow: "🟡", red: "🔴", unknown: "⚪" };
const DIRS = ["N", "NE", "E", "SE", "S", "SO", "O", "NO"];

function degToDir(deg) {
  return DIRS[Math.round(deg / 45) % 8];
}

function formatTime(iso) {
  const h = iso.slice(11, 13);
  return `${parseInt(h, 10)}h`;
}

function slugify(name) {
  return name.toLowerCase().replace(/[^a-z0-9]+/g, "-");
}

function isIdealHour(h) {
  // Green with wind in the ideal-ideal 15-22 range — highlight as sweet spot
  return h.status === "green" && h.wind >= 15 && h.wind <= 22;
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
    card.id = "spot-" + slugify(spot.name);
    card.innerHTML = `
      <header class="spot-head">
        <h2>${spot.name}</h2>
        <span class="status" title="Aujourd'hui → Demain">${today}<small>→</small>${tom}</span>
      </header>
      <p class="dirs">Directions acceptables : ${spot.allowed_dirs.join(", ")}</p>
      <div class="days"></div>
    `;

    if (spot.excellent_tomorrow) {
      const w = spot.excellent_tomorrow;
      const banner = document.createElement("div");
      banner.className = "excellent-banner";
      banner.innerHTML = `✨ <b>Excellent demain :</b> ${w.start}–${w.end} · ${w.wind_min}-${w.wind_max} kn · ${w.dominant_dir}`;
      card.insertBefore(banner, card.querySelector(".days"));
    }

    const daysDiv = card.querySelector(".days");
    for (const [dayKey, label] of [["today", "Aujourd'hui"], ["tomorrow", "Demain"]]) {
      const dayIso = data[dayKey];
      const hours = spot.hourly.filter(h => h.time.startsWith(dayIso));
      const dayEl = document.createElement("div");
      dayEl.className = "day";
      dayEl.innerHTML = `<div class="label">${label} <span class="date">${dayIso.slice(5).replace("-", "/")}</span></div><div class="hours"></div>`;
      const hoursEl = dayEl.querySelector(".hours");
      if (hours.length === 0) {
        hoursEl.innerHTML = '<div class="empty">Pas de données</div>';
      } else {
        for (const h of hours) {
          const cell = document.createElement("div");
          const classes = ["hour", h.status || "unknown"];
          if (isIdealHour(h)) classes.push("ideal");
          cell.className = classes.join(" ");
          const sourceNote = h.sources
            ? "\nSources: " + Object.entries(h.sources).map(([s, v]) => `${s}=${v}`).join(", ")
            : "";
          cell.title = (h.reason || "") + sourceNote;
          cell.innerHTML = `
            <span class="time">${formatTime(h.time)}</span>
            <span class="wind">${h.wind.toFixed(0)}/${h.gust.toFixed(0)}</span>
            <span class="dir">
              <span class="arrow" style="--rot:${h.dir}deg"></span>${degToDir(h.dir)}
            </span>
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
