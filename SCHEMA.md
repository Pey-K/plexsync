# Database Schema Documentation

This document describes the SQLite database schema used by the Plex Collection Sync project.

## Overview

The database uses a normalized schema with foreign key relationships. All tables include:
- `available` (INTEGER): 1 if item exists in Plex, 0 if removed/unavailable
- `lastSeen` (TEXT): ISO timestamp of last successful sync

## Tables

### `movies`

Primary key: `ratingKey` (INTEGER)

**Required Fields:**
- `ratingKey`: Unique Plex identifier
- `title`: Movie title

**Optional Fields:**
- `year`: Release year (INTEGER)
- `contentRating`: Content rating (TEXT, e.g., "PG-13")
- `duration`: Duration in milliseconds (INTEGER)
- `durationHuman`: Human-readable duration (TEXT, e.g., "120 mins")
- `audioCodec`: Audio codec (TEXT, e.g., "AC3")
- `container`: Container format (TEXT, e.g., "mkv")
- `videoCodec`: Video codec (TEXT, e.g., "h264")
- `videoResolution`: Video resolution (TEXT, e.g., "1080p")
- `sizeBytes`: File size in bytes (INTEGER)
- `sizeHuman`: Human-readable size (TEXT, e.g., "5.2 GB")
- `mediaHash`: SHA256 hash fingerprint for change detection (TEXT)
- `summary`: Movie description/plot (TEXT)
- `tagline`: Movie tagline (TEXT)
- `genres`: Comma-separated genres (TEXT, e.g., "Action, Adventure")
- `studio`: Production studio (TEXT)
- `directors`: Comma-separated director names (TEXT)
- `writers`: Comma-separated writer names (TEXT)
- `producers`: Comma-separated producer names (TEXT)
- `actors`: Comma-separated actors formatted as "Name as Role" (TEXT)
- `originallyAvailableAt`: Original release date ISO format (TEXT)
- `rating`: Rating 0-10 scale (REAL)
- `audienceRating`: Audience rating 0-10 scale (REAL)

**Handling Missing Data:**
- Missing metadata fields are stored as `NULL`
- Empty strings are converted to `NULL` for consistency
- Missing media info (codec, resolution) defaults to `NULL`
- Missing year defaults to `NULL` (not 0)

### `tv_shows`

Primary key: `ratingKey` (INTEGER)

**Required Fields:**
- `ratingKey`: Unique Plex identifier
- `title`: Show title

**Optional Fields:**
- `contentRating`: Content rating (TEXT)
- `avgEpisodeDuration`: Average episode duration in milliseconds (INTEGER)
- `avgEpisodeDurationHuman`: Human-readable average duration (TEXT)
- `seasonCount`: Number of seasons (INTEGER)
- `showTotalEpisode`: Total number of episodes (INTEGER)
- `showSizeBytes`: Total size in bytes (INTEGER)
- `showSizeHuman`: Human-readable total size (TEXT)
- `avgVideoResolutions`: Comma-separated unique resolutions (TEXT)
- `avgAudioCodecs`: Comma-separated unique audio codecs (TEXT)
- `avgVideoCodecs`: Comma-separated unique video codecs (TEXT)
- `avgContainers`: Comma-separated unique containers (TEXT)
- `showYearRange`: Year range (TEXT, e.g., "2020-2023" or "2023")
- `summary`: Show description (TEXT)
- `genres`: Comma-separated genres (TEXT)
- `studio`: Production studio (TEXT)
- `actors`: Comma-separated actors (TEXT)
- `originallyAvailableAt`: Original release date (TEXT)
- `rating`: Rating 0-10 (REAL)
- `audienceRating`: Audience rating 0-10 (REAL)

**Handling Missing Data:**
- Aggregated fields (avg*) may be empty strings if no episodes exist
- Year range defaults to `NULL` if no episodes have years

### `seasons`

Primary key: `seasonRatingKey` (INTEGER)
Foreign key: `showRatingKey` → `tv_shows.ratingKey`

**Required Fields:**
- `seasonRatingKey`: Unique Plex identifier
- `showRatingKey`: Parent show identifier

**Optional Fields:**
- `seasonNumber`: Season number (INTEGER)
- `seasonTotalEpisode`: Number of episodes in season (INTEGER)
- `avgSeasonEpisodeDuration`: Average episode duration (INTEGER)
- `avgSeasonEpisodeDurationHuman`: Human-readable duration (TEXT)
- `seasonSizeBytes`: Total size in bytes (INTEGER)
- `seasonSizeHuman`: Human-readable size (TEXT)
- `avgSeasonVideoResolution`: Comma-separated resolutions (TEXT)
- `avgSeasonAudioCodec`: Comma-separated audio codecs (TEXT)
- `avgSeasonVideoCodec`: Comma-separated video codecs (TEXT)
- `avgSeasonContainer`: Comma-separated containers (TEXT)
- `yearRange`: Year range for season (TEXT)
- `summary`: Season description (TEXT)
- `title`: Season title (TEXT, often null for numbered seasons)
- `originallyAvailableAt`: Original release date (TEXT)

### `episodes`

Primary key: `ratingKey` (INTEGER)
Foreign keys: 
- `seasonRatingKey` → `seasons.seasonRatingKey`
- `showRatingKey` → `tv_shows.ratingKey`

**Required Fields:**
- `ratingKey`: Unique Plex identifier
- `seasonRatingKey`: Parent season identifier
- `showRatingKey`: Parent show identifier
- `title`: Episode title

