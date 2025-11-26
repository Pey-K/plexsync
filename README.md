# Plex Collection Sync

A production-ready **Plex library synchronization engine** with live-first Node.js backend and SQLite fallback. Extracts, normalizes, and stores complete media metadata from your Plex server.

## 🚀 Quick Start

### Prerequisites

- Python 3.9+ (for sync script)
- Node.js 18+ (for backend API)
- Access to a Plex Media Server

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/Pey-K/plexsync.git
   cd plexsync
   ```

2. **Set up Python environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Set up Node.js environment**
   ```bash
   npm install
   ```

4. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your Plex credentials
   ```

5. **Run initial sync**
   ```bash
   python plex_sync.py
   ```

6. **Start backend server**
   ```bash
   npm start
   ```

The API will be available at `http://localhost:3000`

### Docker Setup (Alternative)

```bash
docker-compose up -d
```

This will:
- Run the sync script once
- Start the backend API server
- Mount data and assets directories

## 📖 What This Project Does

This tool provides an organized, API-like view of your Plex libraries:
- **Movies**: Full metadata, codecs, sizes, cast, crew, ratings
- **TV Shows**: Shows, seasons, episodes with complete hierarchies
- **Music**: Artists, albums, tracks with full metadata

**Key Features:**
- Live-first architecture: Direct Plex API with automatic SQLite fallback
- Complete metadata extraction (genres, actors, directors, ratings, etc.)
- WebP thumbnail conversion and storage
- Fast full-text search (FTS5)
- Server-side pagination
- Response caching
- Automatic schema migrations
- Production-ready error handling

**Ideal for:**
- Personal dashboards
- Plex statistics sites
- Local metadata exploration
- Analytics tools
- Custom media browsers

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

## 📚 Documentation

- **[Backend API Documentation](README_BACKEND.md)** - Complete API reference
- **[Database Schema](SCHEMA.md)** - Detailed schema documentation
- **[Contributing Guidelines](CONTRIBUTING.md)** - How to contribute
- **[Changelog](CHANGELOG.md)** - Version history

## ⚙️ Requirements

### Python Dependencies

    pip install -r requirements.txt

### Node.js Dependencies

    npm install

### Environment Variables

See `.env.example` for required variables:
- `PLEX_URL`: Your Plex server URL
- `PLEX_TOKEN`: Your Plex authentication token
- `PLEX_LIBRARY_NAMES`: Comma-separated library names
- `DB_PATH`: Path to SQLite database
- `PORT`: Backend server port (default: 3000)
- `LIVE_FIRST`: Enable/disable live-first mode (default: true)

------------------------------------------------------------------------

## 🔍 Example Usage

### Python Sync Script

```bash
# Basic sync
python plex_sync.py

# Fast parallel mode (default)
python plex_sync.py --fast

# Skip images
python plex_sync.py --no-images

# Verbose logging
python plex_sync.py --verbose

# Rebuild database
python plex_sync.py --rebuild-db
```

### Backend API

```bash
# Start server
npm start

# Development mode with auto-reload
npm run dev
```

### API Examples

```bash
# Get all movies (paginated)
curl http://localhost:3000/api/movies?limit=50&offset=0

# Get single movie
curl http://localhost:3000/api/movies/12345

# Get TV show with seasons
curl http://localhost:3000/api/shows/67890/seasons

# Search
curl http://localhost:3000/api/search?q=matrix

# Recently added
curl http://localhost:3000/api/recent?limit=20

# Health check
curl http://localhost:3000/health
```

See [Backend API Documentation](README_BACKEND.md) for complete API reference.

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

# 🧪 Testing

Currently, manual testing is recommended. Future test suite will include:

- Unit tests for utility functions
- Integration tests for database operations
- API endpoint tests
- Error handling tests

To test manually:

```bash
# Test sync script
python plex_sync.py --verbose

# Test backend API
npm start
curl http://localhost:3000/health
curl http://localhost:3000/api/movies?limit=10
```

# 🐳 Docker

See `docker-compose.yml` for containerized setup:

```bash
docker-compose up -d
```

This runs both sync and backend services with proper volume mounts.

# 🪟 Windows One-Click Setup

For Windows users who want a simple solution:

**Option 1: Batch File**
- Create your `.env` file
- Double-click `start.bat`
- Done! The script handles everything automatically

**Option 2: GUI Launcher**
- Create your `.env` file
- Run `python launcher.py` or use the pre-built `PlexSyncLauncher.exe`
- Click "Start Sync & Server" button
- Full GUI with logs and controls

See [Windows Setup Guide](README_WINDOWS.md) for detailed instructions.

# 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

# 🤝 Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

# 📚 Additional Documentation

- [Backend API Documentation](README_BACKEND.md) - Complete API reference
- [Database Schema](SCHEMA.md) - Detailed schema documentation
- [Error Handling](ERROR_HANDLING.md) - Error handling and robustness
- [Contributing Guidelines](CONTRIBUTING.md) - How to contribute
- [Changelog](CHANGELOG.md) - Version history

# 🎉 Final Notes

This project is designed as a **production-ready Plex metadata engine**, suitable
for dashboards, analytics, and custom apps. It provides both a Python sync tool
and a Node.js API backend with automatic fallback for maximum reliability.
