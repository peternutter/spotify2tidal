# TODO

## Apple Music (new)
- [ ] Test with real Apple Music account and tokens
- [ ] Apple Music → Spotify reverse sync
- [ ] Apple Music library CSV export (`library_csv_apple.py`)
- [ ] Apple Music counts in `--status` command
- [ ] Tests for Apple Music client, searcher, fetcher
- [ ] Handle token expiry gracefully (clear instructions to re-extract)
- [ ] Artist sync to Apple Music (Apple Music doesn't have "follow artist" — need to decide behavior)

## General / Existing
- [ ] Sync from backup CSV to Spotify/Tidal/Apple Music (restore from ground truth)
- [ ] Why does the one playlist transfer from Spotify to Tidal not work? Maybe not all playlists synced
- [ ] Save after each step (fetch) so we can resume
- [ ] Webapp: Apple Music support (low priority — CLI works better for long processes)
- [ ] Better matching: use playlistor's Jaro-Winkler weighted scoring approach
- [ ] Differential sync: only fetch items added since last sync
- [ ] Duplicate detection and removal
