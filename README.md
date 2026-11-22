# Tribute Show Planner

A playlist checker for live concerts. A tribute act keeps a catalogue of
songs and outfits, puts songs in order for a show, and the app reports what
is wrong with that order: running time over the limit, outfit changes
without a long enough break, poor energy pacing, and retired or repeated
songs.

**Live:** https://fmedinaieu2024ui.z1.web.core.windows.net (Azure). The
first page after the app has been idle can take 30-50 s while a service
and its database wake up; sometimes the page says the service may be
starting up, and Try again then loads it (measured on 22 Nov, ADR-8).

It runs as a static UI (`ui/`: HTML, CSS and plain JavaScript, no build
step) that calls two services from the browser. Each service is a Flask
app served by waitress with its own SQL Server database (ADR-6, ADR-7 in
`ADR.md`):

- **Catalogue** (`services/catalogue/`): songs and outfits, as a JSON API
  at http://localhost:8001/api/. Owns the `outfits` and `songs` tables.
- **Shows** (`services/shows/`): shows (each planned, confirmed or
  cancelled), ordered setlists and the setlist checks (`shows/rules.py`),
  as a JSON API at http://localhost:8002/api/. Owns the `shows` and
  `setlist_items` tables.

The shows service gets song details only from the catalogue's JSON API,
over HTTP:

| Endpoint | Returns |
|----------|---------|
| `GET /api/songs?ids=3,7` | The songs with these ids (unknown ids are left out) |
| `GET /api/songs/active` | The songs that can be added to a setlist |
| `GET /health` (both services) | 200 `{"status": "ok", "db": "ok", "version": "<git sha>"}` when the service can read and write its own database, 503 otherwise |

The rest of the catalogue API is for the browser. Errors are
`{"errors": ["message", ...]}`: 400 for invalid values (every field error
at once), 404 for an unknown id, 409 for removing an outfit songs use,
and, in both services, 403 for a change (anything but GET) sent from a
page on an origin not in `CORS_ORIGINS` (`app/cors.py`).

| Endpoint | Returns |
|----------|---------|
| `GET /api/songs/all` | Every song, active first, with `duration` as `"4:54"` |
| `GET /api/songs/{id}` | One song (404 if unknown) |
| `POST /api/songs` | 201 and the new song, or 400 |
| `PUT /api/songs/{id}` | The saved song, 400 or 404 |
| `POST /api/songs/{id}/retire`, `/reactivate` | The song, or 404 |
| `GET /api/outfits` | Every outfit, with `song_count` |
| `POST /api/outfits` | 201 and the new outfit, or 400 |
| `PUT /api/outfits/{id}` | The saved outfit, 400 or 404 |
| `DELETE /api/outfits/{id}` | 204, 404, or 409 if songs (also retired ones) use it |

The shows API, also for the browser, with the same error shape. Every
change to a setlist answers with the show's new **overview**: the show,
its setlist with song details, the running time and the check results.
If the catalogue is down, the overview is still 200, with
`catalogue_available: false`, song details `null` and the checks skipped
(`problems: null`); adding a song is then refused with 503.

| Endpoint | Returns |
|----------|---------|
| `GET /api/shows` | Every show, soonest first |
| `POST /api/shows` | 201 and the new show, or 400. `status` is optional: `planned` (the default), `confirmed` or `cancelled` |
| `GET /api/shows/{id}` | The overview, or 404 |
| `PUT /api/shows/{id}` | The new overview, 400 or 404. It replaces every field, so a missing `status` means `planned` |
| `DELETE /api/shows/{id}` | 204 (its setlist is deleted too) or 404 |
| `POST /api/shows/{id}/songs` | 201 and the overview, 400, 404, or 503 if the catalogue is down |
| `POST /api/shows/{id}/breaks` | 201 and the overview, 400 or 404 |
| `POST /api/shows/{id}/items/{item_id}/move` | `{"direction": "up"}` or `"down"`: the overview, 400 or 404 |
| `DELETE /api/shows/{id}/items/{item_id}` | The overview, or 404 |

## Run locally

You need Docker with Docker Compose. From the repository root:

```
docker compose up --build
```

