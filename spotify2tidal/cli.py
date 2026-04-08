"""
Command-line interface for spotify2tidal.

Production-ready CLI with structured logging and colorized output.
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

import yaml

from .auth import open_apple_music_session, open_spotify_session, open_tidal_session
from .cache import MatchCache
from .logging_utils import SyncLogger, UserErrors
from .sync_engine import SyncEngine


class _SyncLoggerBridgeHandler(logging.Handler):
    """Forwards stdlib `logging` records to a SyncLogger so warnings/errors
    from modules like apple_music_client surface in the CLI output instead of
    being silently swallowed by the unconfigured root logger."""

    def __init__(self, sync_logger: SyncLogger):
        super().__init__(level=logging.WARNING)
        self._sync_logger = sync_logger

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
        except Exception:
            return
        if record.levelno >= logging.ERROR:
            self._sync_logger.error(msg)
        else:
            self._sync_logger.warning(msg)


def load_config(config_path: str) -> dict:
    """Load configuration from YAML file."""
    path = Path(config_path)
    if not path.exists():
        return {}
    with open(path) as f:
        return yaml.safe_load(f) or {}


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser with all CLI options."""
    parser = argparse.ArgumentParser(
        description="Sync your music library between Spotify, Tidal, and Apple Music",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples (Spotify → Tidal):
  spotify2tidal --favorites         # Sync liked/saved tracks to Tidal
  spotify2tidal --albums            # Sync saved albums to Tidal
  spotify2tidal --playlists         # Sync all playlists to Tidal
  spotify2tidal --all               # Sync everything to Tidal

Examples (Tidal → Spotify):
  spotify2tidal --to-spotify --favorites   # Sync Tidal favorites to Spotify
  spotify2tidal --to-spotify --all         # Sync everything to Spotify

Examples (Spotify → Apple Music):
  spotify2tidal --to-apple-music --favorites  # Sync liked tracks to Apple Music
  spotify2tidal --to-apple-music --albums     # Sync saved albums to Apple Music
  spotify2tidal --to-apple-music --playlists  # Sync all playlists to Apple Music
  spotify2tidal --to-apple-music --all        # Sync everything to Apple Music

Library Management:
  spotify2tidal --status            # Show library coverage on each platform
  spotify2tidal --export-tidal      # Export Tidal library to CSV
  spotify2tidal --podcasts          # Export podcasts to CSV

Tips:
  Use --verbose for detailed debug output
  Use --quiet for errors only (good for scripts)
  Your progress is cached - resume anytime if interrupted
""",
    )

    parser.add_argument(
        "--config",
        "-c",
        default="config.yml",
        help="Path to config file (default: config.yml)",
    )
    parser.add_argument("--playlist", "-p", help="Sync a specific Spotify playlist (ID or URI)")
    parser.add_argument(
        "--skip-playlist",
        action="append",
        default=[],
        help="Skip playlist by name (can be used multiple times)",
    )
    parser.add_argument(
        "--favorites",
        "-f",
        action="store_true",
        help="Sync liked/saved tracks to Tidal favorites",
    )
    parser.add_argument(
        "--liked-playlist",
        action="store_true",
        help="When syncing favorites to Apple Music, also create an Apple playlist with all liked songs",
    )
    parser.add_argument(
        "--liked-playlist-name",
        default="Spotify Liked Songs",
        help="Name of the Apple playlist to create for liked songs (with --liked-playlist)",
    )
    parser.add_argument(
        "--playlists",
        action="store_true",
        help="Sync all user playlists",
    )
    parser.add_argument("--albums", "-a", action="store_true", help="Sync saved albums")
    parser.add_argument("--artists", "-r", action="store_true", help="Sync followed artists")
    parser.add_argument(
        "--podcasts",
        action="store_true",
        help="Export saved podcasts to CSV (Tidal doesn't support podcasts)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        dest="sync_all",
        help="Sync everything (playlists, favorites, albums, artists, podcasts)",
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose debug output")
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Quiet mode - only show errors",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable colored output",
    )

    # Sync direction options
    parser.add_argument(
        "--to-spotify",
        action="store_true",
        help="Sync direction: FROM Tidal TO Spotify",
    )
    parser.add_argument(
        "--to-apple-music",
        action="store_true",
        help="Sync direction: FROM Spotify TO Apple Music",
    )
    parser.add_argument(
        "--export-tidal",
        action="store_true",
        help="Export current Tidal library to CSV files",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show library status and coverage on each platform",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        metavar="N",
        help="Limit items processed per category (for debugging large libraries)",
    )
    parser.add_argument(
        "--skip-existing-check",
        action="store_true",
        help="Skip fetching existing library IDs from target (faster restart, uses cache instead)",
    )
    parser.add_argument(
        "--clear-failures",
        action="store_true",
        help="Clear cached search failures so not-found tracks get retried",
    )

    return parser


def print_header(logger: SyncLogger, direction: str = "to_tidal"):
    """Print a styled header."""
    logger.info("━" * 50)
    if direction == "to_spotify":
        logger.info("🎵 Tidal → Spotify Sync")
    elif direction == "to_apple_music":
        logger.info("🎵 Spotify → Apple Music Sync")
    else:
        logger.info("🎵 Spotify → Tidal Sync")
    logger.info("━" * 50)


async def show_library_status(engine: SyncEngine, logger: SyncLogger):
    """Show library coverage status on connected platforms."""
    logger.info("")
    logger.info("━" * 50)
    logger.info("📊 Library Status")
    logger.info("━" * 50)

    # Get Spotify counts
    logger.progress("Fetching Spotify library...")
    spotify_tracks = await engine._get_all_spotify_saved_track_ids()
    spotify_albums = await engine._get_all_spotify_saved_album_ids()
    spotify_artists = await engine._get_all_spotify_followed_artist_ids()

    logger.info("")
    logger.info("📱 Spotify Library:")
    logger.info(f"   Tracks:  {len(spotify_tracks)}")
    logger.info(f"   Albums:  {len(spotify_albums)}")
    logger.info(f"   Artists: {len(spotify_artists)}")

    # Get Tidal counts (if connected)
    if engine.tidal_fetcher:
        logger.progress("Fetching Tidal library...")
        tidal_track_ids = await engine._get_all_tidal_favorite_track_ids()
        tidal_album_ids = await engine._get_all_tidal_favorite_album_ids()
        tidal_artist_ids = await engine._get_all_tidal_favorite_artist_ids()

        logger.info("")
        logger.info("🎧 Tidal Library:")
        logger.info(f"   Tracks:  {len(tidal_track_ids)}")
        logger.info(f"   Albums:  {len(tidal_album_ids)}")
        logger.info(f"   Artists: {len(tidal_artist_ids)}")

    # Get cached matches
    cache_stats = engine.cache.get_stats()

    logger.info("")
    logger.info("🔗 Cached Matches:")
    logger.info(f"   Spotify↔Tidal tracks:  {cache_stats['cached_track_matches']}")
    logger.info(f"   Spotify↔Tidal albums:  {cache_stats['cached_album_matches']}")
    logger.info(f"   Spotify→Apple tracks:  {cache_stats['cached_apple_track_matches']}")
    logger.info(f"   Spotify→Apple albums:  {cache_stats['cached_apple_album_matches']}")
    logger.info(f"   Cached failures:       {cache_stats['cached_failures']}")
    logger.info("━" * 50)


def print_summary(results: dict, logger: SyncLogger):
    """Print a formatted summary of sync results."""
    logger.info("")
    logger.info("━" * 50)
    logger.success("Sync Complete!")
    logger.info("━" * 50)

    total_added = 0
    total_not_found = 0

    for category, data in results.items():
        if isinstance(data, dict) and "added" in data:
            added = data["added"]
            not_found = data.get("not_found", 0)
            total_added += added
            total_not_found += not_found
            logger.info(f"  {category.title()}: {added} added, {not_found} not found")
        elif isinstance(data, dict) and "exported" in data:
            logger.info(f"  {category.title()}: {data['exported']} exported")
        elif isinstance(data, dict):
            # Playlist results: dict of playlist_name -> {added, not_found}
            added = sum(d.get("added", 0) for d in data.values() if isinstance(d, dict))
            not_found = sum(d.get("not_found", 0) for d in data.values() if isinstance(d, dict))
            total_added += added
            total_not_found += not_found
            logger.info(f"  {category.title()}: {added} added, {not_found} not found")

    logger.info("━" * 50)
    if total_not_found > 0:
        logger.warning(f"  {total_not_found} items could not be found on the target platform.")


def main():
    parser = create_parser()
    args = parser.parse_args()

    # Initialize logger
    logger = SyncLogger(
        mode="cli",
        verbose=args.verbose,
        quiet=args.quiet,
        use_color=not args.no_color,
    )

    # Surface stdlib `logging` warnings (e.g. from apple_music_client) via the
    # SyncLogger so the user actually sees them. Without this the root logger
    # has no handler and warnings are silently dropped.
    root_logger = logging.getLogger()
    if not any(isinstance(h, _SyncLoggerBridgeHandler) for h in root_logger.handlers):
        root_logger.addHandler(_SyncLoggerBridgeHandler(logger))
        if root_logger.level > logging.WARNING or root_logger.level == logging.NOTSET:
            root_logger.setLevel(logging.WARNING)

    # Determine direction
    if args.to_apple_music:
        direction = "to_apple_music"
    elif args.to_spotify:
        direction = "to_spotify"
    else:
        direction = "to_tidal"

    print_header(logger, direction=direction)

    # Load config
    config = load_config(args.config)
    if not config and not Path(args.config).exists():
        if args.config != "config.yml":
            logger.error(UserErrors.config_not_found(args.config))
            sys.exit(1)
        else:
            logger.debug("No config.yml found, using environment variables")

    # Connect to Spotify (always needed as source)
    logger.progress("Connecting to Spotify...")
    library_config = config.get("library", {})
    library_dir = Path(library_config.get("export_dir", "./library"))
    library_dir.mkdir(parents=True, exist_ok=True)

    spotify_cache_path = str(library_dir / ".spotify_cache")

    try:
        spotify = open_spotify_session(config.get("spotify", {}), cache_path=spotify_cache_path)
        user = spotify.current_user()
        username = user["display_name"] or user["id"]
        logger.success(f"Connected to Spotify as {username}")
    except ValueError as e:
        logger.error(UserErrors.spotify_auth_failed(str(e)))
        sys.exit(1)
    except Exception as e:
        if "connection" in str(e).lower() or "network" in str(e).lower():
            logger.error(UserErrors.network_error(str(e)))
        else:
            logger.error(UserErrors.spotify_auth_failed(str(e)))
        sys.exit(1)

    # Connect to target platform
    tidal = None
    apple_music_client = None

    if direction == "to_apple_music":
        # Connect to Apple Music
        logger.progress("Connecting to Apple Music...")
        try:
            apple_music_client = open_apple_music_session(config.get("apple_music", {}))
            logger.success("Connected to Apple Music")
        except ValueError as e:
            logger.error(str(e))
            sys.exit(1)
        except Exception as e:
            logger.error(f"Apple Music connection failed: {e}")
            sys.exit(1)
    else:
        # Connect to Tidal (for to_tidal and to_spotify directions)
        logger.progress("Connecting to Tidal...")
        tidal_session_path = str(library_dir / ".tidal_session.json")

        try:
            tidal = open_tidal_session(config.get("tidal", {}), session_file=tidal_session_path)
            if not tidal.check_login():
                logger.error(UserErrors.tidal_auth_failed("Login check failed"))
                sys.exit(1)
            logger.success("Connected to Tidal")
        except Exception as e:
            logger.error(UserErrors.tidal_auth_failed(str(e)))
            sys.exit(1)

    # Create sync engine with cache in library directory
    sync_config = config.get("sync", {})
    cache_file = str(library_dir / "cache.json")
    cache = MatchCache(cache_file=cache_file)
    logger.debug(f"Using cache: {cache_file} ({cache.get_stats()})")

    # Create a fallback Apple Music client with US storefront for broader catalog
    apple_music_fallback = None
    if apple_music_client and apple_music_client.storefront != "us":
        from .apple_music_client import AppleMusicClient

        am_config = config.get("apple_music", {})
        apple_music_fallback = AppleMusicClient(
            bearer_token=am_config.get("bearer_token", ""),
            media_user_token=am_config.get("media_user_token", ""),
            cookies=am_config.get("cookies", ""),
            storefront="us",
        )
        logger.info(
            f"Using {apple_music_client.storefront.upper()} catalog "
            f"with US fallback for broader coverage"
        )

    engine = SyncEngine(
        spotify,
        tidal=tidal,
        apple_music=apple_music_client,
        apple_music_fallback=apple_music_fallback,
        max_concurrent=sync_config.get("max_concurrent", 10),
        rate_limit=sync_config.get("rate_limit", 10),
        library_dir=str(library_dir),
        logger=logger,
        cache=cache,
        item_limit=args.limit,
        skip_existing_check=args.skip_existing_check,
    )

    if args.limit:
        logger.warning(f"⚠️  Debug mode: limiting to {args.limit} items per category")

    if args.clear_failures:
        count = cache.clear_failures()
        logger.info(f"Cleared {count} cached failures — tracks will be retried")

    # Determine what to sync
    async def run_sync():
        results = {}

        # Handle status command first
        if args.status:
            await show_library_status(engine, logger)
            return {}

        # Handle Tidal export
        if args.export_tidal:
            logger.progress("Exporting Tidal library...")
            exported = await engine.export_tidal_library()
            for name, path in exported.items():
                logger.success(f"Exported {name}: {path}")
            return {"tidal_export": {"exported": len(exported)}}

        # Reverse sync: Tidal -> Spotify
        if args.to_spotify:
            if args.sync_all:
                logger.progress("Syncing Tidal favorites to Spotify...")
                added, nf = await engine.sync_favorites_to_spotify()
                results["favorites"] = {"added": added, "not_found": nf}

                logger.progress("Syncing Tidal playlists to Spotify...")
                results["playlists"] = await engine.sync_all_playlists_to_spotify()

                logger.progress("Syncing Tidal albums to Spotify...")
                added, nf = await engine.sync_albums_to_spotify()
                results["albums"] = {"added": added, "not_found": nf}

                logger.progress("Syncing Tidal artists to Spotify...")
                added, nf = await engine.sync_artists_to_spotify()
                results["artists"] = {"added": added, "not_found": nf}

                logger.progress("Exporting podcasts...")
                count = await engine.export_podcasts()
                results["podcasts"] = {"exported": count}

            else:
                if args.favorites:
                    logger.progress("Syncing Tidal favorites to Spotify...")
                    added, not_found = await engine.sync_favorites_to_spotify()
                    results["favorites"] = {"added": added, "not_found": not_found}

                if args.playlists:
                    logger.progress("Syncing Tidal playlists to Spotify...")
                    results["playlists"] = await engine.sync_all_playlists_to_spotify()

                if args.albums:
                    logger.progress("Syncing Tidal albums to Spotify...")
                    added, not_found = await engine.sync_albums_to_spotify()
                    results["albums"] = {"added": added, "not_found": not_found}

                if args.artists:
                    logger.progress("Syncing Tidal artists to Spotify...")
                    added, not_found = await engine.sync_artists_to_spotify()
                    results["artists"] = {"added": added, "not_found": not_found}

                if not results:
                    logger.warning(
                        "Use --to-spotify with --favorites, --albums, "
                        "--artists, --playlists, or --all"
                    )
                    return {}

            return results

        # Apple Music sync: Spotify -> Apple Music
        if args.to_apple_music:
            if args.sync_all:
                logger.progress("Syncing liked songs to Apple Music...")
                added, nf = await engine.sync_favorites_to_apple_music()
                results["favorites"] = {"added": added, "not_found": nf}

                logger.progress("Syncing all playlists to Apple Music...")
                results["playlists"] = await engine.sync_all_playlists_to_apple_music(
                    skip_playlists=args.skip_playlist,
                )

                logger.progress("Syncing saved albums to Apple Music...")
                added, nf = await engine.sync_albums_to_apple_music()
                results["albums"] = {"added": added, "not_found": nf}

            else:
                if args.favorites:
                    logger.progress("Syncing liked songs to Apple Music...")
                    added, not_found = await engine.sync_favorites_to_apple_music()
                    results["favorites"] = {"added": added, "not_found": not_found}
                    if args.liked_playlist:
                        logger.progress(
                            f"Creating Apple playlist for liked songs: {args.liked_playlist_name}..."
                        )
                        pl_added, pl_missing = await engine.sync_favorites_playlist_to_apple_music(
                            name=args.liked_playlist_name
                        )
                        results["favorites_playlist"] = {
                            "added": pl_added,
                            "not_found": pl_missing,
                        }

                if args.albums:
                    logger.progress("Syncing saved albums to Apple Music...")
                    added, not_found = await engine.sync_albums_to_apple_music()
                    results["albums"] = {"added": added, "not_found": not_found}

                if args.playlists:
                    logger.progress("Syncing all playlists to Apple Music...")
                    results["playlists"] = await engine.sync_all_playlists_to_apple_music(
                        skip_playlists=args.skip_playlist,
                    )

                if args.playlist:
                    playlist_id = args.playlist.split(":")[-1]
                    logger.progress(f"Syncing playlist to Apple Music: {playlist_id}")
                    added, not_found = await engine.sync_playlist_to_apple_music(playlist_id)
                    results["playlist"] = {"added": added, "not_found": not_found}

                if not results:
                    logger.warning(
                        "Use --to-apple-music with --favorites, --albums, "
                        "--playlists, --playlist <id>, or --all"
                    )
                    return {}

            return results

        # Forward sync: Spotify -> Tidal (default)
        if args.playlist:
            # Sync specific playlist
            playlist_id = args.playlist.split(":")[-1]  # Handle URIs
            logger.progress(f"Syncing playlist: {playlist_id}")
            added, not_found = await engine.sync_playlist(playlist_id)
            results["playlist"] = {"added": added, "not_found": not_found}

        elif args.sync_all:
            # Sync everything
            logger.progress("Syncing liked songs...")
            added, nf = await engine.sync_favorites()
            results["favorites"] = {"added": added, "not_found": nf}

            logger.progress("Syncing all playlists...")
            results["playlists"] = await engine.sync_all_playlists()

            logger.progress("Syncing saved albums...")
            added, nf = await engine.sync_albums()
            results["albums"] = {"added": added, "not_found": nf}

            logger.progress("Syncing followed artists...")
            added, nf = await engine.sync_artists()
            results["artists"] = {"added": added, "not_found": nf}

            # Also export podcasts
            logger.progress("Exporting podcasts...")
            count = await engine.export_podcasts()
            results["podcasts"] = {"exported": count}

        else:
            if args.favorites:
                logger.progress("Syncing liked songs...")
                added, not_found = await engine.sync_favorites()
                results["favorites"] = {"added": added, "not_found": not_found}

            if args.albums:
                logger.progress("Syncing saved albums...")
                added, not_found = await engine.sync_albums()
                results["albums"] = {"added": added, "not_found": not_found}

            if args.artists:
                logger.progress("Syncing followed artists...")
                added, not_found = await engine.sync_artists()
                results["artists"] = {"added": added, "not_found": not_found}

            if args.playlists:
                logger.progress("Syncing all playlists...")
                results["playlists"] = await engine.sync_all_playlists()

            if args.podcasts:
                logger.progress("Exporting podcasts...")
                count = await engine.export_podcasts()
                results["podcasts"] = {"exported": count}

            if not results:
                # Default: show help
                logger.warning("No sync option specified. Use --help to see options.")
                parser.print_help()
            return {}

        return results

    try:
        results = asyncio.run(run_sync())

        if results:
            print_summary(results, logger)

            # Determine which categories to backup based on what was synced
            categories = []
            if args.sync_all:
                categories = None  # Backup everything
            else:
                if args.favorites:
                    categories.append("tracks")
                if args.albums:
                    categories.append("albums")
                if args.artists:
                    categories.append("artists")
                if args.playlists:
                    categories.append("playlists")
                if args.podcasts:
                    categories.append("podcasts")

            # Auto-export backup snapshot (only for forward sync to Tidal)
            if engine.tidal and direction == "to_tidal":
                logger.progress("Exporting backup snapshot...")
                export_result = asyncio.run(engine.export_backup(categories=categories))
                if export_result.get("files"):
                    export_dir = engine.library.export_dir
                    logger.success(f"Backup exported to: {export_dir}")
                    for name, path in export_result["files"].items():
                        logger.debug(f"  - {name}: {path}")

    except KeyboardInterrupt:
        logger.warning("Sync cancelled by user")
        logger.info("Your progress has been cached. Run again to resume.")
        sys.exit(1)
    except Exception as e:
        import traceback

        error_str = str(e).lower()
        if "rate" in error_str or "limit" in error_str or "429" in error_str:
            logger.error(UserErrors.rate_limited())
        elif "connection" in error_str or "network" in error_str:
            logger.error(UserErrors.network_error(str(e)))
        else:
            logger.error(UserErrors.sync_error("sync operation", str(e)))

        # Always log the traceback so bugs are diagnosable
        logger.error(f"Traceback:\n{traceback.format_exc()}")
        sys.exit(1)


if __name__ == "__main__":
    main()
