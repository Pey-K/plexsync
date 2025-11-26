"""
Plex API Sync Script - SQLite Database Version
This replaces the JSON export approach with direct Plex API calls and SQLite storage.

Requirements:
    pip install plexapi pillow

Environment Variables:
    PLEX_URL: Your Plex server URL (e.g., http://192.168.1.100:32400)
    PLEX_TOKEN: Your Plex authentication token
    PLEX_LIBRARY_NAMES: Comma-separated library names (e.g., "Movies,TV Shows,Music")
    DB_PATH: Path to SQLite database file (default: ../../data/plex_collection.db)

CLI Usage:
    python plex_sync.py                    # Normal sync
    python plex_sync.py --fast             # Use parallel processing (default)
    python plex_sync.py --no-parallel      # Disable parallel processing
    python plex_sync.py --rebuild-db       # Drop and recreate database
    python plex_sync.py --no-images        # Skip image downloads
    python plex_sync.py --verbose          # Enable debug logging
"""

import os
import sqlite3
import requests
import time
import hashlib
import logging
import argparse
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from plexapi.server import PlexServer
from plexapi.library import LibrarySection
from plexapi.video import Movie, Show, Season, Episode
from plexapi.audio import Artist, Album, Track
from PIL import Image
import io

# Load environment variables from .env file if it exists
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed, use environment variables only

# Configuration
PLEX_URL = os.getenv("PLEX_URL")
PLEX_TOKEN = os.getenv("PLEX_TOKEN")
LIBRARY_NAMES = [name.strip() for name in os.getenv("PLEX_LIBRARY_NAMES", "Movies,TV Shows,Music").split(",")]
DB_PATH = os.getenv("DB_PATH", "../../data/plex_collection.db")

IMAGE_FOLDERS = {
    "Movies": "../../assets/images/movie_image",
    "TV Shows": "../../assets/images/tv_image",
    "Music": "../../assets/images/music_image"
}

# Global settings (can be overridden by CLI args)
USE_PARALLEL = True
DOWNLOAD_IMAGES = True
SCHEMA_VERSION = 3  # Increment when schema changes

def setup_logging(verbose=False, log_file=None):
    """Setup logging configuration."""
    level = logging.DEBUG if verbose else logging.INFO
    handlers = [logging.StreamHandler()]
    
    if log_file:
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        handlers.append(logging.FileHandler(log_file))
    
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=handlers
    )
    return logging.getLogger(__name__)

def calculate_media_hash(size_bytes, duration, codec, resolution, container, title, year):
    """Calculate a hash fingerprint for media to detect changes."""
    # Create a string representation of key attributes
    hash_string = f"{size_bytes}|{duration}|{codec}|{resolution}|{container}|{title}|{year}"
    return hashlib.md5(hash_string.encode('utf-8')).hexdigest()

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Sync Plex media library to SQLite database',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        '--fast', '--parallel',
        action='store_true',
        default=True,
        help='Use parallel processing for faster syncs (default: enabled)'
    )
    parser.add_argument(
        '--no-parallel',
        dest='fast',
        action='store_false',
        help='Disable parallel processing'
    )
    parser.add_argument(
        '--rebuild-db',
        action='store_true',
        help='Drop and recreate the database (WARNING: deletes all data)'
    )
    parser.add_argument(
        '--no-images',
        action='store_true',
        help='Skip image downloads'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable debug logging'
    )
    parser.add_argument(
        '--log-file',
        type=str,
        help='Path to log file (optional)'
    )
    parser.add_argument(
        '--db-path',
        type=str,
        help='Override database path'
    )
    return parser.parse_args()

def validate_rating_key(rating_key):
    """Validate that ratingKey is an integer."""
    if not isinstance(rating_key, int):
        try:
            return int(rating_key)
        except (ValueError, TypeError):
            raise ValueError(f"Invalid ratingKey: {rating_key} (must be integer)")
    return rating_key

def human_readable_size(total_bytes):
    """Convert bytes to human-readable format."""
    if total_bytes >= 1_000_000_000_000:
        return f"{total_bytes / 1_000_000_000_000:.2f} TB"
    elif total_bytes >= 1_000_000_000:
        return f"{total_bytes / 1_000_000_000:.2f} GB"
    else:
        return f"{total_bytes / 1_000_000:.2f} MB"

def human_readable_duration(total_milliseconds):
    """Convert milliseconds to human-readable duration in full integer minutes."""
    total_seconds = total_milliseconds // 1000
    total_minutes = round(total_seconds / 60)
    # Ensure at least 1 minute if there's any duration
    if total_minutes == 0 and total_seconds > 0:
        total_minutes = 1
    return f"{total_minutes} min{'s' if total_minutes != 1 else ''}"

def format_resolution(resolution):
    """Format resolution string."""
    if resolution is None:
        return None
    resolution = resolution.lower()
    if resolution == "4k":
        return "2160p"
    elif resolution.isdigit():
        return f"{resolution}p"
    return resolution

def format_codec(codec):
    """Format codec string."""
    if codec is None:
        return None
    return codec.upper()

def extract_genres(plex_item):
    """Extract genres as CSV string."""
    if not hasattr(plex_item, 'genres') or not plex_item.genres:
        return None
    return ", ".join([genre.tag for genre in plex_item.genres if genre.tag])

def extract_actors(plex_item):
    """Extract actors as CSV string formatted as 'Name as Role'."""
    if not hasattr(plex_item, 'roles') or not plex_item.roles:
        return None
    actors = []
    for role in plex_item.roles:
        if hasattr(role, 'tag') and role.tag:
            role_name = role.role if hasattr(role, 'role') and role.role else None
            if role_name:
                actors.append(f"{role.tag} as {role_name}")
            else:
                actors.append(role.tag)
    return ", ".join(actors) if actors else None

def extract_directors(plex_item):
    """Extract directors as CSV string."""
    if not hasattr(plex_item, 'directors') or not plex_item.directors:
        return None
    return ", ".join([director.tag for director in plex_item.directors if director.tag])

def extract_writers(plex_item):
    """Extract writers as CSV string."""
    if not hasattr(plex_item, 'writers') or not plex_item.writers:
        return None
    return ", ".join([writer.tag for writer in plex_item.writers if writer.tag])

def extract_producers(plex_item):
    """Extract producers as CSV string."""
    if not hasattr(plex_item, 'producers') or not plex_item.producers:
        return None
    return ", ".join([producer.tag for producer in plex_item.producers if producer.tag])

def extract_studio(plex_item):
    """Extract studio name."""
    if not hasattr(plex_item, 'studio') or not plex_item.studio:
        return None
    return plex_item.studio

def extract_summary(plex_item):
    """Extract summary/description."""
    if not hasattr(plex_item, 'summary') or not plex_item.summary:
        return None
    return plex_item.summary.strip() if plex_item.summary else None

def extract_tagline(plex_item):
    """Extract tagline."""
    if not hasattr(plex_item, 'tagline') or not plex_item.tagline:
        return None
    return plex_item.tagline.strip() if plex_item.tagline else None

def extract_originally_available(plex_item):
    """Extract originallyAvailableAt date as ISO string."""
    if not hasattr(plex_item, 'originallyAvailableAt') or not plex_item.originallyAvailableAt:
        return None
    # Convert to ISO format string if it's a date object
    if hasattr(plex_item.originallyAvailableAt, 'isoformat'):
        return plex_item.originallyAvailableAt.isoformat()
    return str(plex_item.originallyAvailableAt)

def extract_rating(plex_item):
    """Extract rating (0-10 scale)."""
    if not hasattr(plex_item, 'rating') or plex_item.rating is None:
        return None
    try:
        return float(plex_item.rating)
    except (ValueError, TypeError):
        return None

def extract_audience_rating(plex_item):
    """Extract audience rating (0-10 scale)."""
    if not hasattr(plex_item, 'audienceRating') or plex_item.audienceRating is None:
        return None
    try:
        return float(plex_item.audienceRating)
    except (ValueError, TypeError):
        return None

def format_year_range(years):
    """Format year range, handling single year case."""
    valid_years = [year for year in years if year]
    if not valid_years:
        return None
    if len(set(valid_years)) == 1:
        return str(valid_years[0])
    return f"{min(valid_years)}-{max(valid_years)}"

def fetch_with_retry(fetch_func, item_name, max_retries=3, base_wait=2):
    """Generic retry wrapper for Plex API calls."""
    for attempt in range(max_retries):
        try:
            return fetch_func()
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            if attempt < max_retries - 1:
                wait_time = (attempt + 1) * base_wait
                time.sleep(wait_time)
                continue
            else:
                print(f"  ⚠️  Failed to fetch {item_name} after {max_retries} attempts: {e}")
                return []
    return []

