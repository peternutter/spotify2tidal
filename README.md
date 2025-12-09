# spotify2tidal

Sync your Spotify library to Tidal — playlists, favorites, albums, and artists.

This project combines and improves upon two open-source scripts:

- [spotify2tidal](https://github.com/taschenb/spotify2tidal) by taschenb
- [spotify_to_tidal](https://github.com/spotify2tidal/spotify_to_tidal)

## Features

- **Sync playlists** with incremental updates
- **Sync favorites** (liked tracks), albums, and followed artists
- **Smart matching** using ISRC, duration, name, and artist
- **Order preservation** — oldest items appear at bottom (matching Spotify)
- **Caching** to avoid redundant API calls
- **Async** for fast parallel processing

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

## Usage (Without uv)

If using pip (without uv), ensure your virtual environment is activated before running commands.

```bash
# Activate venv if not already done
source .venv/bin/activate

# Then run commands
spotify2tidal --all        # Sync everything
spotify2tidal --playlists  # Sync all playlists
spotify2tidal --favorites  # Sync liked tracks
spotify2tidal --artists    # Sync followed artists
spotify2tidal --albums     # Sync saved albums
spotify2tidal -p <id>      # Sync specific playlist
```

On first run, browsers open for Spotify and Tidal authentication.

## Tests (Without uv)

With pip, activate the venv and run:

```bash
source .venv/bin/activate
pytest tests/ -v
```

## Requirements

- Python 3.10+
- Spotify Premium account
- Tidal account

## License

GPL-3.0