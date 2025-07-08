#!/usr/bin/env python

from typing import Dict, List
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import json
import os
from datetime import datetime as dt
from time import sleep

CREDENTIALS = "credentials.json"
LAST_RUN = "last"

# TODO: Make this more reliable, test for network failures
# and cases where unexpected changes happen outside.

def login() -> spotipy.Spotify:
    # Authenticate on Spotify.

    # TODO: Confirm that I need all these permissions
    scope = "user-library-read playlist-modify-public playlist-modify-private"

    # TODO: Find a more reliable way to handle credentials
    with open(CREDENTIALS) as f:
        credentials = json.load(f)
        client_id = credentials["client_id"]
        client_secret = credentials["client_secret"]
        redirect_uri = credentials["redirect_uri"]

    return spotipy.Spotify(
        auth_manager=SpotifyOAuth(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            scope=scope,
        )
    )


def get_pending(sp: spotipy.Spotify) -> Dict[str, List[str]]:
    # List all liked songs since the last run grouped by month
    # On the first run, archive all songs from the current month

    pending = {}
    offset = 0
    flag = False

    # TODO: Is there a better way to handle state?
    if os.path.exists(LAST_RUN):
        with open(LAST_RUN) as f:
            last = int(f.read().strip())
    else:
        last = (
            dt.utcnow()
            .replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            .timestamp()
        )

    while not flag:
        songs = sp.current_user_saved_tracks(limit=50, offset=offset)

        for song in songs["items"]:
            timestamp = dt.fromisoformat(song["added_at"])
            if timestamp.timestamp() <= last:
                flag = True
                break
            month = timestamp.strftime("%B %Y")
            song_id = song["track"]["id"]
            pending.setdefault(month, []).append(song_id)

        offset += 50

    return pending


def get_user_playlists(sp: spotipy.Spotify, user: str) -> Dict[str, str]:
    # Get all public playlists created by the user

    # TODO: Add an option for private playlists
    # TODO: It would probably be better to test if
    # a specific monthly playlist exists
    playlists = sp.current_user_playlists()
    user_playlists = {
        p["name"]: p["id"]
        for p in playlists["items"]
        if p["owner"]["id"] == user
    }
    return user_playlists


def archive_likes():
    # Archive all likes since the last run in monthly playlists

    sp = login()
    user = sp.current_user()["id"]
    pending = get_pending(sp)
    user_playlists = get_user_playlists(sp, user)

    for month, songs in pending.items():
        # TODO: Can I make sure playlists get updated in the right order
        # so that sorting by modification date in the UI makes sense?
        songs = list(reversed(songs))

        # Chunks of 50 because that's the maximum number of songs you
        # can add to a playlist at once.
        # TODO: Am I sure of this limit? Maybe parametrize this
        # to change it fast if the API changes?
        # TODO: Are you sure there's no better way to get the new playlist ID?

        if month not in user_playlists:
            try:
                sp.user_playlist_create(user, month, public=True)
                print(f"New playlist: {month}")
                sleep(3)
                user_playlists = get_user_playlists(sp, user)
            except spotipy.SpotifyException:
                continue

        playlist_id = user_playlists[month]
        for i in range(0, len(songs), 50):
            chunk = songs[i : i + 50]
            try:
                sp.user_playlist_add_tracks(user, playlist_id, chunk)
            except spotipy.SpotifyException:
                continue
        print(f"{len(songs)} songs added to {month}")

    with open(LAST_RUN, "w+") as f:
        f.write(str(int(dt.now().timestamp())))


if __name__ == "__main__":
    archive_likes()
