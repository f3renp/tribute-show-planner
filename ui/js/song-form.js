// Add or edit a song (song.html, or song.html?id=7 to edit song 7).
// Data: GET /api/outfits for the outfit list, GET /api/songs/7 to fill the
// form. Saving: POST /api/songs (add) or PUT /api/songs/7 (edit).

const songId = queryId();
const form = document.getElementById("song-form");
const errorsList = document.getElementById("errors");
const heading = document.getElementById("heading");

async function loadForm() {
  heading.textContent = songId === null ? "Add a song" : "Edit song";
  const outfits = await loadData("catalogue", "/api/outfits", loadForm);
  if (outfits === null) {
    return;
  }
  if (outfits.length === 0) {
    document.getElementById("no-outfits").hidden = false;
    return;
  }
  fillOutfits(outfits);
  if (songId !== null) {
    const song = await loadData("catalogue", "/api/songs/" + songId, loadForm);
    if (song === null) {
      return;
    }
    fillSong(song);
  }
  form.hidden = false;
}

function fillOutfits(outfits) {
  const options = outfits.map((outfit) => {
    const option = el("option", outfit.name);
    option.value = outfit.id;
    return option;
  });
  form.elements.outfit_id.replaceChildren(...options);
}

// The API sends duration as "4:54", the same text it accepts back.
function fillSong(song) {
  heading.textContent = "Edit " + song.title;
  ["title", "album", "year", "duration", "energy", "kind", "outfit_id"].forEach((field) => {
    form.elements[field].value = song[field];
  });
}

form.addEventListener("submit", async (event) => {
  // Stop the browser's own form submit: the page sends JSON itself.
  event.preventDefault();
  setBusy(form, true);
  const result = songId === null
    ? await callApi("catalogue", "POST", "/api/songs", formToObject(form))
    : await callApi("catalogue", "PUT", "/api/songs/" + songId, formToObject(form));
  setBusy(form, false);
  if (result.ok) {
    window.location.href = "index.html";
  } else {
    showErrors(errorsList, result.errors);
  }
});

loadForm();
