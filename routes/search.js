import { Router } from 'express';

export function searchRouter(plexService, sqliteService) {
  const router = Router();

  router.get('/', async (req, res, next) => {
    try {
      const query = req.query.q || req.query.query;
      if (!query) {
        return res.status(400).json({ error: 'Query parameter "q" or "query" is required' });
      }

      const limit = parseInt(req.query.limit) || 50;

      // Try Plex API first
      if (plexService.isConnected()) {
        try {
          const response = await plexService.search(query);
          const metadata = response.MediaContainer.Metadata || [];
          const items = Array.isArray(metadata) ? metadata : [metadata];
          const results = items.slice(0, limit).map(item => {
            // Determine type and transform accordingly
            if (item.type === 'movie') {
              return { type: 'movie', ...plexService.transformMovie(item) };
            } else if (item.type === 'show') {
              return { type: 'show', ...plexService.transformShow(item) };
            } else if (item.type === 'artist') {
              return { type: 'artist', ...plexService.transformArtist(item) };
            }
            return item;
          });
          
          return res.json({
            data: results,
            total: results.length,
            source: 'plex'
          });
        } catch (error) {
          console.warn('Plex API failed, falling back to SQLite:', error.message);
        }
      }

      // Fallback to SQLite
      const results = sqliteService.search(query, limit);
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

