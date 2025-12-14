# spotify2tidal

Sync your music library between Spotify and Tidal — **bidirectionally**.

This project combines and improves upon two open-source scripts:

- [spotify2tidal](https://github.com/taschenb/spotify2tidal) by taschenb
- [spotify_to_tidal](https://github.com/spotify2tidal/spotify_to_tidal)

## Features

- **Bidirectional sync** — Spotify → Tidal and Tidal → Spotify
- **Sync playlists** with incremental updates (only adds new tracks)
- **Sync favorites** (liked tracks), albums, and followed artists
- **Export podcasts** to CSV (Tidal doesn't support podcasts)
- **Smart matching** using ISRC, duration, name, and artist
- **Order preservation** — oldest items appear at bottom (matching Spotify)
- **Incremental sync** — skips items already in your library
- **Caching** — persists track mappings in JSON for fast re-runs
- **Library status** — see what's on each platform and what's missing

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
2. Add a Redirect URI depending on how you run the project:
   - CLI: `http://127.0.0.1:8888/callback`
   - Streamlit webapp (local): `http://localhost:8501/`
3. Copy `config.example.yml` to `config.yml` and add your credentials

## CLI Usage

### Spotify → Tidal (default)

```bash
# Sync everything (playlists, favorites, albums, artists)
spotify2tidal --all

# Sync specific categories
spotify2tidal --favorites    # Liked tracks
spotify2tidal --albums       # Saved albums
spotify2tidal --artists      # Followed artists
spotify2tidal --playlists    # All playlists
spotify2tidal --podcasts     # Export podcasts to CSV

# Sync a specific playlist
spotify2tidal -p <playlist_id_or_uri>
```

### Tidal → Spotify

```bash
# Sync everything from Tidal to Spotify
spotify2tidal --to-spotify --all

# Sync specific categories
spotify2tidal --to-spotify --favorites   # Tidal favorites → Spotify liked songs
spotify2tidal --to-spotify --albums      # Tidal albums → Spotify library
spotify2tidal --to-spotify --artists     # Tidal follows → Spotify follows
```

### Library Management

```bash
# Show library status on both platforms
spotify2tidal --status

# Export current Tidal library to CSV
spotify2tidal --export-tidal

# Verbose output
spotify2tidal --all -v
```

### Debugging Large Libraries

```bash
# Limit to 10 items per category for faster testing
spotify2tidal --favorites --limit 10

# Test albums with only 5 items
spotify2tidal --albums --limit 5

# Works with all sync modes
spotify2tidal --all --limit 20
spotify2tidal --to-spotify --favorites --limit 10
```

On first run, browsers open for Spotify and Tidal authentication.

## Incremental Sync

The tool is smart about avoiding duplicates:

- **Favorites, albums, artists**: Fetches ALL existing items from Tidal before syncing
- **Playlists**: Checks existing tracks in each Tidal playlist
- **Cache**: Remembers Spotify→Tidal track mappings between runs

This means running the sync multiple times is fast and won't create duplicates.

## Data Storage

All CLI data is stored in the `library/` directory:

- `cache.json` — Spotify→Tidal track/album/artist mappings
- `.spotify_cache` — Spotify OAuth token
- `.tidal_session.json` — Tidal session

**Interoperability**: The web app export ZIP uses the same cache format. You can:

- **Export from CLI**: Copy `library/cache.json` and CSVs
- **Import to web app**: Upload the file as a ZIP
- **Export from web app**: Extract the ZIP to `library/`
- **Clear**: Delete files to force re-authentication/search

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
