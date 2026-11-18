// Shows page: every show, and the form to plan a new one.
// Data: GET /api/shows on the shows service. Saving: POST /api/shows.

const showsTable = document.getElementById("shows");
const noShows = document.getElementById("no-shows");
const showForm = document.getElementById("show-form");
const errorsList = document.getElementById("errors");

async function loadShows() {
  const shows = await loadData("shows", "/api/shows", loadShows);
  if (shows !== null) {
    renderShows(shows);
  }
}

function renderShows(shows) {
  showsTable.querySelector("tbody").replaceChildren(...shows.map(showRow));
  showsTable.hidden = shows.length === 0;
  noShows.hidden = shows.length > 0;
}

function showRow(show) {
  const row = el("tr");
  const nameCell = el("td");
  const link = el("a", show.name);
  link.href = "show.html?id=" + show.id;
  nameCell.appendChild(link);
  row.appendChild(nameCell);
  [show.venue, show.show_date, show.max_minutes].forEach((text) => {
    row.appendChild(el("td", text));
  });
  return row;
}

// A new show opens its own page, where the setlist is built.
showForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  setBusy(showForm, true);
  const result = await callApi("shows", "POST", "/api/shows", formToObject(showForm));
  setBusy(showForm, false);
  if (result.ok) {
    window.location.href = "show.html?id=" + result.data.id;
  } else {
    showErrors(errorsList, result.errors);
  }
});

loadShows();
