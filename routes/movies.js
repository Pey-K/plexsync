import { Router } from 'express';

export function moviesRouter(plexService, sqliteService) {
  const router = Router();

  // Get all movies
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
          const movieLibrary = directories.find(
            lib => (lib.type || lib.$.type) === 'movie'
          );
          
          if (movieLibrary) {
            const key = movieLibrary.key || movieLibrary.$.key;
            const response = await plexService.getLibraryItems(key, { offset, limit });
            const metadata = response.MediaContainer.Metadata || [];
            const items = Array.isArray(metadata) ? metadata : [metadata];
            const movies = items.map(item => plexService.transformMovie(item));
            
            // Get total count from Plex response
            const totalSize = response.MediaContainer.totalSize || response.MediaContainer.size || items.length;
            
            return res.json({
              data: movies,
              total: totalSize,
              source: 'plex'
            });
          }
        } catch (error) {
          console.warn('Plex API failed, falling back to SQLite:', error.message);
        }
      }

      // Fallback to SQLite
      const movies = sqliteService.getMovies(limit, offset);
      res.json({
        data: movies,
        total: movies.length,
        source: 'sqlite',
        fallback: true
      });
    } catch (error) {
      next(error);
    }
  });

  // Get single movie
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
            const movie = plexService.transformMovie(items[0]);
            return res.json({ data: movie, source: 'plex' });
          }
        } catch (error) {
          console.warn('Plex API failed, falling back to SQLite:', error.message);
        }
      }

      // Fallback to SQLite
      const movie = sqliteService.getMovie(ratingKey);
      if (!movie) {
        return res.status(404).json({ error: 'Movie not found' });
      }
      res.json({ data: movie, source: 'sqlite', fallback: true });
    } catch (error) {
      next(error);
    }
  });

  return router;
}

