"use strict";
const $ = (id) => document.getElementById(id);
const state = {token: sessionStorage.getItem("ruta-token"), airports: [], trips: [], view: "explore", shown: 12,
  selectedId: null, reportLoaded: false};
const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const NETWORK_ERROR = "Error de red. Inténtalo nuevamente.";
let pendingDelete = null;

// ---------- Small helpers ----------
const wait = ms => new Promise(resolve => setTimeout(resolve, ms));
function restartAnimation(element, className) {
  if (!element) return;
  element.classList.remove(className);
  void element.offsetWidth; // force reflow so the animation plays again
  element.classList.add(className);
}
function formatNumber(value, decimals = 0) {
  return value.toLocaleString("es-CO", {minimumFractionDigits: decimals, maximumFractionDigits: decimals});
}
function countUp(element, value) {
  const target = Number(value);
  if (!Number.isFinite(target)) { element.textContent = value ?? "—"; return; }
  const decimals = Number.isInteger(target) ? 0 : 1;
  const from = Number(element.dataset.value) || 0;
  element.dataset.value = target;
  if (reduceMotion || from === target) { element.textContent = formatNumber(target, decimals); return; }
  const start = performance.now(), duration = 900;
  const step = now => {
    const progress = Math.min(1, (now - start) / duration);
    const eased = 1 - Math.pow(1 - progress, 3);
    element.textContent = formatNumber(from + (target - from) * eased, decimals);
    if (progress < 1) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}
function daysUntil(date) {
  const today = new Date(); today.setHours(0, 0, 0, 0);
  return Math.round((new Date(date + "T00:00:00") - today) / 86400000);
}
function tripStatus(trip) {
  const days = daysUntil(trip.departure_date);
  if (days > 1) return {key: "upcoming", label: "En " + days + " días"};
  if (days === 1) return {key: "soon", label: "Mañana"};
  if (days === 0) return {key: "today", label: "Hoy"};
  if (days + trip.duration_days > 0) return {key: "ongoing", label: "En curso"};
  return {key: "past", label: "Finalizado"};
}

// ---------- Feedback ----------
function notice(message, error = false) {
  $("notice").textContent = message;
  $("notice").className = "alert " + (error ? "alert-danger" : "alert-success");
  $("notice").hidden = false;
}
function showToast(message, type = "success") {
  const toast = document.createElement("div");
  toast.className = "toast toast-" + type;
  const icon = document.createElement("span");
  icon.className = "toast-icon"; icon.setAttribute("aria-hidden", "true");
  icon.textContent = type === "error" ? "!" : "✓";
  toast.append(icon, document.createTextNode(message));
  $("toast-container").appendChild(toast);
  requestAnimationFrame(() => toast.classList.add("visible"));
  setTimeout(() => {
    toast.classList.remove("visible");
    setTimeout(() => toast.remove(), 300);
  }, 2900);
}
function errorText(body) {
  if (Array.isArray(body.detail)) return body.detail.map(e => e.msg).join(". ");
  return body.detail || "No se pudo completar la solicitud.";
}
async function api(path, options = {}) {
  let response;
  try {
    response = await fetch("/api" + path, {...options, headers: {
      "Content-Type": "application/json",
      ...(state.token ? {Authorization: "Bearer " + state.token} : {}),
      ...options.headers
    }});
  } catch {
    showToast(NETWORK_ERROR, "error");
    throw new Error(NETWORK_ERROR);
  }
  if (response.status === 401 && path !== "/auth/login") {
    logout();
    throw new Error("Tu sesión venció. Vuelve a ingresar.");
  }
  if (response.status === 204) return null;
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    if (response.status === 429) throw new Error("Has realizado muchas solicitudes. Espera un minuto.");
    throw new Error(errorText(body));
  }
  return body;
}
async function busy(button, action) {
  button.disabled = true; button.classList.add("is-loading");
  try { await action(); return true; } catch (error) {
    notice(error.message, true);
    return false;
  } finally { button.disabled = false; button.classList.remove("is-loading"); }
}

// ---------- Welcome animation ----------
const HERO_ROUTES = [["BOG", "Bogotá", "CTG", "Cartagena"], ["MDE", "Medellín", "SMR", "Santa Marta"],
  ["CLO", "Cali", "ADZ", "San Andrés"], ["BAQ", "Barranquilla", "LET", "Leticia"], ["PEI", "Pereira", "CTG", "Cartagena"]];
