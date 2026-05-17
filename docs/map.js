const SOURCE_LABEL = {
  open_meteo: "Open-Meteo",
  gem: "GEM (Env Canada)",
  met_norway: "MET Norway",
};

function slugify(name) {
  return name.toLowerCase().replace(/[^a-z0-9]+/g, "-");
}

function anyAlert(spot, dayKey) {
  return Object.values(spot.alerts[dayKey]).some(Boolean);
}

function makeIcon(state) {
  return L.divIcon({
    className: "",
    html: `<div class="kite-pin ${state}"></div>`,
    iconSize: [28, 28],
    iconAnchor: [14, 14],
    popupAnchor: [0, -14],
  });
}

function popupHtml(spot) {
  const sources = Object.keys(spot.alerts.today);
  function dayBlock(dayKey, label) {
    const lines = [];
    let hasAny = false;
    for (const src of sources) {
      const w = spot.alerts[dayKey][src];
      if (w) {
        hasAny = true;
        lines.push(`<span class="pop-src hit">⚠ ${SOURCE_LABEL[src] || src} : ${w.start}–${w.end} · ${w.wind_min}-${w.wind_max} kn · ${w.dominant_dir}</span>`);
      } else {
        lines.push(`<span class="pop-src">${SOURCE_LABEL[src] || src} : —</span>`);
      }
    }
    return `<div class="pop-day"><b>${label}${hasAny ? " ⚠" : ""}</b>${lines.join("")}</div>`;
  }
  return `
    <h3>${spot.name}</h3>
    ${dayBlock("today", "Aujourd'hui")}
    ${dayBlock("tomorrow", "Demain")}
    <div class="pop-day" style="font-size:0.75rem; color:#666;">
      Directions OK : ${spot.allowed_dirs.join(", ")}
    </div>
    <a href="index.html#spot-${slugify(spot.name)}">Voir détail horaire →</a>
  `;
}

function pinState(spot) {
  const t = anyAlert(spot, "today");
  const tm = anyAlert(spot, "tomorrow");
  if (t && tm) return "urgent";
  if (t || tm) return "alert";
  return "quiet";
}

async function load() {
  try {
    const res = await fetch("data.json?" + Date.now());
    if (!res.ok) throw new Error("data.json introuvable");
    const data = await res.json();
    render(data);
  } catch (err) {
    document.getElementById("generated").textContent = "Pas encore de données.";
    console.error(err);
  }
}

function render(data) {
  const gen = new Date(data.generated_at);
  document.getElementById("generated").textContent =
    "Mis à jour : " + gen.toLocaleString("fr-CA", { dateStyle: "short", timeStyle: "short" });

  const lats = data.spots.map(s => s.lat).filter(v => v != null);
  const lons = data.spots.map(s => s.lon).filter(v => v != null);
  const center = lats.length
    ? [lats.reduce((a, b) => a + b, 0) / lats.length, lons.reduce((a, b) => a + b, 0) / lons.length]
    : [45.45, -74.0];

  const map = L.map("map", { scrollWheelZoom: false }).setView(center, 10);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: "© OpenStreetMap",
    maxZoom: 18,
  }).addTo(map);

  const markers = [];
  for (const spot of data.spots) {
    if (spot.lat == null || spot.lon == null) continue;
    const m = L.marker([spot.lat, spot.lon], {
      icon: makeIcon(pinState(spot)),
      title: spot.name,
    }).addTo(map);
    m.bindPopup(popupHtml(spot));
    markers.push(m);
  }
  if (markers.length > 1) {
    map.fitBounds(L.featureGroup(markers).getBounds().pad(0.2));
  }
}

load();
