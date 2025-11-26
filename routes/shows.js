import { Router } from 'express';

export function showsRouter(plexService, sqliteService) {
  const router = Router();

  // Get all shows
  router.get('/', async (req, res, next) => {
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
          const showLibrary = directories.find(
            lib => (lib.type || lib.$.type) === 'show'
          );
          
          if (showLibrary) {
            const key = showLibrary.key || showLibrary.$.key;
            const response = await plexService.getLibraryItems(key, { offset, limit });
            const metadata = response.MediaContainer.Metadata || [];
            const items = Array.isArray(metadata) ? metadata : [metadata];
            const shows = items.map(item => plexService.transformShow(item));
            
            // Get total count from Plex response
            const totalSize = response.MediaContainer.totalSize || response.MediaContainer.size || items.length;
            
            return res.json({
              data: shows,
              total: totalSize,
              source: 'plex'
            });
          }
        } catch (error) {
          console.warn('Plex API failed, falling back to SQLite:', error.message);
        }
      }

      // Fallback to SQLite
      const shows = sqliteService.getShows(limit, offset);
      res.json({
        data: shows,
        total: shows.length,
        source: 'sqlite',
        fallback: true
      });
    } catch (error) {
      next(error);
    }
  });

  // Get single show
  router.get('/:ratingKey', async (req, res, next) => {
    try {
      const ratingKey = parseInt(req.params.ratingKey);

      // Try Plex API first
      if (plexService.isConnected()) {
        try {
          const response = await plexService.getMetadata(ratingKey);
          const metadata = response.MediaContainer.Metadata || [];
          const items = Array.isArray(metadata) ? metadata : [metadata];
          if (items.length > 0) {
            const show = plexService.transformShow(items[0]);
            return res.json({ data: show, source: 'plex' });
          }
        } catch (error) {
          console.warn('Plex API failed, falling back to SQLite:', error.message);
        }
      }

      // Fallback to SQLite
      const show = sqliteService.getShow(ratingKey);
      if (!show) {
        return res.status(404).json({ error: 'Show not found' });
      }
      res.json({ data: show, source: 'sqlite', fallback: true });
    } catch (error) {
      next(error);
    }
  });

  // Get seasons for a show
  router.get('/:ratingKey/seasons', async (req, res, next) => {
    try {
      const ratingKey = parseInt(req.params.ratingKey);

      // Try Plex API first
      if (plexService.isConnected()) {
        try {
          const response = await plexService.getChildren(ratingKey);
          const metadata = response.MediaContainer.Metadata || [];
          const items = Array.isArray(metadata) ? metadata : [metadata];
          const seasons = items.map(item => plexService.transformSeason(item));
          return res.json({ data: seasons, source: 'plex' });
        } catch (error) {
          console.warn('Plex API failed, falling back to SQLite:', error.message);
        }
      }

      // Fallback to SQLite
      const seasons = sqliteService.getSeasons(ratingKey);
      res.json({ data: seasons, source: 'sqlite', fallback: true });
    } catch (error) {
      next(error);
    }
  });

  // Get single season
  router.get('/seasons/:seasonRatingKey', async (req, res, next) => {
    try {
      const seasonRatingKey = parseInt(req.params.seasonRatingKey);

      // Try Plex API first
      if (plexService.isConnected()) {
        try {
          const response = await plexService.getMetadata(seasonRatingKey);
          const metadata = response.MediaContainer.Metadata || [];
          const items = Array.isArray(metadata) ? metadata : [metadata];
          if (items.length > 0) {
            const season = plexService.transformSeason(items[0]);
            return res.json({ data: season, source: 'plex' });
          }
        } catch (error) {
          console.warn('Plex API failed, falling back to SQLite:', error.message);
        }
      }

      // Fallback to SQLite
      const season = sqliteService.getSeason(seasonRatingKey);
      if (!season) {
        return res.status(404).json({ error: 'Season not found' });
      }
      res.json({ data: season, source: 'sqlite', fallback: true });
    } catch (error) {
      next(error);
    }
  });

  // Get episodes for a season
  router.get('/seasons/:seasonRatingKey/episodes', async (req, res, next) => {
    try {
      const seasonRatingKey = parseInt(req.params.seasonRatingKey);

      // Try Plex API first
      if (plexService.isConnected()) {
        try {
          const response = await plexService.getChildren(seasonRatingKey);
          const metadata = response.MediaContainer.Metadata || [];
          const items = Array.isArray(metadata) ? metadata : [metadata];
          const episodes = items.map(item => plexService.transformEpisode(item));
          return res.json({ data: episodes, source: 'plex' });
        } catch (error) {
          console.warn('Plex API failed, falling back to SQLite:', error.message);
        }
      }

      // Fallback to SQLite
      const episodes = sqliteService.getEpisodes(seasonRatingKey);
      res.json({ data: episodes, source: 'sqlite', fallback: true });
    } catch (error) {
      next(error);
    }
  });

  // Get single episode
  router.get('/episodes/:ratingKey', async (req, res, next) => {
    try {
      const ratingKey = parseInt(req.params.ratingKey);

      // Try Plex API first
      if (plexService.isConnected()) {
        try {
          const response = await plexService.getMetadata(ratingKey);
          const metadata = response.MediaContainer.Metadata || [];
          const items = Array.isArray(metadata) ? metadata : [metadata];
          if (items.length > 0) {
            const episode = plexService.transformEpisode(items[0]);
            return res.json({ data: episode, source: 'plex' });
          }
        } catch (error) {
          console.warn('Plex API failed, falling back to SQLite:', error.message);
        }
      }

      // Fallback to SQLite
      const episode = sqliteService.getEpisode(ratingKey);
      if (!episode) {
        return res.status(404).json({ error: 'Episode not found' });
      }
      res.json({ data: episode, source: 'sqlite', fallback: true });
    } catch (error) {
      next(error);
    }
  });

  return router;
}

