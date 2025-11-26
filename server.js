import express from 'express';
import cors from 'cors';
import dotenv from 'dotenv';
import { PlexService } from './services/plexService.js';
import { SqliteService } from './services/sqliteService.js';
import { createRouter } from './routes/index.js';

dotenv.config();

const app = express();
const PORT = process.env.PORT || 3000;

// Middleware
app.use(cors());
app.use(express.json());

// Initialize services
const plexService = new PlexService(
  process.env.PLEX_URL,
  process.env.PLEX_TOKEN
);
const sqliteService = new SqliteService(process.env.DB_PATH || './data/plex_collection.db');

// Routes
app.use('/api', createRouter(plexService, sqliteService));

// Health check
app.get('/health', (req, res) => {
  res.json({ 
    status: 'ok', 
    plex: plexService.isConnected(),
    sqlite: sqliteService.isConnected()
  });
});

// Error handling middleware
app.use((err, req, res, next) => {
  console.error('Error:', err);
  res.status(err.status || 500).json({
    error: err.message || 'Internal server error',
    fallback: err.fallback || false
  });
});

app.listen(PORT, () => {
  console.log(`🚀 Server running on port ${PORT}`);
  console.log(`📡 Plex URL: ${process.env.PLEX_URL || 'Not configured'}`);
  console.log(`💾 SQLite DB: ${process.env.DB_PATH || './data/plex_collection.db'}`);
});

