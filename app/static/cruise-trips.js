const form = document.querySelector("#trip-form");
const shipSelect = document.querySelector("#ship-name");
const tripList = document.querySelector("#trip-list");
const tripCount = document.querySelector("#trip-count");
const tripMessage = document.querySelector("#trip-message");
const listMessage = document.querySelector("#trip-list-message");
const portStops = document.querySelector("#port-stops");
const addStopButton = document.querySelector("#add-stop");
const submitButton = form.querySelector('button[type="submit"]');

let ships = [];
let ports = [];
let submitting = false;

async function requestJson(url, options) {
  const response = await fetch(url, options);
  const data = await response.json();
  if (!response.ok) {
    const detail = typeof data.detail === "string" ? data.detail : `HTTP ${response.status}`;
    throw new Error(detail);
  }
  return data;
}

function formatDate(date) {
  return new Date(`${date}T00:00:00`).toLocaleDateString(undefined, {
    year: "numeric", month: "short", day: "numeric",
  });
}

function formatDateTime(dateTime) {
  return new Date(dateTime).toLocaleString(undefined, {
    month: "short", day: "numeric", hour: "numeric", minute: "2-digit",
  });
}

function addPortStop() {
  const row = document.createElement("div");
  row.className = "port-stop-row";

  const portLabel = document.createElement("label");
  portLabel.textContent = "Port";
  const portSelect = document.createElement("select");
  portSelect.className = "stop-port";
  portSelect.required = true;
  const placeholder = document.createElement("option");
  placeholder.value = "";
  placeholder.textContent = "Select a port";
  portSelect.append(placeholder);
  for (const port of ports) {
    const option = document.createElement("option");
    option.value = port.PORT_ID;
    option.textContent = port.PORT_NAME;
    portSelect.append(option);
  }
  portLabel.append(portSelect);

  const arrivalLabel = document.createElement("label");
  arrivalLabel.textContent = "Arrival";
  const arrivalInput = document.createElement("input");
  arrivalInput.className = "stop-arrival";
  arrivalInput.type = "datetime-local";
  arrivalInput.required = true;
  arrivalLabel.append(arrivalInput);

  const departureLabel = document.createElement("label");
  departureLabel.textContent = "Departure";
  const departureInput = document.createElement("input");
  departureInput.className = "stop-departure";
  departureInput.type = "datetime-local";
  departureInput.required = true;
  departureLabel.append(departureInput);

  const removeButton = document.createElement("button");
  removeButton.className = "button button-remove-stop";
  removeButton.type = "button";
  removeButton.textContent = "Remove stop";
  removeButton.addEventListener("click", () => row.remove());

  row.append(portLabel, arrivalLabel, departureLabel, removeButton);
  portStops.append(row);
}

function normalizeDateTime(value) {
  return value.length === 16 ? `${value}:00` : value;
}

async function verifyPortStops(tripId, expectedStops) {
  const data = await requestJson("/current_port_stops");
  const actualStops = data.port_stops.filter((stop) => stop.TRIP_ID === tripId);
  const matches = actualStops.length === expectedStops.length && expectedStops.every((expected) =>
    actualStops.some((actual) =>
      actual.STOP_NO === expected.stop_no &&
      actual.PORT_ID === expected.port_id &&
      normalizeDateTime(actual.PSTART_DATE) === normalizeDateTime(expected.pstart_date) &&
      normalizeDateTime(actual.PEND_DATE) === normalizeDateTime(expected.pend_date)
    )
  );
  return matches;
}

async function loadTrips() {
  listMessage.textContent = "Loading scheduled trips...";
  try {
    const response = await fetch("/current_trips");
    const data = await response.json();
    if (!response.ok && !(response.status === 404 && data.detail === "No current cruise trips found")) {
      throw new Error(typeof data.detail === "string" ? data.detail : `HTTP ${response.status}`);
    }
    const trips = response.ok ? data.trips : [];
    const stopData = await requestJson("/current_port_stops");
    renderTrips(trips, stopData.port_stops);
    listMessage.textContent = "";
  } catch (error) {
    tripList.replaceChildren();
    tripCount.textContent = "";
    listMessage.textContent = `Couldn't load scheduled trips: ${error.message}. Refresh the page to retry.`;
  }
}

