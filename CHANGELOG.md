# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- FTS5 full-text search index for faster search queries
- Server-side pagination for Plex API calls
- Response caching with 5-minute TTL
- Global recently added endpoint
- LIVE_FIRST environment variable to toggle live-first mode
- Comprehensive metadata extraction (genres, actors, directors, writers, producers, ratings, etc.)
- Extended metadata support for all media types (movies, shows, seasons, episodes, artists, albums, tracks)
- Automatic schema migrations
- Health check endpoint

### Changed
- Improved error handling with automatic fallback to SQLite
- Optimized database queries with better indexes
- Enhanced logging with structured levels

## [1.0.0] - 2024-01-XX

### Added
- Initial release
- Python sync script with SQLite database
- Node.js backend with live-first architecture
- Automatic fallback to SQLite when Plex is unavailable
- Full support for Movies, TV Shows, Seasons, Episodes, Artists, Albums, Tracks
- WebP image conversion and storage
- Media hash fingerprinting for change detection
- Parallel processing for image downloads
- CLI arguments for flexible execution

[Unreleased]: https://github.com/yourusername/plex-collection-sync/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/yourusername/plex-collection-sync/releases/tag/v1.0.0

