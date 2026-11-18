// Where the browser finds the two services. This is the only file with
// their URLs: every page loads it first, and js/api.js reads it.
//
// Locally these are the ports docker compose publishes. On Azure the CD
// pipeline overwrites this file with the Container Apps' HTTPS URLs.
window.CONFIG = {
  CATALOGUE_URL: "http://localhost:8001",
  SHOWS_URL: "http://localhost:8002",
};
