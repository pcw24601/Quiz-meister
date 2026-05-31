# Contributing to Quiz-Meister

Thank you for your interest in contributing! This document provides guidelines and instructions for contributing.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Project Structure](#project-structure)
- [Making Changes](#making-changes)
- [Testing](#testing)
- [Pull Request Process](#pull-request-process)
- [Style Guide](#style-guide)

## Code of Conduct

This project follows the [Contributor Covenant Code of Conduct](https://www.contributor-covenant.org/version/2/1/code_of_conduct/). By participating, you are expected to uphold this code. Please report unacceptable behavior to the project maintainers.

## Getting Started

1. Fork the repository on GitHub
2. Clone your fork locally
3. Create a virtual environment and install dependencies
4. Create a branch for your changes

## Development Setup

### Prerequisites

- Python 3.10+ (Python 3.11 or 3.12 recommended)
- Git
- A code editor (VS Code, PyCharm, etc.)

### Setup Steps

```bash
# Clone your fork
git clone https://github.com/YOUR_USERNAME/quiz-meister.git
cd quiz-meister

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Start the server to verify setup
python start.py
```

Open `http://localhost:8000/host` in your browser to verify everything works.

## Project Structure

```
quiz-meister/
├── server/
│   ├── app.py           # FastAPI backend, WebSocket handler
│   ├── db.py            # Supabase database operations
│   └── quiz_loader.py   # YAML quiz file parser
├── static/
│   ├── host.html        # Host control panel UI
│   ├── display.html     # Big screen display UI
│   ├── play.html        # Player handset UI
│   ├── editor.html      # Quiz YAML editor UI
│   ├── css/
│   │   ├── base.css     # Shared styles
│   │   ├── host.css     # Host panel styles
│   │   ├── display.css  # Display styles
│   │   └── play.css     # Player handset styles
│   └── js/
│       ├── host.js      # Host panel logic
│       ├── display.js   # Display logic
│       ├── play.js      # Player logic
│       └── qrcode.min.js # QR code library
├── quizzes/
│   └── example.yaml     # Sample quiz file
├── supabase/
│   └── migrations/      # Database migrations
├── start.py             # Server entry point
├── start.sh             # Linux/Mac launcher
├── start.bat            # Windows launcher
├── requirements.txt     # Python dependencies
├── README.md            # User documentation
└── CONTRIBUTING.md      # This file
```

## Making Changes

### Branch Naming

Create a branch with a descriptive name:

- `feature/add-new-question-type`
- `fix/leaderboard-navigation`
- `docs/improve-readme`

### Commit Messages

Write clear, descriptive commit messages:

```
Add picture question type to quiz editor

- Add image URL field to editor UI
- Update YAML parser to handle image field
- Add example picture question to example.yaml
```

### Code Changes

1. **Backend (Python)**:
   - `server/app.py` — API endpoints, WebSocket handling
   - `server/db.py` — Database operations
   - `server/quiz_loader.py` — YAML parsing and scoring

2. **Frontend (HTML/CSS/JS)**:
   - `static/*.html` — Page structure
   - `static/css/*.css` — Styling
   - `static/js/*.js` — Client-side logic

3. **Database**:
   - Add migrations in `supabase/migrations/`
   - Follow the migration naming convention: `YYYYMMDD_description.sql`

## Testing

### Manual Testing

1. Start the server: `python start.py`
2. Open host panel: `http://localhost:8000/host`
3. Open display in a second tab: `http://localhost:8000/display`
4. Open player on your phone or another tab: scan QR or use the player URL
5. Run through a quiz to verify your changes work correctly

### Testing Checklist

Before submitting a PR, verify:

- [ ] Server starts without errors
- [ ] Host panel loads and can create a session
- [ ] Players can join (test with multiple browser tabs)
- [ ] All question types work correctly
- [ ] Leaderboard updates properly
- [ ] Timer and answer reveal work
- [ ] No JavaScript console errors
- [ ] Responsive design works on mobile

### YAML Parser Testing

Test changes to quiz_loader.py:

```bash
python3 -c "
import sys; sys.path.insert(0, 'server')
from quiz_loader import load_quiz, score_answer
quiz = load_quiz('quizzes/example.yaml')
print('Quiz loaded:', quiz['title'])
print('Rounds:', len(quiz['rounds']))
"
```

## Pull Request Process

1. **Update documentation** if your changes affect user-facing features
2. **Add comments** to complex code sections
3. **Test thoroughly** using the checklist above
4. **Squash commits** if you have many small fix-up commits
5. **Write a PR description** explaining:
   - What you changed
   - Why you changed it
   - How to test it

### PR Template

```markdown
## Summary
Brief description of changes

## Changes Made
- List of specific changes

## Testing
How you tested these changes

## Screenshots
If applicable, add screenshots

## Related Issues
Closes #123
```

## Style Guide

### Python

- Follow [PEP 8](https://pep8.org/)
- Use 4 spaces for indentation
- Maximum line length: 100 characters
- Use f-strings for string formatting
- Prefer explicit over implicit

### JavaScript

- Use 2 spaces for indentation
- Use `const` and `let` (not `var`)
- Use arrow functions for callbacks
- Use template literals for string concatenation
- Handle errors gracefully

### CSS

- Use CSS custom properties (variables) from `base.css`
- Follow BEM-like naming: `.component-element--modifier`
- Mobile-first responsive design
- Use flexbox and grid for layouts

### YAML Quiz Files

- Indent with 2 spaces
- Use double quotes for strings with special characters
- Include all required fields for each question type
- Add comments to explain complex setups

## Adding New Question Types

When adding a new question type:

1. **Backend** (`server/quiz_loader.py`):
   - Add parsing logic in `_parse_question()`
   - Add scoring logic in `score_answer()`

2. **Player UI** (`static/play.html`, `static/js/play.js`, `static/css/play.css`):
   - Add HTML for input controls
   - Add JavaScript handler
   - Add CSS styling

3. **Display UI** (`static/js/display.js`, `static/css/display.css`):
   - Show question format on big screen
   - Add reveal animation

4. **Host UI** (`static/js/host.js`):
   - Update answer formatting
   - Add to qtypeLabel mapping

5. **Editor** (`static/editor.html`):
   - Add option in question type select
   - Add fields for the new type

6. **Documentation** (`README.md`):
   - Add to question types table
   - Add example YAML

7. **Example** (`quizzes/example.yaml`):
   - Add sample question

## Questions?

Feel free to open an issue for:
- Bug reports
- Feature requests
- Questions about the codebase
- Discussion before implementing large changes

Thank you for contributing!
