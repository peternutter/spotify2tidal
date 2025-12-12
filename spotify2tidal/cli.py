"""
Command-line interface for spotify2tidal.
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

import yaml

from .auth import open_spotify_session, open_tidal_session
from .sync import SyncEngine


def setup_logging(verbose: bool = False):
    """Configure logging."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(levelname)s: %(message)s")


def load_config(config_path: str) -> dict:
    """Load configuration from YAML file."""
    path = Path(config_path)
    if not path.exists():
        return {}
    with open(path) as f:
        return yaml.safe_load(f) or {}


def main():
    parser = argparse.ArgumentParser(
        description="Sync your Spotify library to Tidal",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  spotify2tidal --playlists         # Sync all playlists
  spotify2tidal --favorites         # Sync liked/saved tracks
  spotify2tidal --albums            # Sync saved albums
  spotify2tidal --artists           # Sync followed artists
  spotify2tidal --podcasts          # Export podcasts to CSV (Tidal doesn't support podcasts)
  spotify2tidal --all               # Sync everything + export podcasts
  spotify2tidal --playlist <id>     # Sync specific playlist
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
        help="Sync everything (playlists, favorites, albums, artists) + export podcasts",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose output"
    )

    args = parser.parse_args()
    setup_logging(args.verbose)

    # Load config
    config = load_config(args.config)

    # Open sessions
    print("Connecting to Spotify...")
    try:
        spotify = open_spotify_session(config.get("spotify", {}))
    except Exception as e:
        print(f"Failed to connect to Spotify: {e}")
        sys.exit(1)

    print("Connecting to Tidal...")
    try:
        tidal = open_tidal_session(config.get("tidal", {}))
    except Exception as e:
        print(f"Failed to connect to Tidal: {e}")
        sys.exit(1)

    if not tidal.check_login():
        print("Failed to authenticate with Tidal")
        sys.exit(1)

    # Create sync engine
    sync_config = config.get("sync", {})
    library_config = config.get("library", {})
    engine = SyncEngine(
        spotify,
        tidal,
        max_concurrent=sync_config.get("max_concurrent", 10),
        rate_limit=sync_config.get("rate_limit", 10),
        library_dir=library_config.get("export_dir", "./library"),
    )

    # Determine what to sync
    async def run_sync():
        results = {}

        if args.playlist:
            # Sync specific playlist
            playlist_id = args.playlist.split(":")[-1]  # Handle URIs
            added, not_found = await engine.sync_playlist(playlist_id)
            results["playlist"] = {"added": added, "not_found": not_found}

        elif args.sync_all:
            # Sync everything
            results["playlists"] = await engine.sync_all_playlists()
            added, nf = await engine.sync_favorites()
            results["favorites"] = {"added": added, "not_found": nf}
            added, nf = await engine.sync_albums()
            results["albums"] = {"added": added, "not_found": nf}
            added, nf = await engine.sync_artists()
            results["artists"] = {"added": added, "not_found": nf}
            # Also export podcasts
            count = await engine.export_podcasts()
            results["podcasts"] = {"exported": count}

        elif args.favorites:
            added, not_found = await engine.sync_favorites()
            results["favorites"] = {"added": added, "not_found": not_found}

        elif args.albums:
            added, not_found = await engine.sync_albums()
            results["albums"] = {"added": added, "not_found": not_found}

        elif args.artists:
            added, not_found = await engine.sync_artists()
            results["artists"] = {"added": added, "not_found": not_found}

        elif args.playlists:
            # Sync all playlists
            results["playlists"] = await engine.sync_all_playlists()

        elif args.podcasts:
            # Export podcasts only
            count = await engine.export_podcasts()
            results["podcasts"] = {"exported": count}

        else:
            # Default: show help
            print("No sync option specified. Use --help to see available options.")
            return {}

        return results

    try:
        results = asyncio.run(run_sync())
        print("\n" + "=" * 40)
        print("Sync completed!")
        print("=" * 40)

        for category, data in results.items():
            if isinstance(data, dict) and "added" in data:
                print(
                    f"{category}: {data['added']} added, {data['not_found']} not found"
                )
            elif isinstance(data, dict):
                total_added = sum(d.get("added", 0) for d in data.values())
                total_nf = sum(d.get("not_found", 0) for d in data.values())
                print(f"{category}: {total_added} added, {total_nf} not found")

        # Auto-export library data
        if results:
            print("\nExporting library data...")
            export_result = engine.export_library()
            if export_result["files"]:
                print(f"Library exported to: {engine.library.export_dir}")
                for name, path in export_result["files"].items():
                    print(f"  - {name}: {path}")

    except KeyboardInterrupt:
        print("\nSync cancelled")
        sys.exit(1)
    except Exception as e:
        print(f"Error during sync: {e}")
        if args.verbose:
            import traceback

            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
