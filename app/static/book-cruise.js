// Book a cruise page: loads upcoming trips from GET /available_trips and
// lists each one with its ship, dates and port stops.

const tripList = document.querySelector("#trip-list");
const tripCount = document.querySelector("#trip-count");
const tripMessage = document.querySelector("#trip-message");

// "2027-01-10" -> "Jan 10, 2027"
function formatDate(date) {
  return new Date(`${date}T00:00:00`).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

// "2027-01-10T11:00:00" -> "Jan 10, 11:00 AM"
function formatDateTime(dateTime) {
  return new Date(dateTime).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

// Build one trip card. Text is set with textContent, never innerHTML.
function renderTrip(trip) {
  const item = document.createElement("article");
  item.className = "trip-item";

  const details = document.createElement("div");
  details.className = "trip-details";

  const shipName = document.createElement("h3");
  shipName.textContent = trip.SHIP_NAME;

  const nights = `${trip.NIGHTS} ${trip.NIGHTS === 1 ? "night" : "nights"}`;
  const dates = document.createElement("p");
  dates.textContent = `${formatDate(trip.START_DATE)} – ${formatDate(trip.END_DATE)} · ${nights}`;

  details.append(shipName, dates);

  if (trip.PORT_STOPS.length > 0) {
    const departs = document.createElement("p");
    departs.textContent = `Departs from ${trip.PORT_STOPS[0].PORT_NAME}`;

    const itinerary = document.createElement("ol");
    itinerary.className = "trip-itinerary";
    for (const stop of trip.PORT_STOPS) {
      const stopItem = document.createElement("li");
      stopItem.textContent =
        `${stop.PORT_NAME} (${stop.CITY}): ` +
        `${formatDateTime(stop.PSTART_DATE)} – ${formatDateTime(stop.PEND_DATE)}`;
      itinerary.append(stopItem);
    }
    details.append(departs, itinerary);
  }

  // Booking needs login, which isn't built yet.
  const bookButton = document.createElement("button");
  bookButton.className = "button button-primary";
  bookButton.type = "button";
  bookButton.disabled = true;
  bookButton.title = "Booking opens once login is ready";
  bookButton.textContent = "Book (coming soon)";

  item.append(details, bookButton);
  return item;
}

function renderTrips(trips) {
  tripList.replaceChildren();
  tripCount.textContent = `${trips.length} ${trips.length === 1 ? "trip" : "trips"}`;
  tripMessage.textContent =
    trips.length === 0 ? "There are no upcoming trips right now. Check back soon." : "";
  for (const trip of trips) {
    tripList.append(renderTrip(trip));
  }
}

async function loadTrips() {
  try {
    const response = await fetch("/available_trips");
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    const data = await response.json();
    renderTrips(data.trips);
  } catch (error) {
    // Also what you see if the page was opened as a file instead of through
    // the server: the trip list only loads from http://127.0.0.1:8000.
    tripCount.textContent = "";
    tripMessage.textContent =
      "Couldn't load trips. Make sure the API is running (uvicorn main:app --reload) " +
      "and open this page at http://127.0.0.1:8000/book-cruise.";
  }
}

loadTrips();