Then open **http://localhost:8080** (the UI, served by a stock
`nginx:1.27-alpine` with `ui/` mounted read-only). Use `localhost`, not
`127.0.0.1`: the services only accept browser calls from the origin
`http://localhost:8080`. The JSON APIs are at http://localhost:8001/api/
(catalogue) and http://localhost:8002/api/ (shows). Stop with Ctrl+C.
`docker compose down` removes the containers;
the data stays in the `sqlserver-data` volume until you run
`docker compose down -v`.

There is no other setup step and no `.env` file is needed. Compose starts
SQL Server, `db-init` runs `db/init.sql` (databases and logins), then each
service applies its pending migrations (see Migrations below). If the
catalogue is empty, it also adds a demo catalogue (`seed.py`): 7 outfits
and 20 songs, with one song already retired. A catalogue that already has
data is never changed.

### Migrations

Each service's schema is a numbered list of SQL files in
`services/<name>/migrations/`, applied in order by `app/migrate.py` when
the service starts. Each file runs once, in one transaction with its row
in the `schema_migrations` table, so a second start applies nothing and a
failed file leaves nothing half applied. An applied file is never edited;
a change is a new file (ADR-7).

| Service | Migration | What it does |
|---------|-----------|--------------|
| catalogue | `001_init.sql` | The `outfits` and `songs` tables |
| shows | `001_init.sql` | The `shows` and `setlist_items` tables |
| shows | `002_add_show_status.sql` | Adds `status` (`planned`, `confirmed`, `cancelled`) to `shows`, which already holds data: `NOT NULL` with the default `planned`, so every existing show becomes planned and keeps every value, and the previous image keeps working during a deploy |

Each start logs either `migration applied: <file>` for each new file or
`migrations: database is up to date`.

### Without Docker (for development)

Each service runs on its own with Python 3.10 or newer (developed with
3.14). In two terminals, with a virtual environment active:

```
cd services/catalogue
pip install -r requirements.txt
$env:PORT = "8001"; python app/main.py      # macOS/Linux: PORT=8001 python app/main.py
```

```
cd services/shows
pip install -r requirements.txt
$env:PORT = "8002"; python app/main.py      # macOS/Linux: PORT=8002 python app/main.py
```

## Configuration

Everything is set through environment variables with defaults.
`docker-compose.yml` sets the ones the containers need; `.env.example`
lists the ones you may want to change.

| Variable | Service | Default | What it does |
|----------|---------|---------|--------------|
| `PORT` | both | `8000` | Port the server listens on. It always binds to `0.0.0.0`. |
| `DATABASE_URL` | both | none (required, holds a password) | `mssql://user:password@host:1433/database`. Compose sets it with a local-only password. |
| `DB_CONNECT_ATTEMPTS` | both | `8` | Connection attempts, with waits of 1, 2, 4, 8, 15... s between them (about a minute). |
| `DB_LOGIN_TIMEOUT_SECONDS` | both | `10` | Seconds one connection attempt may take. |
| `HEALTH_DB_TIMEOUT_SECONDS` | both | `2` | Seconds `/health` waits for the database to accept a login (one attempt, no retries). |
| `GIT_SHA` | both | `dev` | Commit shown as `version` by `/health`. Set in the image by the Dockerfile's `GIT_SHA` build argument, which CI fills with the commit SHA. |
| `CATALOGUE_URL` | shows | `http://localhost:8001` | Where shows calls the catalogue API. Compose sets `http://catalogue:8000`. |
| `CATALOGUE_TIMEOUT` | shows | `5` | Seconds to wait for the catalogue. |
| `CORS_ORIGINS` | both | `http://localhost:8080` | Comma-separated origins whose pages may call the API from the browser. Empty allows none. Compose sets `http://localhost:8080`. |

The UI's only settings are the two service URLs in `ui/config.js`
(`CATALOGUE_URL` `http://localhost:8001`, `SHOWS_URL`
`http://localhost:8002`). No other UI file contains a URL.

## System description

- `services/catalogue/openapi.yaml` and `services/shows/openapi.yaml`:
  OpenAPI 3.1 documents of every endpoint, `/health` included, written by
  hand from the routes.
- `system.yaml`: both services, every environment variable they read with
  its default (secrets marked `secret: true`, with no default), the call
  across the seam, and the Azure resources.
- `system.schema.json`: the format of `system.yaml`, the professor's
  schema copied unchanged. Its objects are closed, so a misspelt or extra
  field is an error, and so is a missing required one.

