# Windows One-Click Setup

For Windows users who want a simple, one-click solution to run Plex Collection Sync.

## Option 1: Batch File (Simplest)

1. **Create your `.env` file** (copy from `.env.example` and edit with your Plex credentials)

2. **Double-click `start.bat`**

That's it! The script will:
- Check for Python and Node.js
- Install dependencies automatically
- Run the initial sync
- Start the backend server
- Open the API in your browser

The server will run until you close the window or press Ctrl+C.

## Option 2: GUI Launcher (Recommended)

### Using the Python Script

1. **Create your `.env` file**

2. **Run the GUI launcher:**
   ```bash
   python launcher.py
   ```

3. **Click "Start Sync & Server"**

The GUI provides:
- Visual progress indicators
- Real-time log output
- Easy server control (start/stop)
- One-click API access

### Creating a Standalone Executable

To create a `.exe` file that doesn't require Python:

1. **Install PyInstaller:**
   ```bash
   pip install pyinstaller
   ```

2. **Build the executable:**
   ```bash
   build_windows_exe.bat
   ```

3. **Distribute `dist/PlexSyncLauncher.exe`**

Users can then:
- Double-click `PlexSyncLauncher.exe`
- No Python/Node.js installation needed (if bundled)
- Full GUI experience

## Requirements

**For Batch File (`start.bat`):**
- **Python 3.9+** - [Download](https://www.python.org/downloads/)
  - ⚠️ **Important:** Check "Add Python to PATH" during installation!
- **Node.js 18+** - [Download](https://nodejs.org/)
- **`.env` file** - See `.env.example`

**For GUI Launcher (`launcher.py`):**
- Same as batch file (Python + Node.js)
- tkinter (usually bundled with Python on Windows)

**For Standalone Executable (`PlexSyncLauncher.exe`):**
- **No Python/Node.js needed!** (if properly bundled)
- Just the `.exe` file and `.env` file
- Windows 10/11

The batch file and GUI will check for these automatically and guide you if anything is missing.

## Troubleshooting

### "Python not found"
- Install Python from https://www.python.org/
- Make sure to check "Add Python to PATH" during installation
- Restart your computer after installation

### "Node.js not found"
- Install Node.js from https://nodejs.org/
- Restart your computer after installation

### ".env file not found"
- Copy `.env.example` to `.env`
- Edit `.env` with your Plex server URL and token

### Port 3000 already in use
- Change `PORT=3000` to a different port in `.env`
- Or stop the application using port 3000

## What Gets Created

- `data/plex_collection.db` - Your SQLite database
- `assets/images/` - Downloaded thumbnails (WebP format)

## Running in Background

To run the backend as a Windows service (optional):

1. Install NSSM (Non-Sucking Service Manager)
2. Create a service pointing to `node server.js`
3. Set working directory to project folder

Or use the batch file in a minimized window.

