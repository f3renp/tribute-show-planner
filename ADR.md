# Architecture Decision Records

## 1. Choose Flask and built-in sqlite3 over FastAPI and Django
Date: 2026-10-05
Status: Decided
Context: This assignment needs a small web app that runs as one process and gets containerised later. It has two domains and a handful of pages, and the brief requires SQLite for storage.
Decision: I chose Python with Flask for the web pages and Python's built-in sqlite3 so I can write the SQL queries myself. The app is served by waitress, which app.py starts, so "python app.py" is the only command needed.
Alternatives considered: I considered Django because I used it last semester in my Database class, but it comes with features this app does not need, such as the admin panel, and it needs a manual "python manage.py migrate" step before its tables exist, which conflicts with the brief's rule of no manual setup at startup. I also considered FastAPI, but it is designed for JSON APIs while this app serves HTML pages, and it has concepts I would have had to learn first. I did not add an ORM like SQLAlchemy because it is an extra package and it generates the SQL for me, so I could not explain those queries myself.
Consequences: I have to write myself what Django would have given me: the SQL queries, creating the tables at startup and form validation, and there is no ready-made login if I ever need one. But in return, the app depends on only 4 direct packages.