def download_and_convert_image(plex_item, output_path, plex_server, max_retries=3):
    """Download thumbnail from Plex and convert to WebP with retry logic."""
    logger = logging.getLogger(__name__)
    for attempt in range(max_retries):
        try:
            # Ensure output directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # Get thumbnail URL
            if not plex_item.thumb:
                return False
                
            thumb_url = plex_server.url(plex_item.thumb, includeToken=True)
            
            # Download image with longer timeout
            response = requests.get(thumb_url, timeout=30)
            if response.status_code == 200:
                # Convert to WebP
                img = Image.open(io.BytesIO(response.content))
                # Convert RGBA to RGB if needed
                if img.mode == 'RGBA':
                    rgb_img = Image.new('RGB', img.size, (0, 0, 0))
                    rgb_img.paste(img, mask=img.split()[3])
                    img = rgb_img
                
                # Save as WebP (output_path should already be .webp)
                img.save(output_path, 'WEBP', quality=80)
                return True
        except requests.exceptions.Timeout:
            if attempt < max_retries - 1:
                wait_time = (attempt + 1) * 2
                logger.debug(f"Timeout downloading image, retrying in {wait_time}s... (attempt {attempt + 1}/{max_retries})")
                time.sleep(wait_time)
                continue
            else:
                logger.warning(f"Failed to download image after {max_retries} attempts")
        except Exception as e:
            if attempt < max_retries - 1:
                wait_time = (attempt + 1) * 2
                logger.debug(f"Error downloading image, retrying in {wait_time}s... (attempt {attempt + 1}/{max_retries})")
                time.sleep(wait_time)
                continue
            else:
                item_name = plex_item.title if hasattr(plex_item, 'title') else 'unknown'
                logger.warning(f"Error downloading image for {item_name}: {e}")
    return False

def download_image_worker(args):
    """Worker function for parallel image downloads."""
    plex_item, output_path, plex_server = args
    success = download_and_convert_image(plex_item, output_path, plex_server)
    item_name = plex_item.title if hasattr(plex_item, 'title') else 'unknown'
    return (success, item_name, output_path)

def download_images_parallel(image_tasks, max_workers=10):
    """Download images in parallel using ThreadPoolExecutor."""
    logger = logging.getLogger(__name__)
    if not image_tasks:
        return {'downloaded': 0, 'failed': 0}
    
    downloaded = 0
    failed = 0
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_task = {executor.submit(download_image_worker, task): task for task in image_tasks}
        
        for future in as_completed(future_to_task):
            try:
                success, item_name, output_path = future.result()
                if success:
                    downloaded += 1
                else:
                    failed += 1
            except Exception as e:
                failed += 1
                logger.error(f"Exception in image download worker: {e}")
    
    return {'downloaded': downloaded, 'failed': failed}

def process_episode(episode: Episode, season_rating_key: int, show_rating_key: int,
                   image_folder: str, plex_server: PlexServer, current_time: str,
                   image_stats: dict, download_image=True):
    """Process a single episode and return data for batch insert."""
    logger = logging.getLogger(__name__)
    episode_rating_key = validate_rating_key(episode.ratingKey)
    episode_duration = episode.duration or 0
    
    if not episode.media:
        logger.debug(f"    Skipping episode '{episode.title}': no media found")
        return None
    
    episode_media = episode.media[0]
    if not episode_media.parts:
        logger.debug(f"    Skipping episode '{episode.title}': no media parts found")
        return None
    
    episode_part = episode_media.parts[0]
    size_bytes = episode_part.size or 0
    audio_codec = format_codec(episode_media.audioCodec)
    video_codec = format_codec(episode_media.videoCodec)
    video_resolution = format_resolution(episode_media.videoResolution)
    
    # Calculate media hash to detect changes
    media_hash = calculate_media_hash(
        size_bytes, episode_duration, video_codec, video_resolution,
        episode_part.container, episode.title, episode.year
    )
    
    # Download and convert episode thumbnail (if requested)
    if download_image and DOWNLOAD_IMAGES:
        episode_image_path = os.path.join(image_folder, f"{episode_rating_key}.thumb.webp")
        if download_and_convert_image(episode, episode_image_path, plex_server):
            image_stats['downloaded'] += 1
        else:
            image_stats['failed'] += 1
            logger.debug(f"    Image download failed for episode '{episode.title}'")
    
    # Extract metadata
    summary = extract_summary(episode)
    originally_available = extract_originally_available(episode)
    directors = extract_directors(episode)
    writers = extract_writers(episode)
    actors = extract_actors(episode)
    rating = extract_rating(episode)
    audience_rating = extract_audience_rating(episode)
    
    # Return episode data and metadata
    # Note: duration/sizeBytes are raw values, durationHuman/sizeHuman are display-friendly
    episode_data = (
        episode_rating_key,
        season_rating_key,
        show_rating_key,
        episode.index,
        episode.title,
        episode.year,
        episode_duration,  # Raw duration in milliseconds
        human_readable_duration(episode_duration) if episode_duration else None,  # Display-friendly
        audio_codec,
        episode_part.container,
        video_codec,
        video_resolution,
        size_bytes,  # Raw size in bytes
        human_readable_size(size_bytes),  # Display-friendly
        media_hash,  # Hash fingerprint
        summary,
        originally_available,
        directors,
        writers,
        actors,
        rating,
        audience_rating,
        1,  # available
        current_time
    )
    
    return {
        'data': episode_data,
        'duration': episode_duration,
        'size_bytes': size_bytes,
        'year': episode.year,
        'video_resolution': video_resolution,
        'audio_codec': audio_codec,
        'video_codec': video_codec,
        'container': episode_part.container,
        'media_hash': media_hash
    }

def process_season(season: Season, show_rating_key: int, image_folder: str,
                  plex_server: PlexServer, current_time: str, image_stats: dict):
    """Process a single season and return data for batch insert."""
    logger = logging.getLogger(__name__)
    season_rating_key = validate_rating_key(season.ratingKey)
    
    season_size_bytes = 0
    season_total_episodes = 0
    season_total_duration = 0
    season_years = []
    season_video_resolutions = []
    season_audio_codecs = []
    season_video_codecs = []
    season_containers = []
    episodes_data = []
    episode_image_tasks = []
    
    # Fetch episodes with retry
    episodes_list = fetch_with_retry(
        lambda: season.episodes(),
        f"episodes for season {season.seasonNumber}",
        max_retries=3
    )
    
    for episode in episodes_list:
        # Process episode (don't download images yet if using parallel mode)
        download_now = not (USE_PARALLEL and DOWNLOAD_IMAGES)
        episode_result = process_episode(
            episode, season_rating_key, show_rating_key,
            image_folder, plex_server, current_time, image_stats,
            download_image=download_now
        )
        
        if episode_result:
            episodes_data.append(episode_result['data'])
            season_total_episodes += 1
            season_total_duration += episode_result['duration']
            season_size_bytes += episode_result['size_bytes']
            season_years.append(episode_result['year'])
            season_video_resolutions.append(episode_result['video_resolution'])
            season_audio_codecs.append(episode_result['audio_codec'])
            season_video_codecs.append(episode_result['video_codec'])
            season_containers.append(episode_result['container'])
            
            # Collect image task for parallel download
            if USE_PARALLEL and DOWNLOAD_IMAGES:
                episode_rating_key = episode_result['data'][0]  # ratingKey is first element
                episode_image_path = os.path.join(image_folder, f"{episode_rating_key}.thumb.webp")
                episode_image_tasks.append((episode, episode_image_path, plex_server))
    
    # Calculate average episode duration for the season
    avg_season_duration = season_total_duration // season_total_episodes if season_total_episodes > 0 else 0
    
    # Download and convert season thumbnail
    season_image_path = os.path.join(image_folder, f"{season_rating_key}.thumb.webp")
    if DOWNLOAD_IMAGES:
        if download_and_convert_image(season, season_image_path, plex_server):
            image_stats['downloaded'] += 1
        else:
            image_stats['failed'] += 1
    
    # Format year range (handles single year case)
    year_range = format_year_range(season_years)
    
    # Extract metadata
    summary = extract_summary(season)
    season_title = season.title if hasattr(season, 'title') and season.title else None
    originally_available = extract_originally_available(season)
    
    # Collect season data for batch insert
    season_data = (
        season_rating_key,
        show_rating_key,
        season.seasonNumber,
        season_total_episodes,
        avg_season_duration,  # Raw average duration in milliseconds
        human_readable_duration(avg_season_duration) if avg_season_duration > 0 else None,  # Display-friendly
        season_size_bytes,  # Raw size in bytes
        human_readable_size(season_size_bytes),  # Display-friendly
        ", ".join(sorted(set([r for r in season_video_resolutions if r]))),
        ", ".join(sorted(set([c for c in season_audio_codecs if c]))),
        ", ".join(sorted(set([c for c in season_video_codecs if c]))),
        ", ".join(sorted(set([c for c in season_containers if c]))),
        year_range,
        summary,
        season_title,
        originally_available,
        1,  # available
        current_time
    )
    
    return {
        'season_data': season_data,
        'episodes_data': episodes_data,
        'episode_image_tasks': episode_image_tasks,
        'total_episodes': season_total_episodes,
        'total_duration': season_total_duration,
        'size_bytes': season_size_bytes,
        'years': season_years,
        'video_resolutions': season_video_resolutions,
        'audio_codecs': season_audio_codecs,
        'video_codecs': season_video_codecs,
        'containers': season_containers
    }

