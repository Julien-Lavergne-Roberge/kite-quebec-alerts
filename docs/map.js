const STATUS_LABEL = {
  green: "Excellent",
  yellow: "Marginal",
  red: "Non kiteable",
  unknown: "Inconnu",
};
const RANK = { green: 0, yellow: 1, red: 2, unknown: 3 };

function bestOf(a, b) {
  const ra = RANK[a] ?? 9;
  const rb = RANK[b] ?? 9;
  return ra <= rb ? a : b;
}

function slugify(name) {
  return name.toLowerCase().replace(/[^a-z0-9]+/g, "-");
}

function makeIcon(status, hasExcellent) {
  const cls = ["kite-pin", status || "unknown"];
  if (hasExcellent) cls.push("excellent");
  return L.divIcon({
    className: "",
    html: `<div class="${cls.join(" ")}"></div>`,
    iconSize: [28, 28],
    iconAnchor: [14, 14],
    popupAnchor: [0, -14],
  });
}

function popupHtml(spot) {
  const today = spot.today || "unknown";
  const tom = spot.tomorrow || "unknown";
  const excellent = spot.excellent_tomorrow;
  const excerpt = excellent
    ? `<div class="excellent-note">✨ Fenêtre excellente demain : <b>${excellent.start}–${excellent.end}</b> · ${excellent.wind_min}-${excellent.wind_max} kn · ${excellent.dominant_dir}</div>`
    : "";
  return `
    <h3>${spot.name}</h3>
    <div class="pop-day">
      <span class="dot ${today}"></span>
      <b>Aujourd'hui :</b> ${STATUS_LABEL[today] || "—"}
    </div>
    <div class="pop-day">
      <span class="dot ${tom}"></span>
      <b>Demain :</b> ${STATUS_LABEL[tom] || "—"}
    </div>
    ${excerpt}
    <div class="pop-day" style="font-size:0.75rem; color:#666;">
      Directions OK : ${spot.allowed_dirs.join(", ")}
    </div>
    <a href="index.html#spot-${slugify(spot.name)}">Voir le détail horaire →</a>
  `;
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

  // Center roughly on the 6 Montreal/West spots
  const lats = data.spots.map(s => s.lat).filter(Boolean);
  const lons = data.spots.map(s => s.lon).filter(Boolean);
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
    const best = bestOf(spot.today || "unknown", spot.tomorrow || "unknown");
    const m = L.marker([spot.lat, spot.lon], {
      icon: makeIcon(best, !!spot.excellent_tomorrow),
      title: spot.name,
    }).addTo(map);
    m.bindPopup(popupHtml(spot));
    markers.push(m);
  }

  if (markers.length > 1) {
    const group = L.featureGroup(markers);
    map.fitBounds(group.getBounds().pad(0.2));
  }
}

load();
