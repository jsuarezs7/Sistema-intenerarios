"use strict";
const $ = (id) => document.getElementById(id);
const state = {token: sessionStorage.getItem("ruta-token"), airports: [], trips: [], view: "explore", shown: 12};
let pendingDelete = null;

function notice(message, error = false) {
  $("notice").textContent = message;
  $("notice").className = "alert " + (error ? "alert-danger" : "alert-success");
  $("notice").hidden = false;
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
  } catch { throw new Error("No hay conexión con el servidor. Inténtalo nuevamente."); }
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
  button.disabled = true;
  try { await action(); } catch (error) { notice(error.message, true); }
  finally { button.disabled = false; }
}
function showView(view) {
  state.view = view;
  for (const name of ["explore", "trips", "reports"]) $(name + "-view").hidden = name !== view;
  document.querySelectorAll("[data-view]").forEach(button => {
    if (button.dataset.view === view) button.setAttribute("aria-current", "page");
    else button.removeAttribute("aria-current");
  });
  if (view === "explore" && window.Plotly && $("map").data) Plotly.Plots.resize($("map"));
}
function logout() {
  state.token = null; state.airports = []; state.trips = [];
  sessionStorage.removeItem("ruta-token");
  sessionStorage.removeItem("ruta-user");
  $("workspace").hidden = true; $("account").hidden = true; $("login-view").hidden = false;
  $("login-password").value = "";
  $("itinerary-dialog").close(); $("delete-dialog").close();
  $("trips-list").replaceChildren(); $("report-metrics").replaceChildren();
  $("report-routes").replaceChildren(); $("report-routes").hidden = true;
  $("report-caption").textContent = "Genera un reporte para consultar las métricas de tus itinerarios.";
}
async function enter() {
  $("login-view").hidden = true; $("workspace").hidden = false; $("account").hidden = false;
  $("username").textContent = sessionStorage.getItem("ruta-user") || "Mi cuenta";
  showView("explore");
  const results = await Promise.allSettled([loadAirports(), loadTrips()]);
  for (const result of results) if (result.status === "rejected") notice(result.reason.message, true);
}
$("login-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  await busy(event.submitter, async () => {
    const result = await api("/auth/login", {method: "POST", body: JSON.stringify({
      username: $("login-user").value.trim(), password: $("login-password").value
    })});
    state.token = result.access_token;
    sessionStorage.setItem("ruta-token", state.token);
    sessionStorage.setItem("ruta-user", $("login-user").value.trim());
    $("login-password").value = ""; $("notice").hidden = true;
    await enter();
  });
});
$("logout").addEventListener("click", logout);
document.querySelectorAll("[data-view]").forEach(button => button.addEventListener("click", () => showView(button.dataset.view)));

