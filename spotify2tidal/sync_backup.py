"""Backup/export helpers used by `SyncEngine`.

These functions are implementation details used by `SyncEngine` wrappers.
"""

from __future__ import annotations

import logging
from typing import List, Optional

logger = logging.getLogger(__name__)


async def export_tidal_library(engine) -> dict:
    """Export current Tidal favorites to CSV files."""
    if not engine.library:
        return {}

    from .library_csv_tidal import (
        export_tidal_albums,
        export_tidal_artists,
        export_tidal_tracks,
    )

    results: dict = {}

    engine._log("progress", "Fetching Tidal favorite tracks...")
    tracks = await engine.tidal_fetcher.get_favorite_tracks()
    if tracks:
        results["tidal_tracks"] = export_tidal_tracks(tracks, engine.library.export_dir)
        logger.info(f"Exported {len(tracks)} Tidal tracks")

    engine._log("progress", "Fetching Tidal favorite albums...")
    albums = await engine.tidal_fetcher.get_favorite_albums()
    if albums:
        results["tidal_albums"] = export_tidal_albums(albums, engine.library.export_dir)
        logger.info(f"Exported {len(albums)} Tidal albums")

    engine._log("progress", "Fetching Tidal favorite artists...")
    artists = await engine.tidal_fetcher.get_favorite_artists()
    if artists:
        results["tidal_artists"] = export_tidal_artists(
            artists, engine.library.export_dir
        )
        logger.info(f"Exported {len(artists)} Tidal artists")

    return results


async def export_backup(engine, categories: Optional[List[str]] = None) -> dict:
    """
    Export a snapshot of Spotify + Tidal libraries and playlists.
    If categories is provided, only those categories will be fetched/exported.
    Supported: 'tracks', 'albums', 'artists', 'podcasts', 'playlists'.
    """
    if not engine.library:
        return {"files": {}, "stats": {}}

    from .library_csv_tidal import (
        export_tidal_albums,
        export_tidal_artists,
        export_tidal_tracks,
    )

    # If categories is None, we export everything
    sync_all = categories is None

    # 1. Spotify / Podcasts
    if sync_all or "tracks" in categories:
        engine._log("progress", "Fetching Spotify tracks snapshot...")
        engine.library.tracks = await engine.spotify_fetcher.get_saved_tracks(
            limit=engine._item_limit
        )

    if sync_all or "albums" in categories:
        engine._log("progress", "Fetching Spotify albums snapshot...")
        engine.library.albums = await engine.spotify_fetcher.get_saved_albums(
            limit=engine._item_limit
        )

    if sync_all or "artists" in categories:
        engine._log("progress", "Fetching Spotify artists snapshot...")
        engine.library.artists = await engine.spotify_fetcher.get_followed_artists(
            limit=engine._item_limit
        )

    if sync_all or "podcasts" in categories:
        engine._log("progress", "Fetching Spotify podcasts snapshot...")
        engine.library.podcasts = await engine.spotify_fetcher.get_saved_shows(
            limit=engine._item_limit
        )

    # 2. Spotify Playlists
    if sync_all or "playlists" in categories:
        engine._log("progress", "Fetching Spotify playlists snapshot...")
        spotify_playlists: List[dict] = []
        results = engine.spotify.current_user_playlists()
        while True:
            spotify_playlists.extend(results.get("items", []))
            if not results.get("next"):
                break
            results = engine.spotify.next(results)

        spotify_playlists = engine._apply_limit(spotify_playlists)
        spotify_playlist_items: List[dict] = []

        for playlist in spotify_playlists:
            playlist_id = playlist.get("id")
            if not playlist_id:
                continue
            playlist_name = playlist.get("name", "") or ""

            tracks = await engine.spotify_fetcher.get_playlist_tracks(
                playlist_id, limit=engine._item_limit
            )
            for idx, track in enumerate(tracks):
                if not track or not track.get("id"):
                    continue
                artists = ", ".join(a["name"] for a in track.get("artists", []))
                album = track.get("album", {}).get("name", "")
                isrc = track.get("external_ids", {}).get("isrc", "")
                tidal_match = engine.cache.get_track_match(track["id"]) or ""

                spotify_playlist_items.append(
                    {
                        "spotify_playlist_id": playlist_id,
                        "playlist_name": playlist_name,
                        "position": idx,
                        "spotify_track_id": track.get("id", ""),
                        "tidal_track_id": tidal_match,
                        "name": track.get("name", ""),
                        "artists": artists,
                        "album": album,
                        "isrc": isrc,
                    }
                )

        engine.library.spotify_playlists = spotify_playlists
        engine.library.spotify_playlist_items = spotify_playlist_items

    # 3. Tidal Snapshot
    tidal_exports: dict = {}

    if sync_all or any(c in categories for c in ["tracks", "albums", "artists"]):
        engine._log("progress", "Fetching Tidal library snapshot...")

        if sync_all or "tracks" in categories:
            tidal_tracks = await engine.tidal_fetcher.get_favorite_tracks(
                limit_total=engine._item_limit
            )
            if tidal_tracks:
                tidal_exports["tidal_tracks"] = export_tidal_tracks(
                    tidal_tracks, engine.library.export_dir
                )

        if sync_all or "albums" in categories:
            tidal_albums = await engine.tidal_fetcher.get_favorite_albums(
                limit_total=engine._item_limit
            )
            if tidal_albums:
                tidal_exports["tidal_albums"] = export_tidal_albums(
                    tidal_albums, engine.library.export_dir
                )

        if sync_all or "artists" in categories:
            tidal_artists = await engine.tidal_fetcher.get_favorite_artists(
                limit_total=engine._item_limit
            )
            if tidal_artists:
                tidal_exports["tidal_artists"] = export_tidal_artists(
                    tidal_artists, engine.library.export_dir
                )

    # 4. Tidal Playlists
    if sync_all or "playlists" in categories:
        engine._log("progress", "Fetching Tidal playlists snapshot...")
        tidal_playlists = list(engine.tidal.user.playlists())
        tidal_playlists = engine._apply_limit(tidal_playlists)

        tidal_playlist_items: List[dict] = []
        for playlist in tidal_playlists:
            playlist_id = getattr(playlist, "id", None)
            playlist_name = getattr(playlist, "name", None) or ""
            if not playlist_id:
                continue

            tracks = await engine.tidal_fetcher.get_playlist_tracks(
                playlist, limit_total=engine._item_limit
            )
            for idx, track in enumerate(tracks):
                if not track:
                    continue
                try:
                    artists = ", ".join(a.name for a in (track.artists or []))
                    album_name = track.album.name if track.album else ""
                    isrc = getattr(track, "isrc", "") or ""
                    spotify_match = engine.cache.get_spotify_track_match(track.id) or ""

                    tidal_playlist_items.append(
                        {
                            "tidal_playlist_id": playlist_id,
                            "playlist_name": playlist_name,
                            "position": idx,
                            "tidal_track_id": track.id,
                            "spotify_track_id": spotify_match,
                            "name": track.name or "",
                            "artists": artists,
                            "album": album_name,
                            "isrc": isrc,
                        }
                    )
                except Exception:
                    continue

        engine.library.tidal_playlists = tidal_playlists
        engine.library.tidal_playlist_items = tidal_playlist_items

    exported = engine.library.export_all()
    files = {**exported, **tidal_exports}
    return {"files": files, "stats": engine.library.get_stats()}
