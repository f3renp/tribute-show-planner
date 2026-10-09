"""Setlist checks: each one reports what is wrong with a show's order.

Every check takes the items from service.get_setlist (in order, each song
item with a "song" dict from the catalogue, or None if the id is missing)
and returns a list of problem messages. An empty list means no problems.
No database and no Flask here, so each check can be tested on its own.
"""


def format_duration(seconds):
    """Turn 294 seconds into "4:54"."""
    return f"{seconds // 60}:{seconds % 60:02d}"


def setlist_seconds(items):
    """Total length of the setlist: every song plus every break.

    A song whose details are missing adds nothing, because its length is
    unknown. The retired and missing song check reports it instead.
    """
    total = 0
    for item in items:
        if item["item_type"] == "break":
            total += item["break_seconds"]
        elif item["song"] is not None:
            total += item["song"]["duration_seconds"]
    return total


def check_running_time(items, max_minutes):
    """Report it when the setlist is longer than the show's limit."""
    total = setlist_seconds(items)
    limit = max_minutes * 60
    if total <= limit:
        return []
    over = format_duration(total - limit)
    return [
        f"Running time is {format_duration(total)}, "
        f"{over} over the {max_minutes}-minute limit."
    ]


def check_outfit_changes(items):
    """Report each outfit change that the breaks before it are too short for.

    When two songs in a row use different outfits, the breaks between
    them must add up to at least the new outfit's change_seconds.
    """
    problems = []
    previous_song = None
    break_seconds = 0
    for item in items:
        if item["item_type"] == "break":
            break_seconds += item["break_seconds"]
            continue
        song = item["song"]
        if song is None:
            continue
        if previous_song is not None and song["outfit_id"] != previous_song["outfit_id"]:
            needed = song["outfit_change_seconds"]
            if break_seconds < needed:
                problems.append(
                    f"Position {item['position']}: changing into "
                    f"{song['outfit_name']} for \"{song['title']}\" takes "
                    f"{needed} s, but the break before it is only "
                    f"{break_seconds} s."
                )
        previous_song = song
        break_seconds = 0
    return problems
