"""Playlist-related sync helpers (both directions).

These functions are implementation details used by `SyncEngine` wrappers.
"""

from __future__ import annotations

import logging
from typing import List, Optional, Set, Tuple

import tidalapi

logger = logging.getLogger(__name__)


async def sync_playlist(
    engine,
    spotify_playlist_id: str,
    tidal_playlist_id: Optional[str] = None,
) -> Tuple[int, int]:
    """Sync a Spotify playlist to Tidal (add-only)."""
    engine.rate_limiter.start()
    try:
        engine._report_progress(event="phase", phase="fetching")

        spotify_tracks = await _get_spotify_playlist_tracks(engine, spotify_playlist_id)
        playlist_name = engine.spotify.playlist(spotify_playlist_id)["name"]
        logger.info(
            f"Found {len(spotify_tracks)} tracks in Spotify playlist '{playlist_name}'"
        )

        if not spotify_tracks:
            return 0, 0

        spotify_tracks = engine._apply_limit(spotify_tracks)

        if tidal_playlist_id:
            tidal_playlist = engine.tidal.playlist(tidal_playlist_id)
        else:
            tidal_playlist = await _get_or_create_tidal_playlist(engine, playlist_name)

        existing_tidal_ids: Set[int] = set()
        if getattr(tidal_playlist, "num_tracks", 0) > 0:
            existing_tidal_ids = await _get_all_tidal_playlist_track_ids(
                engine, tidal_playlist
            )
            logger.info(
                f"Found {len(existing_tidal_ids)} existing tracks in Tidal playlist"
            )

        if engine.library:
            engine.library.add_tracks(spotify_tracks)

        tidal_track_ids: list[int] = []
        not_found_tracks: list[dict] = []
        not_found_strings: list[str] = []

        for spotify_track in engine._progress_iter(
            spotify_tracks, f"Searching: {playlist_name[:20]}", phase="searching"
        ):
            tidal_id = await engine.searcher.search_track(spotify_track)
            if tidal_id:
                tidal_track_ids.append(tidal_id)
                engine._report_progress(event="item", matched=True)
            else:
                artist = spotify_track["artists"][0]["name"]
                name = spotify_track["name"]
                not_found_strings.append(f"{artist} - {name}")
                not_found_tracks.append(spotify_track)
                engine._report_progress(event="item", matched=False)

        if engine.library:
            for track in not_found_tracks:
                engine.library.add_not_found_track(track)

        new_ids = [tid for tid in tidal_track_ids if tid not in existing_tidal_ids]

        if new_ids:
            chunk_size = 50
            chunks = [
                new_ids[i : i + chunk_size] for i in range(0, len(new_ids), chunk_size)
            ]
            for chunk in engine._progress_iter(
                chunks, "Adding to playlist", phase="adding"
            ):
                tidal_playlist.add(chunk)
            logger.info(f"Added {len(new_ids)} new tracks to Tidal playlist")
        else:
            logger.info("No new tracks to add")

        if not_found_strings:
            logger.warning(f"Could not find {len(not_found_strings)} tracks:")
            for track in not_found_strings[:10]:
                logger.warning(f"  - {track}")
            if len(not_found_strings) > 10:
                logger.warning(f"  ... and {len(not_found_strings) - 10} more")

        return len(new_ids), len(not_found_strings)
    finally:
        engine.rate_limiter.stop()


async def sync_all_playlists(engine) -> dict:
    """Sync all user-accessible Spotify playlists to Tidal."""
    playlists = await engine.spotify_fetcher.get_playlists(limit=engine._item_limit)
    user_id = engine.spotify.current_user()["id"]

    results: dict = {}

    for playlist in playlists:
        is_owner = playlist.get("owner", {}).get("id") == user_id
        name = playlist.get("name", "")
        owner_name = playlist.get("owner", {}).get("display_name", "unknown")

        if not is_owner:
            logger.info(f"Syncing followed playlist: {name} (by {owner_name})")
        else:
            logger.info(f"Syncing owned playlist: {name}")

        added, not_found = await sync_playlist(engine, playlist["id"])
        results[name] = {"added": added, "not_found": not_found}

    return results