def get_schema_version(conn):
    """Get current schema version from database."""
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT version FROM schema_version ORDER BY version DESC LIMIT 1")
        result = cursor.fetchone()
        return result[0] if result else 0
    except sqlite3.OperationalError:
        # Table doesn't exist yet
        return 0

def set_schema_version(conn, version):
    """Set schema version in database."""
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER PRIMARY KEY,
            applied_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("INSERT OR REPLACE INTO schema_version (version) VALUES (?)", (version,))
    conn.commit()

def run_migrations(conn, current_version, target_version):
    """Run database migrations from current_version to target_version."""
    logger = logging.getLogger(__name__)
    
    if current_version >= target_version:
        logger.info(f"Database schema is up to date (version {current_version})")
        return
    
    logger.info(f"Migrating database from version {current_version} to {target_version}")
    cursor = conn.cursor()
    
    # Migration 1: Add mediaHash columns
    if current_version < 1:
        logger.info("Applying migration 1: Adding mediaHash columns...")
        try:
            cursor.execute("ALTER TABLE movies ADD COLUMN mediaHash TEXT")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_movies_hash ON movies(mediaHash)")
        except sqlite3.OperationalError as e:
            if "duplicate column" not in str(e).lower():
                raise
            logger.debug("movies.mediaHash already exists")
        
        try:
            cursor.execute("ALTER TABLE episodes ADD COLUMN mediaHash TEXT")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_episodes_hash ON episodes(mediaHash)")
        except sqlite3.OperationalError as e:
            if "duplicate column" not in str(e).lower():
                raise
            logger.debug("episodes.mediaHash already exists")
        
        try:
            cursor.execute("ALTER TABLE tracks ADD COLUMN mediaHash TEXT")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tracks_hash ON tracks(mediaHash)")
        except sqlite3.OperationalError as e:
            if "duplicate column" not in str(e).lower():
                raise
            logger.debug("tracks.mediaHash already exists")
        
        set_schema_version(conn, 1)
        logger.info("Migration 1 completed")
    
    # Migration 2: Add extended metadata columns
    if current_version < 2:
        logger.info("Applying migration 2: Adding extended metadata columns...")
        
        # Movies metadata
        movie_columns = [
            ("summary", "TEXT"),
            ("tagline", "TEXT"),
            ("genres", "TEXT"),
            ("studio", "TEXT"),
            ("directors", "TEXT"),
            ("writers", "TEXT"),
            ("producers", "TEXT"),
            ("actors", "TEXT"),
            ("originallyAvailableAt", "TEXT"),
            ("rating", "REAL"),
            ("audienceRating", "REAL")
        ]
        for col_name, col_type in movie_columns:
            try:
                cursor.execute(f"ALTER TABLE movies ADD COLUMN {col_name} {col_type}")
            except sqlite3.OperationalError as e:
                if "duplicate column" not in str(e).lower():
                    raise
                logger.debug(f"movies.{col_name} already exists")
        
        # TV Shows metadata
        show_columns = [
            ("summary", "TEXT"),
            ("genres", "TEXT"),
            ("studio", "TEXT"),
            ("actors", "TEXT"),
            ("originallyAvailableAt", "TEXT"),
            ("rating", "REAL"),
            ("audienceRating", "REAL")
        ]
        for col_name, col_type in show_columns:
            try:
                cursor.execute(f"ALTER TABLE tv_shows ADD COLUMN {col_name} {col_type}")
            except sqlite3.OperationalError as e:
                if "duplicate column" not in str(e).lower():
                    raise
                logger.debug(f"tv_shows.{col_name} already exists")
        
        # Seasons metadata
        season_columns = [
            ("summary", "TEXT"),
            ("title", "TEXT"),
            ("originallyAvailableAt", "TEXT")
        ]
        for col_name, col_type in season_columns:
            try:
                cursor.execute(f"ALTER TABLE seasons ADD COLUMN {col_name} {col_type}")
            except sqlite3.OperationalError as e:
                if "duplicate column" not in str(e).lower():
                    raise
                logger.debug(f"seasons.{col_name} already exists")
        
        # Episodes metadata
        episode_columns = [
            ("summary", "TEXT"),
            ("originallyAvailableAt", "TEXT"),
            ("directors", "TEXT"),
            ("writers", "TEXT"),
            ("actors", "TEXT"),
            ("rating", "REAL"),
            ("audienceRating", "REAL")
        ]
        for col_name, col_type in episode_columns:
            try:
                cursor.execute(f"ALTER TABLE episodes ADD COLUMN {col_name} {col_type}")
            except sqlite3.OperationalError as e:
                if "duplicate column" not in str(e).lower():
                    raise
                logger.debug(f"episodes.{col_name} already exists")
        
        # Artists metadata
        artist_columns = [
            ("summary", "TEXT"),
            ("genres", "TEXT")
        ]
        for col_name, col_type in artist_columns:
            try:
                cursor.execute(f"ALTER TABLE artists ADD COLUMN {col_name} {col_type}")
            except sqlite3.OperationalError as e:
                if "duplicate column" not in str(e).lower():
                    raise
                logger.debug(f"artists.{col_name} already exists")
        
        # Albums metadata
        album_columns = [
            ("summary", "TEXT"),
            ("genres", "TEXT"),
            ("originallyAvailableAt", "TEXT"),
            ("studio", "TEXT")
        ]
        for col_name, col_type in album_columns:
            try:
                cursor.execute(f"ALTER TABLE albums ADD COLUMN {col_name} {col_type}")
            except sqlite3.OperationalError as e:
                if "duplicate column" not in str(e).lower():
                    raise
                logger.debug(f"albums.{col_name} already exists")
        
        # Tracks metadata
        track_columns = [
            ("summary", "TEXT"),
            ("originallyAvailableAt", "TEXT"),
            ("genres", "TEXT")
        ]
        for col_name, col_type in track_columns:
            try:
                cursor.execute(f"ALTER TABLE tracks ADD COLUMN {col_name} {col_type}")
            except sqlite3.OperationalError as e:
                if "duplicate column" not in str(e).lower():
                    raise
                logger.debug(f"tracks.{col_name} already exists")
        
        set_schema_version(conn, 2)
        logger.info("Migration 2 completed")
    
    # Migration 3: Add FTS5 search index (optional optimization)
    if current_version < 3:
        logger.info("Applying migration 3: Creating FTS5 search index...")
        try:
            cursor.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS search_fts USING fts5(
                    type,
                    ratingKey UNINDEXED,
                    title,
                    summary,
                    year UNINDEXED,
                    available UNINDEXED,
                    content='',
                    content_rowid='ratingKey'
                )
            """)
            
            # Populate FTS5 table
            cursor.execute("""
                INSERT OR IGNORE INTO search_fts(type, ratingKey, title, summary, year, available)
                SELECT 'movie', ratingKey, title, COALESCE(summary, ''), year, available
                FROM movies WHERE available = 1
            """)
            
            cursor.execute("""
                INSERT OR IGNORE INTO search_fts(type, ratingKey, title, summary, year, available)
                SELECT 'show', ratingKey, title, COALESCE(summary, ''), NULL, available
                FROM tv_shows WHERE available = 1
            """)
            
            cursor.execute("""
                INSERT OR IGNORE INTO search_fts(type, ratingKey, title, summary, year, available)
                SELECT 'artist', ratingKey, artistName, COALESCE(summary, ''), NULL, available
                FROM artists WHERE available = 1
            """)
            
            set_schema_version(conn, 3)
            logger.info("Migration 3 completed: FTS5 search index created")
        except sqlite3.OperationalError as e:
            if "fts5" in str(e).lower() or "no such module" in str(e).lower():
                logger.warning("FTS5 not available in this SQLite build, skipping search optimization")
            else:
                raise
            set_schema_version(conn, 3)  # Mark as complete even if FTS5 unavailable

def init_database(db_path, rebuild=False):
    """Initialize SQLite database with all required tables."""
    logger = logging.getLogger(__name__)
    
    if rebuild and os.path.exists(db_path):
        logger.warning(f"Rebuilding database: deleting {db_path}")
        os.remove(db_path)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Enable foreign keys
    cursor.execute("PRAGMA foreign_keys = ON")
    
    # Check current schema version
    current_version = get_schema_version(conn)
    logger.info(f"Current database schema version: {current_version}")
    
    # Movies table
    # Note: duration/sizeBytes are raw values (milliseconds/bytes), durationHuman/sizeHuman are display-friendly
    # mediaHash is a fingerprint to detect changes and skip unnecessary updates
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS movies (
            ratingKey INTEGER PRIMARY KEY,
            title TEXT NOT NULL,
            year INTEGER,
            contentRating TEXT,
            duration INTEGER,  -- Raw duration in milliseconds
            durationHuman TEXT,  -- Display-friendly duration (e.g., "120 mins")
            audioCodec TEXT,
            container TEXT,
            videoCodec TEXT,
            videoResolution TEXT,
            sizeBytes INTEGER,  -- Raw size in bytes
            sizeHuman TEXT,  -- Display-friendly size (e.g., "5.2 GB")
            mediaHash TEXT,  -- Hash fingerprint to detect changes
            summary TEXT,  -- Movie description/summary
            tagline TEXT,  -- Movie tagline
            genres TEXT,  -- CSV of genre names
            studio TEXT,  -- Production studio
            directors TEXT,  -- CSV of director names
            writers TEXT,  -- CSV of writer names
            producers TEXT,  -- CSV of producer names
            actors TEXT,  -- CSV of actors formatted as "Name as Role"
            originallyAvailableAt TEXT,  -- Original release date (ISO format)
            rating REAL,  -- Rating (0-10 scale)
            audienceRating REAL,  -- Audience rating (0-10 scale)
            available INTEGER DEFAULT 1,
            lastSeen TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # TV Shows table
    # Note: avgEpisodeDuration/showSizeBytes are raw values, avgEpisodeDurationHuman/showSizeHuman are display-friendly
    # CSV fields (avgVideoResolutions, etc.) aggregate values across all episodes for display
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tv_shows (
            ratingKey INTEGER PRIMARY KEY,
            title TEXT NOT NULL,
            contentRating TEXT,
            avgEpisodeDuration INTEGER,  -- Raw average duration in milliseconds
            avgEpisodeDurationHuman TEXT,  -- Display-friendly duration (e.g., "45 mins")
            seasonCount INTEGER,
            showTotalEpisode INTEGER,
            showSizeBytes INTEGER,  -- Raw total size in bytes
            showSizeHuman TEXT,  -- Display-friendly size (e.g., "500 GB")
            avgVideoResolutions TEXT,  -- CSV of unique resolutions across episodes
            avgAudioCodecs TEXT,  -- CSV of unique audio codecs
            avgVideoCodecs TEXT,  -- CSV of unique video codecs
            avgContainers TEXT,  -- CSV of unique containers
            showYearRange TEXT,  -- Year range (e.g., "2020-2023" or "2023" for single year)
            summary TEXT,  -- Show description/summary
            genres TEXT,  -- CSV of genre names
            studio TEXT,  -- Production studio
            actors TEXT,  -- CSV of actors formatted as "Name as Role"
            originallyAvailableAt TEXT,  -- Original release date (ISO format)
            rating REAL,  -- Rating (0-10 scale)
            audienceRating REAL,  -- Audience rating (0-10 scale)
            available INTEGER DEFAULT 1,
            lastSeen TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Seasons table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS seasons (
            seasonRatingKey INTEGER PRIMARY KEY,
            showRatingKey INTEGER NOT NULL,
            seasonNumber INTEGER,
            seasonTotalEpisode INTEGER,
            avgSeasonEpisodeDuration INTEGER,
            avgSeasonEpisodeDurationHuman TEXT,
            seasonSizeBytes INTEGER,
            seasonSizeHuman TEXT,
            avgSeasonVideoResolution TEXT,
            avgSeasonAudioCodec TEXT,
            avgSeasonVideoCodec TEXT,
            avgSeasonContainer TEXT,
            yearRange TEXT,
            summary TEXT,  -- Season description/summary
            title TEXT,  -- Season title
            originallyAvailableAt TEXT,  -- Original release date (ISO format)
            available INTEGER DEFAULT 1,
            lastSeen TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (showRatingKey) REFERENCES tv_shows(ratingKey) ON DELETE CASCADE
        )
    """)
    
    # Episodes table
    # Note: mediaHash is a fingerprint to detect changes and skip unnecessary updates
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS episodes (
            ratingKey INTEGER PRIMARY KEY,
            seasonRatingKey INTEGER NOT NULL,
            showRatingKey INTEGER NOT NULL,
            episodeNumber INTEGER,
            title TEXT,
            year INTEGER,
            duration INTEGER,
            durationHuman TEXT,
            audioCodec TEXT,
            container TEXT,
            videoCodec TEXT,
            videoResolution TEXT,
            sizeBytes INTEGER,
            sizeHuman TEXT,
            mediaHash TEXT,  -- Hash fingerprint to detect changes
            summary TEXT,  -- Episode description/summary
            originallyAvailableAt TEXT,  -- Original air date (ISO format)
            directors TEXT,  -- CSV of director names
            writers TEXT,  -- CSV of writer names
            actors TEXT,  -- CSV of actors formatted as "Name as Role"
            rating REAL,  -- Rating (0-10 scale)
            audienceRating REAL,  -- Audience rating (0-10 scale)
            available INTEGER DEFAULT 1,
            lastSeen TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (seasonRatingKey) REFERENCES seasons(seasonRatingKey) ON DELETE CASCADE,
            FOREIGN KEY (showRatingKey) REFERENCES tv_shows(ratingKey) ON DELETE CASCADE
        )
    """)
    
    # Artists table
    # Note: totalSizeBytes is raw value, totalSizeHuman is display-friendly
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS artists (
            ratingKey INTEGER PRIMARY KEY,
            artistName TEXT NOT NULL,
            totalAlbums INTEGER,
            totalTracks INTEGER,
            totalSizeBytes INTEGER,  -- Raw total size in bytes
            totalSizeHuman TEXT,  -- Display-friendly size (e.g., "50 GB")
            yearRange TEXT,  -- Year range (e.g., "2020-2023" or "2023" for single year)
            summary TEXT,  -- Artist biography/description
            genres TEXT,  -- CSV of genre names
            available INTEGER DEFAULT 1,
            lastSeen TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Albums table
    # Note: albumSizeBytes/albumDuration are raw values, albumSizeHuman/albumDurationHuman are display-friendly
    # albumContainers is CSV of container types (may vary across tracks, usually not critical for UI)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS albums (
            ratingKey INTEGER PRIMARY KEY,
            artistRatingKey INTEGER NOT NULL,
            title TEXT NOT NULL,
            year INTEGER,
            tracks INTEGER,
            albumSizeBytes INTEGER,  -- Raw total size in bytes
            albumSizeHuman TEXT,  -- Display-friendly size (e.g., "500 MB")
            albumDuration INTEGER,  -- Raw total duration in milliseconds
            albumDurationHuman TEXT,  -- Display-friendly duration (e.g., "45 mins")
            albumContainers TEXT,  -- CSV of container types (may vary per track)
            summary TEXT,  -- Album description/summary
            genres TEXT,  -- CSV of genre names
            originallyAvailableAt TEXT,  -- Original release date (ISO format)
            studio TEXT,  -- Record label/studio
            available INTEGER DEFAULT 1,
            lastSeen TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (artistRatingKey) REFERENCES artists(ratingKey) ON DELETE CASCADE
        )
    """)
    
    # Tracks table
    # Note: duration/sizeBytes are raw values, durationHuman/sizeHuman are display-friendly
    # mediaHash is a fingerprint to detect changes and skip unnecessary updates
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tracks (
            ratingKey INTEGER PRIMARY KEY,
            albumRatingKey INTEGER NOT NULL,
            artistRatingKey INTEGER NOT NULL,
            title TEXT NOT NULL,
            trackNumber INTEGER,
            duration INTEGER,  -- Raw duration in milliseconds
            durationHuman TEXT,  -- Display-friendly duration (e.g., "3 mins")
            sizeBytes INTEGER,  -- Raw size in bytes
            sizeHuman TEXT,  -- Display-friendly size (e.g., "5 MB")
            container TEXT,
            mediaHash TEXT,  -- Hash fingerprint to detect changes
            summary TEXT,  -- Track description/summary (when available)
            originallyAvailableAt TEXT,  -- Original release date (ISO format, when available)
            genres TEXT,  -- CSV of genre names (when available)
            available INTEGER DEFAULT 1,
            lastSeen TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (albumRatingKey) REFERENCES albums(ratingKey) ON DELETE CASCADE,
            FOREIGN KEY (artistRatingKey) REFERENCES artists(ratingKey) ON DELETE CASCADE
        )
    """)
    
    # Create indexes for better query performance
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_seasons_show ON seasons(showRatingKey)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_episodes_season ON episodes(seasonRatingKey)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_episodes_show ON episodes(showRatingKey)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_albums_artist ON albums(artistRatingKey)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tracks_album ON tracks(albumRatingKey)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tracks_artist ON tracks(artistRatingKey)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_movies_available ON movies(available)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tv_shows_available ON tv_shows(available)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_seasons_available ON seasons(available)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_episodes_available ON episodes(available)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_artists_available ON artists(available)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_albums_available ON albums(available)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tracks_available ON tracks(available)")
    
    # Create FTS5 virtual table for fast full-text search (optional but recommended)
    # This significantly speeds up search queries on large libraries
    try:
        cursor.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS search_fts USING fts5(
                type,
                ratingKey UNINDEXED,
                title,
                summary,
                year UNINDEXED,
                available UNINDEXED,
                content='',
                content_rowid='ratingKey'
            )
        """)
        
        # Populate FTS5 table with data from all searchable tables
        cursor.execute("""
            INSERT INTO search_fts(type, ratingKey, title, summary, year, available)
            SELECT 'movie', ratingKey, title, COALESCE(summary, ''), year, available
            FROM movies WHERE available = 1
        """)
        
        cursor.execute("""
            INSERT INTO search_fts(type, ratingKey, title, summary, year, available)
            SELECT 'show', ratingKey, title, COALESCE(summary, ''), NULL, available
            FROM tv_shows WHERE available = 1
        """)
        
        cursor.execute("""
            INSERT INTO search_fts(type, ratingKey, title, summary, year, available)
            SELECT 'artist', ratingKey, artistName, COALESCE(summary, ''), NULL, available
            FROM artists WHERE available = 1
        """)
        
        logger.info("FTS5 search index created and populated")
    except sqlite3.OperationalError as e:
        # FTS5 might not be available in this SQLite build
        logger.warning(f"FTS5 not available, search will use LIKE fallback: {e}")
    
    conn.commit()
    
    # Run migrations if needed
    run_migrations(conn, current_version, SCHEMA_VERSION)
    
    conn.close()
    logger.info(f"Database initialized at {db_path}")

