// Outfits page: list, add, edit and remove outfits.
// Data: GET /api/outfits (each with song_count). Saving: POST /api/outfits,
// PUT /api/outfits/3, DELETE /api/outfits/3.

const outfitsTable = document.getElementById("outfits");
const noOutfits = document.getElementById("no-outfits");
const listErrors = document.getElementById("list-errors");
const outfitForm = document.getElementById("outfit-form");
const formErrors = document.getElementById("form-errors");
const formHeading = document.getElementById("form-heading");
const saveButton = document.getElementById("save");
const cancelEditButton = document.getElementById("cancel-edit");

// The id of the outfit being edited, or null while the form adds a new one.
let editingId = null;

async function loadOutfits() {
  const outfits = await loadData("catalogue", "/api/outfits", loadOutfits);
  if (outfits !== null) {
    renderOutfits(outfits);
  }
}

function renderOutfits(outfits) {
  outfitsTable.querySelector("tbody").replaceChildren(...outfits.map(outfitRow));
  outfitsTable.hidden = outfits.length === 0;
  noOutfits.hidden = outfits.length > 0;
}

function songCountText(count) {
  return count === 1 ? "1 song" : count + " songs";
}

function outfitRow(outfit) {
  const row = el("tr");
  row.appendChild(el("td", outfit.name));
  row.appendChild(el("td", outfit.change_seconds));
  row.appendChild(el("td", songCountText(outfit.song_count)));

  const actions = el("td", null, "actions");
  actions.appendChild(button("Edit", () => startEditing(outfit)));
  const remove = button("Remove", () => removeOutfit(outfit, row));
  actions.appendChild(remove);
  // The catalogue refuses (409) to remove an outfit songs use; the button
  // says so before the user tries.
  if (outfit.song_count > 0) {
    remove.disabled = true;
    remove.title = "Used by " + songCountText(outfit.song_count) + ": move them to another outfit first.";
    actions.appendChild(el("span", "in use", "hint"));
  }
  row.appendChild(actions);
  return row;
}

function startEditing(outfit) {
  editingId = outfit.id;
  outfitForm.elements.name.value = outfit.name;
  outfitForm.elements.change_seconds.value = outfit.change_seconds;
  formHeading.textContent = "Edit " + outfit.name;
  saveButton.textContent = "Save";
  cancelEditButton.hidden = false;
  showErrors(formErrors, []);
  outfitForm.elements.name.focus();
}

function stopEditing() {
  editingId = null;
  outfitForm.reset();
  formHeading.textContent = "Add an outfit";
  saveButton.textContent = "Add outfit";
  cancelEditButton.hidden = true;
  showErrors(formErrors, []);
}

async function removeOutfit(outfit, row) {
  if (!window.confirm("Remove the outfit " + outfit.name + "?")) {
    return;
  }
  setBusy(row, true);
  const result = await callApi("catalogue", "DELETE", "/api/outfits/" + outfit.id);
  setBusy(row, false);
  // A 409 (songs started using it meanwhile) shows its message here.
  showErrors(listErrors, result.errors);
  if (result.ok) {
    if (editingId === outfit.id) {
      stopEditing();
    }
    loadOutfits();
  }
}

outfitForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  setBusy(outfitForm, true);
  const result = editingId === null
    ? await callApi("catalogue", "POST", "/api/outfits", formToObject(outfitForm))
    : await callApi("catalogue", "PUT", "/api/outfits/" + editingId, formToObject(outfitForm));
  setBusy(outfitForm, false);
  if (result.ok) {
    stopEditing();
    loadOutfits();
  } else {
    showErrors(formErrors, result.errors);
  }
});

cancelEditButton.addEventListener("click", stopEditing);

loadOutfits();