async def sync_tidal_playlist_to_spotify(engine, tidal_playlist) -> Tuple[int, int]:
    """Sync single Tidal playlist to Spotify (add-only, preserves source order)."""
    from .spotify_searcher import SpotifySearcher

    engine.rate_limiter.start()
    try:
        engine._report_progress(event="phase", phase="fetching")

        playlist_name = getattr(tidal_playlist, "name", None) or "Tidal Playlist"
        spotify_playlist_id = await _find_or_create_spotify_playlist(
            engine, playlist_name
        )

        tidal_tracks = await engine.tidal_fetcher.get_playlist_tracks(tidal_playlist)
        tidal_tracks = engine._apply_limit(tidal_tracks)
        if not tidal_tracks:
            return 0, 0

        existing_spotify_ids = await _get_spotify_playlist_track_ids(
            engine, spotify_playlist_id
        )

        searcher = SpotifySearcher(engine.spotify, engine.cache, engine.rate_limiter)

        spotify_ids_in_order: List[str] = []
        not_found = 0

        for tidal_track in engine._progress_iter(
            tidal_tracks, f"Searching: {playlist_name[:20]}", phase="searching"
        ):
            spotify_id = await searcher.search_track(tidal_track)
            if not spotify_id:
                not_found += 1
                engine._report_progress(event="item", matched=False)
                if engine.library:
                    try:
                        artists = ", ".join(
                            a.name
                            for a in (getattr(tidal_track, "artists", None) or [])
                        )
                        album_name = (
                            getattr(getattr(tidal_track, "album", None), "name", "")
                            if getattr(tidal_track, "album", None)
                            else ""
                        )
                        engine.library.add_not_found_tidal_track(
                            {
                                "tidal_id": getattr(tidal_track, "id", ""),
                                "name": getattr(tidal_track, "name", "") or "",
                                "artists": artists,
                                "album": album_name,
                                "duration": getattr(tidal_track, "duration", 0) or 0,
                                "isrc": getattr(tidal_track, "isrc", "") or "",
                                "context": f"playlist:{playlist_name}",
                            }
                        )
                    except Exception:
                        pass
                continue

            engine._report_progress(event="item", matched=True)
            spotify_ids_in_order.append(spotify_id)

        to_add = [
            sid for sid in spotify_ids_in_order if sid not in existing_spotify_ids
        ]
        if not to_add:
            return 0, not_found

        engine._report_progress(event="phase", phase="adding")

        chunk_size = 100
        chunks = [to_add[i : i + chunk_size] for i in range(0, len(to_add), chunk_size)]
        for chunk in engine._progress_iter(
            chunks, "Adding to Spotify playlist", phase="adding"
        ):
            engine.spotify.playlist_add_items(spotify_playlist_id, chunk)

        return len(to_add), not_found
    finally:
        engine.rate_limiter.stop()


async def sync_all_playlists_to_spotify(engine) -> dict:
    """Sync all Tidal playlists to Spotify (create if missing, add-only)."""
    playlists = await engine.tidal_fetcher.get_playlists(limit=engine._item_limit)

    results: dict = {}
    for playlist in playlists:
        name = getattr(playlist, "name", None) or "Tidal Playlist"
        logger.info(f"Syncing Tidal playlist to Spotify: {name}")
        added, not_found = await sync_tidal_playlist_to_spotify(engine, playlist)
        results[name] = {"added": added, "not_found": not_found}

    return results


async def _get_spotify_playlist_tracks(engine, playlist_id: str) -> List[dict]:
    if engine._item_limit:
        return await engine.spotify_fetcher.get_playlist_tracks(
            playlist_id, limit=engine._item_limit
        )
    return await engine.spotify_fetcher.get_playlist_tracks(playlist_id)


async def _get_all_tidal_playlist_track_ids(
    engine, playlist: tidalapi.Playlist
) -> Set[int]:
    return await engine.tidal_fetcher.get_playlist_track_ids(playlist)


async def _get_or_create_tidal_playlist(engine, name: str) -> tidalapi.Playlist:
    playlists = engine.tidal.user.playlists()
    for playlist in playlists:
        if playlist.name == name:
            return playlist

    return engine.tidal.user.create_playlist(name, "")


async def _get_spotify_playlist_track_ids(engine, playlist_id: str) -> Set[str]:
    existing: Set[str] = set()
    try:
        results = engine.spotify.playlist_items(
            playlist_id, fields="items(track(id,type)),next"
        )
        while True:
            for item in results.get("items", []):
                track = item.get("track")
                if track and track.get("type") == "track" and track.get("id"):
                    existing.add(track["id"])

            if not results.get("next"):
                break
            results = engine.spotify.next(results)
    except Exception as e:
        logger.warning(f"Could not fetch Spotify playlist tracks for dedupe: {e}")

    return existing


async def _find_or_create_spotify_playlist(engine, name: str) -> str:
    user = engine.spotify.current_user()
    user_id = user["id"]

    results = engine.spotify.current_user_playlists()
    while True:
        for playlist in results.get("items", []):
            if (
                playlist.get("name") == name
                and playlist.get("owner", {}).get("id") == user_id
            ):
                return playlist["id"]
        if not results.get("next"):
            break
        results = engine.spotify.next(results)

    created = engine.spotify.user_playlist_create(
        user=user_id, name=name, public=False, description=""
    )
    return created["id"]
