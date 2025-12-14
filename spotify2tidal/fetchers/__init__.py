"""Fetchers for extracting data from music platforms."""

from .spotify_fetcher import SpotifyFetcher
from .tidal_fetcher import TidalFetcher

__all__ = ["SpotifyFetcher", "TidalFetcher"]