const HERO_WORDS = ["destinos.", "aventuras.", "paisajes.", "recuerdos."];
let heroRunning = false;
function swapText(element, text) { element.textContent = text; restartAnimation(element, "swap"); }
function startHero() {
  const path = $("flight-path");
  if (heroRunning || reduceMotion || !path || $("login-view").hidden) return;
  heroRunning = true;
  const length = path.getTotalLength(), FLY = 3000, CYCLE = 4300, WORD_EVERY = 2800;
  const plane = $("flight-plane");
  path.style.strokeDasharray = length;
  let start = performance.now(), lastWord = start, route = 0, word = 0;
  const frame = now => {
    if ($("login-view").hidden) { heroRunning = false; return; }
    let elapsed = now - start;
    if (elapsed >= CYCLE) {
      start = now; elapsed = 0; route = (route + 1) % HERO_ROUTES.length;
      const [fromCode, fromCity, toCode, toCity] = HERO_ROUTES[route];
      swapText($("from-code"), fromCode); swapText($("from-city"), fromCity);
      swapText($("to-code"), toCode); swapText($("to-city"), toCity);
    }
    if (now - lastWord >= WORD_EVERY) {
      lastWord = now; word = (word + 1) % HERO_WORDS.length; swapText($("hero-word"), HERO_WORDS[word]);
    }
    const t = Math.min(1, elapsed / FLY);
    const eased = t < .5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
    const at = eased * length;
    const point = path.getPointAtLength(at);
    const ahead = path.getPointAtLength(Math.min(length, at + .5)), behind = path.getPointAtLength(Math.max(0, at - .5));
    const angle = Math.atan2(ahead.y - behind.y, ahead.x - behind.x) * 180 / Math.PI;
    plane.setAttribute("transform", `translate(${point.x.toFixed(2)} ${point.y.toFixed(2)}) rotate(${angle.toFixed(1)})`);
    path.style.strokeDashoffset = length * (1 - eased);
    const landing = elapsed > FLY ? Math.max(0, 1 - (elapsed - FLY) / 350) : 1;
    plane.style.opacity = Math.min(1, t * 12) * landing;
    path.style.opacity = elapsed > CYCLE - 450 ? Math.max(0, (CYCLE - elapsed) / 450) : 1;
    requestAnimationFrame(frame);
  };
  requestAnimationFrame(frame);
}

// ---------- Navigation & session ----------
function moveInk() {
  const active = document.querySelector(".view-nav [aria-current]");
  if (!active) return;
  $("nav-ink").style.width = active.offsetWidth + "px";
  $("nav-ink").style.transform = `translateX(${active.offsetLeft}px)`;
}
function showView(view) {
  state.view = view;
  for (const name of ["explore", "trips", "reports"]) {
    const section = $(name + "-view");
    section.hidden = name !== view;
    if (name === view) restartAnimation(section, "view-enter");
  }
  document.querySelectorAll("[data-view]").forEach(button => {
    if (button.dataset.view === view) button.setAttribute("aria-current", "page");
    else button.removeAttribute("aria-current");
  });
  moveInk();
  if (view === "explore" && window.Plotly && $("map").data) Plotly.Plots.resize($("map"));
  if (view === "reports" && !state.reportLoaded) $("refresh-report").click();
}
function greeting(user) {
  const hour = new Date().getHours();
  const text = hour < 12 ? "Buenos días" : hour < 19 ? "Buenas tardes" : "Buenas noches";
  return (text + ", " + user).toLocaleUpperCase("es");
}
function logout() {
  state.token = null; state.airports = []; state.trips = []; state.selectedId = null; state.reportLoaded = false;
  sessionStorage.removeItem("ruta-token");
  sessionStorage.removeItem("ruta-user");
  $("workspace").hidden = true; $("account").hidden = true; $("login-view").hidden = false;
  $("login-password").value = "";
  $("itinerary-dialog").close(); $("delete-dialog").close();
  $("trips-list").replaceChildren(); $("report-metrics").replaceChildren();
  $("report-routes").replaceChildren(); $("report-routes").hidden = true;
  $("report-caption").textContent = "Genera un reporte para consultar las métricas de tus itinerarios.";
  startHero();
}
async function enter() {
  $("login-view").hidden = true; $("workspace").hidden = false; $("account").hidden = false;
  const user = sessionStorage.getItem("ruta-user") || "Mi cuenta";
  $("username").textContent = user;
  $("greeting").textContent = greeting(user);
  showView("explore");
  const results = await Promise.allSettled([loadAirports(), loadTrips()]);
  for (const result of results) if (result.status === "rejected") notice(result.reason.message, true);
}

