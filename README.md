# spotify2tidal

Sync your Spotify library to Tidal — playlists, favorites, albums, artists, and podcasts.

This project combines and improves upon two open-source scripts:

- [spotify2tidal](https://github.com/taschenb/spotify2tidal) by taschenb
- [spotify_to_tidal](https://github.com/spotify2tidal/spotify_to_tidal)

## Features

- **Sync playlists** with incremental updates (only adds new tracks)
- **Sync favorites** (liked tracks), albums, and followed artists
- **Export podcasts** to CSV (Tidal doesn't support podcasts)
- **Smart matching** using ISRC, duration, name, and artist
- **Order preservation** — oldest items appear at bottom (matching Spotify)
- **Incremental sync** — skips items already in your Tidal library
- **Caching** — persists Spotify→Tidal mappings in SQLite for fast re-runs
- **Async** for fast parallel processing

## Web App

A Streamlit-based web interface is available for non-technical users:

```bash
uv run streamlit run webapp.py
```

Features:

- Connect to Spotify and Tidal with OAuth
- One-click sync of your entire library
- Download exported CSVs and cache backup
- Upload cache to restore sync progress

See [DEPLOYMENT.md](DEPLOYMENT.md) for cloud deployment.

## Installation

```bash
# With uv (recommended)
git clone https://github.com/taschenb/spotify2tidal
cd spotify2tidal
uv sync

# With pip
git clone https://github.com/taschenb/spotify2tidal
cd spotify2tidal
python3 -m venv .venv
source .venv/bin/activate  # On Linux; activate each time
pip install -e .
```

## Setup

1. Create a Spotify app at [developer.spotify.com/dashboard](https://developer.spotify.com/dashboard)
2. Add `http://127.0.0.1:8888/callback` to Redirect URIs
3. Copy `config.example.yml` to `config.yml` and add your credentials

## CLI Usage

```bash
# Sync everything (playlists, favorites, albums, artists)
spotify2tidal --all

# Sync specific categories
spotify2tidal --playlists    # All playlists
spotify2tidal --favorites    # Liked tracks
spotify2tidal --albums       # Saved albums
spotify2tidal --artists      # Followed artists
spotify2tidal --podcasts     # Export podcasts to CSV (no Tidal sync)

# Sync a specific playlist
spotify2tidal -p <playlist_id_or_uri>

# Verbose output
spotify2tidal --all -v
```

On first run, browsers open for Spotify and Tidal authentication.

## Incremental Sync

The tool is smart about avoiding duplicates:

- **Favorites, albums, artists**: Fetches ALL existing items from Tidal before syncing
- **Playlists**: Checks existing tracks in each Tidal playlist
- **Cache**: Remembers Spotify→Tidal track mappings between runs

This means running the sync multiple times is fast and won't create duplicates.

## Cache Management

Track mappings are stored in `~/.spotify2tidal_cache.db`. You can:

- **Backup**: Copy the file to save your sync progress
- **Restore**: Replace the file to restore progress on a new machine
- **Clear**: Delete the file to force fresh searches

## Library Export

After each sync, CSVs are exported to `./library/`:

- `spotify_tracks.csv` - All synced tracks
- `spotify_albums.csv` - All synced albums  
- `spotify_artists.csv` - All synced artists
- `spotify_podcasts.csv` - All podcasts (if exported)
- `not_found_*.csv` - Items not found on Tidal

## Tests

```bash
# With uv
uv run python -m pytest tests/ -v

# With pip (venv activated)
pytest tests/ -v
```

## Requirements

- Python 3.10+
- Spotify Premium account
- Tidal account

## License

GPL-3.0
