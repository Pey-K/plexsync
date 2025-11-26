# Plex Collection Backend API

Live-first Node.js backend with automatic SQLite fallback for Plex media collection.

## 🚀 Features

- **Live-first architecture**: Primary data source is direct Plex API calls
- **Automatic fallback**: Falls back to SQLite database if Plex is unreachable
- **Full API coverage**: Movies, TV Shows, Seasons, Episodes, Artists, Albums, Tracks
- **Search & Recent**: Full-text search and recently added items
- **Zero downtime**: Site stays functional even when Plex is down

## 📦 Installation

```bash
npm install
```

## ⚙️ Configuration

The backend uses the same `.env` file as the Python sync script:

```env
PLEX_URL=http://your-plex-ip:32400
PLEX_TOKEN=YOURTOKENHERE
DB_PATH=./data/plex_collection.db
PORT=3000
LIVE_FIRST=true  # Set to 'false' to force SQLite-only mode
```

### Environment Variables

- `PLEX_URL` - Your Plex server URL (required for live mode)
- `PLEX_TOKEN` - Your Plex authentication token (required for live mode)
- `DB_PATH` - Path to SQLite database (default: `./data/plex_collection.db`)
- `PORT` - Server port (default: `3000`)
- `LIVE_FIRST` - Enable/disable live-first mode (default: `true`, set to `false` to force SQLite-only)

## 🏃 Running

```bash
# Production
npm start

# Development (with auto-reload)
npm run dev
```

The server will start on `http://localhost:3000` (or your configured PORT).

## 📡 API Endpoints

### Movies

- `GET /api/movies` - Get all movies (with pagination: `?limit=100&offset=0`)
- `GET /api/movies/:ratingKey` - Get single movie

### TV Shows

- `GET /api/shows` - Get all shows
- `GET /api/shows/:ratingKey` - Get single show
- `GET /api/shows/:ratingKey/seasons` - Get seasons for a show
- `GET /api/shows/seasons/:seasonRatingKey` - Get single season
- `GET /api/shows/seasons/:seasonRatingKey/episodes` - Get episodes for a season
- `GET /api/shows/episodes/:ratingKey` - Get single episode

### Music

- `GET /api/music/artists` - Get all artists
- `GET /api/music/artists/:ratingKey` - Get single artist
- `GET /api/music/artists/:ratingKey/albums` - Get albums for an artist
- `GET /api/music/albums/:ratingKey` - Get single album
- `GET /api/music/albums/:ratingKey/tracks` - Get tracks for an album
- `GET /api/music/tracks/:ratingKey` - Get single track

### Search

- `GET /api/search?q=query` - Search across all media types

### Recently Added

- `GET /api/recent?limit=20` - Get recently added items

### Health Check

- `GET /health` - Check server and service status

## 🔄 How It Works

1. **Primary**: Every request first tries to fetch live data from Plex API
2. **Fallback**: If Plex is unreachable, times out, or errors → automatically uses SQLite
3. **Response**: Includes `source: 'plex'` or `source: 'sqlite'` and `fallback: true` flag
4. **Caching**: Live Plex responses are cached for 5 minutes to reduce API load
5. **Pagination**: Server-side pagination via Plex API (no more loading 2000+ items at once!)

### Example Response

```json
{
  "data": [...],
  "total": 150,
  "source": "plex"  // or "sqlite"
}
```

When using fallback:

```json
{
  "data": [...],
  "total": 150,
  "source": "sqlite",
  "fallback": true
}
```

## 🗄️ Database Sync

Keep your SQLite database fresh by running the Python sync script:

```bash
# Manual sync
python plex_sync.py

# Or set up a cron job (every 6-24 hours)
0 */6 * * * cd /path/to/project && python plex_sync.py
```

## 🛠️ Development

The backend is built with:

- **Express.js** - Web framework
- **plex-api** - Plex HTTP API client
- **better-sqlite3** - Fast SQLite driver
- **dotenv** - Environment variable management

## 📝 Notes

- The SQLite database is opened in **read-only mode** for safety
- All Plex API calls have a 10-second timeout
- Fallback is automatic and transparent to clients
- The backend transforms Plex API responses to match your database schema
- **Server-side pagination**: Plex API pagination is used natively (no client-side slicing)
- **Caching**: Live responses cached for 5 minutes to reduce API load
- **Global recent**: Uses Plex's `/library/recentlyAdded` endpoint (faster than per-library)
- **Live-first toggle**: Set `LIVE_FIRST=false` in `.env` to force SQLite-only mode

## 🔍 Troubleshooting

### Plex API not working

Check your `.env` file has correct `PLEX_URL` and `PLEX_TOKEN`. The backend will automatically fall back to SQLite.

### SQLite not found

Ensure `plex_sync.py` has been run at least once to create the database.

### Port already in use

Change the `PORT` in `.env` or use a different port:

```bash
PORT=3001 npm start
```

