const ports = [
  "PortMiami",
  "Port Canaveral",
  "Port Everglades",
  "Port Tampa Bay",
  "Port of Galveston",
  "Port of New Orleans",
  "Port of Key West",
  "Port of San Juan",
  "Havensight Cruise Dock",
  "Cozumel Cruise Terminal",
  "Costa Maya Port",
  "Port of Seattle Pier 91",
  "Juneau Cruise Terminal",
  "Ketchikan Cruise Berths",
  "Skagway Railroad Dock",
  "World Cruise Center",
  "Port of San Diego",
  "Ensenada Cruiseport Village",
  "Cabo San Lucas Tender Pier",
  "Puerto Vallarta Cruise Terminal",
  "Cape Liberty Cruise Port",
  "Flynn Cruiseport Boston",
  "Aloha Tower Marketplace",
];

const trips = [
  {
    id: 1,
    ship: "Test",
    start: "2027-01-10",
    end: "2027-01-17",
    stops: [
      { port: "PortMiami", arrival: "2027-01-10T11:00", departure: "2027-01-10T16:00" },
      { port: "Port of San Juan", arrival: "2027-01-12T08:00", departure: "2027-01-12T17:00" },
      { port: "Havensight Cruise Dock", arrival: "2027-01-13T08:00", departure: "2027-01-13T17:00" },
      { port: "Port of Key West", arrival: "2027-01-15T08:00", departure: "2027-01-15T17:00" },
      { port: "PortMiami", arrival: "2027-01-17T07:00", departure: "2027-01-17T10:00" },
    ],
  },
];

const form = document.querySelector("#trip-form");
const tripList = document.querySelector("#trip-list");
const tripCount = document.querySelector("#trip-count");
const tripMessage = document.querySelector("#trip-message");
const portStops = document.querySelector("#port-stops");

function formatDate(date) {
  return new Date(`${date}T00:00:00`).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

function formatDateTime(dateTime) {
  return new Date(dateTime).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function addPortStop(stop = {}) {
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
    option.value = port;
    option.textContent = port;
    portSelect.append(option);
  }
  portSelect.value = stop.port ?? "";
  portLabel.append(portSelect);

  const arrivalLabel = document.createElement("label");
  arrivalLabel.textContent = "Arrival";
  const arrivalInput = document.createElement("input");
  arrivalInput.className = "stop-arrival";
  arrivalInput.type = "datetime-local";
  arrivalInput.required = true;
  arrivalInput.value = stop.arrival ?? "";
  arrivalLabel.append(arrivalInput);

  const departureLabel = document.createElement("label");
  departureLabel.textContent = "Departure";
  const departureInput = document.createElement("input");
  departureInput.className = "stop-departure";
  departureInput.type = "datetime-local";
  departureInput.required = true;
  departureInput.value = stop.departure ?? "";
  departureLabel.append(departureInput);

  const removeButton = document.createElement("button");
  removeButton.className = "button button-remove-stop";
  removeButton.type = "button";
  removeButton.textContent = "Remove stop";
  removeButton.addEventListener("click", () => row.remove());

  row.append(portLabel, arrivalLabel, departureLabel, removeButton);
  portStops.append(row);
}

function renderTrips() {
  tripList.replaceChildren();
  tripCount.textContent = `${trips.length} ${trips.length === 1 ? "trip" : "trips"}`;

  if (trips.length === 0) {
    const emptyState = document.createElement("p");
    emptyState.className = "empty-state-message";
    emptyState.textContent = "There are no scheduled trips yet.";
    tripList.append(emptyState);
    return;
  }

  for (const trip of trips) {
    const item = document.createElement("article");
    item.className = "trip-item";

    const details = document.createElement("div");
    details.className = "trip-details";

    const shipName = document.createElement("h3");
    shipName.textContent = trip.ship;

    const dates = document.createElement("p");
    dates.textContent = `${formatDate(trip.start)} – ${formatDate(trip.end)}`;

    const ship = document.createElement("p");
    ship.className = "trip-ship";
    ship.textContent = `Ship: ${trip.ship}`;

    const itinerary = document.createElement("ol");
    itinerary.className = "trip-itinerary";
    for (const stop of trip.stops) {
      const stopItem = document.createElement("li");
      stopItem.textContent =
        `${stop.port}: ${formatDateTime(stop.arrival)} – ${formatDateTime(stop.departure)}`;
      itinerary.append(stopItem);
    }

    const removeButton = document.createElement("button");
    removeButton.className = "button button-danger";
    removeButton.type = "button";
    removeButton.textContent = "Remove trip";
    removeButton.setAttribute("aria-label", `Remove ${trip.ship} trip`);
    removeButton.addEventListener("click", () => {
      if (!window.confirm(`Remove the ${trip.ship} trip from this preview?`)) {
        return;
      }

      trips.splice(
        trips.findIndex((currentTrip) => currentTrip.id === trip.id),
        1,
      );
      tripMessage.textContent = "Trip removed from this preview.";
      renderTrips();
    });

    details.append(shipName, dates, ship, itinerary);
    item.append(details, removeButton);
    tripList.append(item);
  }
}

document.querySelector("#add-stop").addEventListener("click", () => {
  addPortStop();
});

form.addEventListener("submit", (event) => {
  event.preventDefault();

  const ship = document.querySelector("#ship-name").value;
  const start = document.querySelector("#start-date").value;
  const end = document.querySelector("#end-date").value;
  const stops = [...portStops.querySelectorAll(".port-stop-row")].map((row) => ({
    port: row.querySelector(".stop-port").value,
    arrival: row.querySelector(".stop-arrival").value,
    departure: row.querySelector(".stop-departure").value,
  }));

  if (end <= start) {
    tripMessage.textContent = "End date must be after the start date.";
    document.querySelector("#end-date").focus();
    return;
  }

  if (stops.length === 0) {
    tripMessage.textContent = "Add at least one port stop to the itinerary.";
    document.querySelector("#add-stop").focus();
    return;
  }

  for (const [index, stop] of stops.entries()) {
    const arrivalDate = stop.arrival.slice(0, 10);
    const departureDate = stop.departure.slice(0, 10);
    if (
      stop.departure <= stop.arrival ||
      arrivalDate < start ||
      departureDate > end ||
      (index > 0 && stop.arrival < stops[index - 1].departure)
    ) {
      tripMessage.textContent =
        "Each stop must be within the trip dates and follow the previous stop.";
      portStops.querySelectorAll(".stop-arrival")[index].focus();
      return;
    }
  }

  trips.unshift({
    id: Math.max(0, ...trips.map((trip) => trip.id)) + 1,
    ship,
    start,
    end,
    stops,
  });
  form.reset();
  portStops.replaceChildren();
  addPortStop();
  tripMessage.textContent = "Trip added to this preview.";
  renderTrips();
});

addPortStop();
renderTrips();
