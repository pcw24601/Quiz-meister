# Quiz-Meister

Host a live quiz night on your local WiFi. Players join via their phone browsers — no app to install. Display questions on a big screen, control the game from your laptop, and let teams compete in real-time.

## Features

- **Self-hosted** — runs on any OS (Windows, Mac, Linux)
- **Phone-friendly** — players scan a QR code to join, no app needed
- **Real-time sync** — WebSockets keep all screens in sync
- **6 question types** — multiple choice, select many, put in order, numeric, picture round, first letter
- **Dramatic reveals** — animated leaderboard, fireworks finale
- **Manual score override** — host can adjust scores anytime
- **Persistent state** — session saved to database, survives restarts

## Requirements

- **Python 3.10+** (Python 3.11 or 3.12 recommended)
- A modern web browser (Chrome, Firefox, Safari, Edge)
- WiFi network for players to connect to

## Quick Start (3 Steps)

### Step 1: Install Dependencies

Open a terminal in the project folder and run:

**Windows:**
```
pip install -r requirements.txt
```

**Mac/Linux:**
```
pip3 install -r requirements.txt
```

If you get a permission error on Mac/Linux, use:
```
pip3 install -r requirements.txt --break-system-packages
```

### Step 2: Start the Server

**Windows:**
- Double-click `start.bat`
- Or run: `python start.py`

**Mac/Linux:**
```bash
chmod +x start.sh
./start.sh
```
Or run: `python3 start.py`

You'll see something like:
```
╔═══════════════════════════════════════════╗
║           Quiz-Meister Starting           ║
╠═══════════════════════════════════════════╣
║  Host panel:  http://localhost:8000/host  ║
║  Big screen:  http://localhost:8000/display
║  Player URL:  http://192.168.1.42:8000/play
╚═══════════════════════════════════════════╝
```

### Step 3: Open the Host Panel

1. Open `http://localhost:8000/host` in your browser
2. Select a quiz file (e.g., `example.yaml`)
3. Click **Start Session**

## Running a Quiz Night

### Setup

1. **Open the Host Panel** (`/host`) — this is your control screen
2. **Open the Big Screen** (`/display`) — project this on a TV or large monitor
3. Click **Open Display** from the host panel, or go to the URL shown

### Getting Players to Join

Players have two options:

**Option A: Scan QR Code**
- The QR code is displayed on the host panel and big screen
- Players scan it with their phone camera
- They enter their team name and join

**Option B: Direct URL**
- Share the player URL shown on startup (e.g., `http://192.168.1.42:8000/play`)
- Players open it in their phone browser
- They enter the session ID (shown on host panel) and their team name

### During the Game

The host panel shows:
- **Lobby** — wait for teams to join, click "Start Round" to begin
- **Question** — the current question, timer, and how many teams have answered
- **Answer Reveal** — see all team answers, override scores if needed
- **Leaderboard** — scores after each round

Use the controls:
- **Reveal Answer Now** — skip the timer and show the answer
- **Override Score** — click "Edit" next to any team's answer to adjust
- **Next Question** — advance to the next question
- **Show Leaderboard** — display the ranked scores

### What Players See

- **Lobby** — waiting screen with team count
- **Question** — the question text, image (if any), and answer input
- **Answer Submitted** — confirmation they've answered
- **Reveal** — the correct answer and what they submitted
- **Leaderboard** — current rankings

## Writing Quiz Questions

Quiz questions are defined in YAML files in the `quizzes/` folder.

### Example Quiz File

```yaml
title: "My Quiz Night"

rounds:
  - name: "General Knowledge"
    questions:
      - type: multiple_choice
        text: "What is the capital of France?"
        options:
          - London
          - Paris
          - Berlin
          - Madrid
        correct: 1
        time: 30
        points: 1

      - type: select_many
        text: "Which are primary colors?"
        options:
          - Red
          - Green
          - Blue
          - Yellow
        correct: [0, 2, 3]
        time: 30
        points: 2

      - type: order
        text: "Put these in chronological order"
        items:
          - World War I
          - World War II
          - Cold War
        time: 45
        points: 2

      - type: numeric
        text: "How many continents are there?"
        answer: 7
        tolerance: 0
        time: 30
        points: 1

      - type: first_letter
        text: "What is the first letter of the Greek alphabet?"
        answer: A
        time: 15
        points: 1
```

### Question Types

| Type | Description | Key Fields |
|------|-------------|------------|
| `multiple_choice` | One correct answer | `options`, `correct` (index) |
| `select_many` | Multiple correct answers (partial credit) | `options`, `correct` (array of indices) |
| `order` | Drag to reorder items | `items` (correct order) |
| `numeric` | Closest number wins | `answer`, `tolerance` (optional) |
| `picture` | Like multiple choice with image | `options`, `correct`, `image` (URL) |
| `first_letter` | Tap the first letter of answer | `answer`, `letters` (optional, defaults A-Z) |

### Optional Fields

- `time` — seconds for the question timer (default: 30)
- `points` — points for correct answer (default: 1)
- `tiebreaker` — mark as tiebreaker question (default: false)
- `image` — URL to an image to display

## Network Setup Tips

### Same WiFi Network

All devices (host computer, big screen, player phones) must be on the same WiFi network.

### Windows: Find Your IP Address

1. Open Command Prompt
2. Run: `ipconfig`
3. Look for "IPv4 Address" under your WiFi adapter

### Mac: Find Your IP Address

1. Open System Preferences → Network
2. Your IP is shown under the connected WiFi

### Linux: Find Your IP Address

```bash
ip addr show | grep inet
```

### Firewall Settings

If players can't connect, check your firewall allows connections on port 8000 (or whichever port you're using).

## Troubleshooting

### "Address already in use"

Another program is using port 8000. Either:
- Close the other program
- Change the port: `PORT=8080 python start.py`

### Players can't connect

1. Verify all devices are on the same WiFi network
2. Check the URL players are using matches your computer's IP
3. Try disabling your firewall temporarily
4. Make sure you're using `http://` not `https://`

### Session lost after restart

The session state is saved to the Supabase database. You can resume:
1. Copy the Session ID from the host panel
2. Copy the Host Secret
3. On a new host panel, paste both and click "Resume Session"

### QR Code not working

Some older phones can't scan QR codes from the camera app. Players can manually enter the URL instead.

## Customization

### Change the Port

Set the `PORT` environment variable:

**Windows (PowerShell):**
```
$env:PORT=8080; python start.py
```

**Mac/Linux:**
```
PORT=8080 python3 start.py
```

### Add Your Own Quiz

1. Create a `.yaml` file in the `quizzes/` folder
2. Follow the format in `example.yaml`
3. Restart the server (or it auto-reloads if running with `--reload`)

## Tech Stack

- **Backend:** Python + FastAPI + WebSockets
- **Database:** Supabase (PostgreSQL)
- **Frontend:** Plain HTML/CSS/JavaScript (no framework)
- **Dependencies:** See `requirements.txt`

## License

MIT License — use freely for any purpose.
