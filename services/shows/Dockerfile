# syntax=docker/dockerfile:1
# Image for the shows service. Build context: services/shows
FROM python:3.12-slim

# PORT is read by main.py; 8000 is only the default. DATABASE_URL has no
# default here: it holds a password, so it is given when the container runs.
ENV PORT=8000 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Same layout as the repo (app/ next to migrations/), so config.py finds
# the migrations at ../migrations in both places.
WORKDIR /service

# Unprivileged user. It owns nothing in /service, so it cannot change the
# code; the data lives in SQL Server, not in the container.
RUN useradd --create-home --uid 10001 appuser

# Dependencies first: editing code does not reinstall packages (layer cache).
# The pymssql wheel includes its own FreeTDS driver, so no apt-get is needed.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Only the service code and migrations. Never COPY . . (tests, .git, .env stay out).
COPY app/ ./app/
COPY migrations/ ./migrations/

# Commit this image is built from, shown by GET /health. CI passes
# --build-arg GIT_SHA=<commit SHA>; a local build says "dev". After the
# COPY lines, so a new commit does not reinstall the packages.
ARG GIT_SHA=dev
ENV GIT_SHA=$GIT_SHA

USER appuser

EXPOSE 8000

# urlopen raises on any status that is not 2xx, so a 503 from /health (the
# database cannot be read or written) exits with 1 and counts as a failure.
# /health tries one connection with a 2 s login timeout. If the database's
# host name cannot be found at all (compose with sqlserver stopped), the
# name lookup alone takes ~6 s; a check that runs past --timeout also
# counts as a failure, so the container is still marked unhealthy.
HEALTHCHECK --interval=10s --timeout=5s --start-period=10s --retries=3 \
  CMD ["python", "-c", "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/health' % os.environ['PORT'], timeout=4)"]

# main.py binds 0.0.0.0 and reads PORT. Python puts app/ (the script's
# folder) on the import path, so "import config" works.
CMD ["python", "app/main.py"]