CI checks them in its `validate` job (with the versions pinned there). To
run the same checks locally, from the repository root:

```
uvx check-jsonschema==0.39.0 --schemafile system.schema.json system.yaml
uvx --from openapi-spec-validator==0.9.0 openapi-spec-validator services/catalogue/openapi.yaml services/shows/openapi.yaml
```

The tests also compare these files with the code, so they cannot drift:
`tests/test_system_yaml.py` (each service) checks that `system.yaml` lists
exactly the variables `app/config.py` reads, with the same defaults;
`tests/test_openapi.py` checks that the documented paths are exactly the
app's routes, and in shows that the catalogue's song schemas are the same
in both documents.

## Tests and coverage

Each service has its own tests in its `tests/` folder. The database tests
run on that service's `_test` database (`catalogue_test`, `shows_test`) in
the compose SQL Server; start it first with
`docker compose up -d sqlserver db-init`. The schema is built once per
run, and every test starts with empty tables and ids from 1
(`tests/conftest.py`). The shows tests never call the
real catalogue: they use a fake one (the `catalogue` fixture in
`services/shows/tests/conftest.py`).

The test and lint tools are in each service's `requirements-dev.txt`,
which also installs `requirements.txt`. The images only install
`requirements.txt`. These are the commands CI runs: lint with ruff (rules
in `ruff.toml`), then the tests with a coverage gate. Coverage is measured
on everything in `app/` (`.coveragerc` leaves out the tests), and the run
fails below 70%.

```
cd services/catalogue
pip install -r requirements-dev.txt
ruff check .
python -m pytest --cov --cov-report=term-missing --cov-fail-under=70
cd ../shows
pip install -r requirements-dev.txt
ruff check .
python -m pytest --cov --cov-report=term-missing --cov-fail-under=70
```

Result on 2026-11-22:

| Service | Tests | Coverage | Time (laptop) |
|---------|-------|----------|---------------|
| catalogue | 168 passed | 99.40% | ~55 s |
| shows | 186 passed | 99.31% | ~35 s |

`services/shows/tests/test_migrate.py` also tests the real migration 002
the way it ran on Azure: it applies only `001_init.sql`, saves a show
with three songs and a break, applies `002_add_show_status.sql`, and
checks that every row is still there with the same values and the show
is `planned`.

### Cross-seam integration test

`tests/integration/test_seam.py` (at the repository root, since it tests
both services together) runs against the whole system started by compose,
with the real catalogue, not a fake. It adds a real catalogue song to a new
show and checks that the overview has exactly the catalogue's song details
and that the checks ran on them. Then it stops the catalogue
(`docker compose stop catalogue`) and checks that the same show comes back
degraded (200, `catalogue_available: false`, checks `null`) within 15 s,
that adding a song is refused with 503 and saves nothing, and that shows'
`/health` is still 200. It starts the catalogue again at the end and
deletes the shows it created. CI runs it in the `integration` job.

```
docker compose up -d --build
pip install -r tests/integration/requirements.txt
python -m pytest tests/integration -v
```

Result on 2026-11-22: 2 passed in 20 s. When I measured it on 2026-11-19,
the degraded overview with the catalogue stopped took 3-4 s, mostly the
failed name lookup of `catalogue`.

Since the pages became JSON APIs (18 Nov), each service's `tests/test_api.py`
tests every endpoint and status code through Flask's test client, so
`api.py` is covered too, not only the rules and services (ADR-4).

## Azure setup (one time)

Done once, by hand, on 20 Nov 2026, following the professor's Azure guide
for Assignment 2. From then on only the pipeline changes anything. These are
the exact commands, in order, run in Windows PowerShell with the Azure CLI
(2.92), Docker and the GitHub CLI. No password appears here: each one is
generated inside the command that uses it.

Everything is in my own Azure for Students subscription, in one resource
group, in **swedencentral** (one of the five regions this subscription's
policy "Allowed resource deployment regions" allows, listed with
`az policy assignment list`).

| Resource | Name |
|----------|------|
| Resource group | `rg-fmedina-ieu2024` |
| Storage account (static website: the UI) | `fmedinaieu2024ui` |
| SQL server | `fmedina-ieu2024-sql` |
| SQL databases (serverless, free offer) | `fmedina-ieu2024-catalogue-db`, `fmedina-ieu2024-shows-db` |
| Container Apps environment | `fmedina-ieu2024-env` (with its Log Analytics workspace, named by Azure) |
| Container Apps | `fmedina-ieu2024-catalogue`, `fmedina-ieu2024-shows` |
| Managed identity (the pipeline signs in as it) | `fmedina-ieu2024-github` |

