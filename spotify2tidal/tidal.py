import logging
from pathlib import Path

import tidalapi


class Tidal:
    """Provide a search-based adding of new favorites to Tidal.

    Add new artists/albums/tracks/albums by searching for them with
    save_artist(), save_album(), and save_track().

    Authentication is done via OAuth. On first run, a browser will open
    to complete authentication. The session is then saved to a file for
    future use.

    Parameters
    ----------
    session_file: str or Path, optional
        Path to store the OAuth session file. Defaults to 'tidal_session.json'
    """

    def __init__(self, session_file=None):
        self.session_file = (
            Path(session_file) if session_file else Path.home() / ".tidal_session.json"
        )
        self.tidal_session = self._connect()

    @property
    def own_playlists(self):
        """All playlists of the current user."""
        return self.tidal_session.get_user_playlists(self.tidal_session.user.id)

    def add_track_to_playlist(self, playlist_id, name, artist):
        """Search tidal for a track and add it to a playlist.

        Parameters
        ----------
        playlist_id:
            Playlist to add track to
        name: str
            Name of the track
        artist: str
            Artist of the track
        """
        track_id = self._search_track(name, artist)

        if track_id:
            # Get playlist object and add track using tidalapi
            playlist = self.tidal_session.playlist(playlist_id)
            playlist.add([track_id])
            logging.getLogger(__name__).info("Added: %s - %s", artist, name)

        else:
            logging.getLogger(__name__).warning(
                "Could not find track: %s - %s", artist, name
            )

    def delete_existing_playlist(self, playlist_name):
        """Delete any existing playlist with a given name.

        Parameters
        ----------
        playlist_name: str
            Playlist name to delete
        """
        for playlist in self.own_playlists:
            if playlist.name == playlist_name:
                self._delete_playlist(playlist.id)

    def save_album(self, name, artist_name):
        """Find an album and save it to your favorites.

        Parameters
        ----------
        name: str
            Name of the album
        artist_name: str
            Name of the artist
        """
        album = self._search_album(name, artist_name)

        if album:
            self.tidal_session.user.favorites.add_album(album)
            logging.getLogger(__name__).warning(
                "Added album: %s from %s", name, artist_name
            )
        else:
            logging.getLogger(__name__).warning(
                "Could not find album: %s from %s", name, artist_name
            )

    def save_artist(self, name):
        """Find an artist by name and save it to your favorites.

        Parameters
        ----------
        name: str
            Name of the artist
        """
        artist = self._search_artist(name)

        if artist:
            self.tidal_session.user.favorites.add_artist(artist)
            logging.getLogger(__name__).warning("Added artist: %s", name)
        else:
            logging.getLogger(__name__).warning("Could not find artist: %s", name)

    def save_track(self, name, artist_name):
        """Find a track and save it to your favorites.

        Parameters
        ----------
        name: str
            Name of the track
        artist_name: str
            Name of the artist
        """
        track = self._search_track(name, artist_name)

        if track:
            self.tidal_session.user.favorites.add_track(track)
            logging.getLogger(__name__).warning(
                "Added track: %s from %s", name, artist_name
            )
        else:
            logging.getLogger(__name__).warning(
                "Could not find track: %s from %s", name, artist_name
            )

    def _create_playlist(self, playlist_name, delete_existing=False):
        """Create a tidal playlist and return its ID.

        Parameters
        ----------
        playlist_name: str
            Name of the playlist to create
        delete_existing: str
            Delete any existing playlist with the same name
        """
        if delete_existing is True:
            self.delete_existing_playlist(playlist_name)

        # Use tidalapi to create playlist
        playlist = self.tidal_session.user.create_playlist(playlist_name, "")

        logging.getLogger(__name__).debug("Created playlist: %s", playlist_name)

        return playlist.id

    def _connect(self):
        """Connect to tidal using OAuth and return a session object.

        If a session file exists, it will try to load from it.
        Otherwise, it will initiate OAuth login flow.
        """
        tidal_session = tidalapi.Session()

        # Try to load existing session
        if self.session_file.exists():
            try:
                tidal_session.load_session_from_file(self.session_file)
                if tidal_session.check_login():
                    logging.getLogger(__name__).info("Loaded existing Tidal session")
                    return tidal_session
            except Exception as e:
                logging.getLogger(__name__).warning(f"Could not load session: {e}")

        # Start OAuth login
        logging.getLogger(__name__).info("Starting Tidal OAuth login...")
        tidal_session.login_oauth_simple()

        if tidal_session.check_login():
            # Save session for future use
            tidal_session.save_session_to_file(self.session_file)
            logging.getLogger(__name__).info("Tidal login successful, session saved")
            return tidal_session
        else:
            raise ValueError("Could not connect to Tidal")

    def _delete_playlist(self, playlist_id):
        """Delete a playlist.

        Parameters
        ----------
        playlist_id: str
            Playlist ID to delete
        """
        playlist = self.tidal_session.playlist(playlist_id)
        playlist.delete()

    def _search_track(self, name, artist):
        """Search tidal and return the track ID.

        Parameters
        ----------
        name: str
            Name of the track
        artist: str
            Artist of the track
        """
        search_query = f"{name} {artist}"
        results = self.tidal_session.search(
            search_query, models=[tidalapi.media.Track], limit=20
        )
        tracks = (
            results.get("tracks", [])
            if isinstance(results, dict)
            else getattr(results, "tracks", [])
        )

        for t in tracks:
            if t.artist and t.artist.name.lower() == artist.lower():
                return t.id

    def _search_album(self, name, artist):
        """Search tidal and return the album ID.

        Parameters
        ----------
        name: str
            Name of the album
        artist: str
            Artist of the album
        """
        search_query = f"{name} {artist}"
        results = self.tidal_session.search(
            search_query, models=[tidalapi.album.Album], limit=20
        )
        albums = (
            results.get("albums", [])
            if isinstance(results, dict)
            else getattr(results, "albums", [])
        )

        for a in albums:
            if a.artist and a.artist.name.lower() == artist.lower():
                return a.id

    def _search_artist(self, name):
        """Search tidal and return the artist ID.

        Parameters
        ----------
        name: str
            Name of the artist
        """
        results = self.tidal_session.search(
            name, models=[tidalapi.artist.Artist], limit=20
        )
        artists = (
            results.get("artists", [])
            if isinstance(results, dict)
            else getattr(results, "artists", [])
        )

        for a in artists:
            if a.name.lower() == name.lower():
                return a.id
