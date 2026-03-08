# TODO

## Apple Music Sync (ready to test)
- [ ] Test with real Apple Music account — verify favorites endpoint works
- [ ] Verify playlist ordering is preserved (added in Spotify order)
- [ ] Apple Music → Spotify reverse sync
- [ ] Apple Music library CSV export
- [ ] Tests for Apple Music client, searcher, fetcher
- [ ] Handle token expiry gracefully (clear instructions to re-extract)
- [ ] Artist sync (Apple Music doesn't have "follow artist" — skip or add top tracks?)

## Quick Wins (small, high-value fixes)
- [ ] Extract `paginate_spotify()` helper (8+ methods with identical boilerplate)
- [ ] Unify logging: pass SyncLogger to sync functions instead of `getattr(engine, "_logger")` hack
- [ ] Auto-expire cache failures after N days (currently block retries forever)
- [ ] Prune stale cache entries (file grows unbounded)

## Robustness
- [ ] Retry individual items from failed batch adds (currently all-or-nothing)
- [ ] Preemptive rate limiting for Apple Music (currently reactive, waits for 429)
- [ ] Validate playlist ordering after add (fetch back and compare positions)
- [ ] Add pagination completeness check to Apple Music `_get_paginated()`

## Larger Features
- [ ] Sync from backup CSV to any platform (restore from ground truth)
- [ ] Differential sync: only fetch items added since last sync
- [ ] Duplicate detection and removal across platforms
- [ ] Save checkpoint after each fetch phase for resume on crash
- [ ] Webapp: Apple Music support (low priority — CLI works better)
- [ ] Better matching: Jaro-Winkler weighted scoring (see playlistor)