**1. Subscription.**

```
az account set --subscription 8760a18e-dad4-457b-8c81-473b82b3be23
az extension add --name containerapp --upgrade
```

**2. Providers and resource group.**

```
az provider register --namespace Microsoft.App --wait
az provider register --namespace Microsoft.OperationalInsights --wait
az provider register --namespace Microsoft.Sql --wait
az provider register --namespace Microsoft.Storage --wait
az provider register --namespace Microsoft.ManagedIdentity --wait
az group create --name rg-fmedina-ieu2024 --location swedencentral
```

**3. The UI: a Storage static website.** Its web endpoint,
`https://fmedinaieu2024ui.z1.web.core.windows.net`, is the system's public
address and the only origin the services accept (`CORS_ORIGINS`).

```
az storage account create --name fmedinaieu2024ui --resource-group rg-fmedina-ieu2024 --location swedencentral --kind StorageV2 --sku Standard_LRS
az storage blob service-properties update --account-name fmedinaieu2024ui --static-website --index-document index.html
az storage account show --name fmedinaieu2024ui --resource-group rg-fmedina-ieu2024 --query primaryEndpoints.web -o tsv
```

**4. SQL server and two serverless databases on the free offer.** The
admin password is random and thrown away right after: whenever admin access
is needed again, step 7 resets it (the script does). The connection policy
is Proxy, so every connection uses port 1433 (pymssql's FreeTDS and
Azure's default Redirect policy, which moves connections from inside Azure
to ports 11000-11999, are not a combination I wanted to depend on). The
free offer fixes auto-pause at 60 minutes and the size at 32 GB, so
`--auto-pause-delay` and `--max-size` are not passed. When a database uses
up its free monthly allowance, `AutoPause` pauses it until the next month
instead of billing it.

```
$adminPassword = <32 random letters and digits, generated in PowerShell>
az sql server create --name fmedina-ieu2024-sql --resource-group rg-fmedina-ieu2024 --location swedencentral --admin-user fmedinaadmin --admin-password $adminPassword
az sql server firewall-rule create --resource-group rg-fmedina-ieu2024 --server fmedina-ieu2024-sql --name AllowAzureServices --start-ip-address 0.0.0.0 --end-ip-address 0.0.0.0
az sql server conn-policy update --resource-group rg-fmedina-ieu2024 --server fmedina-ieu2024-sql --connection-type Proxy
az sql db create --resource-group rg-fmedina-ieu2024 --server fmedina-ieu2024-sql --name fmedina-ieu2024-catalogue-db --edition GeneralPurpose --compute-model Serverless --family Gen5 --min-capacity 0.5 --capacity 1 --backup-storage-redundancy Local --use-free-limit true --free-limit-exhaustion-behavior AutoPause
az sql db create --resource-group rg-fmedina-ieu2024 --server fmedina-ieu2024-sql --name fmedina-ieu2024-shows-db --edition GeneralPurpose --compute-model Serverless --family Gen5 --min-capacity 0.5 --capacity 1 --backup-storage-redundancy Local --use-free-limit true --free-limit-exhaustion-behavior AutoPause
```

**5. Container Apps.** Both start with the placeholder image; the first
deploy replaces it. External ingress on port 8000 (the port the images
listen on), 0 to 1 replicas, the smallest size. The plain settings are set
here; `DATABASE_URL` is a Container Apps secret that the CD workflow sets
on every deploy from the GitHub secrets. CORS is in the services' code
(`app/cors.py`), never on the ingress.

