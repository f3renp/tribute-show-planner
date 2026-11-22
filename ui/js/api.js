// Calls to the two services from the browser, and small helpers every page
// uses. No rules live here: validation and the setlist checks are done by
// the services, and the pages only show what they answer.
//
// Page data is always put in with textContent, never innerHTML: titles and
// venues are typed by users, and innerHTML would run any HTML in them.

// An Azure cold start (container start + database resume) can take about a
// minute, so the browser waits that long before giving up.
const TIMEOUT_MS = 60000;

// The base URL of "catalogue" or "shows", from config.js.
function serviceUrl(service) {
  const url = service === "catalogue" ? window.CONFIG.CATALOGUE_URL : window.CONFIG.SHOWS_URL;
  return url.replace(/\/$/, "");
}

// The message for a service that gave no answer we can use.
function notAnsweringMessage(service) {
  return (
    "The " + service + " service is not answering. It may be starting up, " +
    "which can take up to a minute after a quiet period. Try again."
  );
}

// The JSON body of a response, or null if it has none (e.g. 204).
async function readJson(response) {
  try {
    return await response.json();
  } catch (error) {
    return null;
  }
}

// Call a service and return {ok, status, data, errors, serviceDown}.
// Never throws: every failure becomes a list of messages to show.
// - the service answered {"errors": [...]}: those messages (400, 404, 409,
//   and the shows 503 "Catalogue service unavailable...");
// - no answer (network error, timeout, CORS refusal) or a 5xx without our
//   JSON (e.g. a 502 from Azure while the container starts): the
//   "not answering" message, and serviceDown is true.
async function callApi(service, method, path, body) {
  const options = { method: method, headers: {}, signal: AbortSignal.timeout(TIMEOUT_MS) };
  if (body !== undefined) {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }
  let response;
  try {
    response = await fetch(serviceUrl(service) + path, options);
  } catch (error) {
    return { ok: false, status: 0, data: null, errors: [notAnsweringMessage(service)], serviceDown: true };
  }
  const data = await readJson(response);
  if (response.ok) {
    return { ok: true, status: response.status, data: data, errors: [], serviceDown: false };
  }
  const serviceDown = response.status >= 500;
  if (data && Array.isArray(data.errors)) {
    return { ok: false, status: response.status, data: data, errors: data.errors, serviceDown: serviceDown };
  }
  return { ok: false, status: response.status, data: null, errors: [notAnsweringMessage(service)], serviceDown: serviceDown };
}

// Load what a page needs. While waiting it shows #loading; if the call
// fails it shows the messages in #page-error, with a "Try again" button
// (which calls retry) when the service is down. Returns the data, or null.
async function loadData(service, path, retry) {
  const loading = document.getElementById("loading");
  const pageError = document.getElementById("page-error");
  pageError.hidden = true;
  loading.hidden = false;
  const result = await callApi(service, "GET", path);
  loading.hidden = true;
  if (result.ok) {
    return result.data;
  }
  pageError.replaceChildren(el("span", result.errors.join(" ")));
  if (result.serviceDown) {
    pageError.appendChild(button("Try again", retry));
  }
  pageError.hidden = false;
  return null;
}

// Show error messages in a <ul class="errors">, or hide it if there are none.
function showErrors(list, errors) {
  list.replaceChildren(...errors.map((message) => el("li", message)));
  list.hidden = errors.length === 0;
}

// Disable every button in a form (or table row) while a call runs, so a
// double click does not send the same request twice.
function setBusy(element, busy) {
  element.querySelectorAll("button").forEach((each) => {
    if (busy) {
      each.dataset.wasDisabled = each.disabled ? "yes" : "";
      each.disabled = true;
    } else {
      each.disabled = each.dataset.wasDisabled === "yes";
    }
  });
}

// A form's fields as a plain object, e.g. {title: "Bad", year: "1987"}.
// The services accept numbers as text and validate them.
function formToObject(form) {
  return Object.fromEntries(new FormData(form));
}

// The ?id=7 of the page address as a number, or null if there is none.
function queryId() {
  const text = new URLSearchParams(window.location.search).get("id");
  return text !== null && /^\d+$/.test(text) ? Number(text) : null;
}

// A new element with optional text (set with textContent) and class.
function el(tag, text, className) {
  const element = document.createElement(tag);
  if (text !== undefined && text !== null) {
    element.textContent = String(text);
  }
  if (className) {
    element.className = className;
  }
  return element;
}

// A show's status ("planned", "confirmed" or "cancelled") as a small badge.
// Used by the shows list and the show page.
function statusBadge(status) {
  return el("span", status, "status status-" + status);
}

// A <button type="button"> that calls onClick.
function button(text, onClick) {
  const element = el("button", text);
  element.type = "button";
  element.addEventListener("click", onClick);
  return element;
}
