# Plex Sync Engine -- SQLite Metadata Indexer

This project is a **full Plex library synchronization engine** designed
to extract, normalize, and store media metadata into a clean,
query-friendly **SQLite database**.\
It provides an organized, API-like view of your Plex libraries ---
movies, TV shows, seasons, episodes, artists, albums, and tracks ---
with thumbnails, codecs, durations, file sizes, and full metadata.

This tool is ideal for:

-   Personal dashboards\
-   Plex statistics sites\
-   Local metadata exploration\
-   Analytics tools\
-   Integration into apps like PyWebView or custom media browsers

------------------------------------------------------------------------

# ✨ Features

## 🔍 Deep Plex Metadata Extraction

Pulls every important field Plex exposes:

-   Titles, years, content ratings\
-   Duration, codec, resolution\
-   Genres, summaries, taglines\
-   Studios, writers, directors, producers\
-   Actors (formatted like "Actor as Character")\
-   Release dates\
-   Ratings + Audience Ratings\
-   Episode numbering\
-   Music metadata (artists, albums, tracks)

## 📦 Clean SQLite Database

Fully normalized schema with:

-   `movies`
-   `tv_shows`
-   `seasons`
-   `episodes`
-   `artists`
-   `albums`
-   `tracks`

Includes:

-   Human-readable sizes & durations\
-   Media hash fingerprints\
-   Availability tracking\
-   Automatic schema migrations\
-   Cascading foreign keys

## 🖼 WebP Thumbnail Downloading

Downloads Plex thumbnails and stores them in organized folders:

    assets/images/movie_image/
    assets/images/tv_image/
    assets/images/music_image/

All images are down-converted to **WebP** for small size and fast
loading.

## ⚡ Fast Parallel Sync Engine

Uses a thread pool to:

-   Download thumbnails in parallel\
-   Reduce API latency\
-   Survive Plex API timeouts with retry logic

Syncing large libraries becomes dramatically faster.

------------------------------------------------------------------------

# 📁 Folder Structure

    project/
    │── plex_sync.py
    │── .env
    │── data/
    │   └── plex_collection.db
    └── assets/
        └── images/
            ├── movie_image/
            ├── tv_image/
            └── music_image/

------------------------------------------------------------------------

# ⚙️ Requirements

Install all dependencies with:

    pip install -r requirements.txt

------------------------------------------------------------------------

# 🔐 Environment Variables

Create a `.env` file:

    PLEX_URL=http://your-plex-ip:32400
    PLEX_TOKEN=YOURTOKENHERE
    PLEX_LIBRARY_NAMES=Movies,TV Shows,Music
    DB_PATH=./data/plex_collection.db

------------------------------------------------------------------------

# 🚀 Running the Sync

Basic run:

    python plex_sync.py

Fast parallel mode (default):

    python plex_sync.py --fast

Turn off parallelization:

    python plex_sync.py --no-parallel

Skip downloading images:

    python plex_sync.py --no-images

Verbose debug mode:

    python plex_sync.py --verbose

Rebuild the database from scratch:

    python plex_sync.py --rebuild-db

------------------------------------------------------------------------

# 🧠 How the Sync Engine Works

1.  Connects to your Plex server using `PLEX_URL` + `PLEX_TOKEN`\
2.  Loads the SQLite database\
3.  Applies schema migrations (automatically)\
4.  For each library in `PLEX_LIBRARY_NAMES`:
    -   Fetch items (movies / shows / artists)
    -   Extract full metadata
    -   Compute a **mediaHash** fingerprint (to detect changes)
    -   Insert or update entries in SQLite
    -   Mark missing items as `available = 0`
    -   Download/convert thumbnails

The result is a mirror of your Plex metadata in a structured
SQL database.

------------------------------------------------------------------------

# 🧩 Database Schema

This is a simplified, readable overview (fields trimmed to essentials).

------------------------------------------------------------------------

## `movies`

-   ratingKey (primary key)\
-   title, year\
-   duration / durationHuman\
-   sizeBytes / sizeHuman\
-   audioCodec, videoCodec, videoResolution\
-   genres, studio, writers, directors, actors\
-   summary, tagline\
-   originallyAvailableAt\
-   rating, audienceRating\
-   mediaHash\
-   available\
-   lastSeen

------------------------------------------------------------------------

## `tv_shows`

-   ratingKey (primary key)\
-   title\
-   avgEpisodeDuration\
-   seasonCount\
-   totalEpisodes\
-   totalSizeBytes\
-   avgVideoResolutions\
-   avgAudioCodecs\
-   actors\
-   summary, genres, studio\
-   timestamps

------------------------------------------------------------------------

## `seasons`

-   seasonRatingKey (primary key)\
-   showRatingKey (FK)\
-   seasonNumber\
-   seasonTotalEpisode\
-   avgSeasonEpisodeDuration\
-   seasonSizeBytes\
-   yearRange

------------------------------------------------------------------------

## `episodes`

-   ratingKey (primary key)\
-   seasonRatingKey (FK)\
-   showRatingKey (FK)\
-   episodeNumber\
-   title, year\
-   duration / durationHuman\
-   codecs, resolution\
-   sizeBytes / sizeHuman\
-   directors / writers / actors\
-   rating / audienceRating\
-   summary\
-   originallyAvailableAt\
-   mediaHash

------------------------------------------------------------------------

## `artists`

-   ratingKey\
-   artistName\
-   totalAlbums\
-   totalTracks\
-   totalSizeBytes\
-   yearRange\
-   summary / genres

------------------------------------------------------------------------

## `albums`

-   ratingKey\
-   artistRatingKey\
-   title, year\
-   tracks\
-   albumSizeBytes\
-   albumDuration\
-   albumContainers\
-   summary

------------------------------------------------------------------------

## `tracks`

-   ratingKey\
-   albumRatingKey\
-   artistRatingKey\
-   title, trackNumber\
-   duration / durationHuman\
-   sizeBytes / sizeHuman\
-   container\
-   mediaHash\
-   summary\
-   originallyAvailableAt\
-   genres

------------------------------------------------------------------------

# 🔍 How Media Hashing Works

The script builds a fingerprint using:

    size | duration | codec | resolution | container | title | year

If nothing changed → item is skipped.

This dramatically speeds up re-syncs.

------------------------------------------------------------------------

# 🌐 Image Handling

Images are downloaded via Plex's thumbnail endpoints and converted to
WebP:

    {ratingKey}.thumb.webp

Stored separately for movies, TV, and music.

------------------------------------------------------------------------

# 🛠 Troubleshooting

### Timeout fetching items

Try `--no-parallel`.

### Nothing shows up in DB

Check `.env` variables and library names.

------------------------------------------------------------------------

# 🎉 Final Notes

This project is designed as a **Plex-level metadata engine**, suitable
for dashboards, analytics, and custom apps.
