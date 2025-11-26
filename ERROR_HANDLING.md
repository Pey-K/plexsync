# Error Handling & Robustness

This document describes how the project handles errors, edge cases, and failure scenarios.

## Error Handling Strategy

### Python Sync Script

#### Plex API Failures

**Connection Errors:**
- Retry logic with exponential backoff (3 attempts)
- Waits: 5s, 10s, 15s between retries
- Logs warnings but continues processing other libraries
- Example: `requests.exceptions.Timeout`, `requests.exceptions.ConnectionError`

**Missing Media:**
- Items without media files are skipped (not inserted)
- Logs: `"Skipping movie 'X': no media found"`
- Continues processing remaining items

**Invalid Rating Keys:**
- Validates `ratingKey` is integer
- Raises `ValueError` if invalid
- Caught and logged, item skipped

**Image Download Failures:**
- Individual image failures don't stop sync
- Tracks success/failure counts
- Logs warnings for failed downloads
- Continues with remaining images

#### Database Errors

**Schema Migration Failures:**
- Checks for duplicate columns before adding
- Logs warnings for expected errors (e.g., column already exists)
- Continues with other migrations

**Foreign Key Violations:**
- Foreign keys enabled with `PRAGMA foreign_keys = ON`
- Cascading deletes prevent orphaned records
- Transaction rollback on constraint violations

**Database Locks:**
- SQLite handles concurrent reads (read-only mode in backend)
- Write operations are sequential (sync script)
- No explicit lock handling (single-writer assumption)

#### Partial Writes

**Transaction Safety:**
- Each library processed in separate transaction
- `conn.commit()` after each library
- If sync fails mid-library, previous libraries remain committed

**Batch Inserts:**
- Uses `executemany()` for atomic batch operations
- All-or-nothing for each batch
- Failed batches logged, sync continues

### Node.js Backend

#### Plex API Failures

**Connection Errors:**
- 10-second timeout per request
- Automatic fallback to SQLite on any error
- Logs warnings: `"Plex API failed, falling back to SQLite"`
- Response includes `fallback: true` flag

**Timeout Handling:**
- Uses `AbortController` for request cancellation
- Throws timeout error, triggers fallback
- No retry logic (relies on SQLite fallback)

**XML Parsing Errors:**
- Tries JSON first, falls back to XML parsing
- XML parsing errors trigger SQLite fallback
- Logs parsing errors

#### SQLite Fallback

**Database Not Found:**
- Checks `isConnected()` before queries
- Returns empty arrays/null if not connected
- Logs connection errors on initialization

**Query Errors:**
- All queries wrapped in try-catch
- Returns empty results on error
- Logs errors: `"SQLite error (getMovies): ..."`

**Read-Only Mode:**
- Database opened in read-only mode
- Prevents accidental writes
- Safe for concurrent reads

## Edge Cases

### Missing Metadata

**Handling:**
- All optional fields default to `NULL`
- Empty strings converted to `NULL`
- Missing years default to `NULL` (not 0)
- Missing codecs/resolutions default to `NULL`

**Examples:**
- Movie without tagline → `tagline = NULL`
- Episode without summary → `summary = NULL`
- Track without genres → `genres = NULL`

### Special Characters

**Handling:**
- UTF-8 encoding throughout
- SQLite handles Unicode natively
- No special escaping needed for titles/summaries
- CSV fields use comma-space separator

### Multiple Codecs/Resolutions

**Handling:**
- Aggregated as comma-separated values
- Unique values only (sorted)
- Example: `"1080p, 720p"` or `"h264, hevc"`

### Missing Thumbnails

**Handling:**
- Image download failures logged but don't stop sync
- Missing images don't prevent item insertion
- Image stats tracked separately

### Large Libraries

**Performance:**
- Server-side pagination (no loading all items)
- Batch inserts with `executemany()`
- Parallel image downloads (optional)
- FTS5 search index for fast queries
- Response caching (5-minute TTL)

**Memory:**
- Processes items in batches
- Doesn't load entire library into memory
- Streaming approach for large datasets

### Concurrent Access

**Sync Script:**
- Single-writer assumption
- Not designed for concurrent writes
- Use file locks if needed

**Backend:**
- Read-only SQLite access
- Safe for concurrent reads
- No write operations

## Failure Recovery

### Sync Script Failures

**Partial Sync:**
- Previous libraries remain in database
- Failed library can be re-synced
- Use `--rebuild-db` to start fresh

**Database Corruption:**
- SQLite is resilient to crashes
- Use `VACUUM` to recover space
- `--rebuild-db` recreates from scratch

### Backend Failures

**Plex Unavailable:**
- Automatic fallback to SQLite
- Site remains functional
- No user-visible errors

**SQLite Unavailable:**
- Returns empty results
- Logs errors
- Health endpoint shows status

## Logging

### Log Levels

- **DEBUG**: Detailed information (verbose mode)
- **INFO**: Normal operations
- **WARNING**: Recoverable issues (fallbacks, missing data)
- **ERROR**: Failures that prevent operation

### Log Output

- Console output (default)
- Optional file logging (`--log-file`)
- Structured format with timestamps

## Monitoring

### Health Check Endpoint

```bash
GET /health
```

Returns:
```json
{
  "status": "ok",
  "plex": true,
  "sqlite": true
}
```

### Response Metadata

All API responses include:
- `source`: "plex" or "sqlite"
- `fallback`: true if using fallback
- `total`: Total count (when applicable)

## Best Practices

1. **Run sync regularly**: Keep SQLite fresh (cron every 6-24h)
2. **Monitor logs**: Check for repeated failures
3. **Test fallback**: Disable Plex to verify SQLite works
4. **Backup database**: SQLite files are easily backed up
5. **Version control**: Track schema migrations

## Troubleshooting

### Common Issues

**"Plex API failed"**
- Check PLEX_URL and PLEX_TOKEN
- Verify Plex server is accessible
- Check network connectivity
- Backend will fallback to SQLite automatically

**"SQLite error"**
- Verify database file exists
- Check file permissions
- Ensure database isn't corrupted
- Run sync script to recreate

**"No results returned"**
- Check if items are marked `available = 1`
- Verify library names in PLEX_LIBRARY_NAMES
- Check sync script ran successfully
- Review logs for errors

**"Image download failed"**
- Check Plex server accessibility
- Verify image folder permissions
- Check disk space
- Images are optional, sync continues