function airportLabel(id) {
  const airport = state.airports.find(item => item.id === id);
  return airport ? (airport.iata_code || airport.city || airport.name) : "#" + id;
}
async function loadAirports() {
  $("map-status").textContent = "Cargando aeropuertos…";
  try {
    const airports = await api("/airports");
    if (!state.token) return;
    state.airports = airports;
    $("map-caption").textContent = airports.length + " aeropuertos para explorar";
    renderAirports(); renderTrips();
    const located = airports.filter(a => Number.isFinite(a.latitude) && Number.isFinite(a.longitude));
    if (!window.Plotly) throw new Error("No se pudo cargar el mapa. La lista de aeropuertos sigue disponible.");
    const escape = value => String(value).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
    await Plotly.newPlot("map", [{
      type: "scattergeo", mode: "markers",
      lat: located.map(a => a.latitude), lon: located.map(a => a.longitude),
      text: located.map(a => escape(a.name) + "<br>" + escape(a.city)),
      hovertemplate: "%{text}<extra></extra>",
      marker: {size: 8, color: "#246453", opacity: .85, line: {color: "white", width: 1.2}}
    }], {
      margin: {t: 12, r: 8, b: 12, l: 8}, paper_bgcolor: "#edf2ed",
      geo: {projection: {type: "mercator"}, resolution: 50, showland: true,
        landcolor: "#dce6d9", showocean: true, oceancolor: "#edf2ed",
        showcountries: true, countrycolor: "#a5b8aa", coastlinecolor: "#a5b8aa",
        bgcolor: "#edf2ed", lonaxis: {range: [-82, -66]}, lataxis: {range: [-5, 14]}}
    }, {responsive: true, displayModeBar: false});
    $("map-status").textContent = located.length + " ubicaciones en el mapa. " +
      (airports.length - located.length) + " aeropuertos sin coordenadas válidas.";
  } catch (error) { $("map-status").textContent = error.message; throw error; }
}
function renderAirports() {
  const query = $("airport-search").value.toLocaleLowerCase("es");
  const matching = state.airports.filter(a => [a.name, a.city, a.iata_code].join(" ").toLocaleLowerCase("es").includes(query));
  $("airport-list").replaceChildren();
  for (const airport of matching.slice(0, state.shown)) {
    const column = document.createElement("div"); column.className = "col-md-6 col-lg-4";
    const card = document.createElement("article"); card.className = "panel airport-card";
    const code = document.createElement("span"); code.className = "code"; code.textContent = airport.iata_code || "SIN IATA";
    const title = document.createElement("h3"); title.textContent = airport.name;
    const city = document.createElement("p"); city.className = "small text-secondary mb-0"; city.textContent = airport.city || "Ciudad no informada";
    card.append(code, title, city); column.append(card); $("airport-list").append(column);
  }
  if (!matching.length) $("airport-list").textContent = "No encontramos aeropuertos con esa búsqueda.";
  $("more-airports").hidden = matching.length <= state.shown;
}
$("airport-search").addEventListener("input", () => { state.shown = 12; renderAirports(); });
$("more-airports").addEventListener("click", () => { state.shown += 12; renderAirports(); });
$("reload-airports").addEventListener("click", e => busy(e.currentTarget, loadAirports));

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
function renderTrips() {
  $("trip-count").textContent = state.trips.length;
  $("trips-empty").hidden = state.trips.length !== 0;
  $("trips-list").replaceChildren();
  for (const trip of state.trips) {
    const column = document.createElement("div"); column.className = "col-md-6 col-lg-4";
    const card = document.createElement("article"); card.className = "panel trip-card";
    const route = document.createElement("h3"); route.className = "trip-route";
    route.textContent = airportLabel(trip.departure_airport_id) + " → " + airportLabel(trip.arrival_airport_id);
    const meta = document.createElement("p"); meta.className = "trip-meta";
    meta.textContent = new Date(trip.departure_date + "T12:00:00").toLocaleDateString("es-CO", {day:"numeric",month:"long",year:"numeric"}) + " · " + trip.duration_days + " día(s)";
    const edit = document.createElement("button"); edit.className = "btn btn-sm btn-outline-secondary me-2"; edit.textContent = "Editar";
    edit.addEventListener("click", () => openForm(trip));
    const remove = document.createElement("button"); remove.className = "btn btn-sm text-danger"; remove.textContent = "Eliminar";
    remove.addEventListener("click", () => { pendingDelete = trip.id; $("delete-dialog").showModal(); });
    card.append(route, meta, edit, remove); column.append(card); $("trips-list").append(column);
  }
}
function openForm(trip = null) {
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
  }
  $("itinerary-dialog").showModal();
}
$("new-itinerary").addEventListener("click", () => openForm());
$("first-itinerary").addEventListener("click", () => openForm());
$("close-dialog").addEventListener("click", () => $("itinerary-dialog").close());
$("cancel-delete").addEventListener("click", () => $("delete-dialog").close());
$("confirm-delete").addEventListener("click", e => busy(e.currentTarget, async () => {
  await api("/itineraries/" + pendingDelete, {method: "DELETE"});
  $("delete-dialog").close();
  state.trips = state.trips.filter(t => t.id !== pendingDelete); renderTrips();
  notice("Itinerario eliminado.");
}));
$("itinerary-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = event.submitter; button.disabled = true;
  try {
    const body = {departure_airport_id: Number($("departure").value),
      arrival_airport_id: Number($("arrival").value), departure_date: $("departure-date").value,
      duration_days: Number($("duration").value)};
    if (body.departure_airport_id === body.arrival_airport_id) throw new Error("Elige aeropuertos de salida y llegada diferentes.");
    const id = $("itinerary-id").value;
    const saved = await api("/itineraries" + (id ? "/" + id : ""), {method: id ? "PUT" : "POST", body: JSON.stringify(body)});
    state.trips = id ? state.trips.map(t => t.id === id ? saved : t) : [...state.trips, saved];
    $("itinerary-dialog").close(); renderTrips(); showView("trips");
    notice(id ? "Cambios guardados." : "Itinerario creado. La notificación se procesará en segundo plano.");
  } catch (error) { $("form-error").textContent = error.message; $("form-error").hidden = false; }
  finally { button.disabled = false; }
});
$("refresh-report").addEventListener("click", e => busy(e.currentTarget, async () => {
  const report = await api("/reports");
  $("report-metrics").replaceChildren();
  for (const [label, value] of [["Itinerarios", report.total_itineraries], ["Días planeados", report.total_duration_days], ["Días por viaje", report.average_duration_days]]) {
    const column = document.createElement("div"); column.className = "col-md-4";
    const card = document.createElement("div"); card.className = "panel metric";
    const caption = document.createElement("span"); caption.textContent = label;
    const number = document.createElement("strong"); number.textContent = value;
    card.append(caption, number); column.append(card); $("report-metrics").append(column);
  }
  $("report-caption").textContent = "Generado: " + new Date().toLocaleString("es-CO");
  $("report-routes").replaceChildren(); $("report-routes").hidden = false;
  const title = document.createElement("h3"); title.className = "h5"; title.textContent = "Rutas planeadas"; $("report-routes").append(title);
  for (const [route, count] of Object.entries(report.routes)) {
    const ids = route.split(" → ").map(Number);
    const line = document.createElement("p"); line.className = "mb-2";
    line.textContent = airportLabel(ids[0]) + " → " + airportLabel(ids[1]) + " · " + count + " viaje(s)";
    $("report-routes").append(line);
  }
  if (!report.total_itineraries) $("report-routes").append(document.createTextNode("Aún no tienes itinerarios."));
}));
if (state.token) enter().catch(error => notice(error.message, true));
