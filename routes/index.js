import { Router } from 'express';
import { moviesRouter } from './movies.js';
import { showsRouter } from './shows.js';
import { musicRouter } from './music.js';
import { searchRouter } from './search.js';
import { recentRouter } from './recent.js';

export function createRouter(plexService, sqliteService) {
  const router = Router();

  router.use('/movies', moviesRouter(plexService, sqliteService));
  router.use('/shows', showsRouter(plexService, sqliteService));
  router.use('/music', musicRouter(plexService, sqliteService));
  router.use('/search', searchRouter(plexService, sqliteService));
  router.use('/recent', recentRouter(plexService, sqliteService));

  return router;
}

