// Songs page (index.html): every song, with Edit, Retire and Reactivate.
// Data: GET /api/songs/all on the catalogue.

const songsTable = document.getElementById("songs");
const noSongs = document.getElementById("no-songs");
const errorsList = document.getElementById("errors");

async function loadSongs() {
  const songs = await loadData("catalogue", "/api/songs/all", loadSongs);
  if (songs !== null) {
    renderSongs(songs);
  }
}

function renderSongs(songs) {
  const rows = songs.map(songRow);
  songsTable.querySelector("tbody").replaceChildren(...rows);
  songsTable.hidden = songs.length === 0;
  noSongs.hidden = songs.length > 0;
}

function songRow(song) {
  const row = el("tr", null, song.active ? "" : "retired");
  const cells = [
    song.title, song.album, song.year, song.duration, song.energy,
    song.kind, song.outfit_name, song.active ? "Active" : "Retired",
  ];
  cells.forEach((text) => row.appendChild(el("td", text)));

  const actions = el("td", null, "actions");
  const edit = el("a", "Edit");
  edit.href = "song.html?id=" + song.id;
  actions.appendChild(edit);
  if (song.active) {
    actions.appendChild(button("Retire", () => retire(song, row)));
  } else {
    actions.appendChild(button("Reactivate", () => changeStatus(song, "reactivate", row)));
  }
  row.appendChild(actions);
  return row;
}

function retire(song, row) {
  const question =
    "Retire " + song.title + "? It stays in existing setlists but cannot be added to new ones.";
  if (window.confirm(question)) {
    changeStatus(song, "retire", row);
  }
}

// POST /api/songs/7/retire or /reactivate, then reload the list.
async function changeStatus(song, action, row) {
  setBusy(row, true);
  const result = await callApi("catalogue", "POST", "/api/songs/" + song.id + "/" + action);
  setBusy(row, false);
  showErrors(errorsList, result.errors);
  if (result.ok) {
    loadSongs();
  }
}

loadSongs();
