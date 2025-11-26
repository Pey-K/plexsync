import Database from 'better-sqlite3';

export class SqliteService {
  constructor(dbPath) {
    try {
      this.db = new Database(dbPath, { readonly: true });
      this.connected = true;
      console.log(`✅ Connected to SQLite database: ${dbPath}`);
    } catch (error) {
      console.error(`❌ Failed to connect to SQLite: ${error.message}`);
      this.connected = false;
      this.db = null;
    }
  }

  isConnected() {
    return this.connected && this.db !== null;
  }

  // Movies
  getMovies(limit = 100, offset = 0) {
    if (!this.isConnected()) return [];
    try {
      return this.db.prepare(`
        SELECT * FROM movies 
        WHERE available = 1 
        ORDER BY title 
        LIMIT ? OFFSET ?
      `).all(limit, offset);
    } catch (error) {
      console.error('SQLite error (getMovies):', error.message);
      return [];
    }
  }

  getMovie(ratingKey) {
    if (!this.isConnected()) return null;
    try {
      return this.db.prepare('SELECT * FROM movies WHERE ratingKey = ? AND available = 1').get(ratingKey);
    } catch (error) {
      console.error('SQLite error (getMovie):', error.message);
      return null;
    }
  }

  // TV Shows
  getShows(limit = 100, offset = 0) {
    if (!this.isConnected()) return [];
    try {
      return this.db.prepare(`
        SELECT * FROM tv_shows 
        WHERE available = 1 
        ORDER BY title 
        LIMIT ? OFFSET ?
      `).all(limit, offset);
    } catch (error) {
      console.error('SQLite error (getShows):', error.message);
      return [];
    }
  }

  getShow(ratingKey) {
    if (!this.isConnected()) return null;
    try {
      return this.db.prepare('SELECT * FROM tv_shows WHERE ratingKey = ? AND available = 1').get(ratingKey);
    } catch (error) {
      console.error('SQLite error (getShow):', error.message);
      return null;
    }
  }

  getSeasons(showRatingKey) {
    if (!this.isConnected()) return [];
    try {
      return this.db.prepare(`
        SELECT * FROM seasons 
        WHERE showRatingKey = ? AND available = 1 
        ORDER BY seasonNumber
      `).all(showRatingKey);
    } catch (error) {
      console.error('SQLite error (getSeasons):', error.message);
      return [];
    }
  }

  getSeason(seasonRatingKey) {
    if (!this.isConnected()) return null;
    try {
      return this.db.prepare('SELECT * FROM seasons WHERE seasonRatingKey = ? AND available = 1').get(seasonRatingKey);
    } catch (error) {
      console.error('SQLite error (getSeason):', error.message);
      return null;
    }
  }

  getEpisodes(seasonRatingKey) {
    if (!this.isConnected()) return [];
    try {
      return this.db.prepare(`
        SELECT * FROM episodes 
        WHERE seasonRatingKey = ? AND available = 1 
        ORDER BY episodeNumber
      `).all(seasonRatingKey);
    } catch (error) {
      console.error('SQLite error (getEpisodes):', error.message);
      return [];
    }
  }

  getEpisode(ratingKey) {
    if (!this.isConnected()) return null;
    try {
      return this.db.prepare('SELECT * FROM episodes WHERE ratingKey = ? AND available = 1').get(ratingKey);
    } catch (error) {
      console.error('SQLite error (getEpisode):', error.message);
      return null;
    }
  }

  // Music
  getArtists(limit = 100, offset = 0) {
    if (!this.isConnected()) return [];
    try {
      return this.db.prepare(`
        SELECT * FROM artists 
        WHERE available = 1 
        ORDER BY artistName 
        LIMIT ? OFFSET ?
      `).all(limit, offset);
    } catch (error) {
      console.error('SQLite error (getArtists):', error.message);
      return [];
    }
  }

  getArtist(ratingKey) {
    if (!this.isConnected()) return null;
    try {
      return this.db.prepare('SELECT * FROM artists WHERE ratingKey = ? AND available = 1').get(ratingKey);
    } catch (error) {
      console.error('SQLite error (getArtist):', error.message);
      return null;
    }
  }

  getAlbums(artistRatingKey) {
    if (!this.isConnected()) return [];
    try {
      return this.db.prepare(`
        SELECT * FROM albums 
        WHERE artistRatingKey = ? AND available = 1 
        ORDER BY year, title
      `).all(artistRatingKey);
    } catch (error) {
      console.error('SQLite error (getAlbums):', error.message);
      return [];
    }
  }

