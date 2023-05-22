#!/usr/bin/env python

import spotipy
from spotipy.oauth2 import SpotifyOAuth
import json
from datetime import datetime as dt
from time import sleep

CREDENTIALS = "credentials.json"
LAST_RUN = "last"

# TODO: Make this more reliable, test for network failures
# and cases where unexpected changes happen outside.


def login():
    # Authenticate on Spotify.

    # TODO: Confirm that I need all these permissions
    scope = "user-library-read playlist-modify-public playlist-modify-private"

    # TODO: Find a more reliable way to handle credentials
    with open(CREDENTIALS, "r+") as f:
        credentials = json.load(f)

    # The first time a user runs the script,
    # he'll have to copy a url from his browser
    # TODO: How to improve first-time authentication?
    return spotipy.Spotify(
        auth_manager=SpotifyOAuth(
            client_id=credentials["client_id"],
            client_secret=credentials["client_secret"],
            redirect_uri="https://example.org",
            scope=scope,
        )
    )


def get_pending(sp):
    # List all liked songs since the last run grouped by month

    pending = {}
    offset = 0

    # TODO: Is there a better way to handle state?
    # TODO: What happens when there's no LAST_RUN file?
    with open(LAST_RUN, "r+") as f:
        last = int(f.read().strip())

    # TODO: A nested loop looks ugly, is there a better way?
    while True:
        songs = sp.current_user_saved_tracks(limit=50, offset=offset)

        for song in songs["items"]:
            timestamp = dt.fromisoformat(song["added_at"])
            if timestamp.timestamp() <= last:
                flag = True
                break
            else:
                month = timestamp.strftime("%B %Y")
                song_id = song["track"]["id"]
                if month in pending.keys():
                    pending[month].append(song_id)
                else:
                    pending[month] = [song_id]
        if flag:
            break

        offset += 50

    return pending


def get_user_playlists(sp, user):
    # Get all public playlists created by the user

    # TODO: Add an option for private playlists
    # TODO: It would probably be better to test if
    # a specific monthly playlist exists
    playlists = sp.current_user_playlists()
    user_playlists = {
        p["name"]: p["id"]
        for p in playlists["items"]
        if p["owner"]["id"] == user and p["public"]
    }
    return user_playlists


def archive_likes():
    # Archive all likes since the last run in monthly playlists

    # TODO: Passing around `sp` looks ugly, is there a better way?
    sp = login()
    user = sp.current_user()["id"]
    pending = get_pending(sp)
    user_playlists = get_user_playlists(sp, user)

    for month in pending.keys():
        # TODO: Can I make sure playlists get updated in the right order
        # so that sorting by modification date in the UI makes sense?
        pending_month = list(reversed(pending[month]))
        # Chunks of 50 because that's the maximum number of songs you
        # can add to a playlist at once.
        # TODO: Am I sure of this limit? Maybe parametrize this
        # to change it fast if the API changes?
        pending_month = [
            pending_month[i : i + 50] for i in range(0, len(pending_month), 50)
        ]

        # TODO: Are you sure there's no better way to get the new playlist ID?
        if month not in user_playlists.keys():
            print(f"New playlist: {month}")
            sp.user_playlist_create(user, month, public=True)
            sleep(3)
            user_playlists = get_user_playlists(sp, user)

        for songs in pending_month:
            print(f"{len(songs)} songs added to {month}")
            sp.user_playlist_add_tracks(user, user_playlists[month], songs)

    with open(LAST_RUN, "w+") as f:
        f.write(str(int(dt.now().timestamp())))

if __name__ == "__main__":
    archive_likes()
