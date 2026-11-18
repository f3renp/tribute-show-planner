"""SQL for the catalogue tables. Only this file reads or writes songs and outfits.

%s takes a value from a tuple, %(name)s from a dict (pymssql's markers).
"""
import db

# Songs ------------------------------------------------------------------


def list_songs():
    """All songs with their outfit name, active songs first."""
    return db.fetch_all(
        """
        SELECT songs.id, title, album, year, duration_seconds, energy, kind,
               outfit_id, active, outfits.name AS outfit_name
        FROM songs
        JOIN outfits ON outfits.id = songs.outfit_id
        ORDER BY active DESC, title
        """
    )


def get_song(song_id):
    """One song as a dict, or None if the id does not exist."""
    return db.fetch_one("SELECT * FROM songs WHERE id = %s", (song_id,))


def get_songs_with_outfits(song_ids):
    """The songs with these ids, each with its outfit name and change time."""
    if not song_ids:
        return []
    # One "%s" per id, e.g. "%s, %s, %s" for three ids.
    placeholders = ", ".join("%s" for _ in song_ids)
    return db.fetch_all(
        f"""
        SELECT songs.id, title, album, year, duration_seconds, energy, kind,
               outfit_id, active, outfits.name AS outfit_name,
               outfits.change_seconds AS outfit_change_seconds
        FROM songs
        JOIN outfits ON outfits.id = songs.outfit_id
        WHERE songs.id IN ({placeholders})
        """,
        tuple(song_ids),
    )


def find_song_by_title_and_album(title, album):
    """The song with this title and album, or None."""
    return db.fetch_one(
        "SELECT * FROM songs WHERE title = %s AND album = %s", (title, album)
    )


def insert_song(song):
    """Save a new song and return its id. song uses the column names as keys."""
    # OUTPUT INSERTED.id returns the id SQL Server gave the new row.
    return db.insert(
        """
        INSERT INTO songs (title, album, year, duration_seconds, energy, kind, outfit_id)
        OUTPUT INSERTED.id
        VALUES (%(title)s, %(album)s, %(year)s, %(duration_seconds)s,
                %(energy)s, %(kind)s, %(outfit_id)s)
        """,
        song,
    )


def update_song(song_id, song):
    """Overwrite the details of an existing song."""
    db.execute(
        """
        UPDATE songs
        SET title = %(title)s, album = %(album)s, year = %(year)s,
            duration_seconds = %(duration_seconds)s, energy = %(energy)s,
            kind = %(kind)s, outfit_id = %(outfit_id)s
        WHERE id = %(id)s
        """,
        dict(song, id=song_id),
    )


def set_song_active(song_id, active):
    """Mark a song as active (True) or retired (False)."""
    db.execute(
        "UPDATE songs SET active = %s WHERE id = %s", (int(active), song_id)
    )


# Outfits ----------------------------------------------------------------


def list_outfits():
    """All outfits, sorted by name."""
    return db.fetch_all("SELECT * FROM outfits ORDER BY name")


def list_outfits_with_song_count():
    """All outfits sorted by name, each with song_count: how many songs
    (active or retired) use it. The UI uses it to explain why an outfit
    cannot be removed."""
    # LEFT JOIN keeps outfits no song uses; COUNT(songs.id) is 0 for them.
    return db.fetch_all(
        """
        SELECT outfits.id, outfits.name, outfits.change_seconds,
               COUNT(songs.id) AS song_count
        FROM outfits
        LEFT JOIN songs ON songs.outfit_id = outfits.id
        GROUP BY outfits.id, outfits.name, outfits.change_seconds
        ORDER BY outfits.name
        """
    )


def get_outfit(outfit_id):
    """One outfit as a dict, or None if the id does not exist."""
    return db.fetch_one("SELECT * FROM outfits WHERE id = %s", (outfit_id,))


def find_outfit_by_name(name):
    """The outfit with this name, or None."""
    return db.fetch_one("SELECT * FROM outfits WHERE name = %s", (name,))


def insert_outfit(outfit):
    """Save a new outfit and return its id."""
    return db.insert(
        """
        INSERT INTO outfits (name, change_seconds)
        OUTPUT INSERTED.id
        VALUES (%(name)s, %(change_seconds)s)
        """,
        outfit,
    )


def update_outfit(outfit_id, outfit):
    """Overwrite the name and change time of an existing outfit."""
    db.execute(
        """
        UPDATE outfits
        SET name = %(name)s, change_seconds = %(change_seconds)s
        WHERE id = %(id)s
        """,
        dict(outfit, id=outfit_id),
    )


def count_songs_using_outfit(outfit_id):
    """How many songs, active or retired, use this outfit."""
    row = db.fetch_one(
        "SELECT COUNT(*) AS song_count FROM songs WHERE outfit_id = %s",
        (outfit_id,),
    )
    return row["song_count"]


def delete_outfit(outfit_id):
    """Delete an outfit. The caller checks first that no song uses it."""
    db.execute("DELETE FROM outfits WHERE id = %s", (outfit_id,))