  getAlbum(ratingKey) {
    if (!this.isConnected()) return null;
    try {
      return this.db.prepare('SELECT * FROM albums WHERE ratingKey = ? AND available = 1').get(ratingKey);
    } catch (error) {
      console.error('SQLite error (getAlbum):', error.message);
      return null;
    }
  }

  getTracks(albumRatingKey) {
    if (!this.isConnected()) return [];
    try {
      return this.db.prepare(`
        SELECT * FROM tracks 
        WHERE albumRatingKey = ? AND available = 1 
        ORDER BY trackNumber
      `).all(albumRatingKey);
    } catch (error) {
      console.error('SQLite error (getTracks):', error.message);
      return [];
    }
  }

  getTrack(ratingKey) {
    if (!this.isConnected()) return null;
    try {
      return this.db.prepare('SELECT * FROM tracks WHERE ratingKey = ? AND available = 1').get(ratingKey);
    } catch (error) {
      console.error('SQLite error (getTrack):', error.message);
      return null;
    }
  }

  // Search with FTS5 optimization (falls back to LIKE if FTS5 not available)
  search(query, limit = 50) {
    if (!this.isConnected()) return [];
    const searchTerm = `%${query}%`;
    const ftsQuery = query.trim().replace(/\s+/g, ' OR ');
    
    try {
      // Try FTS5 first (much faster for large datasets)
      try {
        // Check if FTS5 search table exists
        const ftsCheck = this.db.prepare(`
          SELECT name FROM sqlite_master 
          WHERE type='table' AND name='search_fts'
        `).get();
        
        if (ftsCheck) {
          // Use FTS5 for fast full-text search
          const results = this.db.prepare(`
            SELECT type, ratingKey, title, year, summary
            FROM search_fts
            WHERE search_fts MATCH ? AND available = 1
            ORDER BY rank
            LIMIT ?
          `).all(ftsQuery, limit);
          
          if (results.length > 0) {
            return results;
          }
        }
      } catch (ftsError) {
        // FTS5 not available or table doesn't exist, fall back to LIKE
        console.debug('FTS5 search not available, using LIKE fallback');
      }
      
      // Fallback to LIKE search (original implementation)
      const movies = this.db.prepare(`
        SELECT 'movie' as type, ratingKey, title, year, summary 
        FROM movies 
        WHERE available = 1 AND (title LIKE ? OR summary LIKE ?)
        LIMIT ?
      `).all(searchTerm, searchTerm, limit);
      
      const shows = this.db.prepare(`
        SELECT 'show' as type, ratingKey, title, NULL as year, summary 
        FROM tv_shows 
        WHERE available = 1 AND (title LIKE ? OR summary LIKE ?)
        LIMIT ?
      `).all(searchTerm, searchTerm, limit);
      
      const artists = this.db.prepare(`
        SELECT 'artist' as type, ratingKey, artistName as title, NULL as year, summary 
        FROM artists 
        WHERE available = 1 AND (artistName LIKE ? OR summary LIKE ?)
        LIMIT ?
      `).all(searchTerm, searchTerm, limit);
      
      return [...movies, ...shows, ...artists].slice(0, limit);
    } catch (error) {
      console.error('SQLite error (search):', error.message);
      return [];
    }
  }

  // Recently added (from lastSeen)
  getRecentlyAdded(limit = 20) {
    if (!this.isConnected()) return [];
    try {
      const movies = this.db.prepare(`
        SELECT 'movie' as type, ratingKey, title, year, lastSeen 
        FROM movies 
        WHERE available = 1 
        ORDER BY lastSeen DESC 
        LIMIT ?
      `).all(limit);
      
      const shows = this.db.prepare(`
        SELECT 'show' as type, ratingKey, title, NULL as year, lastSeen 
        FROM tv_shows 
        WHERE available = 1 
        ORDER BY lastSeen DESC 
        LIMIT ?
      `).all(limit);
      
      const artists = this.db.prepare(`
        SELECT 'artist' as type, ratingKey, artistName as title, NULL as year, lastSeen 
        FROM artists 
        WHERE available = 1 
        ORDER BY lastSeen DESC 
        LIMIT ?
      `).all(limit);
      
      return [...movies, ...shows, ...artists]
        .sort((a, b) => new Date(b.lastSeen) - new Date(a.lastSeen))
        .slice(0, limit);
    } catch (error) {
      console.error('SQLite error (getRecentlyAdded):', error.message);
      return [];
    }
  }
}

