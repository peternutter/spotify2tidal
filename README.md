# spotify2tidal

Sync your music library between Spotify, Tidal, and Apple Music.

This project combines and improves upon two open-source scripts:

- [spotify2tidal](https://github.com/taschenb/spotify2tidal) by taschenb
- [spotify_to_tidal](https://github.com/spotify2tidal/spotify_to_tidal)

## Features

- **Multi-platform** -- Spotify ↔ Tidal and Spotify → Apple Music
- **Sync playlists** with incremental updates (only adds new tracks)
- **Sync favorites** (liked tracks), albums, and followed artists
- **Export podcasts** to CSV & OPML (Tidal/Apple Music don't support podcasts)
- **Smart matching** using ISRC, duration, name, and artist
- **Order preservation** -- oldest items appear at bottom (matching Spotify)
- **Incremental sync** -- skips items already in your library
- **Caching** -- persists track mappings in JSON for fast re-runs
- **Library status** -- see what's on each platform and what's missing

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

See <DEPLOYMENT.md> for cloud deployment.

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

### Spotify

1. Create a Spotify app at [developer.spotify.com/dashboard](https://developer.spotify.com/dashboard)
2. Add a Redirect URI depending on how you run the project:

- CLI: `http://127.0.0.1:8888/callback`
- Streamlit webapp (local): `http://localhost:8501/`

3. Copy `config.example.yml` to `config.yml` and add your credentials

> **Note (March 2026):** Spotify now requires the app owner to have an active **Premium subscription** for Dev Mode API access. Free/Student plans may not work. See [Spotify's announcement](https://developer.spotify.com/blog/2026-02-06-update-on-developer-access-and-platform-security).

### Apple Music (optional)

Apple Music sync uses cookie-based authentication — no Apple Developer account needed. Tokens last ~6 months.

1. Open https://music.apple.com in your browser and sign in
2. Open DevTools (F12) → Network tab
3. Click any request to `amp-api.music.apple.com`
4. Copy these headers into `config.yml`:
   - `Authorization` → `bearer_token` (without the "Bearer " prefix)
   - `Media-User-Token` → `media_user_token`
   - `Cookie` → `cookies`
5. Set `storefront` to your account region (e.g., `us`, `cz`, `gb`)

If your storefront has a smaller catalog, the tool automatically falls back to the US catalog for better match rates.

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
spotify2tidal --podcasts     # Export podcasts to CSV & OPML

# Sync a specific playlist
spotify2tidal -p <playlist_id_or_uri>
```

### Spotify → Apple Music

```bash
# Sync everything to Apple Music
spotify2tidal --to-apple-music --all

# Sync specific categories
spotify2tidal --to-apple-music --favorites   # Liked songs → Apple Music Library + Favorites
spotify2tidal --to-apple-music --albums      # Saved albums → Apple Music Library
spotify2tidal --to-apple-music --playlists   # All playlists

# Sync a specific playlist
spotify2tidal --to-apple-music -p <playlist_id>

# Skip specific playlists (by name)
spotify2tidal --to-apple-music --playlists --skip-playlist "Huge Playlist"
```

### Tidal → Spotify

```bash
# Sync everything from Tidal to Spotify
spotify2tidal --to-spotify --all

# Sync specific categories
spotify2tidal --to-spotify --favorites   # Tidal favorites → Spotify liked songs
spotify2tidal --to-spotify --albums      # Tidal albums → Spotify library
spotify2tidal --to-spotify --playlists   # Tidal playlists → Spotify playlists (add-only)
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

- `cache.json` -- Spotify→Tidal track/album/artist mappings
- `.spotify_cache` -- Spotify OAuth token
- `.tidal_session.json` -- Tidal session

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
- `spotify_podcasts.opml` - Podcasts in OPML format for RSS readers
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
- Spotify Premium account (required for API access since March 2026)
- Tidal account (optional)
- Apple Music account (optional)

## License

GPL-3.0