**Optional Fields:**
- `episodeNumber`: Episode number (INTEGER)
- `year`: Release year (INTEGER)
- `duration`: Duration in milliseconds (INTEGER)
- `durationHuman`: Human-readable duration (TEXT)
- `audioCodec`: Audio codec (TEXT)
- `container`: Container format (TEXT)
- `videoCodec`: Video codec (TEXT)
- `videoResolution`: Video resolution (TEXT)
- `sizeBytes`: File size in bytes (INTEGER)
- `sizeHuman`: Human-readable size (TEXT)
- `mediaHash`: SHA256 hash fingerprint (TEXT)
- `summary`: Episode description (TEXT)
- `originallyAvailableAt`: Original air date (TEXT)
- `directors`: Comma-separated directors (TEXT)
- `writers`: Comma-separated writers (TEXT)
- `actors`: Comma-separated actors (TEXT)
- `rating`: Rating 0-10 (REAL)
- `audienceRating`: Audience rating 0-10 (REAL)

**Handling Missing Data:**
- Episodes without media files are skipped (not inserted)
- Missing episode numbers default to `NULL`

### `artists`

Primary key: `ratingKey` (INTEGER)

**Required Fields:**
- `ratingKey`: Unique Plex identifier
- `artistName`: Artist name

**Optional Fields:**
- `totalAlbums`: Number of albums (INTEGER)
- `totalTracks`: Number of tracks (INTEGER)
- `totalSizeBytes`: Total size in bytes (INTEGER)
- `totalSizeHuman`: Human-readable size (TEXT)
- `yearRange`: Year range (TEXT)
- `summary`: Artist biography (TEXT)
- `genres`: Comma-separated genres (TEXT)

**Handling Missing Data:**
- Counts default to 0 if no albums/tracks
- Summary may be null for artists without biography

### `albums`

Primary key: `ratingKey` (INTEGER)
Foreign key: `artistRatingKey` → `artists.ratingKey`

**Required Fields:**
- `ratingKey`: Unique Plex identifier
- `artistRatingKey`: Parent artist identifier
- `title`: Album title

**Optional Fields:**
- `year`: Release year (INTEGER)
- `tracks`: Number of tracks (INTEGER)
- `albumSizeBytes`: Total size in bytes (INTEGER)
- `albumSizeHuman`: Human-readable size (TEXT)
- `albumDuration`: Total duration in milliseconds (INTEGER)
- `albumDurationHuman`: Human-readable duration (TEXT)
- `albumContainers`: Comma-separated containers (TEXT)
- `summary`: Album description (TEXT)
- `genres`: Comma-separated genres (TEXT)
- `originallyAvailableAt`: Release date (TEXT)
- `studio`: Record label (TEXT)

### `tracks`

Primary key: `ratingKey` (INTEGER)
Foreign keys:
- `albumRatingKey` → `albums.ratingKey`
- `artistRatingKey` → `artists.ratingKey`

**Required Fields:**
- `ratingKey`: Unique Plex identifier
- `albumRatingKey`: Parent album identifier
- `artistRatingKey`: Parent artist identifier
- `title`: Track title

**Optional Fields:**
- `trackNumber`: Track number (INTEGER)
- `duration`: Duration in milliseconds (INTEGER)
- `durationHuman`: Human-readable duration (TEXT)
- `sizeBytes`: File size in bytes (INTEGER)
- `sizeHuman`: Human-readable size (TEXT)
- `container`: Container format (TEXT)
- `mediaHash`: SHA256 hash fingerprint (TEXT)
- `summary`: Track description (TEXT, rarely available)
- `originallyAvailableAt`: Release date (TEXT, rarely available)
- `genres`: Comma-separated genres (TEXT, rarely available)

**Handling Missing Data:**
- Track summaries are almost always null
- Track genres are rarely populated (usually inherit from album)

## Virtual Tables

### `search_fts`

FTS5 virtual table for fast full-text search (optional, created if FTS5 is available).

**Columns:**
- `type`: Media type ('movie', 'show', 'artist')
- `ratingKey`: Reference to original table
- `title`: Searchable title
- `summary`: Searchable summary
- `year`: Year (unindexed)
- `available`: Availability flag (unindexed)

**Usage:**
- Automatically populated during sync
- Updated when items are inserted/updated
- Used by backend search endpoint for fast queries

## Data Types

- **INTEGER**: Whole numbers (ratingKey, year, duration, sizeBytes, counts)
- **REAL**: Floating point numbers (ratings 0-10)
- **TEXT**: Strings (titles, descriptions, CSV lists, ISO dates)
- **NULL**: Missing/unknown values

## Constraints

- **Primary Keys**: All tables use `ratingKey` (or variant) as primary key
- **Foreign Keys**: Enforced with `PRAGMA foreign_keys = ON`
- **Cascade Deletes**: Foreign keys use `ON DELETE CASCADE`
- **Availability**: Items marked `available = 0` are excluded from normal queries

## Indexes

Standard indexes on:
- Foreign key columns
- `available` flags
- `mediaHash` columns (for change detection)

FTS5 index (if available):
- `search_fts` virtual table for full-text search

## Migration System

Schema changes are managed through migrations:
- Version 1: Added `mediaHash` columns
- Version 2: Added extended metadata columns
- Version 3: Added FTS5 search index

Migrations run automatically on database initialization.

## Notes

- All timestamps use ISO 8601 format (TEXT)
- CSV fields use comma-space separator (", ")
- Actors formatted as "Name as Role" (role optional)
- Human-readable sizes use appropriate units (MB, GB, TB)
- Human-readable durations use hours/minutes format
- Year ranges format as "YYYY" or "YYYY-YYYY"

