# Architecture Decision Records

## 1. Choose Flask and built-in sqlite3 over FastAPI and Django
Date: 2026-10-05
Status: Decided
Context: This assignment needs a small web app that runs as one process and gets containerised later. It has two domains and a handful of pages, and the brief requires SQLite for storage.
Decision: I chose Python with Flask for the web pages and Python's built-in sqlite3 so I can write the SQL queries myself. The app is served by waitress, which app.py starts, so "python app.py" is the only command needed.
Alternatives considered: I considered Django because I used it last semester in my Database class, but it comes with features this app does not need, such as the admin panel, and it needs a manual "python manage.py migrate" step before its tables exist, which conflicts with the brief's rule of no manual setup at startup. I also considered FastAPI, but it is designed for JSON APIs while this app serves HTML pages, and it has concepts I would have had to learn first. I did not add an ORM like SQLAlchemy because it is an extra package and it generates the SQL for me, so I could not explain those queries myself.
Consequences: I have to write myself what Django would have given me: the SQL queries, creating the tables at startup and form validation, and there is no ready-made login if I ever need one. But in return, the app depends on only 4 direct packages.

## 2. Keep catalogue and show builder as separate packages
Date: 2026-10-06
Status: Decided
Context: The brief requires two separate feature areas, the catalogue and the show builder, which could later become independent services. Because of that, they should not be too tightly connected.
Decision: The code will be split into two folders, catalogue/ and shows/. The show builder will only store a song_id and will ask the catalogue for the full song details when needed.
Alternatives considered: A simpler option was to put everything in one folder, or organise it only by type, such as keeping all database code together and all pages together. I rejected that because it would mix the two domains and make them harder to separate later.
Consequences: The cost is that the structure is slightly more complex and some communication between the two parts is needed. The benefit is that the code is cleaner and each domain can be changed or separated more easily later.

## 3. Setlist items reference songs by ID only
Date: 2026-10-08
Status: Decided
Context: The catalogue and show builder are separate domains, so a decision is needed about how setlists refer to songs without tightly coupling both parts.
Decision: setlist_items stores only the song_id, not the full song data. When the show builder needs the details, it asks the catalogue through two read-only functions, get_songs_by_ids() and list_active_songs().
Alternatives considered: The normal approach would be a foreign key from song_id to songs, or a SQL JOIN between the show and catalogue tables. It would make a future split into separate services harder because the songs table would then live in a different database, and a foreign key cannot point into another database.
Consequences: The cost is that the database can no longer guarantee that every song_id actually exists in songs. The benefit is that if the catalogue becomes a separate service later, the show builder can keep storing IDs and only the way it fetches song details would need to change.