$("login-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const ok = await busy(event.submitter, async () => {
    const result = await api("/auth/login", {method: "POST", body: JSON.stringify({
      username: $("login-user").value.trim(), password: $("login-password").value
    })});
    state.token = result.access_token;
    sessionStorage.setItem("ruta-token", state.token);
    sessionStorage.setItem("ruta-user", $("login-user").value.trim());
    $("login-password").value = ""; $("notice").hidden = true;
    await enter();
  });
  if (!ok) restartAnimation(document.querySelector(".login-panel"), "shake");
});
$("logout").addEventListener("click", logout);
document.querySelectorAll("[data-view]").forEach(button => button.addEventListener("click", () => showView(button.dataset.view)));
window.addEventListener("resize", moveInk);
window.addEventListener("scroll", () => document.querySelector(".topbar").classList.toggle("scrolled", window.scrollY > 8), {passive: true});
document.addEventListener("pointermove", event => {
  const element = event.target.closest?.(".glow");
  if (!element) return;
  const box = element.getBoundingClientRect();
  element.style.setProperty("--mx", event.clientX - box.left + "px");
  element.style.setProperty("--my", event.clientY - box.top + "px");
}, {passive: true});

// ---------- Airports ----------
function airportById(id) { return state.airports.find(item => item.id === id); }
function airportLabel(id) {
  const airport = airportById(id);
  return airport ? (airport.iata_code || airport.city || airport.name) : "#" + id;
}
function routeLabel(trip) { return airportLabel(trip.departure_airport_id) + " → " + airportLabel(trip.arrival_airport_id); }
function hasCoordinates(airport) { return Number.isFinite(airport?.latitude) && Number.isFinite(airport?.longitude); }
function renderSkeletons() {
  $("airport-list").replaceChildren();
  for (let i = 0; i < 6; i++) {
    const column = document.createElement("div"); column.className = "col-md-6 col-lg-4";
    const block = document.createElement("div"); block.className = "skeleton";
    column.append(block); $("airport-list").append(column);
  }
}
async function loadAirports() {
  $("map-status").textContent = "Cargando aeropuertos…";
  if (!state.airports.length) renderSkeletons();
  try {
    const airports = await api("/airports");
    if (!state.token) return;
    state.airports = airports;
    $("map-caption").textContent = airports.length + " aeropuertos para explorar";
    renderAirports(); renderTrips();
    const located = airports.filter(hasCoordinates);
    if (!window.Plotly) throw new Error("No se pudo cargar el mapa. La lista de aeropuertos sigue disponible.");
    const escape = value => String(value).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
    await Plotly.newPlot("map", [{
      type: "scattergeo", mode: "markers",
      lat: located.map(a => a.latitude), lon: located.map(a => a.longitude), customdata: located.map(a => a.id),
      text: located.map(a => escape(a.name) + "<br>" + escape(a.city)),
      hovertemplate: "%{text}<extra></extra>",
      marker: {size: 8, color: "#387963", opacity: .85, line: {color: "white", width: 1.2}}
    }, {
      type: "scattergeo", mode: "markers", lat: [], lon: [], hoverinfo: "skip",
      marker: {size: 17, color: "#e05d2f", line: {color: "white", width: 3}}
    }], {
      margin: {t: 12, r: 8, b: 12, l: 8}, paper_bgcolor: "#edf2ed", showlegend: false,
      hoverlabel: {bgcolor: "#ffffff", bordercolor: "#f0d9c8", font: {color: "#3a2016"}},
      geo: {projection: {type: "mercator"}, resolution: 50, showland: true,
        landcolor: "#dce6d9", showocean: true, oceancolor: "#edf2ed",
        showcountries: true, countrycolor: "#a5b8aa", coastlinecolor: "#a5b8aa",
        bgcolor: "#edf2ed", lonaxis: {range: [-82, -66]}, lataxis: {range: [-5, 14]}}
    }, {responsive: true, displayModeBar: false});
    const map = $("map");
    map.removeAllListeners?.("plotly_click");
    map.on("plotly_click", event => {
      const point = event.points?.[0];
      const airport = point && point.curveNumber === 0 ? airportById(point.customdata) : null;
      if (airport) selectAirport(airport, true);
    });
    highlightOnMap(airportById(state.selectedId));
    $("map-status").textContent = located.length + " ubicaciones en el mapa (haz clic en una para ver su detalle). " +
      (airports.length - located.length) + " aeropuertos sin coordenadas válidas.";
  } catch (error) { $("map-status").textContent = error.message; throw error; }
}
function highlightOnMap(airport) {
  if (!window.Plotly || !$("map").data || $("map").data.length < 2) return;
  const located = hasCoordinates(airport);
  Plotly.restyle("map", {lat: [located ? [airport.latitude] : []], lon: [located ? [airport.longitude] : []]}, [1]);
}
function renderAirportDetail(airport) {
  const empty = !airport;
  $("airport-detail-name").textContent = empty ? "Selecciona un aeropuerto" : airport.name;
  $("airport-detail-city").textContent = empty ? "Elige uno de la lista para ver información del destino." : (airport.city || "Ciudad no informada") + " · " + (airport.country || "País no informado");
  $("airport-detail-iata").textContent = airport?.iata_code || "—";
  $("airport-detail-country").textContent = airport?.country || "—";
  $("airport-detail-city2").textContent = airport?.city || "—";
  $("airport-detail-coords").textContent = hasCoordinates(airport) ? `${airport.latitude}, ${airport.longitude}` : "—";
  $("detail-plan").hidden = empty;
  restartAnimation($("airport-detail"), "refresh");
}
function selectAirport(airport, fromMap = false) {
  state.selectedId = airport ? airport.id : null;
  renderAirportDetail(airport);
  document.querySelectorAll(".airport-card").forEach(card => card.classList.toggle("selected", Number(card.dataset.id) === state.selectedId));
  highlightOnMap(airport);
  if (fromMap && window.innerWidth < 992) $("airport-detail").scrollIntoView({behavior: reduceMotion ? "auto" : "smooth", block: "center"});
}
function renderAirports() {
  const query = $("airport-search").value.trim().toLocaleLowerCase("es");
  const field = $("airport-filter-type").value;
  const matching = state.airports.filter(airport => {
    const haystack = field === "all"
      ? [airport.name, airport.city, airport.country, airport.iata_code].join(" ")
      : String(airport[field] ?? "");
    return haystack.toLocaleLowerCase("es").includes(query);
  });
  $("airport-list").replaceChildren();
  matching.slice(0, state.shown).forEach((airport, index) => {
    const column = document.createElement("div"); column.className = "col-md-6 col-lg-4";
    const card = document.createElement("article");
    card.className = "panel airport-card glow rise" + (airport.id === state.selectedId ? " selected" : "");
    card.style.setProperty("--i", index);
    card.dataset.id = airport.id;
    card.tabIndex = 0;
    card.setAttribute("role", "button");
    card.addEventListener("click", () => selectAirport(airport));
    card.addEventListener("keydown", event => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        selectAirport(airport);
      }
    });
    const code = document.createElement("span"); code.className = "code"; code.textContent = airport.iata_code || "SIN IATA";
    const title = document.createElement("h3"); title.textContent = airport.name;
    const city = document.createElement("p"); city.className = "small text-secondary mb-0"; city.textContent = airport.city || "Ciudad no informada";
    card.append(code, title, city); column.append(card); $("airport-list").append(column);
  });
  if (!matching.length) {
    $("airport-list").textContent = "No encontramos aeropuertos con esa búsqueda.";
    selectAirport(null);
  } else if (!matching.some(airport => airport.id === state.selectedId)) {
    selectAirport(matching[0]);
  }
  $("more-airports").hidden = matching.length <= state.shown;
}
$("airport-search").addEventListener("input", () => { state.shown = 12; renderAirports(); });
$("airport-filter-type").addEventListener("change", () => { state.shown = 12; renderAirports(); });
$("more-airports").addEventListener("click", () => { state.shown += 12; renderAirports(); });
$("reload-airports").addEventListener("click", e => busy(e.currentTarget, loadAirports));
$("detail-plan").addEventListener("click", () => openForm(null, {departure: state.selectedId}));