```
az containerapp env create --name fmedina-ieu2024-env --resource-group rg-fmedina-ieu2024 --location swedencentral
az containerapp create --name fmedina-ieu2024-catalogue --resource-group rg-fmedina-ieu2024 --environment fmedina-ieu2024-env --image mcr.microsoft.com/k8se/quickstart:latest --ingress external --target-port 8000 --min-replicas 0 --max-replicas 1 --cpu 0.25 --memory 0.5Gi --env-vars "CORS_ORIGINS=https://fmedinaieu2024ui.z1.web.core.windows.net"
az containerapp show --name fmedina-ieu2024-catalogue --resource-group rg-fmedina-ieu2024 --query properties.configuration.ingress.fqdn -o tsv
az containerapp create --name fmedina-ieu2024-shows --resource-group rg-fmedina-ieu2024 --environment fmedina-ieu2024-env --image mcr.microsoft.com/k8se/quickstart:latest --ingress external --target-port 8000 --min-replicas 0 --max-replicas 1 --cpu 0.25 --memory 0.5Gi --env-vars "CORS_ORIGINS=https://fmedinaieu2024ui.z1.web.core.windows.net" "CATALOGUE_URL=https://fmedina-ieu2024-catalogue.jollymeadow-b6aa2757.swedencentral.azurecontainerapps.io"
```

**6. The pipeline's identity.** A user-assigned managed identity with
Contributor on the resource group only, and two federated credentials that
let a GitHub Actions run on `main` of this repository sign in as it (OIDC:
no client secret exists). GitHub may send the subject with names or with
numeric IDs, so both are registered; the IDs come from
`https://api.github.com/repos/f3renp/tribute-show-planner` (`owner.id`, `id`).

```
az identity create --name fmedina-ieu2024-github --resource-group rg-fmedina-ieu2024 --location swedencentral
az role assignment create --assignee-object-id <principalId from identity create> --assignee-principal-type ServicePrincipal --role Contributor --scope /subscriptions/8760a18e-dad4-457b-8c81-473b82b3be23/resourceGroups/rg-fmedina-ieu2024
az identity federated-credential create --name github-main --identity-name fmedina-ieu2024-github --resource-group rg-fmedina-ieu2024 --issuer https://token.actions.githubusercontent.com --audiences api://AzureADTokenExchange --subject "repo:f3renp/tribute-show-planner:ref:refs/heads/main"
az identity federated-credential create --name github-main-ids --identity-name fmedina-ieu2024-github --resource-group rg-fmedina-ieu2024 --issuer https://token.actions.githubusercontent.com --audiences api://AzureADTokenExchange --subject "repo:f3renp@207438248/tribute-show-planner@1406038961:ref:refs/heads/main"
```

**7. One database user per service, and the GitHub secrets and
variables.** `db/create_azure_users.ps1` does the database part, so no
password is ever shown:

```
.\db\create_azure_users.ps1
```

For each service it waits until the database answers (a new firewall rule
can take minutes, and a paused database about a minute to resume), runs
`db/azure_user.sql` as admin to create a contained user (`catalogue_app`
or `shows_app`: it exists only inside its own database, with roles
`db_datareader`, `db_datawriter` and `db_ddladmin` for the migrations),
checks that the user can sign in, and only then stores its password with
`gh secret set CATALOGUE_DB_PASSWORD` / `SHOWS_DB_PASSWORD`. At the end it
checks that `catalogue_app` is refused by the shows database. It opens the
firewall to this machine's IP only while it runs. On a network with several
public IPs (Azure saw `.33` and `.35` on the same campus network) the rule
cannot match; I ran it from a phone hotspot.

The rest of the GitHub settings (the IDs are not credentials: without the
federated credential they let nobody sign in):

```
gh secret set AZURE_CLIENT_ID --body <clientId from identity create>
gh secret set AZURE_TENANT_ID --body <tenantId from az account show>
gh secret set AZURE_SUBSCRIPTION_ID --body 8760a18e-dad4-457b-8c81-473b82b3be23
gh variable set PREFIX --body fmedina-ieu2024
gh variable set RESOURCE_GROUP --body rg-fmedina-ieu2024
gh variable set UI_STORAGE --body fmedinaieu2024ui
```

**8. Read access for the professors.**

```
az role assignment create --assignee amartini@faculty.ie.edu --role Reader --scope /subscriptions/8760a18e-dad4-457b-8c81-473b82b3be23/resourceGroups/rg-fmedina-ieu2024
az role assignment create --assignee bserra@faculty.ie.edu --role Reader --scope /subscriptions/8760a18e-dad4-457b-8c81-473b82b3be23/resourceGroups/rg-fmedina-ieu2024
```