def mark_unavailable(conn, table_name, seen_keys, library_type, key_column="ratingKey"):
    """Mark items as unavailable if they weren't seen in the current scan."""
    logger = logging.getLogger(__name__)
    cursor = conn.cursor()
    
    if not seen_keys:
        # If no items were seen, mark all as unavailable
        cursor.execute(f"UPDATE {table_name} SET available = 0 WHERE available = 1")
        affected = cursor.rowcount
    else:
        # Mark items not in seen list as unavailable
        placeholders = ','.join('?' * len(seen_keys))
        cursor.execute(
            f"UPDATE {table_name} SET available = 0 WHERE {key_column} NOT IN ({placeholders}) AND available = 1",
            seen_keys
        )
        affected = cursor.rowcount
    
    conn.commit()
    if affected > 0:
        logger.info(f"  Marked {affected} {library_type} item(s) as unavailable")
    
    # Update FTS5 search index to reflect availability changes
    try:
        if table_name in ['movies', 'tv_shows', 'artists']:
            type_map = {'movies': 'movie', 'tv_shows': 'show', 'artists': 'artist'}
            fts_type = type_map.get(table_name)
            if fts_type:
                if not seen_keys:
                    cursor.execute(f"""
                        UPDATE search_fts 
                        SET available = 0 
                        WHERE type = ? AND available = 1
                    """, (fts_type,))
                else:
                    placeholders = ','.join('?' * len(seen_keys))
                    cursor.execute(f"""
                        UPDATE search_fts 
                        SET available = 0 
                        WHERE type = ? AND ratingKey NOT IN ({placeholders}) AND available = 1
                    """, [fts_type] + seen_keys)
                conn.commit()
    except sqlite3.OperationalError:
        pass  # FTS5 table might not exist