function renderTrips(trips, stops) {
  tripList.replaceChildren();
  tripCount.textContent = `${trips.length} ${trips.length === 1 ? "trip" : "trips"}`;
  if (trips.length === 0) {
    const emptyState = document.createElement("p");
    emptyState.className = "empty-state-message";
    emptyState.textContent = "There are no scheduled trips yet.";
    tripList.append(emptyState);
    return;
  }

  const shipNames = new Map(ships.map((ship) => [ship.SHIP_ID, ship.SHIP_NAME]));
  const portNames = new Map(ports.map((port) => [port.PORT_ID, port.PORT_NAME]));
  for (const trip of trips) {
    const name = shipNames.get(trip.SHIP_ID) ?? `Ship ${trip.SHIP_ID}`;
    const item = document.createElement("article");
    item.className = "trip-item";
    const details = document.createElement("div");
    details.className = "trip-details";
    const shipName = document.createElement("h3");
    shipName.textContent = name;
    const dates = document.createElement("p");
    dates.textContent = `${formatDate(trip.START_DATE)} – ${formatDate(trip.END_DATE)}`;
    const itinerary = document.createElement("ol");
    itinerary.className = "trip-itinerary";
    for (const stop of stops.filter((stop) => stop.TRIP_ID === trip.TRIP_ID)) {
      const stopItem = document.createElement("li");
      const portName = portNames.get(stop.PORT_ID) ?? `Port ${stop.PORT_ID}`;
      stopItem.textContent =
        `${portName}: ${formatDateTime(stop.PSTART_DATE)} – ${formatDateTime(stop.PEND_DATE)}`;
      itinerary.append(stopItem);
    }
    const removeButton = document.createElement("button");
    removeButton.className = "button button-danger";
    removeButton.type = "button";
    removeButton.textContent = "Remove trip";
    removeButton.setAttribute("aria-label", `Remove ${name} trip ${trip.TRIP_ID}`);
    removeButton.addEventListener("click", async () => {
      if (!window.confirm(`Permanently remove trip ${trip.TRIP_ID} and its port stops?`)) {
        return;
      }
      removeButton.disabled = true;
      try {
        await requestJson(`/delete_trip/${trip.TRIP_ID}`, { method: "DELETE" });
        tripMessage.textContent = `Trip ${trip.TRIP_ID} removed.`;
        await loadTrips();
      } catch (error) {
        tripMessage.textContent = `Couldn't remove trip: ${error.message}`;
        removeButton.disabled = false;
      }
    });
    details.append(shipName, dates, itinerary);
    item.append(details, removeButton);
    tripList.append(item);
  }
}

addStopButton.addEventListener("click", addPortStop);

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (submitting) return;

  const start = document.querySelector("#start-date").value;
  const end = document.querySelector("#end-date").value;
  const stops = [...portStops.querySelectorAll(".port-stop-row")].map((row, index) => ({
    stop_no: index + 1,
    port_id: Number(row.querySelector(".stop-port").value),
    pstart_date: row.querySelector(".stop-arrival").value,
    pend_date: row.querySelector(".stop-departure").value,
  }));
  if (end <= start) {
    tripMessage.textContent = "End date must be after the start date.";
    document.querySelector("#end-date").focus();
    return;
  }
  if (stops.length === 0) {
    tripMessage.textContent = "Add at least one port stop to the itinerary.";
    addStopButton.focus();
    return;
  }
  for (const [index, stop] of stops.entries()) {
    if (
      stop.pend_date <= stop.pstart_date ||
      stop.pstart_date.slice(0, 10) < start ||
      stop.pend_date.slice(0, 10) > end ||
      (index > 0 && stop.pstart_date < stops[index - 1].pend_date)
    ) {
      tripMessage.textContent =
        "Each stop must be within the trip dates and follow the previous stop, with departure after arrival.";
      portStops.querySelectorAll(".stop-arrival")[index].focus();
      return;
    }
  }

  submitting = true;
  submitButton.disabled = true;
  tripMessage.textContent = "Saving trip...";
  const payload = {
    ship_id: Number(shipSelect.value),
    start_date: start,
    end_date: end,
    port_stops: stops,
  };
  try {
    const result = await requestJson("/create_trip", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    form.reset();
    portStops.replaceChildren();
    addPortStop();
    try {
      const verified = await verifyPortStops(result.trip_id, stops);
      if (verified) {
        tripMessage.textContent =
          `Trip ${result.trip_id} created with ${stops.length} port ${stops.length === 1 ? "stop" : "stops"}.`;
      } else {
        tripMessage.textContent = `Trip ${result.trip_id} was created, but its saved port stops do not match. Check the server terminal and database; do not resubmit the trip.`;
      }
    } catch (error) {
      tripMessage.textContent = `Trip ${result.trip_id} was created, but its port stops could not be verified: ${error.message}. Check the server terminal and database; do not resubmit the trip.`;
    }
    await loadTrips();
  } catch (error) {
    tripMessage.textContent = `Couldn't confirm trip creation: ${error.message}. Check scheduled trips before retrying.`;
  } finally {
    submitting = false;
    submitButton.disabled = false;
  }
});

async function initialize() {
  tripMessage.textContent = "Loading ships and ports...";
  try {
    const [shipData, portData] = await Promise.all([
      requestJson("/get_cruises"),
      requestJson("/current_ports"),
    ]);
    ships = shipData.cruises;
    ports = portData.ports;
    for (const ship of ships) {
      const option = document.createElement("option");
      option.value = ship.SHIP_ID;
      option.textContent = ship.SHIP_NAME;
      shipSelect.append(option);
    }
    shipSelect.disabled = ships.length === 0;
    addStopButton.disabled = ports.length === 0;
    submitButton.disabled = ships.length === 0 || ports.length === 0;
    if (ports.length > 0) addPortStop();
    tripMessage.textContent = ships.length === 0 || ports.length === 0
      ? "Add at least one ship and one port before creating a trip."
      : "";
    await loadTrips();
  } catch (error) {
    tripMessage.textContent = `Couldn't load ships or ports: ${error.message}. Refresh the page to retry.`;
    listMessage.textContent = "Scheduled trips could not be loaded.";
  }
}

initialize();