// ---------- Itineraries ----------
async function loadTrips() {
  const trips = [];
  while (true) {
    const page = await api("/itineraries?limit=100&offset=" + trips.length);
    trips.push(...page);
    if (page.length < 100) break;
  }
  if (!state.token) return;
  state.trips = trips; renderTrips();
}
function renderTrips(highlightId = null) {
  if ($("trip-count").textContent !== String(state.trips.length)) {
    $("trip-count").textContent = state.trips.length;
    restartAnimation($("trip-count"), "bump");
  }
  $("trips-empty").hidden = state.trips.length !== 0;
  $("trips-list").replaceChildren();
  const sorted = [...state.trips].sort((a, b) => String(a.departure_date).localeCompare(String(b.departure_date)));
  sorted.forEach((trip, index) => {
    const status = tripStatus(trip);
    const column = document.createElement("div"); column.className = "col-md-6 col-lg-4";
    const card = document.createElement("article");
    card.className = "panel trip-card glow " + (String(trip.id) === String(highlightId) ? "just-saved" : "rise");
    card.style.setProperty("--i", index);
    card.dataset.id = trip.id; card.dataset.status = status.key;
    const badge = document.createElement("span"); badge.className = "trip-badge"; badge.textContent = status.label;
    const route = document.createElement("h3"); route.className = "trip-route";
    route.setAttribute("aria-label", routeLabel(trip));
    const from = document.createElement("span"); from.textContent = airportLabel(trip.departure_airport_id);
    const to = document.createElement("span"); to.textContent = airportLabel(trip.arrival_airport_id);
    const path = document.createElement("span"); path.className = "trip-path"; path.setAttribute("aria-hidden", "true");
    const plane = document.createElement("i"); plane.className = "trip-plane"; plane.textContent = "✈︎";
    path.append(plane); route.append(from, path, to);
    const cities = document.createElement("p"); cities.className = "trip-cities";
    const departure = airportById(trip.departure_airport_id), arrival = airportById(trip.arrival_airport_id);
    cities.textContent = (departure?.city || "Origen") + " → " + (arrival?.city || "Destino");
    const meta = document.createElement("p"); meta.className = "trip-meta";
    meta.textContent = new Date(trip.departure_date + "T12:00:00").toLocaleDateString("es-CO", {day:"numeric",month:"long",year:"numeric"}) + " · " + trip.duration_days + " día(s)";
    const edit = document.createElement("button"); edit.className = "btn btn-sm btn-outline-secondary me-2"; edit.textContent = "Editar";
    edit.addEventListener("click", () => openForm(trip));
    const remove = document.createElement("button"); remove.className = "btn btn-sm text-danger"; remove.textContent = "Eliminar";
    remove.addEventListener("click", () => { pendingDelete = trip.id; $("delete-dialog").showModal(); });
    card.append(badge, route, cities, meta, edit, remove); column.append(card); $("trips-list").append(column);
  });
}
function openForm(trip = null, preset = {}) {
  if (!state.airports.length) { notice("Carga los aeropuertos antes de crear o editar un itinerario.", true); return; }
  $("form-error").hidden = true;
  $("itinerary-form").reset();
  $("itinerary-id").value = trip ? trip.id : "";
  $("form-title").textContent = trip ? "Ajusta tu itinerario" : "Un nuevo destino";
  for (const id of ["departure", "arrival"]) {
    $(id).replaceChildren(new Option("Selecciona un aeropuerto", ""));
    for (const airport of state.airports) $(id).add(new Option(airport.name + " · " + airport.city, airport.id));
  }
  if (trip) {
    $("departure").value = trip.departure_airport_id; $("arrival").value = trip.arrival_airport_id;
    $("departure-date").value = trip.departure_date; $("duration").value = trip.duration_days;
  } else if (preset.departure) {
    $("departure").value = preset.departure;
  }
  $("itinerary-dialog").showModal();
}
$("new-itinerary").addEventListener("click", () => openForm());
$("first-itinerary").addEventListener("click", () => openForm());
$("close-dialog").addEventListener("click", () => $("itinerary-dialog").close());
$("cancel-delete").addEventListener("click", () => $("delete-dialog").close());
$("confirm-delete").addEventListener("click", e => busy(e.currentTarget, async () => {
  const id = pendingDelete;
  await api("/itineraries/" + id, {method: "DELETE"});
  $("delete-dialog").close();
  const card = [...document.querySelectorAll(".trip-card")].find(item => item.dataset.id === String(id));
  if (card && !reduceMotion) { card.classList.add("leaving"); await wait(280); }
  state.trips = state.trips.filter(t => t.id !== id); state.reportLoaded = false;
  renderTrips();
  const message = "Itinerario eliminado.";
  showToast(message, "success");
  notice(message);
}));
$("itinerary-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = event.submitter; button.disabled = true; button.classList.add("is-loading");
  try {
    const body = {departure_airport_id: Number($("departure").value),
      arrival_airport_id: Number($("arrival").value), departure_date: $("departure-date").value,
      duration_days: Number($("duration").value)};
    if (body.departure_airport_id === body.arrival_airport_id) throw new Error("Elige aeropuertos de salida y llegada diferentes.");
    const id = $("itinerary-id").value;
    const saved = await api("/itineraries" + (id ? "/" + id : ""), {method: id ? "PUT" : "POST", body: JSON.stringify(body)});
    state.trips = id ? state.trips.map(t => t.id === id ? saved : t) : [...state.trips, saved];
    state.reportLoaded = false;
    $("itinerary-dialog").close(); showView("trips"); renderTrips(saved.id);
    const message = id ? "Cambios guardados." : "Itinerario creado.";
    showToast(message, "success");
    notice(message);
  } catch (error) {
    $("form-error").textContent = error.message; $("form-error").hidden = false;
    restartAnimation($("itinerary-dialog"), "shake");
  } finally { button.disabled = false; button.classList.remove("is-loading"); }
});

