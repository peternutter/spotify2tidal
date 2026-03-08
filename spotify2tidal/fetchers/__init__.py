"""Fetchers for extracting data from music platforms."""

from .apple_music_fetcher import AppleMusicFetcher
from .spotify_fetcher import SpotifyFetcher
from .tidal_fetcher import TidalFetcher

__all__ = ["AppleMusicFetcher", "SpotifyFetcher", "TidalFetcher"]
