# Contributing to Quiz-Meister

Thank you for your interest in contributing to Quiz-Meister! This document provides guidelines and setup instructions for contributors.

---

## ⚠️ A Note on "Vibe-Coding" & the Front-End

First, an honest confession: **Quiz-Meister is entirely vibe-coded!**

Front-end development (HTML, CSS, JavaScript) is well beyond the author's core background and experience. The entire client-side interface across `static/` (host panel, player handset, big screen display, and visual editor) was built collaboratively through rapid AI-assisted iteration ("vibe coding").

What this means for contributors:
- **It works, but it's quirky:** The front-end delivers a fun, fast, real-time quiz experience, but you will encounter idiosyncratic CSS structures, vanilla JS paradigms, and places that could be much cleaner or more modern.
- **Front-end contributions are deeply appreciated:** If you know HTML, CSS, JavaScript, responsive mobile UI, or accessibility (a11y), your help is very welcome.
- **No sacred cows:** Feel completely free to refactor, tidy up styles, streamline event handling, improve responsive layouts, or introduce better patterns. You won't hurt anyone's feelings or violate an untouchable architecture!

---

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup with `uv`](#development-setup-with-uv)
- [Project Structure](#project-structure)
- [Making Changes](#making-changes)
- [Testing](#testing)
- [Adding New Question Types](#adding-new-question-types)
- [Pull Request Process](#pull-request-process)
- [Style Guide](#style-guide)

---

## Code of Conduct

This project follows the [Contributor Covenant Code of Conduct](https://www.contributor-covenant.org/version/2/1/code_of_conduct/). By participating, you are expected to uphold this code.

---

## Getting Started

1. Fork the repository on GitHub (`https://github.com/pcw24601/quiz-meister`).
2. Clone your fork locally.
3. Install dependencies using **`uv`**.
4. Create a feature branch for your changes.

---

## Development Setup with `uv`

### Prerequisites

- **Python 3.13+**
- **[uv](https://docs.astral.sh/uv/)** (recommended for all dependency and environment management)
- **Git**
- A code editor (VS Code, Cursor, PyCharm, etc.)

### Setup Steps

```bash
# 1. Clone your fork
git clone https://github.com/pcw24601/quiz-meister.git
cd quiz-meister

# 2. Sync dependencies and create environment with uv
uv sync

# 3. Start the server
uv run python start.py
```

Open `http://localhost:8000/host` in your browser to verify that the host panel loads and connects.

---

## Project Structure

```text
quiz-meister/
├── server/
│   ├── app.py           # FastAPI backend, REST endpoints, WebSocket handlers
│   ├── db.py            # In-memory session and game state management
│   └── quiz_loader.py   # YAML quiz parser and answer scoring logic
├── static/
│   ├── host.html        # Host control panel UI
│   ├── display.html     # Big screen display UI
│   ├── play.html        # Player handset UI
│   ├── editor.html      # Visual Quiz YAML editor UI
│   ├── css/
│   │   ├── base.css     # Shared variables, layout, and reset styles
│   │   ├── host.css     # Host panel styles
│   │   ├── display.css  # Display styles
│   │   └── play.css     # Player handset styles
│   └── js/
│       ├── host.js      # Host panel logic & WebSocket client
│       ├── display.js   # Display logic & WebSocket client
│       ├── play.js      # Player handset logic & WebSocket client
│       └── qrcode.min.js# QR code generation library
├── quizzes/
│   ├── example.yaml     # Sample quiz file
│   └── images/          # Local quiz images
├── tests/
│   └── test_api.py      # Automated API and scoring tests
├── pyproject.toml       # Project metadata, dependencies, and scripts
├── uv.lock              # Reproducible dependency lockfile
├── start.py             # Server launcher script
├── start.sh             # Linux / macOS start script
├── start.bat            # Windows start script
├── LICENSE              # GNU General Public License v3.0
├── README.md            # Main user documentation
└── CONTRIBUTING.md      # Contributor guide
```

---

## Making Changes

### Branch Naming

Use clear, descriptive branch names:
- `feature/add-new-question-type`
- `fix/leaderboard-equal-rank`
- `refactor/play-css-cleanup`
- `docs/clarify-offline-wifi`

### Commit Messages

Write concise, descriptive commit messages:
```text
Improve player handset button responsiveness on mobile

- Increase tap target size for options in play.css
- Prevent accidental double-submits in play.js
```

---

## Testing

### Automated Tests with `uv`

Run the test suite using `uv`:

```bash
uv run pytest
```

### Manual Testing Checklist

Before opening a pull request, test changes manually across multiple browser windows:

1. Start server: `uv run python start.py`
2. Open Host panel: `http://localhost:8000/host`
3. Open Big Screen Display: `http://localhost:8000/display`
4. Open Player handset: `http://localhost:8000/play` (open on 2 or 3 devices to simulate competing teams)
5. Verify:
   - [ ] Host panel loads quiz and starts session
   - [ ] Teams can join and appear in the host lobby
   - [ ] Questions display correctly on both display and player tabs
   - [ ] Answering, timers, and answer reveals synchronize via WebSockets
   - [ ] Score overrides work on the host panel
   - [ ] Leaderboard ranks teams correctly (including equal ties)
   - [ ] No (new) errors in browser Developer Tools console

### Testing YAML Parser & Scoring via CLI

You can test quiz parsing and scoring directly using `uv run python`:

```bash
# Verify quiz loads without error
uv run python -c "
import sys; sys.path.insert(0, 'server')
from quiz_loader import load_quiz
quiz = load_quiz('quizzes/example.yaml')
print(f'Successfully loaded: {quiz[\"title\"]} with {len(quiz[\"rounds\"])} rounds')
"

# Test answer scoring
uv run python -c "
import sys; sys.path.insert(0, 'server')
from quiz_loader import load_quiz, score_answer
quiz = load_quiz('quizzes/example.yaml')
q = quiz['rounds'][0]['questions'][0]
score = score_answer(q, [1])
print(f'Question: {q[\"text\"]}')
print(f'Score for option index [1]: {score}')
"
```

---

## Adding New Question Types

To add a new question type to Quiz-Meister:

1. **Backend Parser & Scorer** (`server/quiz_loader.py`):
   - Add parsing logic in `_parse_question()`.
   - Add scoring rules in `score_answer()`.
2. **Player Handset UI** (`static/play.html`, `static/js/play.js`, `static/css/play.css`):
   - Add markup/templates for player input controls.
   - Add input collection and submission handler.
   - Add mobile styling.
3. **Display Screen** (`static/js/display.js`, `static/css/display.css`):
   - Add question rendering for the big screen.
   - Add correct answer reveal animations.
4. **Host Panel** (`static/js/host.js`):
   - Add label to `qtypeLabel` mapping.
   - Format submitted team answers for review.
5. **Visual Editor** (`static/editor.html`):
   - Add option in the question type dropdown and provide input fields.
6. **Documentation & Examples** (`README.md`, `quizzes/example.yaml`):
   - Add the question type to the documentation table and provide an example in `example.yaml`.

---

## Pull Request Process

1. Ensure all tests pass: `uv run pytest`.
2. If introducing user-facing features or network options, update [README.md](README.md).
3. Open a pull request against `dev` (or `main`) with:
   - A clear summary of what was changed and why.
   - Notes on how you tested it (browsers used, devices tested).
   - Screenshots or GIFs for UI changes.

---

## Style Guide

- **Python**: Follow PEP 8 guidelines. Format with `uv run ruff format` or standard 4-space indentation.
- **JavaScript**: Vanilla ES6+ (no external frameworks required for runtime). Use `const`/`let`, arrow functions, template strings, and clear async/await handling.
- **CSS**: Modern CSS with CSS variables in `base.css`. Responsive, mobile-first layouts for player handsets.
- **YAML**: Valid YAML 1.2 with 2-space indentation.

Thank you for helping make Quiz-Meister better!
