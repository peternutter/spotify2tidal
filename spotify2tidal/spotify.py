import logging

import spotipy
from spotipy.oauth2 import SpotifyOAuth


class Spotify:
    """Access a Spotify-account.

    Parameters
    ----------
    username: str
        Username for the Spotify-account
    client_id: str
        Client ID for the app, created at developer.spotify.com/dashboard
    client_secret: str
        Secret for the client ID, created along with the ID
    client_redirect_uri: str
        Link to redirect after successful authentification
    discover_weekly_id: str, optional
        Playlist-ID for the 'Discover Weekly' playlist provided by Spotify
    """

    def __init__(
        self,
        username,
        client_id,
        client_secret,
        client_redirect_uri,
        discover_weekly_id=None,
    ):
        self.username = username
        self._client_id = client_id
        self._client_secret = client_secret
        self._client_redirect_uri = client_redirect_uri
        self._discover_weekly_id = discover_weekly_id

        self.spotify_session = self._connect()

    @property
    def own_playlists(self):
        """All playlists of the user.

        This does not include things like 'Discover Weekly', since these are
        technically owned by Spotify, not the user.
        """
        try:
            result = self.spotify_session.current_user_playlists()
            playlists = result["items"]

            while result["next"]:
                result = self.spotify_session.next(result)
                playlists.extend(result["items"])
        except spotipy.client.SpotifyException:
            self._refresh_expired_token()
            return self.own_playlists

        return playlists

    @property
    def saved_artists(self):
        """List with all saved artists."""
        try:
            result = self.spotify_session.current_user_followed_artists()["artists"]
            artists = result["items"]

            while result["next"]:
                result = self.spotify_session.next(result)["artists"]
                artists.extend(result["items"])
        except spotipy.client.SpotifyException:
            self._refresh_expired_token()
            return self.saved_artists

        return artists

    @property
    def saved_albums(self):
        """List with all saved albums."""
        try:
            result = self.spotify_session.current_user_saved_albums()
            albums = result["items"]

            while result["next"]:
                result = self.spotify_session.next(result)
                albums.extend(result["items"])
        except spotipy.client.SpotifyException:
            self._refresh_expired_token()
            return self.saved_albums

        return albums

    @property
    def saved_tracks(self):
        """List with all saved tracks."""
        try:
            result = self.spotify_session.current_user_saved_tracks()
            tracks = result["items"]

            while result["next"]:
                result = self.spotify_session.next(result)
                tracks.extend(result["items"])
        except spotipy.client.SpotifyException:
            self._refresh_expired_token()
            return self.saved_tracks

        return tracks

    @property
    def discover_weekly_playlist(self):
        """Playlist object of the 'Discover Weekly" playlist.

        Since the discover weekly is special in the sense that it isn't actually
        owned by the user, its ID has to be manually provided beforehand.
        """
        if not self._discover_weekly_id:
            raise ValueError("No discover weekly ID set")

        try:
            return self.spotify_session.user_playlist(
                self.username, self._discover_weekly_id
            )
        except spotipy.client.SpotifyException:
            self._refresh_expired_token()
            return self.discover_weekly_playlist()

    def tracks_from_playlist(self, playlist):
        """Return a list with all tracks from a given playlist.

        Parameters
        ----------
        playlist:
            spotipy playlist to get tracks from
        """
        try:
            result = self.spotify_session.user_playlist(
                user=playlist["owner"]["id"],
                playlist_id=playlist["id"],
                fields="tracks,next",
            )["tracks"]

            tracks = result["items"]

            while result["next"]:
                result = self.spotify_session.next(result)
                tracks.extend(result["items"])
        except spotipy.client.SpotifyException:
            self._refresh_expired_token()
            return self.tracks_from_playlist(playlist)

        return tracks

    def _connect(self):
        """Connect to Spotify and return a session object.

        Use spotify's Authorization Code Flow with SpotifyOAuth.
        This requires a registered client at spotify with a valid client-id,
        client-secret and some redirection-url
        More information on authorization:
        https://developer.spotify.com/documentation/general/guides/authorization-guide/
        https://spotipy.readthedocs.io/en/latest/#authorized-requests
        """
        scope = " ".join(
            [
                "user-library-read",
                "playlist-read-private",
                "user-follow-read",
                "playlist-modify-private",
                "playlist-modify-public",
            ]
        )

        auth_manager = SpotifyOAuth(
            client_id=self._client_id,
            client_secret=self._client_secret,
            redirect_uri=self._client_redirect_uri,
            scope=scope,
            username=self.username,
            open_browser=True,
        )

        return spotipy.Spotify(auth_manager=auth_manager)

    def _refresh_expired_token(self):
        """When the token expires after 1h, refresh it.

        With SpotifyOAuth auth_manager, tokens are automatically refreshed.
        This method is kept for backwards compatibility but the auth_manager
        handles token refresh automatically.
        """
        logging.getLogger(__name__).debug("Token refresh handled by auth_manager")
        # SpotifyOAuth handles refresh automatically, but reconnect if needed
        self.spotify_session = self._connect()
