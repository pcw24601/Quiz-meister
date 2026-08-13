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
- WiFi network OR laptop with WiFi hotspot capability

## Quick Start (3 Steps)

### Step 1: Create a Virtual Environment

This keeps Quiz-Meister isolated from your system Python.

**Windows:**
```
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

**Mac/Linux:**
```
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

> **Note:** Always activate the virtual environment before running. You'll see `(venv)` in your terminal prompt when active.

### Step 2: Start the Server

Make sure your virtual environment is activated (you see `(venv)` in the prompt), then run:

**Windows:**
- Double-click `start.bat`
- Or run: `python start.py`

**Mac/Linux:**
```bash
chmod +x start.sh
./start.sh
```
Or run: `python start.py`

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
2. Select a quiz file (e.g., `example.yaml`) or use the Browse... option to enter an absolute path on the host machine
3. Click **Start Session**

## Network Setup Options

You have two options for connecting players:

### Option A: Use Your Existing WiFi Router

If you have a home or venue WiFi network:

1. Connect your laptop (host computer) to the WiFi
2. Connect player phones to the same WiFi
3. Use the Player URL shown on startup

### Option B: Create a WiFi Hotspot (No Router Needed)

If you don't have a WiFi router, your laptop can create one. All devices will connect directly to your laptop.

#### Windows: Mobile Hotspot

1. Open **Settings** → **Network & Internet** → **Mobile hotspot**
2. Turn on "Share my Internet connection from" — select your WiFi or Ethernet
3. Click **Edit** to set a network name and password
4. Players connect to this hotspot on their phones
5. Run Quiz-Meister — the Player URL will be your laptop's hotspot IP

#### Mac: Internet Sharing

1. Open **System Settings** → **General** → **Sharing**
2. Turn on **Internet Sharing**
3. Share from: your Ethernet or WiFi connection
4. To computers using: **Wi-Fi**
5. Click **Wi-Fi Options** to set a network name and password
6. Players connect to this network on their phones
7. Run Quiz-Meister — the Player URL will be your Mac's IP

#### Linux: Create a Hotspot

**Using GNOME (Ubuntu, Fedora, etc.):**
1. Click the WiFi icon in the system tray
2. Select **Turn On Wi-Fi Hotspot**
3. Set a network name and password
4. Players connect to this hotspot

**Using terminal:**
```bash
nmcli device wifi hotspot ifname wlan0 ssid "QuizNight" password "quizmaster123"
```

> **Tip:** The Player URL displayed on startup will show your laptop's hotspot IP address (usually something like `192.168.137.1` on Windows or `192.168.2.1` on Mac).

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
- `image` — URL to an image to display (for picture type)
- `note` — hint text to display with question (not used for first_letter)

### Picture Questions

Any question type can include an image. The `picture` type is specifically for questions where the image IS the question, but you can add images to other types too.

**Add image to any question:**
```yaml
- type: numeric
  text: "How many stars are in this cluster?"
  image: "/quiz-images/star-cluster.jpg"
  answer: 150
  time: 30
```

**External URL:**
```yaml
image: "https://example.com/photo.jpg"
```

**Local file:**
1. Place image files in the `quizzes/images/` folder
2. Reference them as: `/quiz-images/filename.jpg`

```yaml
image: "/quiz-images/landmark.jpg"
```

**Organizing local images:**
```
quizzes/
  my-quiz.yaml
  images/
    round1/
      q1.jpg
      q2.jpg
    round2/
      famous-landmark.png
```

Then reference: `/quiz-images/round1/q1.jpg`

Tiebreaker questions are used to break ties when teams have the same score at the end of the quiz. They work differently depending on question type:

**How they work:**

1. Mark a question as `tiebreaker: true` in your YAML file
2. During the quiz, tiebreaker questions are marked with a "TIEBREAKER" badge
3. If two or more teams are tied on the leaderboard, the host can use the tiebreaker results to declare a winner

**For numeric questions:**
- The team with the answer **closest** to the correct answer wins
- Used when you need a definitive winner (e.g., "How many Jellybeans in this jar?")

**For multiple choice / first_letter:**
- First correct answer wins (based on submission time)
- If both wrong, continue to the next tiebreaker question

**Example:**
```yaml
- type: numeric
  text: "In what year was the first Super Bowl played?"
  answer: 1967
  tolerance: 0
  time: 20
  points: 0  # Points don't matter for tiebreakers
  tiebreaker: true
```

**Note:** Tiebreaker questions are typically worth 0 points since they're only used to break ties, not to add to the score.

## Troubleshooting

### "Address already in use"

Another program is using port 8000. Either:
- Close the other program
- Change the port: `PORT=8080 python start.py`

### Players can't connect

1. Verify all devices are on the same network (same WiFi or your laptop's hotspot)
2. Check the URL players are using matches your computer's IP
3. Try disabling your firewall temporarily
4. Make sure you're using `http://` not `https://`
5. If using a hotspot, confirm players are connected to it

### Virtual environment not activating

If you see an error like "execution policy" on Windows:
```
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

On Mac/Linux, if `source venv/bin/activate` doesn't work:
```bash
chmod +x venv/bin/activate
source venv/bin/activate
```

### Session lost after restart

**Note:** Quiz sessions are stored in memory and will be lost on server restart. To preserve quiz data:
- Save your quiz YAML files to disk (they persist across restarts)
- Use the Quiz Editor to create and save quizzes
- The current game session (teams, scores) is temporary and designed for single-event use

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
PORT=8080 python start.py
```

### Add Your Own Quiz

**Option A: Use the Quiz Editor (Recommended)**

1. Start the server and open `http://localhost:8000/editor`
2. Click "Add Round" to create rounds
3. Add questions using the form interface
4. Click "Save Quiz" to download a YAML file
5. Move the downloaded file to your `quizzes/` folder

**Option B: Write YAML Manually**

1. Create a `.yaml` file in the `quizzes/` folder
2. Follow the format in `example.yaml`
3. Restart the server (or it auto-reloads if running with `--reload`)

## Tech Stack

- **Backend:** Python + FastAPI + WebSockets
- **Storage:** In-memory (session state), Local files (quiz YAMLs, images)
- **Frontend:** Plain HTML/CSS/JavaScript (no framework)
- **Dependencies:** See `requirements.txt`

## License

MIT License — use freely for any purpose.
