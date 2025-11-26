import { parseStringPromise } from 'xml2js';
import NodeCache from 'node-cache';

export class PlexService {
  constructor(plexUrl, plexToken) {
    this.plexUrl = plexUrl?.replace(/\/$/, ''); // Remove trailing slash
    this.plexToken = plexToken;
    this.connected = false;
    this.liveFirst = process.env.LIVE_FIRST !== 'false'; // Default to true, can disable with LIVE_FIRST=false
    
    // Cache layer: 5 minute TTL for live hits
    this.cache = new NodeCache({ stdTTL: 300, checkperiod: 60 });
    
    if (plexUrl && plexToken) {
      this.connected = true;
      console.log(`✅ Plex client initialized: ${this.plexUrl} (live-first: ${this.liveFirst}, cache: enabled)`);
    } else {
      console.warn('⚠️  Plex URL or token not configured, API will be unavailable');
    }
  }

  isConnected() {
    return this.connected && this.liveFirst && this.plexUrl && this.plexToken;
  }

  async query(endpoint, params = {}) {
    if (!this.isConnected()) {
      throw new Error('Plex client not initialized');
    }

    // Create cache key from endpoint and params
    const cacheKey = `${endpoint}:${JSON.stringify(params)}`;
    
    // Check cache first
    const cached = this.cache.get(cacheKey);
    if (cached) {
      return cached;
    }

    try {
      const url = new URL(`${this.plexUrl}${endpoint}`);
      url.searchParams.set('X-Plex-Token', this.plexToken);
      
      // Add any additional query parameters
      Object.entries(params).forEach(([key, value]) => {
        if (key !== 'X-Plex-Token') {
          url.searchParams.set(key, value.toString());
        }
      });

      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 10000);

      const response = await fetch(url.toString(), {
        signal: controller.signal,
        headers: {
          'Accept': 'application/json'
        }
      });

      clearTimeout(timeoutId);

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      // Plex API returns XML by default
      const text = await response.text();
      
      let result;
      // Try to parse as JSON first (if Accept: application/json was honored)
      try {
        result = JSON.parse(text);
      } catch {
        // Parse as XML
        try {
          result = await parseStringPromise(text, {
            explicitArray: false,
            mergeAttrs: true,
            explicitCharkey: false,
            trim: true
          });
        } catch (xmlError) {
          throw new Error(`Failed to parse Plex response: ${xmlError.message}`);
        }
      }
      
      // Cache the result
      this.cache.set(cacheKey, result);
      
      return result;
    } catch (error) {
      if (error.name === 'AbortError') {
        throw new Error('Plex API request timeout');
      }
      console.error(`Plex API error (${endpoint}):`, error.message);
      throw error;
    }
  }

  async getLibraries() {
    const response = await this.query('/library/sections');
    // Plex returns XML, but we need to handle it
    // For now, return a structure that matches what routes expect
    return this.parsePlexResponse(response);
  }

  async getLibraryItems(sectionKey, params = {}) {
    const defaultParams = {
      'X-Plex-Container-Start': params.offset || 0,
      'X-Plex-Container-Size': params.limit || 100
    };
    const endpoint = `/library/sections/${sectionKey}/all`;
    const response = await this.query(endpoint, defaultParams);
    return this.parsePlexResponse(response);
  }

  async getMetadata(ratingKey) {
    const response = await this.query(`/library/metadata/${ratingKey}`);
    return this.parsePlexResponse(response);
  }

  async getChildren(ratingKey) {
    const response = await this.query(`/library/metadata/${ratingKey}/children`);
    return this.parsePlexResponse(response);
  }

  async search(query) {
    const response = await this.query('/search', { query });
    return this.parsePlexResponse(response);
  }

  async getRecentlyAdded(sectionKey, count = 10) {
    const response = await this.query(`/library/sections/${sectionKey}/recentlyAdded`, {
      'X-Plex-Container-Size': count.toString()
    });
    return this.parsePlexResponse(response);
  }

  async getGlobalRecentlyAdded(count = 20) {
    const response = await this.query('/library/recentlyAdded', {
      'X-Plex-Container-Size': count.toString()
    });
    return this.parsePlexResponse(response);
  }

  // Helper to normalize Plex XML/JSON responses to consistent structure
  parsePlexResponse(data) {
    // Handle XML structure from xml2js
    if (data && data.MediaContainer) {
      return data;
    }
    
    // If it's already in the right format, return it
    return data;
  }

  // Transform Plex API response to match our database schema
  transformMovie(plexItem) {
    // Handle both XML (array) and object structures
    const media = Array.isArray(plexItem.Media) ? plexItem.Media[0] : plexItem.Media;
    const part = media && (Array.isArray(media.Part) ? media.Part[0] : media.Part);
    
    return {
      ratingKey: parseInt(plexItem.ratingKey || plexItem.$.ratingKey),
      title: plexItem.title || plexItem.$.title,
      year: plexItem.year ? parseInt(plexItem.year) : null,
      contentRating: plexItem.contentRating || plexItem.$.contentRating || null,
      duration: plexItem.duration ? parseInt(plexItem.duration) : null,
      durationHuman: this.formatDuration(plexItem.duration),
      audioCodec: part?.audioCodec || part?.$.audioCodec || null,
      container: part?.container || part?.$.container || null,
      videoCodec: media?.videoCodec || media?.$.videoCodec || null,
      videoResolution: media?.videoResolution || media?.$.videoResolution || null,
      sizeBytes: part?.size ? parseInt(part.size) : null,
      sizeHuman: this.formatSize(part?.size),
      summary: plexItem.summary || null,
      tagline: plexItem.tagline || null,
      genres: this.extractGenres(plexItem),
      studio: plexItem.studio || null,
      directors: this.extractDirectors(plexItem),
      writers: this.extractWriters(plexItem),
      producers: this.extractProducers(plexItem),
      actors: this.extractActors(plexItem),
      originallyAvailableAt: plexItem.originallyAvailableAt || null,
      rating: plexItem.rating ? parseFloat(plexItem.rating) : null,
      audienceRating: plexItem.audienceRating ? parseFloat(plexItem.audienceRating) : null,
      available: 1,
      lastSeen: new Date().toISOString()
    };
  }

  transformShow(plexItem) {
    return {
      ratingKey: parseInt(plexItem.ratingKey || plexItem.$.ratingKey),
      title: plexItem.title || plexItem.$.title,
      contentRating: plexItem.contentRating || plexItem.$.contentRating || null,
      seasonCount: (plexItem.childCount || plexItem.$.childCount) ? parseInt(plexItem.childCount || plexItem.$.childCount) : 0,
      summary: plexItem.summary || null,
      genres: this.extractGenres(plexItem),
      studio: plexItem.studio || null,
      actors: this.extractActors(plexItem),
      originallyAvailableAt: plexItem.originallyAvailableAt || null,
      rating: plexItem.rating ? parseFloat(plexItem.rating) : null,
      audienceRating: plexItem.audienceRating ? parseFloat(plexItem.audienceRating) : null,
      available: 1,
      lastSeen: new Date().toISOString()
    };
  }

  transformSeason(plexItem) {
    return {
      seasonRatingKey: parseInt(plexItem.ratingKey || plexItem.$.ratingKey),
      showRatingKey: parseInt(plexItem.parentRatingKey || plexItem.$.parentRatingKey),
      seasonNumber: (plexItem.index || plexItem.$.index) ? parseInt(plexItem.index || plexItem.$.index) : null,
      summary: plexItem.summary || null,
      title: plexItem.title || plexItem.$.title || null,
      originallyAvailableAt: plexItem.originallyAvailableAt || null,
      available: 1,
      lastSeen: new Date().toISOString()
    };
  }

  transformEpisode(plexItem) {
    // Handle both XML (array) and object structures
    const media = Array.isArray(plexItem.Media) ? plexItem.Media[0] : plexItem.Media;
    const part = media && (Array.isArray(media.Part) ? media.Part[0] : media.Part);
    
    return {
      ratingKey: parseInt(plexItem.ratingKey || plexItem.$.ratingKey),
      seasonRatingKey: parseInt(plexItem.parentRatingKey || plexItem.$.parentRatingKey),
      showRatingKey: parseInt(plexItem.grandparentRatingKey || plexItem.$.grandparentRatingKey),
      episodeNumber: (plexItem.index || plexItem.$.index) ? parseInt(plexItem.index || plexItem.$.index) : null,
      title: plexItem.title || plexItem.$.title,
      year: plexItem.year ? parseInt(plexItem.year) : null,
      duration: plexItem.duration ? parseInt(plexItem.duration) : null,
      durationHuman: this.formatDuration(plexItem.duration),
      audioCodec: part?.audioCodec || part?.$.audioCodec || null,
      container: part?.container || part?.$.container || null,
      videoCodec: media?.videoCodec || media?.$.videoCodec || null,
      videoResolution: media?.videoResolution || media?.$.videoResolution || null,
      sizeBytes: part?.size ? parseInt(part.size) : null,
      sizeHuman: this.formatSize(part?.size),
      summary: plexItem.summary || null,
      originallyAvailableAt: plexItem.originallyAvailableAt || null,
      directors: this.extractDirectors(plexItem),
      writers: this.extractWriters(plexItem),
      actors: this.extractActors(plexItem),
      rating: plexItem.rating ? parseFloat(plexItem.rating) : null,
      audienceRating: plexItem.audienceRating ? parseFloat(plexItem.audienceRating) : null,
      available: 1,
      lastSeen: new Date().toISOString()
    };
  }

  transformArtist(plexItem) {
    return {
      ratingKey: parseInt(plexItem.ratingKey || plexItem.$.ratingKey),
      artistName: plexItem.title || plexItem.$.title,
      summary: plexItem.summary || null,
      genres: this.extractGenres(plexItem),
      available: 1,
      lastSeen: new Date().toISOString()
    };
  }

  transformAlbum(plexItem) {
    return {
      ratingKey: parseInt(plexItem.ratingKey || plexItem.$.ratingKey),
      artistRatingKey: parseInt(plexItem.parentRatingKey || plexItem.$.parentRatingKey),
      title: plexItem.title || plexItem.$.title,
      year: plexItem.year ? parseInt(plexItem.year) : null,
      summary: plexItem.summary || null,
      genres: this.extractGenres(plexItem),
      originallyAvailableAt: plexItem.originallyAvailableAt || null,
      studio: plexItem.studio || null,
      available: 1,
      lastSeen: new Date().toISOString()
    };
  }

  transformTrack(plexItem) {
    // Handle both XML (array) and object structures
    const media = Array.isArray(plexItem.Media) ? plexItem.Media[0] : plexItem.Media;
    const part = media && (Array.isArray(media.Part) ? media.Part[0] : media.Part);
    
    return {
      ratingKey: parseInt(plexItem.ratingKey || plexItem.$.ratingKey),
      albumRatingKey: parseInt(plexItem.parentRatingKey || plexItem.$.parentRatingKey),
      artistRatingKey: parseInt(plexItem.grandparentRatingKey || plexItem.$.grandparentRatingKey),
      title: plexItem.title || plexItem.$.title,
      trackNumber: (plexItem.index || plexItem.$.index) ? parseInt(plexItem.index || plexItem.$.index) : null,
      duration: plexItem.duration ? parseInt(plexItem.duration) : null,
      durationHuman: this.formatDuration(plexItem.duration),
      sizeBytes: part?.size ? parseInt(part.size) : null,
      sizeHuman: this.formatSize(part?.size),
      container: part?.container || part?.$.container || null,
      summary: plexItem.summary || null,
      originallyAvailableAt: plexItem.originallyAvailableAt || null,
      genres: this.extractGenres(plexItem),
      available: 1,
      lastSeen: new Date().toISOString()
    };
  }

  // Helper methods - handle both XML array and object structures
  extractGenres(plexItem) {
    const genres = plexItem.Genre || [];
    const genreArray = Array.isArray(genres) ? genres : (genres ? [genres] : []);
    if (genreArray.length === 0) return null;
    return genreArray.map(g => (g.tag || g.$.tag || g)).join(', ');
  }

  extractActors(plexItem) {
    const roles = plexItem.Role || [];
    const roleArray = Array.isArray(roles) ? roles : (roles ? [roles] : []);
    if (roleArray.length === 0) return null;
    return roleArray.map(r => {
      const tag = r.tag || r.$.tag || r;
      const role = (r.role || r.$.role) ? ` as ${r.role || r.$.role}` : '';
      return `${tag}${role}`;
    }).join(', ');
  }

  extractDirectors(plexItem) {
    const directors = plexItem.Director || [];
    const directorArray = Array.isArray(directors) ? directors : (directors ? [directors] : []);
    if (directorArray.length === 0) return null;
    return directorArray.map(d => (d.tag || d.$.tag || d)).join(', ');
  }

  extractWriters(plexItem) {
    const writers = plexItem.Writer || [];
    const writerArray = Array.isArray(writers) ? writers : (writers ? [writers] : []);
    if (writerArray.length === 0) return null;
    return writerArray.map(w => (w.tag || w.$.tag || w)).join(', ');
  }

  extractProducers(plexItem) {
    const producers = plexItem.Producer || [];
    const producerArray = Array.isArray(producers) ? producers : (producers ? [producers] : []);
    if (producerArray.length === 0) return null;
    return producerArray.map(p => (p.tag || p.$.tag || p)).join(', ');
  }

  formatDuration(ms) {
    if (!ms) return null;
    const minutes = Math.floor(ms / 60000);
    const hours = Math.floor(minutes / 60);
    if (hours > 0) {
      return `${hours}h ${minutes % 60}m`;
    }
    return `${minutes}m`;
  }

  formatSize(bytes) {
    if (!bytes) return null;
    const gb = bytes / 1_000_000_000_000;
    if (gb >= 1) return `${gb.toFixed(2)} TB`;
    const mb = bytes / 1_000_000_000;
    if (mb >= 1) return `${mb.toFixed(2)} GB`;
    return `${(bytes / 1_000_000).toFixed(2)} MB`;
  }
}

