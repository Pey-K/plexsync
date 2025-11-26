import { Router } from 'express';

export function recentRouter(plexService, sqliteService) {
  const router = Router();

  router.get('/', async (req, res, next) => {
    try {
      const limit = parseInt(req.query.limit) || 20;

      // Try Plex API first
      if (plexService.isConnected()) {
        try {
          // Use global recently added endpoint (faster than per-library)
          const response = await plexService.getGlobalRecentlyAdded(limit);
          const metadata = response.MediaContainer.Metadata || [];
          const items = Array.isArray(metadata) ? metadata : [metadata];
          
          const allRecent = items.map(item => {
            const type = item.type || item.$.type;
            if (type === 'movie') {
              return { type: 'movie', ...plexService.transformMovie(item) };
            } else if (type === 'show') {
              return { type: 'show', ...plexService.transformShow(item) };
            } else if (type === 'artist') {
              return { type: 'artist', ...plexService.transformArtist(item) };
            }
            return null;
          }).filter(Boolean);

          return res.json({
            data: allRecent.slice(0, limit),
            total: allRecent.length,
            source: 'plex'
          });
        } catch (error) {
          console.warn('Plex API failed, falling back to SQLite:', error.message);
        }
      }

      // Fallback to SQLite
      const results = sqliteService.getRecentlyAdded(limit);
      res.json({
        data: results,
        total: results.length,
        source: 'sqlite',
        fallback: true
      });
    } catch (error) {
      next(error);
    }
  });

  return router;
}

