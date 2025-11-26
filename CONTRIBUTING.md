# Contributing to Plex Collection Sync

Thank you for your interest in contributing! This document provides guidelines and instructions for contributing to this project.

## Code of Conduct

- Be respectful and inclusive
- Welcome newcomers and help them learn
- Focus on constructive feedback
- Respect different viewpoints and experiences

## How to Contribute

### Reporting Bugs

1. Check if the issue already exists in the issue tracker
2. If not, create a new issue with:
   - Clear title and description
   - Steps to reproduce
   - Expected vs actual behavior
   - Environment details (OS, Python/Node versions, Plex version)
   - Relevant logs or error messages

### Suggesting Features

1. Check existing issues and discussions
2. Open a new issue with:
   - Clear description of the feature
   - Use case and motivation
   - Potential implementation approach (if you have ideas)

### Pull Requests

1. **Fork the repository**
2. **Create a feature branch**: `git checkout -b feature/your-feature-name`
3. **Make your changes**:
   - Follow the code style (see below)
   - Add tests if applicable
   - Update documentation
   - Update CHANGELOG.md
4. **Test your changes**:
   - Run the sync script with your changes
   - Test the backend API endpoints
   - Verify error handling
5. **Commit your changes**:
   - Use clear, descriptive commit messages
   - Follow conventional commits format: `type(scope): description`
   - Examples: `feat(api): add pagination support`, `fix(sync): handle missing metadata`
6. **Push to your fork**: `git push origin feature/your-feature-name`
7. **Open a Pull Request**:
   - Provide a clear description
   - Reference related issues
   - Include screenshots/examples if applicable

## Code Style

### Python

- Follow PEP 8 style guide
- Use 4 spaces for indentation
- Maximum line length: 100 characters
- Use type hints where helpful
- Add docstrings for functions and classes
- Use descriptive variable names

### JavaScript

- Follow ESLint configuration (if added)
- Use 2 spaces for indentation
- Use `const`/`let` instead of `var`
- Use async/await instead of callbacks
- Add JSDoc comments for functions

### General

- Write clear, self-documenting code
- Add comments for complex logic
- Keep functions focused and small
- Handle errors explicitly
- Use meaningful commit messages

## Development Setup

### Python Environment

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Node.js Environment

```bash
# Install dependencies
npm install

# Run in development mode
npm run dev
```

### Testing

Currently, manual testing is recommended. Future test suite will include:

- Unit tests for utility functions
- Integration tests for database operations
- API endpoint tests
- Error handling tests

## Project Structure

```
.
├── plex_sync.py          # Python sync script
├── server.js             # Node.js backend server
├── services/             # Backend services
│   ├── plexService.js   # Plex API client
│   └── sqliteService.js # SQLite fallback service
├── routes/               # API route handlers
├── data/                 # SQLite database (gitignored)
└── assets/              # Images and static files
```

## Areas for Contribution

- **Testing**: Add unit tests, integration tests
- **Documentation**: Improve README, add API docs, code comments
- **Error Handling**: Better error messages, recovery strategies
- **Performance**: Optimize queries, caching strategies
- **Features**: New endpoints, metadata fields, search improvements
- **DevOps**: Docker setup, CI/CD pipelines

## Questions?

Feel free to open an issue for questions or discussions. We're happy to help!

Thank you for contributing! 🎉

