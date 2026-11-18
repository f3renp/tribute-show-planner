// One show (show.html?id=4): its setlist, running time and checks, and every
// change to it. Data: GET /api/shows/4 (the overview) on the shows service.
// Every change (edit, add song or break, move, remove) answers with the new
// overview, and the page is redrawn from it: the checks are always the
// ones the service just ran. The page never computes a check itself.

const showId = queryId();
const content = document.getElementById("content");
const editForm = document.getElementById("edit-form");
const songForm = document.getElementById("song-form");
const breakForm = document.getElementById("break-form");
const setlistErrors = document.getElementById("setlist-errors");

async function loadShow() {
  if (showId === null) {
    window.location.href = "shows.html";
    return;
  }
  const overview = await loadData("shows", "/api/shows/" + showId, loadShow);
  if (overview !== null) {
    renderOverview(overview);
  }
}

// Draw the whole page from one overview.
function renderOverview(overview) {
  content.hidden = false;
  renderShow(overview.show);
  document.getElementById("catalogue-down").hidden = overview.catalogue_available;
  renderSetlist(overview);
  renderSongPicker(overview);
}

function renderShow(show) {
  document.title = show.name + " - Tribute Show Planner";
  document.getElementById("show-name").textContent = show.name;
  document.getElementById("show-facts").textContent =
    show.venue + ", " + show.show_date + ". Limit: " + show.max_minutes + " minutes.";
  ["name", "venue", "show_date", "max_minutes"].forEach((field) => {
    editForm.elements[field].value = show[field];
  });
}

// Setlist, running time and checks -------------------------------------

function renderSetlist(overview) {
  const items = overview.items;
  const rows = items.map((item, index) =>
    itemRow(item, index === 0, index === items.length - 1, overview.catalogue_available)
  );
  document.querySelector("#setlist tbody").replaceChildren(...rows);
  document.getElementById("empty-setlist").hidden = items.length > 0;
  document.getElementById("setlist-results").hidden = items.length === 0;
  renderRunningTime(overview);
  renderChecks(overview.problems);
}

// The cells of one row, as text: item, duration, energy, kind, outfit.
function itemCells(item, catalogueAvailable) {
  if (item.item_type === "break") {
    return ["Break: " + item.break_label, item.break_seconds + " s", "", "", ""];
  }
  if (item.song !== null) {
    const song = item.song;
    return [song.title, song.duration, song.energy, song.kind, song.outfit_name];
  }
  // No details: the catalogue is down, or the song is no longer in it.
  const label = catalogueAvailable ? "Unknown song" : "Song details unavailable";
  return [label + " (id " + item.song_id + ")", "", "", "", ""];
}

function itemRow(item, isFirst, isLast, catalogueAvailable) {
  const row = el("tr", null, item.item_type);
  row.appendChild(el("td", item.position));
  itemCells(item, catalogueAvailable).forEach((text) => row.appendChild(el("td", text)));

  const actions = el("td", null, "actions");
  const moves = el("span");
  const up = button("Up", () => moveItem(item, "up", row));
  const down = button("Down", () => moveItem(item, "down", row));
  up.disabled = isFirst;
  down.disabled = isLast;
  moves.append(up, down);
  actions.append(moves, button("Remove", () => removeItem(item, row)));
  row.appendChild(actions);
  return row;
}

function renderRunningTime(overview) {
  const box = document.getElementById("running-time");
  const limit = overview.show.max_minutes + " minutes";
  if (overview.total_duration === null) {
    box.className = "running-time";
    box.textContent = "Running time unknown (catalogue unavailable), limit " + limit + ".";
    return;
  }
  box.className = overview.over_limit ? "running-time over-limit" : "running-time";
  box.replaceChildren(
    "Running time ", el("strong", overview.total_duration), " of a " + limit + " limit"
  );
}

// problems: null = skipped (catalogue down), [] = none found.
function renderChecks(problems) {
  const checks = document.getElementById("checks");
  if (problems === null) {
    checks.replaceChildren(el("p", "Checks skipped: the catalogue service is unavailable.", "checks-skipped"));
  } else if (problems.length === 0) {
    checks.replaceChildren(el("p", "No problems found.", "no-problems"));
  } else {
    const list = el("ul", null, "problems");
    list.replaceChildren(...problems.map((problem) => el("li", problem)));
    checks.replaceChildren(list);
  }
}

function renderSongPicker(overview) {
  const message = document.getElementById("no-song-picker");
  const canPick = overview.catalogue_available && overview.songs.length > 0;
  songForm.hidden = !canPick;
  message.hidden = canPick;
  if (!overview.catalogue_available) {
    message.textContent = "Songs cannot be added while the catalogue service is unavailable.";
  } else if (overview.songs.length === 0) {
    const link = el("a", "catalogue");
    link.href = "index.html";
    message.replaceChildren("No active songs. Add some in the ", link, " first.");
  }
  const options = overview.songs.map((song) => {
    const option = el("option", song.title + " (" + song.album + ")");
    option.value = song.id;
    return option;
  });
  songForm.elements.song_id.replaceChildren(...options);
}

// Changes --------------------------------------------------------------

// Send one change to the shows service. On success redraw the page from the
// overview it answers with; otherwise show the messages in errorsList.
// busyElement's buttons are disabled meanwhile. Returns true if it worked.
async function change(method, path, body, errorsList, busyElement) {
  setBusy(busyElement, true);
  const result = await callApi("shows", method, "/api/shows/" + showId + path, body);
  setBusy(busyElement, false);
  showErrors(errorsList, result.errors);
  if (result.ok) {
    renderOverview(result.data);
  }
  return result.ok;
}

function moveItem(item, direction, row) {
  change("POST", "/items/" + item.id + "/move", { direction: direction }, setlistErrors, row);
}

function removeItem(item, row) {
  if (window.confirm("Remove this item from the setlist?")) {
    change("DELETE", "/items/" + item.id, undefined, setlistErrors, row);
  }
}

editForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const errorsList = document.getElementById("edit-errors");
  if (await change("PUT", "", formToObject(editForm), errorsList, editForm)) {
    document.getElementById("edit-details").open = false;
  }
});

document.getElementById("delete-show").addEventListener("click", async () => {
  if (!window.confirm("Delete this show and its whole setlist?")) {
    return;
  }
  setBusy(editForm, true);
  const result = await callApi("shows", "DELETE", "/api/shows/" + showId);
  setBusy(editForm, false);
  if (result.ok) {
    window.location.href = "shows.html";
  } else {
    showErrors(document.getElementById("edit-errors"), result.errors);
  }
});

songForm.addEventListener("submit", (event) => {
  event.preventDefault();
  // A 503 ("Catalogue service unavailable: the song could not be checked
  // and was not added...") is shown next to this form like any error.
  change("POST", "/songs", formToObject(songForm), document.getElementById("song-errors"), songForm);
});

breakForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const errorsList = document.getElementById("break-errors");
  if (await change("POST", "/breaks", formToObject(breakForm), errorsList, breakForm)) {
    breakForm.reset();
  }
});

loadShow();
