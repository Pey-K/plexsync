# Release Instructions

## Creating a Windows Release

### Prerequisites
- Python 3.11+ with PyInstaller installed
- Node.js 20+ (for testing)
- Git with GitHub access

### Manual Build Process

1. **Update version numbers:**
   - Update `VERSION` file
   - Update `CHANGELOG.md` with new version
   - Update `package.json` version (if needed)

2. **Build the executable:**
   ```bash
   pip install pyinstaller
   pyinstaller --onefile --windowed --name "PlexSyncLauncher" launcher.py
   ```

3. **Create release package:**
   ```bash
   mkdir release
   copy dist\PlexSyncLauncher.exe release\
   copy start.bat release\
   copy .env.example release\.env.example
   copy README_WINDOWS.md release\
   copy LICENSE release\
   ```

4. **Create ZIP archive:**
   ```bash
   powershell Compress-Archive -Path release\* -DestinationPath PlexSyncLauncher-Windows.zip
   ```

5. **Create GitHub release:**
   - Go to https://github.com/Pey-K/plexsync/releases/new
   - Tag: `v1.0.0` (match VERSION file)
   - Title: `v1.0.0 - Windows Release`
   - Description: Copy from CHANGELOG.md
   - Upload: `PlexSyncLauncher-Windows.zip`
   - Publish release

### Automated Build (GitHub Actions)

The `.github/workflows/release.yml` workflow will automatically:
- Build the executable when you push a version tag
- Create a release package
- Upload to GitHub Releases

**To trigger:**
```bash
git tag v1.0.0
git push origin v1.0.0
```

## Release Package Contents

The Windows release ZIP should contain:
- `PlexSyncLauncher.exe` - Main executable (GUI launcher)
- `start.bat` - Alternative batch file launcher
- `.env.example` - Environment variable template
- `README_WINDOWS.md` - Windows-specific instructions
- `LICENSE` - MIT License

## User Instructions (for release notes)

1. Download `PlexSyncLauncher-Windows.zip`
2. Extract to a folder
3. Copy `.env.example` to `.env`
4. Edit `.env` with your Plex credentials:
   - `PLEX_URL=http://your-plex-ip:32400`
   - `PLEX_TOKEN=your-token-here`
5. Double-click `PlexSyncLauncher.exe` or `start.bat`
6. Wait for sync to complete
7. API will be available at http://localhost:3000

**Requirements:**
- Windows 10/11
- Python 3.9+ (for batch file method)
- Node.js 18+ (for batch file method)
- Or use the standalone `.exe` (no Python/Node needed if bundled)

