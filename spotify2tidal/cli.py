"""
Command-line interface for spotify2tidal.

Production-ready CLI with structured logging and colorized output.
"""

import argparse
import asyncio
import sys
from pathlib import Path

import yaml

from .auth import open_spotify_session, open_tidal_session
from .cache import MatchCache
from .logging_utils import SyncLogger, UserErrors
from .sync import SyncEngine


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
        description="Sync your Spotify library to Tidal",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  spotify2tidal --playlists         # Sync all playlists
  spotify2tidal --favorites         # Sync liked/saved tracks
  spotify2tidal --albums            # Sync saved albums
  spotify2tidal --artists           # Sync followed artists
  spotify2tidal --podcasts          # Export podcasts to CSV
  spotify2tidal --all               # Sync everything + export podcasts
  spotify2tidal --playlist <id>     # Sync specific playlist

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
    parser.add_argument(
        "--playlist", "-p", help="Sync a specific Spotify playlist (ID or URI)"
    )
    parser.add_argument(
        "--favorites",
        "-f",
        action="store_true",
        help="Sync liked/saved tracks to Tidal favorites",
    )
    parser.add_argument(
        "--playlists",
        action="store_true",
        help="Sync all user playlists",
    )
    parser.add_argument("--albums", "-a", action="store_true", help="Sync saved albums")
    parser.add_argument(
        "--artists", "-r", action="store_true", help="Sync followed artists"
    )
    parser.add_argument(
        "--podcasts",
        action="store_true",
        help="Export saved podcasts to CSV (Tidal doesn't support podcasts)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        dest="sync_all",
        help="Sync everything (playlists, favorites, albums, artists)",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose debug output"
    )
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

    return parser


def print_header(logger: SyncLogger):
    """Print a styled header."""
    logger.info("━" * 50)
    logger.info("🎵 Spotify → Tidal Sync")
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
            not_found = sum(
                d.get("not_found", 0) for d in data.values() if isinstance(d, dict)
            )
            total_added += added
            total_not_found += not_found
            logger.info(f"  {category.title()}: {added} added, {not_found} not found")

    logger.info("━" * 50)
    if total_not_found > 0:
        logger.warning(
            f"  {total_not_found} items could not be found on Tidal. "
            "Check library/not_found_*.csv for details."
        )


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

    print_header(logger)

    # Load config
    config = load_config(args.config)
    if not config and not Path(args.config).exists():
        if args.config != "config.yml":
            # User specified a config file that doesn't exist
            logger.error(UserErrors.config_not_found(args.config))
            sys.exit(1)
        else:
            logger.debug("No config.yml found, using environment variables")

    # Connect to Spotify
    logger.progress("Connecting to Spotify...")
    try:
        spotify = open_spotify_session(config.get("spotify", {}))
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

    # Connect to Tidal
    logger.progress("Connecting to Tidal...")
    try:
        tidal = open_tidal_session(config.get("tidal", {}))
        if not tidal.check_login():
            logger.error(UserErrors.tidal_auth_failed("Login check failed"))
            sys.exit(1)
        logger.success("Connected to Tidal")
    except Exception as e:
        logger.error(UserErrors.tidal_auth_failed(str(e)))
        sys.exit(1)

    # Create sync engine with cache persistence
    sync_config = config.get("sync", {})
    library_config = config.get("library", {})
    cache_file = str(Path.home() / ".spotify2tidal_cache.json")
    cache = MatchCache(cache_file=cache_file)
    logger.debug(f"Using cache: {cache_file} ({cache.get_stats()})")

    engine = SyncEngine(
        spotify,
        tidal,
        max_concurrent=sync_config.get("max_concurrent", 10),
        rate_limit=sync_config.get("rate_limit", 10),
        library_dir=library_config.get("export_dir", "./library"),
        logger=logger,
        cache=cache,
    )

    # Determine what to sync
    async def run_sync():
        results = {}

        if args.playlist:
            # Sync specific playlist
            playlist_id = args.playlist.split(":")[-1]  # Handle URIs
            logger.progress(f"Syncing playlist: {playlist_id}")
            added, not_found = await engine.sync_playlist(playlist_id)
            results["playlist"] = {"added": added, "not_found": not_found}

        elif args.sync_all:
            # Sync everything
            logger.progress("Syncing all playlists...")
            results["playlists"] = await engine.sync_all_playlists()

            logger.progress("Syncing liked songs...")
            added, nf = await engine.sync_favorites()
            results["favorites"] = {"added": added, "not_found": nf}

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

        elif args.favorites:
            logger.progress("Syncing liked songs...")
            added, not_found = await engine.sync_favorites()
            results["favorites"] = {"added": added, "not_found": not_found}

        elif args.albums:
            logger.progress("Syncing saved albums...")
            added, not_found = await engine.sync_albums()
            results["albums"] = {"added": added, "not_found": not_found}

        elif args.artists:
            logger.progress("Syncing followed artists...")
            added, not_found = await engine.sync_artists()
            results["artists"] = {"added": added, "not_found": not_found}

        elif args.playlists:
            logger.progress("Syncing all playlists...")
            results["playlists"] = await engine.sync_all_playlists()

        elif args.podcasts:
            logger.progress("Exporting podcasts...")
            count = await engine.export_podcasts()
            results["podcasts"] = {"exported": count}

        else:
            # Default: show help
            logger.warning("No sync option specified. Use --help to see options.")
            parser.print_help()
            return {}

        return results

    try:
        results = asyncio.run(run_sync())

        if results:
            print_summary(results, logger)

            # Auto-export library data
            logger.progress("Exporting library data...")
            export_result = engine.export_library()
            if export_result["files"]:
                export_dir = engine.library.export_dir
                logger.success(f"Library exported to: {export_dir}")
                for name, path in export_result["files"].items():
                    logger.debug(f"  - {name}: {path}")

    except KeyboardInterrupt:
        logger.warning("Sync cancelled by user")
        logger.info("Your progress has been cached. Run again to resume.")
        sys.exit(1)
    except Exception as e:
        error_str = str(e).lower()
        if "rate" in error_str or "limit" in error_str or "429" in error_str:
            logger.error(UserErrors.rate_limited())
        elif "connection" in error_str or "network" in error_str:
            logger.error(UserErrors.network_error(str(e)))
        else:
            logger.error(UserErrors.sync_error("sync operation", str(e)))

        if args.verbose:
            import traceback

            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