// ---------- Report ----------
$("refresh-report").addEventListener("click", e => busy(e.currentTarget, async () => {
  const report = await api("/reports");
  state.reportLoaded = true;
  $("report-metrics").replaceChildren();
  [["Itinerarios", report.total_itineraries], ["Días planeados", report.total_duration_days], ["Días por viaje", report.average_duration_days]]
    .forEach(([label, value], index) => {
      const column = document.createElement("div"); column.className = "col-md-4";
      const card = document.createElement("div"); card.className = "panel metric glow rise";
      card.style.setProperty("--i", index);
      const caption = document.createElement("span"); caption.textContent = label;
      const number = document.createElement("strong"); number.textContent = "0";
      card.append(caption, number); column.append(card); $("report-metrics").append(column);
      countUp(number, value);
    });
  $("report-caption").textContent = "Generado: " + new Date().toLocaleString("es-CO");
  $("report-routes").replaceChildren(); $("report-routes").hidden = false;
  const title = document.createElement("h3"); title.className = "h5 mb-3"; title.textContent = "Rutas planeadas"; $("report-routes").append(title);
  const routes = Object.entries(report.routes || {}).sort((a, b) => b[1] - a[1]);
  const max = Math.max(1, ...routes.map(([, count]) => count));
  const fills = [];
  routes.forEach(([route, count], index) => {
    const ids = route.split(" → ").map(Number);
    const row = document.createElement("div"); row.className = "route-row"; row.style.setProperty("--i", index);
    const name = document.createElement("span"); name.className = "route-name"; name.textContent = airportLabel(ids[0]) + " → " + airportLabel(ids[1]);
    const bar = document.createElement("span"); bar.className = "route-bar";
    const fill = document.createElement("span"); fill.className = "route-fill"; fill.dataset.width = (count / max * 100) + "%";
    bar.append(fill); fills.push(fill);
    const total = document.createElement("span"); total.className = "route-count"; total.textContent = count + " viaje(s)";
    row.append(name, bar, total); $("report-routes").append(row);
  });
  requestAnimationFrame(() => requestAnimationFrame(() => fills.forEach(fill => { fill.style.width = fill.dataset.width; })));
  if (!report.total_itineraries) $("report-routes").append(document.createTextNode("Aún no tienes itinerarios."));
}));

if (state.token) enter().catch(error => notice(error.message, true));
else startHero();