**Cost.** With nothing running, about zero: the server, identity, roles and
environment are free; each database is inside the free offer and pauses
instead of billing; the Container Apps scale to zero and use the monthly
free grant when awake (180,000 vCPU-seconds, 360,000 GiB-seconds, 2 million
requests); Log Analytics is free up to 5 GB a month; the UI is under 1 MB
in Standard_LRS storage.

## How deployment works

Changes reach `main` only through pull requests. Two workflows in
`.github/workflows/`:

- **`ci.yml`** runs on every push to a branch other than `main` and on
  every pull request: lint and tests with the coverage gate for each
  service, validation of `system.yaml` and the OpenAPI documents, the
  cross-seam integration test, and both image builds. Nothing is pushed.
- **`cd.yml`** runs on every push to `main` (a merged pull request). Its
  `ci` job calls `ci.yml` again on that commit, which on `main` also pushes
  `ghcr.io/f3renp/tribute-catalogue:<sha>` and `tribute-shows:<sha>`
  (built with `GIT_SHA=<sha>` and `provenance: false`). Only if every CI
  job passed, its `deploy` job:
  1. signs in to Azure as the managed identity with `azure/login` (OIDC:
     GitHub gives the job a token, Azure trusts it through the federated
     credential, no password exists);
  2. reads the UI origin and both Container Apps' addresses from Azure;
  3. for each service, sets the Container Apps secret `database-url` from
     the GitHub secret (`CATALOGUE_DB_PASSWORD`, `SHOWS_DB_PASSWORD`) and
     points the app at the image with this commit's SHA, with
     `DATABASE_URL=secretref:database-url`, `CORS_ORIGINS` (the UI
     origin) and, for shows, `CATALOGUE_URL`. A new commit's image starts
     the app again, so it reads the current secret. On a re-run of the same
     commit the app already runs that image and `update` changes nothing,
     so the workflow stops and starts the app (the Container Apps REST
     actions `stop` and `start`, through `az rest`). Our "express"
     Container Apps environment supports neither `--revision-suffix` nor
     `az containerapp revision restart`;
  4. writes `ui/config.js` with the two Container Apps' HTTPS addresses and
     uploads `ui/` to the storage account's `$web` container;
  5. asks each service's `/health` every 15 s, for up to 5 minutes, until
     it returns 200 with `version` equal to this commit's SHA, and checks
     that a preflight from the UI's origin is allowed. Otherwise the run
     fails.

Each service applies its pending migrations when it starts, with at most
one replica, so they never run twice at the same time. The first request
after an idle period starts a container and may find its database paused;
the services retry the connection for about a minute (`db.py`). If the
container is not ready yet, Azure's ingress answers 503 after about 30 s,
and the UI then says the service may be starting up and offers Try again;
its 60 s timeout is only for a request that gets no answer at all (ADR-8).

### Pipeline runs

