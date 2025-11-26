import { Router } from 'express';

export function musicRouter(plexService, sqliteService) {
  const router = Router();

  // Get all artists
  router.get('/artists', async (req, res, next) => {
    try {
      const limit = parseInt(req.query.limit) || 100;
      const offset = parseInt(req.query.offset) || 0;

      // Try Plex API first
      if (plexService.isConnected()) {
        try {
          const libraries = await plexService.getLibraries();
          const directories = Array.isArray(libraries.MediaContainer.Directory) 
            ? libraries.MediaContainer.Directory 
            : [libraries.MediaContainer.Directory].filter(Boolean);
          const musicLibrary = directories.find(
            lib => (lib.type || lib.$.type) === 'artist'
          );
          
          if (musicLibrary) {
            const key = musicLibrary.key || musicLibrary.$.key;
            const response = await plexService.getLibraryItems(key, { offset, limit });
            const metadata = response.MediaContainer.Metadata || [];
            const items = Array.isArray(metadata) ? metadata : [metadata];
            const artists = items.map(item => plexService.transformArtist(item));
            
            // Get total count from Plex response
            const totalSize = response.MediaContainer.totalSize || response.MediaContainer.size || items.length;
            
            return res.json({
              data: artists,
              total: totalSize,
              source: 'plex'
            });
          }
        } catch (error) {
          console.warn('Plex API failed, falling back to SQLite:', error.message);
        }
      }

      // Fallback to SQLite
      const artists = sqliteService.getArtists(limit, offset);
      res.json({
        data: artists,
        total: artists.length,
        source: 'sqlite',
        fallback: true
      });
    } catch (error) {
      next(error);
    }
  });

  // Get single artist
  router.get('/artists/:ratingKey', async (req, res, next) => {
    try {
      const ratingKey = parseInt(req.params.ratingKey);

      // Try Plex API first
      if (plexService.isConnected()) {
        try {
          const response = await plexService.getMetadata(ratingKey);
          const metadata = response.MediaContainer.Metadata || [];
          const items = Array.isArray(metadata) ? metadata : [metadata];
          if (items.length > 0) {
            const artist = plexService.transformArtist(items[0]);
            return res.json({ data: artist, source: 'plex' });
          }
        } catch (error) {
          console.warn('Plex API failed, falling back to SQLite:', error.message);
        }
      }

      // Fallback to SQLite
      const artist = sqliteService.getArtist(ratingKey);
      if (!artist) {
        return res.status(404).json({ error: 'Artist not found' });
      }
      res.json({ data: artist, source: 'sqlite', fallback: true });
    } catch (error) {
      next(error);
    }
  });

  // Get albums for an artist
  router.get('/artists/:ratingKey/albums', async (req, res, next) => {
    try {
      const ratingKey = parseInt(req.params.ratingKey);

      // Try Plex API first
      if (plexService.isConnected()) {
        try {
          const response = await plexService.getChildren(ratingKey);
          const metadata = response.MediaContainer.Metadata || [];
          const items = Array.isArray(metadata) ? metadata : [metadata];
          const albums = items.map(item => plexService.transformAlbum(item));
          return res.json({ data: albums, source: 'plex' });
        } catch (error) {
          console.warn('Plex API failed, falling back to SQLite:', error.message);
        }
      }

      // Fallback to SQLite
      const albums = sqliteService.getAlbums(ratingKey);
      res.json({ data: albums, source: 'sqlite', fallback: true });
    } catch (error) {
      next(error);
    }
  });

  // Get single album
  router.get('/albums/:ratingKey', async (req, res, next) => {
    try {
      const ratingKey = parseInt(req.params.ratingKey);

      // Try Plex API first
      if (plexService.isConnected()) {
        try {
          const response = await plexService.getMetadata(ratingKey);
          const metadata = response.MediaContainer.Metadata || [];
          const items = Array.isArray(metadata) ? metadata : [metadata];
          if (items.length > 0) {
            const album = plexService.transformAlbum(items[0]);
            return res.json({ data: album, source: 'plex' });
          }
        } catch (error) {
          console.warn('Plex API failed, falling back to SQLite:', error.message);
        }
      }

      // Fallback to SQLite
      const album = sqliteService.getAlbum(ratingKey);
      if (!album) {
        return res.status(404).json({ error: 'Album not found' });
      }
      res.json({ data: album, source: 'sqlite', fallback: true });
    } catch (error) {
      next(error);
    }
  });

  // Get tracks for an album
  router.get('/albums/:ratingKey/tracks', async (req, res, next) => {
    try {
      const ratingKey = parseInt(req.params.ratingKey);

      // Try Plex API first
      if (plexService.isConnected()) {
        try {
          const response = await plexService.getChildren(ratingKey);
          const metadata = response.MediaContainer.Metadata || [];
          const items = Array.isArray(metadata) ? metadata : [metadata];
          const tracks = items.map(item => plexService.transformTrack(item));
          return res.json({ data: tracks, source: 'plex' });
        } catch (error) {
          console.warn('Plex API failed, falling back to SQLite:', error.message);
        }
      }

      // Fallback to SQLite
      const tracks = sqliteService.getTracks(ratingKey);
      res.json({ data: tracks, source: 'sqlite', fallback: true });
    } catch (error) {
      next(error);
    }
  });

  // Get single track
  router.get('/tracks/:ratingKey', async (req, res, next) => {
    try {
      const ratingKey = parseInt(req.params.ratingKey);

      // Try Plex API first
      if (plexService.isConnected()) {
        try {
          const response = await plexService.getMetadata(ratingKey);
          const metadata = response.MediaContainer.Metadata || [];
          const items = Array.isArray(metadata) ? metadata : [metadata];
          if (items.length > 0) {
            const track = plexService.transformTrack(items[0]);
            return res.json({ data: track, source: 'plex' });
          }
        } catch (error) {
          console.warn('Plex API failed, falling back to SQLite:', error.message);
        }
      }

      // Fallback to SQLite
      const track = sqliteService.getTrack(ratingKey);
      if (!track) {
        return res.status(404).json({ error: 'Track not found' });
      }
      res.json({ data: track, source: 'sqlite', fallback: true });
    } catch (error) {
      next(error);
    }
  });

  return router;
}