def process_movies(library: LibrarySection, plex_server: PlexServer, conn: sqlite3.Connection):
    """Process movies library."""
    logger = logging.getLogger(__name__)
    logger.info(f"Processing {library.title} library...")
    
    # Fetch movies with retry logic
    movies = None
    max_retries = 3
    for attempt in range(max_retries):
        try:
            logger.info(f"Fetching movies from library (attempt {attempt + 1}/{max_retries})...")
            movies = library.all()
            break
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            if attempt < max_retries - 1:
                wait_time = (attempt + 1) * 5
                logger.warning(f"  Timeout fetching movies, retrying in {wait_time}s...")
                time.sleep(wait_time)
                continue
            else:
                logger.error(f"Failed to fetch movies after {max_retries} attempts: {e}")
                return
    
    if not movies:
        logger.warning("No movies retrieved")
        # Mark all movies as unavailable
        mark_unavailable(conn, "movies", [], "movie")
        return
    
    cursor = conn.cursor()
    image_folder = IMAGE_FOLDERS.get("Movies")
    os.makedirs(image_folder, exist_ok=True)
    
    total_count = len(movies)
    logger.info(f"Found {total_count} movies. Processing...")
    
    seen_rating_keys = []
    current_time = datetime.now().isoformat()
    movies_data = []
    image_tasks = []
    existing_hashes = {}  # Cache existing hashes to skip unchanged items
    
    # Pre-fetch existing hashes for comparison
    if not USE_PARALLEL:  # Only check hashes if not using parallel (to avoid extra DB queries)
        cursor.execute("SELECT ratingKey, mediaHash FROM movies WHERE available = 1")
        existing_hashes = {row[0]: row[1] for row in cursor.fetchall()}
    
    for idx, movie in enumerate(movies, 1):
        try:
            if idx % 50 == 0 or idx == total_count:
                logger.info(f"  Progress: {idx}/{total_count} ({idx*100//total_count}%)")
            
            # Get media info
            media = movie.media[0] if movie.media else None
            if not media:
                logger.warning(f"  Skipping movie '{movie.title}': no media found")
                continue
                
            part = media.parts[0] if media.parts else None
            if not part:
                logger.warning(f"  Skipping movie '{movie.title}': no media parts found")
                continue
            
            rating_key = validate_rating_key(movie.ratingKey)
            seen_rating_keys.append(rating_key)
            
            size_bytes = part.size or 0
            duration = movie.duration or 0
            audio_codec = format_codec(media.audioCodec)
            video_codec = format_codec(media.videoCodec)
            video_resolution = format_resolution(media.videoResolution)
            
            # Calculate media hash to detect changes
            media_hash = calculate_media_hash(
                size_bytes, duration, video_codec, video_resolution,
                part.container, movie.title, movie.year
            )
            
            # Skip if unchanged (only if not using parallel mode for efficiency)
            if not USE_PARALLEL and rating_key in existing_hashes and existing_hashes[rating_key] == media_hash:
                logger.debug(f"  Skipping unchanged movie '{movie.title}' (ratingKey: {rating_key})")
                continue
            
            # Prepare image download task
            if DOWNLOAD_IMAGES:
                image_path = os.path.join(image_folder, f"{rating_key}.thumb.webp")
                image_tasks.append((movie, image_path, plex_server))
            
            # Extract metadata
            summary = extract_summary(movie)
            tagline = extract_tagline(movie)
            genres = extract_genres(movie)
            studio = extract_studio(movie)
            directors = extract_directors(movie)
            writers = extract_writers(movie)
            producers = extract_producers(movie)
            actors = extract_actors(movie)
            originally_available = extract_originally_available(movie)
            rating = extract_rating(movie)
            audience_rating = extract_audience_rating(movie)
            
            # Collect movie data for batch insert
            # Note: duration/sizeBytes are raw values, durationHuman/sizeHuman are display-friendly
            movies_data.append((
                rating_key,
                movie.title,
                movie.year,
                movie.contentRating,
                duration,  # Raw duration in milliseconds
                human_readable_duration(duration) if duration else None,  # Display-friendly
                audio_codec,
                part.container,
                video_codec,
                video_resolution,
                size_bytes,  # Raw size in bytes
                human_readable_size(size_bytes),  # Display-friendly
                media_hash,  # Hash fingerprint
                summary,
                tagline,
                genres,
                studio,
                directors,
                writers,
                producers,
                actors,
                originally_available,
                rating,
                audience_rating,
                1,  # available
                current_time
            ))
        except ValueError as e:
            logger.error(f"  Error processing movie '{movie.title if hasattr(movie, 'title') else 'unknown'}': {e}")
            continue
        except Exception as e:
            logger.error(f"  Unexpected error processing movie '{movie.title if hasattr(movie, 'title') else 'unknown'}': {e}", exc_info=True)
            continue
    
    # Download images (parallel or sequential)
    if DOWNLOAD_IMAGES and image_tasks:
        logger.info("Downloading images (this may take a while)...")
        if USE_PARALLEL:
            image_stats = download_images_parallel(image_tasks, max_workers=10)
        else:
            image_stats = {'downloaded': 0, 'failed': 0}
            for movie, image_path, plex_server in image_tasks:
                if download_and_convert_image(movie, image_path, plex_server):
                    image_stats['downloaded'] += 1
                else:
                    image_stats['failed'] += 1
                    logger.warning(f"  Image download failed for movie '{movie.title if hasattr(movie, 'title') else 'unknown'}'")
    else:
        image_stats = {'downloaded': 0, 'failed': 0}
    
    # Batch insert all movies
    if movies_data:
        cursor.executemany("""
            INSERT OR REPLACE INTO movies (
                ratingKey, title, year, contentRating, duration, durationHuman,
                audioCodec, container, videoCodec, videoResolution,
                sizeBytes, sizeHuman, mediaHash, summary, tagline, genres,
                studio, directors, writers, producers, actors,
                originallyAvailableAt, rating, audienceRating,
                available, lastSeen
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, movies_data)
        conn.commit()
        logger.info(f"  Inserted/updated {len(movies_data)} movies")
        
        # Update FTS5 search index if it exists
        try:
            cursor.executemany("""
                INSERT OR REPLACE INTO search_fts(type, ratingKey, title, summary, year, available)
                VALUES ('movie', ?, ?, COALESCE(?, ''), ?, ?)
            """, [(row[0], row[1], row[14], row[2], 1) for row in movies_data])
        except sqlite3.OperationalError:
            pass  # FTS5 table might not exist
    
    # Mark unavailable movies
    mark_unavailable(conn, "movies", seen_rating_keys, "movie")
    
    logger.info(f"\nProcessed {len(seen_rating_keys)} movies")
    logger.info(f"Images: {image_stats['downloaded']} downloaded, {image_stats['failed']} failed")

def process_tvshows(library: LibrarySection, plex_server: PlexServer, conn: sqlite3.Connection):
    """Process TV shows library with full episode support."""
    logger = logging.getLogger(__name__)
    logger.info(f"Processing {library.title} library...")
    
    # Fetch shows with retry logic
    shows = None
    max_retries = 3
    for attempt in range(max_retries):
        try:
            logger.info(f"Fetching shows from library (attempt {attempt + 1}/{max_retries})...")
            shows = library.all()
            break
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            if attempt < max_retries - 1:
                wait_time = (attempt + 1) * 5
                logger.warning(f"  Timeout fetching shows, retrying in {wait_time}s...")
                time.sleep(wait_time)
                continue
            else:
                logger.error(f"Failed to fetch shows after {max_retries} attempts: {e}")
                return
    
    if not shows:
        logger.warning("No shows retrieved")
        # Mark all as unavailable
        mark_unavailable(conn, "tv_shows", [], "show")
        mark_unavailable(conn, "seasons", [], "season")
        mark_unavailable(conn, "episodes", [], "episode")
        return
    
    cursor = conn.cursor()
    image_folder = IMAGE_FOLDERS.get("TV Shows")
    os.makedirs(image_folder, exist_ok=True)
    
    total_count = len(shows)
    logger.info(f"Found {total_count} shows. Processing...")
    
    seen_show_keys = []
    seen_season_keys = []
    seen_episode_keys = []
    current_time = datetime.now().isoformat()
    
    # Collect data for batch inserts
    episodes_data = []
    seasons_data = []
    shows_data = []
    
    # Collect all image tasks for parallel download
    show_image_tasks = []
    season_image_tasks = []
    episode_image_tasks = []
    
    # Pre-fetch existing episode hashes for comparison
    existing_episode_hashes = {}
    if not USE_PARALLEL:
        cursor.execute("SELECT ratingKey, mediaHash FROM episodes WHERE available = 1")
        existing_episode_hashes = {row[0]: row[1] for row in cursor.fetchall()}
    
    for idx, show in enumerate(shows, 1):
        try:
            if idx % 10 == 0 or idx == total_count:
                logger.info(f"  Progress: {idx}/{total_count} ({idx*100//total_count}%)")
            
            show_rating_key = validate_rating_key(show.ratingKey)
            seen_show_keys.append(show_rating_key)
            
            show_size_bytes = 0
            show_total_episodes = 0
            show_years = []
            show_video_resolutions = []
            show_audio_codecs = []
            show_video_codecs = []
            show_containers = []
            show_total_duration = 0
            
            # Fetch seasons with retry
            seasons_list = fetch_with_retry(
                lambda: show.seasons(),
                f"seasons for {show.title}",
                max_retries=3
            )
            
            for season in seasons_list:
                season_rating_key = validate_rating_key(season.ratingKey)
                seen_season_keys.append(season_rating_key)
                
                # Process season (handles episodes internally)
                episode_image_stats = {'downloaded': 0, 'failed': 0}
                season_result = process_season(
                    season, show_rating_key, image_folder,
                    plex_server, current_time, episode_image_stats
                )
                
                # Filter episodes by hash if not using parallel
                filtered_episodes = []
                for ep_data in season_result['episodes_data']:
                    ep_rating_key = ep_data[0]  # ratingKey is first element
                    seen_episode_keys.append(ep_rating_key)
                    
                    # Skip if unchanged (only if not using parallel mode)
                    if not USE_PARALLEL and ep_rating_key in existing_episode_hashes:
                        # mediaHash is at index 14 (after sizeHuman at 13)
                        if len(ep_data) > 14 and ep_data[14] == existing_episode_hashes[ep_rating_key]:
                            logger.debug(f"    Skipping unchanged episode (ratingKey: {ep_rating_key})")
                            continue
                    
                    filtered_episodes.append(ep_data)
                
                # Update counters
                season_total_episodes = len(filtered_episodes)
                show_total_episodes += season_total_episodes
                
                # Recalculate season stats based on filtered episodes
                if filtered_episodes:
                    # Recalculate totals from filtered episodes
                    season_total_duration = sum(ep[6] for ep in filtered_episodes)  # duration at index 6
                    season_size_bytes = sum(ep[12] for ep in filtered_episodes)  # sizeBytes at index 12
                    show_total_duration += season_total_duration
                    show_size_bytes += season_size_bytes
                    
                    # Update season data with correct totals
                    season_data_list = list(season_result['season_data'])
                    season_data_list[3] = season_total_episodes  # seasonTotalEpisode
                    season_data_list[4] = season_total_duration // season_total_episodes if season_total_episodes > 0 else 0  # avgSeasonEpisodeDuration
                    season_data_list[5] = human_readable_duration(season_data_list[4]) if season_data_list[4] > 0 else None  # avgSeasonEpisodeDurationHuman
                    season_data_list[6] = season_size_bytes  # seasonSizeBytes
                    season_data_list[7] = human_readable_size(season_size_bytes)  # seasonSizeHuman
                    seasons_data.append(tuple(season_data_list))
                else:
                    # Keep original season data even if no episodes
                    seasons_data.append(season_result['season_data'])
                
                # Collect episode data
                episodes_data.extend(filtered_episodes)
                
                # Collect episode image tasks for parallel download
                if USE_PARALLEL and DOWNLOAD_IMAGES:
                    episode_image_tasks.extend(season_result.get('episode_image_tasks', []))
                
                # Aggregate show-level stats
                show_video_resolutions.extend(season_result['video_resolutions'])
                show_audio_codecs.extend(season_result['audio_codecs'])
                show_video_codecs.extend(season_result['video_codecs'])
                show_containers.extend(season_result['containers'])
                show_years.extend(season_result['years'])
                
                # Collect season image task for parallel download
                if DOWNLOAD_IMAGES:
                    season_image_path = os.path.join(image_folder, f"{season_rating_key}.thumb.webp")
                    season_image_tasks.append((season, season_image_path, plex_server))
            
            # Collect show image task for parallel download
            if DOWNLOAD_IMAGES:
                image_path = os.path.join(image_folder, f"{show_rating_key}.thumb.webp")
                show_image_tasks.append((show, image_path, plex_server))
            
            # Calculate average episode duration for show
            avg_show_duration = show_total_duration // show_total_episodes if show_total_episodes > 0 else (show.duration or 0)
            
            # Format year range (handles single year case)
            show_year_range = format_year_range(show_years)
            
            # Extract metadata
            summary = extract_summary(show)
            genres = extract_genres(show)
            studio = extract_studio(show)
            actors = extract_actors(show)
            originally_available = extract_originally_available(show)
            rating = extract_rating(show)
            audience_rating = extract_audience_rating(show)
            
            # Collect show data for batch insert
            # Note: avgEpisodeDuration/showSizeBytes are raw values, avgEpisodeDurationHuman/showSizeHuman are display-friendly
            shows_data.append((
                show_rating_key,
                show.title,
                show.contentRating,
                avg_show_duration,  # Raw average duration in milliseconds
                human_readable_duration(avg_show_duration) if avg_show_duration else None,  # Display-friendly
                show.seasonCount,
                show_total_episodes,
                show_size_bytes,  # Raw total size in bytes
                human_readable_size(show_size_bytes),  # Display-friendly
                ", ".join(sorted(set([r for r in show_video_resolutions if r]))),  # CSV of unique values
                ", ".join(sorted(set([c for c in show_audio_codecs if c]))),
                ", ".join(sorted(set([c for c in show_video_codecs if c]))),
                ", ".join(sorted(set([c for c in show_containers if c]))),
                show_year_range,
                summary,
                genres,
                studio,
                actors,
                originally_available,
                rating,
                audience_rating,
                1,  # available
                current_time
            ))
            
        except ValueError as e:
            logger.error(f"  Error processing show '{show.title if hasattr(show, 'title') else 'unknown'}': {e}")
            continue
        except Exception as e:
            logger.error(f"  Unexpected error processing show '{show.title if hasattr(show, 'title') else 'unknown'}': {e}", exc_info=True)
            continue
    
    # Download images in parallel or sequentially
    if DOWNLOAD_IMAGES:
        logger.info("Downloading images (this may take a while)...")
        if USE_PARALLEL:
            all_image_tasks = show_image_tasks + season_image_tasks + episode_image_tasks
            if all_image_tasks:
                image_stats = download_images_parallel(all_image_tasks, max_workers=10)
                show_images_downloaded = sum(1 for _ in show_image_tasks if True)  # Will be updated by parallel function
                season_images_downloaded = sum(1 for _ in season_image_tasks if True)
                episode_images_downloaded = sum(1 for _ in episode_image_tasks if True)
                # Note: parallel function returns total stats, individual counts would need tracking
                logger.info(f"  Downloaded {image_stats['downloaded']} images, {image_stats['failed']} failed")
        else:
            # Sequential downloads
            show_images_downloaded = 0
            show_images_failed = 0
            for show, image_path, plex_server in show_image_tasks:
                if download_and_convert_image(show, image_path, plex_server):
                    show_images_downloaded += 1
                else:
                    show_images_failed += 1
                    logger.warning(f"  Image download failed for show '{show.title}'")
            
            season_images_downloaded = 0
            season_images_failed = 0
            for season, image_path, plex_server in season_image_tasks:
                if download_and_convert_image(season, image_path, plex_server):
                    season_images_downloaded += 1
                else:
                    season_images_failed += 1
            
            episode_images_downloaded = 0
            episode_images_failed = 0
            for episode, image_path, plex_server in episode_image_tasks:
                if download_and_convert_image(episode, image_path, plex_server):
                    episode_images_downloaded += 1
                else:
                    episode_images_failed += 1
    else:
        show_images_downloaded = show_images_failed = 0
        season_images_downloaded = season_images_failed = 0
        episode_images_downloaded = episode_images_failed = 0
    
    # Batch insert all data (order matters due to foreign keys: shows -> seasons -> episodes)
    if shows_data:
        cursor.executemany("""
            INSERT OR REPLACE INTO tv_shows (
                ratingKey, title, contentRating, avgEpisodeDuration, avgEpisodeDurationHuman,
                seasonCount, showTotalEpisode, showSizeBytes, showSizeHuman,
                avgVideoResolutions, avgAudioCodecs, avgVideoCodecs,
                avgContainers, showYearRange, summary, genres, studio, actors,
                originallyAvailableAt, rating, audienceRating,
                available, lastSeen
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, shows_data)
        logger.info(f"  Inserted/updated {len(shows_data)} shows")
    
    if seasons_data:
        cursor.executemany("""
            INSERT OR REPLACE INTO seasons (
                seasonRatingKey, showRatingKey, seasonNumber, seasonTotalEpisode,
                avgSeasonEpisodeDuration, avgSeasonEpisodeDurationHuman,
                seasonSizeBytes, seasonSizeHuman, avgSeasonVideoResolution,
                avgSeasonAudioCodec, avgSeasonVideoCodec, avgSeasonContainer,
                yearRange, summary, title, originallyAvailableAt, available, lastSeen
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, seasons_data)
        logger.info(f"  Inserted/updated {len(seasons_data)} seasons")
    
    if episodes_data:
        cursor.executemany("""
            INSERT OR REPLACE INTO episodes (
                ratingKey, seasonRatingKey, showRatingKey, episodeNumber, title, year,
                duration, durationHuman, audioCodec, container, videoCodec,
                videoResolution, sizeBytes, sizeHuman, mediaHash, summary,
                originallyAvailableAt, directors, writers, actors,
                rating, audienceRating, available, lastSeen
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, episodes_data)
        logger.info(f"  Inserted/updated {len(episodes_data)} episodes")
    
    conn.commit()
    
    # Mark unavailable items
    mark_unavailable(conn, "tv_shows", seen_show_keys, "show")
    mark_unavailable(conn, "seasons", seen_season_keys, "season")
    mark_unavailable(conn, "episodes", seen_episode_keys, "episode")
    
    logger.info(f"\nProcessed {len(seen_show_keys)} shows")
    if DOWNLOAD_IMAGES:
        if USE_PARALLEL:
            logger.info(f"Images: {len(show_image_tasks + season_image_tasks + episode_image_tasks)} total tasks processed")
        else:
            logger.info(f"Show images: {show_images_downloaded} downloaded, {show_images_failed} failed")
            logger.info(f"Season images: {season_images_downloaded} downloaded, {season_images_failed} failed")
            logger.info(f"Episode images: {episode_images_downloaded} downloaded, {episode_images_failed} failed")

def process_music(library: LibrarySection, plex_server: PlexServer, conn: sqlite3.Connection):
    """Process music library with full track support."""
    logger = logging.getLogger(__name__)
    logger.info(f"Processing {library.title} library...")
    
    # Fetch artists with retry logic
    artists = None
    max_retries = 3
    for attempt in range(max_retries):
        try:
            logger.info(f"Fetching artists from library (attempt {attempt + 1}/{max_retries})...")
            artists = library.all()
            break
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            if attempt < max_retries - 1:
                wait_time = (attempt + 1) * 5
                logger.warning(f"  Timeout fetching artists, retrying in {wait_time}s...")
                time.sleep(wait_time)
                continue
            else:
                logger.error(f"Failed to fetch artists after {max_retries} attempts: {e}")
                return
    
    if not artists:
        logger.warning("No artists retrieved")
        # Mark all as unavailable
        mark_unavailable(conn, "artists", [], "artist")
        mark_unavailable(conn, "albums", [], "album")
        mark_unavailable(conn, "tracks", [], "track")
        return
    
    cursor = conn.cursor()
    image_folder = IMAGE_FOLDERS.get("Music")
    os.makedirs(image_folder, exist_ok=True)
    
    total_count = len(artists)
    logger.info(f"Found {total_count} artists. Processing...")
    
    # Track seen items for availability marking
    seen_artist_keys = []
    seen_album_keys = []
    seen_track_keys = []
    current_time = datetime.now().isoformat()
    
    # Collect data for batch inserts
    tracks_data = []
    albums_data = []
    artists_data = []
    
    # Collect image tasks for parallel download
    artist_image_tasks = []
    album_image_tasks = []
    
    # Pre-fetch existing track hashes for comparison
    existing_track_hashes = {}
    if not USE_PARALLEL:
        cursor.execute("SELECT ratingKey, mediaHash FROM tracks WHERE available = 1")
        existing_track_hashes = {row[0]: row[1] for row in cursor.fetchall()}
    
    for idx, artist in enumerate(artists, 1):
        try:
            if idx % 10 == 0 or idx == total_count:
                logger.info(f"  Progress: {idx}/{total_count} ({idx*100//total_count}%)")
            
            artist_name = artist.title
            artist_rating_key = validate_rating_key(artist.ratingKey)
            seen_artist_keys.append(artist_rating_key)
            
            # Collect artist image task for parallel download
            if DOWNLOAD_IMAGES:
                image_path = os.path.join(image_folder, f"{artist_rating_key}.thumb.webp")
                artist_image_tasks.append((artist, image_path, plex_server))
            
            # Track artist totals
            artist_total_size_bytes = 0
            artist_total_tracks = 0
            artist_total_albums = 0
            artist_years = []
            
            # Fetch albums with retry
            albums_list = fetch_with_retry(
                lambda: artist.albums(),
                f"albums for {artist_name}",
                max_retries=3
            )
            
            for album in albums_list or []:
                album_rating_key = validate_rating_key(album.ratingKey)
                seen_album_keys.append(album_rating_key)
                
                # Process album and tracks
                album_result, album_size_bytes, album_duration = process_album(
                    album, image_folder, plex_server, artist_rating_key, current_time,
                    seen_track_keys, existing_track_hashes
                )
                
                # Filter tracks by hash if not using parallel
                filtered_tracks = []
                for track_data in album_result['tracks_data']:
                    track_rating_key = track_data[0]  # ratingKey is first element
                    if track_rating_key not in seen_track_keys:
                        seen_track_keys.append(track_rating_key)
                    
                    # Skip if unchanged (only if not using parallel mode)
                    if not USE_PARALLEL and track_rating_key in existing_track_hashes:
                        # mediaHash is at index 10 (after container)
                        if len(track_data) > 10 and track_data[10] == existing_track_hashes[track_rating_key]:
                            logger.debug(f"    Skipping unchanged track (ratingKey: {track_rating_key})")
                            continue
                    
                    filtered_tracks.append(track_data)
                
                # Collect track and album data
                tracks_data.extend(filtered_tracks)
                albums_data.append(album_result['album_data'])
                
            # Collect album image task for parallel download
            if DOWNLOAD_IMAGES:
                album_image_path = os.path.join(image_folder, f"{album_rating_key}.thumb.webp")
                album_image_tasks.append((album, album_image_path, plex_server))
                
                artist_total_size_bytes += album_size_bytes
                artist_total_tracks += len(filtered_tracks)
                artist_total_albums += 1
                artist_years.append(album.year)
            
            # Format year range (handles single year case)
            year_range = format_year_range(artist_years)
            
            # Extract metadata
            summary = extract_summary(artist)
            genres = extract_genres(artist)
            
            # Collect artist data for batch insert
            # Note: totalSizeBytes is raw value, totalSizeHuman is display-friendly
            artists_data.append((
                artist_rating_key,
                artist_name,
                artist_total_albums,
                artist_total_tracks,
                artist_total_size_bytes,  # Raw total size in bytes
                human_readable_size(artist_total_size_bytes),  # Display-friendly
                year_range,
                summary,
                genres,
                1,  # available
                current_time
            ))
        except ValueError as e:
            logger.error(f"  Error processing artist '{artist.title if hasattr(artist, 'title') else 'unknown'}': {e}")
            continue
        except Exception as e:
            logger.error(f"  Unexpected error processing artist '{artist.title if hasattr(artist, 'title') else 'unknown'}': {e}", exc_info=True)
            continue
    
    # Download images in parallel or sequentially
    if DOWNLOAD_IMAGES:
        logger.info("Downloading images (this may take a while)...")
        if USE_PARALLEL:
            all_image_tasks = artist_image_tasks + album_image_tasks
            if all_image_tasks:
                image_stats = download_images_parallel(all_image_tasks, max_workers=10)
                logger.info(f"  Downloaded {image_stats['downloaded']} images, {image_stats['failed']} failed")
        else:
            # Sequential downloads
            artist_images_downloaded = 0
            artist_images_failed = 0
            for artist, image_path, plex_server in artist_image_tasks:
                if download_and_convert_image(artist, image_path, plex_server):
                    artist_images_downloaded += 1
                else:
                    artist_images_failed += 1
                    logger.warning(f"  Image download failed for artist '{artist.title}'")
            
            album_images_downloaded = 0
            album_images_failed = 0
            for album, image_path, plex_server in album_image_tasks:
                if download_and_convert_image(album, image_path, plex_server):
                    album_images_downloaded += 1
                else:
                    album_images_failed += 1
    
    # Batch insert all data (order matters due to foreign keys: artists -> albums -> tracks)
    if artists_data:
        cursor.executemany("""
            INSERT OR REPLACE INTO artists (
                ratingKey, artistName, totalAlbums, totalTracks,
                totalSizeBytes, totalSizeHuman, yearRange, summary, genres,
                available, lastSeen
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, artists_data)
        logger.info(f"  Inserted/updated {len(artists_data)} artists")
    
    if albums_data:
        cursor.executemany("""
            INSERT OR REPLACE INTO albums (
                ratingKey, artistRatingKey, title, year, tracks,
                albumSizeBytes, albumSizeHuman, albumDuration, albumDurationHuman,
                albumContainers, summary, genres, originallyAvailableAt, studio,
                available, lastSeen
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, albums_data)
        logger.info(f"  Inserted/updated {len(albums_data)} albums")
    
    if tracks_data:
        cursor.executemany("""
            INSERT OR REPLACE INTO tracks (
                ratingKey, albumRatingKey, artistRatingKey, title, trackNumber,
                duration, durationHuman, sizeBytes, sizeHuman, container,
                mediaHash, summary, originallyAvailableAt, genres,
                available, lastSeen
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, tracks_data)
        logger.info(f"  Inserted/updated {len(tracks_data)} tracks")
    
    conn.commit()
    
    # Mark unavailable items
    mark_unavailable(conn, "artists", seen_artist_keys, "artist")
    mark_unavailable(conn, "albums", seen_album_keys, "album")
    mark_unavailable(conn, "tracks", seen_track_keys, "track")
    
    logger.info(f"\nProcessed {len(seen_artist_keys)} artists")
    if DOWNLOAD_IMAGES and not USE_PARALLEL:
        logger.info(f"Artist images: {artist_images_downloaded} downloaded, {artist_images_failed} failed")
        logger.info(f"Album images: {album_images_downloaded} downloaded, {album_images_failed} failed")

def process_album(album: Album, image_folder: str, plex_server: PlexServer, 
                 artist_rating_key: int, current_time: str, seen_track_keys: list,
                 existing_track_hashes=None):
    """Process a single album and its tracks, returning data for batch insert."""
    logger = logging.getLogger(__name__)
    if existing_track_hashes is None:
        existing_track_hashes = {}
    
    album_rating_key = validate_rating_key(album.ratingKey)
    album_size_bytes = 0
    total_duration = 0
    containers = set()
    track_count = 0
    tracks_data = []
    
    # Track image stats locally (not mutated externally)
    image_stats = {'downloaded': 0, 'failed': 0}
    
    # Download and convert album thumbnail (only if not using parallel mode)
    if not (USE_PARALLEL and DOWNLOAD_IMAGES):
        image_path = os.path.join(image_folder, f"{album_rating_key}.thumb.webp")
        if DOWNLOAD_IMAGES and download_and_convert_image(album, image_path, plex_server):
            image_stats['downloaded'] += 1
        else:
            image_stats['failed'] += 1
    
    # Fetch tracks with retry
    tracks_list = fetch_with_retry(
        lambda: album.tracks(),
        f"tracks for album {album.title}",
        max_retries=3
    )
    
    # Process each track
    for track in tracks_list or []:
        track_rating_key = validate_rating_key(track.ratingKey)
        if track_rating_key not in seen_track_keys:
            seen_track_keys.append(track_rating_key)
        track_count += 1
        
        track_size_bytes = 0
        track_duration = 0
        track_container = None
        
        for media in track.media:
            containers.add(media.container)
            track_duration = media.duration or 0
            total_duration += track_duration
            for part in media.parts:
                part_size = part.size or 0
                track_size_bytes += part_size
                album_size_bytes += part_size
                if not track_container:
                    track_container = media.container
        
        # Calculate media hash to detect changes
        media_hash = calculate_media_hash(
            track_size_bytes, track_duration, None, None,  # No video codec/resolution for audio
            track_container, track.title, album.year
        )
        
        # Extract track metadata
        track_summary = extract_summary(track)
        track_originally_available = extract_originally_available(track)
        track_genres = extract_genres(track)
        
        # Collect track data for batch insert
        # Note: duration/sizeBytes are raw values, durationHuman/sizeHuman are display-friendly
        tracks_data.append((
            track_rating_key,
            album_rating_key,
            artist_rating_key,
            track.title,
            track.index,
            track_duration,  # Raw duration in milliseconds
            human_readable_duration(track_duration) if track_duration else None,  # Display-friendly
            track_size_bytes,  # Raw size in bytes
            human_readable_size(track_size_bytes),  # Display-friendly
            track_container,
            media_hash,  # Hash fingerprint
            track_summary,
            track_originally_available,
            track_genres,
            1,  # available
            current_time
        ))
    
    # Extract album metadata
    album_summary = extract_summary(album)
    album_genres = extract_genres(album)
    album_originally_available = extract_originally_available(album)
    album_studio = extract_studio(album)
    
    # Prepare album data for batch insert
    # Note: albumSizeBytes/albumDuration are raw values, albumSizeHuman/albumDurationHuman are display-friendly
    # albumContainers is CSV (may vary per track, usually not critical for UI)
    album_data = (
        album_rating_key,
        artist_rating_key,
        album.title,
        album.year,
        track_count,
        album_size_bytes,  # Raw total size in bytes
        human_readable_size(album_size_bytes),  # Display-friendly
        total_duration,  # Raw total duration in milliseconds
        human_readable_duration(total_duration) if total_duration else None,  # Display-friendly
        ", ".join(sorted(containers)),  # CSV of container types
        album_summary,
        album_genres,
        album_originally_available,
        album_studio,
        1,  # available
        current_time
    )
    
    return {
        "tracks": track_count,
        "image_stats": image_stats,
        "tracks_data": tracks_data,
        "album_data": album_data
    }, album_size_bytes, total_duration

def main():
    """Main function to sync all libraries from Plex."""
    # Parse CLI arguments
    args = parse_args()
    
    # Setup logging
    logger = setup_logging(verbose=args.verbose, log_file=args.log_file)
    
    # Update global settings from CLI args
    global USE_PARALLEL, DOWNLOAD_IMAGES, DB_PATH
    USE_PARALLEL = args.fast
    DOWNLOAD_IMAGES = not args.no_images
    if args.db_path:
        DB_PATH = args.db_path
    
    if not PLEX_URL or not PLEX_TOKEN:
        logger.error("PLEX_URL and PLEX_TOKEN environment variables must be set")
        return 1
    
    # Ensure database directory exists
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    
    # Initialize database
    init_database(DB_PATH, rebuild=args.rebuild_db)
    
    logger.info(f"Connecting to Plex server at {PLEX_URL}...")
    try:
        plex = PlexServer(PLEX_URL, PLEX_TOKEN, timeout=300)  # 5 minute timeout
    except Exception as e:
        logger.error(f"Failed to connect to Plex server: {e}")
        logger.info("\nTroubleshooting:")
        logger.info("  1. Verify PLEX_URL is correct and accessible")
        logger.info("  2. Verify PLEX_TOKEN is correct")
        logger.info("  3. Check if Plex server is running")
        return 1
    
    # Connect to database
    conn = sqlite3.connect(DB_PATH)
    # Enable foreign keys for this connection
    conn.execute("PRAGMA foreign_keys = ON")
    
    try:
        # Process each library
        for library_name in LIBRARY_NAMES:
            try:
                library = plex.library.section(library_name)
                logger.info(f"\n{'='*50}")
                logger.info(f"Processing library: {library_name}")
                logger.info(f"{'='*50}")
                
                if library_name == "Movies":
                    process_movies(library, plex, conn)
                elif library_name == "TV Shows":
                    process_tvshows(library, plex, conn)
                elif library_name == "Music":
                    process_music(library, plex, conn)
                else:
                    logger.warning(f"Unknown library type: {library_name}")
            except Exception as e:
                logger.error(f"Error processing library {library_name}: {e}", exc_info=True)
                continue
        
        # Optimize database after sync
        logger.info("\nOptimizing database...")
        conn.execute("VACUUM")
        conn.execute("ANALYZE")
        logger.info("Database optimization complete")
    finally:
        conn.close()
    
    logger.info("\n" + "="*50)
    logger.info("Sync complete!")
    logger.info("="*50)
    return 0

if __name__ == "__main__":
    exit(main())