| CD run | Commit | Result |
|--------|--------|--------|
| [#1](https://github.com/f3renp/tribute-show-planner/actions/runs/44765115676) | `91564a2` | Failed: `ExpressRevisionSuffixNotSupported`, our express environment rejects `--revision-suffix`. Fixed in `d3ebb89`. |
| [#2](https://github.com/f3renp/tribute-show-planner/actions/runs/44767078377) | `f18ee42` | Failed: in an express environment every revision is named `<app>--latest` and revision restart is not supported. Fixed in `c0a01c8` (compare images, stop/start on a re-run). |
| [#3](https://github.com/f3renp/tribute-show-planner/actions/runs/44768707244) | `d998c0a` | Success: the first deploy of both services and the UI. |
| [#4](https://github.com/f3renp/tribute-show-planner/actions/runs/45040502241) | `e6c8bc2` | Success: deployed migration 002 (evidence below). |

### Migration evidence on Azure (22 Nov)

- Before (image `d998c0a`): `GET /api/shows` returned show 1, "christmas
  night", with no `status` field; its overview had 4 items (3 songs and a
  break).
- CD run #4 deployed image `e6c8bc2`. The shows log
  (`az containerapp logs show`) has `migration applied:
  002_add_show_status.sql` at 2026-11-22T15:53:23Z.
- After (image `e6c8bc2`): the same show 1, with the same values, now
  `"status": "planned"`, and the same 4 items.

## Code copied between the services

The two services share no code, so each can be built, tested and deployed
on its own (each Docker build context is its own folder). The code both
need is copied, and ADR-9 lists every copy and why. These files must stay
byte-identical in `services/catalogue` and `services/shows`, and the CI
`validate` job fails if any byte differs: `app/db.py`, `app/migrate.py`,
`app/request_log.py`, `app/cors.py`, `app/health.py` and
`tests/test_system_yaml.py`.

## Assignment 1 container contract check (§7)

This is the evidence for the single-container version of the app from
Assignment 1, before the split. Output of the provided `run.sh`, run on
2026-10-12:

```
=== SDD Assignment 1 contract check ===
Repository: /c/Users/Fernando/SoftwareandDevops/tribute-show-planner

==> Repository shape
  PASS  one Dockerfile, one manifest (requirements.txt)

==> Build from a clean context, no build args
  PASS  image built
  PASS  image size 220 MB

==> Start on PORT=8000 and reach it from the host
  PASS  HTTP 302 from http://localhost:8000/

==> SQLite file under DATA_DIR
  PASS  found in /data: tribute.db

==> Data persists, and a second boot does not re-seed
  PASS  volume at /data persists
  PASS  row counts unchanged across restart: outfits=7 setlist_items=0 shows=0 songs=20

==> PORT override is honoured (not hardcoded)
  PASS  HTTP 302 from http://localhost:9123/

=== ALL CHECKS PASSED ===
Paste this output into your README as the §7 evidence.
```

Notes:

- In the original output the row-counts line was garbled by Windows line
  endings. The line above shows the real counts: `outfits=7
  setlist_items=0 shows=0 songs=20`.
- I ran it in Git Bash on Windows. The script calls `mktemp -t sdd-check`,
  and GNU `mktemp` (the one in Git Bash) needs X's in the template to
  replace with random characters. So I defined a `mktemp` shell function
  that adds `XXXXXX` to the template, then ran the script unchanged.

## Project files

- `docker-compose.yml`: starts SQL Server, `db-init`, both services and
  the `ui` web server; one volume (`sqlserver-data`).
- `db/init.sql`: the local databases and logins (run by `db-init`).
  `db/azure_user.sql` and `db/create_azure_users.ps1`: the database users
  on Azure (Azure setup, step 7).
- `.env.example`: the optional settings for compose.
- `services/<name>/Dockerfile`, `.dockerignore`, `requirements.txt`: how
  each image is built. Only `app/` is copied into the image.
- `services/<name>/requirements-dev.txt`: pytest, pytest-cov, ruff and
  PyYAML, for the tests and lint only. `ruff.toml`: the lint rules.
- `services/<name>/openapi.yaml`: the service's API (see System description).
- `system.yaml`, `system.schema.json`: the whole system and its format.
- `tests/integration/`: the cross-seam integration test and its
  `requirements.txt` (pytest and ruff, for the CI `integration` job only).
- `services/<name>/app/main.py`: builds the Flask app and starts waitress.
- `services/<name>/app/config.py`: reads that service's settings.
- `services/<name>/app/db.py`: SQL Server connections, with retries and
  backoff. `app/migrate.py` and `migrations/`: the versioned migrations,
  applied in order at startup.
- `services/<name>/app/health.py`: `GET /health` (the same file in both
  services).
- `services/catalogue/app/seed.py`: the demo catalogue.
- `services/catalogue/app/catalogue/`: `api.py` (the JSON API, for the
  browser and the shows service), `service.py` (rules and validation),
  `repository.py` (SQL).
- `services/shows/app/shows/`: `api.py` (the JSON API), `service.py`,
  `repository.py`, `rules.py` (the six setlist checks) and
  `catalogue_client.py` (the HTTP calls to the catalogue).
- `services/<name>/app/cors.py`: the CORS headers for `CORS_ORIGINS`
  (the same file in both services).
- `ui/`: the static UI. One page per screen (`index.html` songs,
  `song.html` add/edit song, `outfits.html`, `shows.html`, `show.html`),
  `style.css`, `config.js` (the service URLs) and `js/`: `api.js` (calls
  with a 60 s timeout and the error messages, shared by every page), one
  script per page, and `shouts.js` (the click shouts).
- `docs/diagrams.md`: architecture and database diagrams (still show the
  single-app version).
- `.github/workflows/ci.yml`, `cd.yml`: the pipeline (see How deployment
  works).
- `ADR.md`: architecture decisions. `AI_USAGE.md`: AI usage log.
