# Quiz-Meister

Host a live quiz night on your local Wi-Fi. Players join via their phone browsers — no app to install. Display questions on a big screen, control the game from your laptop, and let teams compete in real time.

> **100% Offline-Capable:** Quiz-Meister requires **no external internet connection**. You can run a complete pub quiz anywhere using just an old, disconnected Wi-Fi router or your laptop's built-in hotspot.

---

## Features

- **100% Offline & Private** — Runs entirely on local Wi-Fi; no internet or cloud services required.
- **Phone-friendly** — Players scan a QR code to join instantly in their browser; no apps to install or accounts to create.
- **Real-time Sync** — Fast WebSockets keep host, big screen, and player handsets synchronized with zero latency.
- **Built-in Visual Quiz Editor** — Create, edit, and test quizzes visually at `http://localhost:8000/editor` without writing YAML manually.
- **5 Question Types** — Multiple choice, select many (exact match), put in order, numeric (with optional accuracy), and first letter.
- **Picture Support** - Add pictures to any question.
- **Tiebreaker Support** — Dedicated tiebreaker questions to resolve draws cleanly.
- **Dramatic Reveals** — Animated leaderboards, equal ranking for tied scores, and fireworks finale.
- **Manual Score Override** — Host can edit and adjust any team's score at any point during the game.
- **Lightweight & Self-hosted** — Fast in-memory session engine for live play, with permanent YAML quiz files and local image storage on disk.

---

## Requirements

- **Python 3.13+**
- **[uv](https://docs.astral.sh/uv/)** — Extremely fast Python package and environment manager
- A modern web browser (Chrome, Firefox, Safari, Edge)
- A local Wi-Fi network (an existing home/venue Wi-Fi, a spare offline router, or a laptop hotspot)

---

## Quick Start (3 Steps)

### Step 1: Install `uv` (if not already installed)

If you don't already have `uv`:

- **macOS / Linux:**
  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```
- **Windows (PowerShell):**
  ```powershell
  powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
  ```
- **Homebrew (macOS/Linux):**
  ```bash
  brew install uv
  ```

### Step 2: Sync Dependencies

Clone the repository and sync dependencies:

```bash
git clone https://github.com/pcw2460/quiz-meister.git
cd quiz-meister
uv sync
```

### Step 3: Start the Server

Run the start script or execute directly with `uv`:

- **macOS / Linux:**
  ```bash
  ./start.sh
  # or directly:
  uv run python start.py
  ```

- **Windows:**
  - Double-click `start.bat`
  - Or in PowerShell/cmd:
    ```powershell
    uv run python start.py
    ```

You will see the startup banner:

```text
╔════════════════════════════════════════════════════╗
║            Quiz-Meister Starting                   ║
╠════════════════════════════════════════════════════╣
║  Host panel:   http://localhost:8000/host          ║
║  Big screen:   http://localhost:8000/display       ║
║  Quiz Editor:  http://localhost:8000/editor        ║
║  Player URL:   http://192.168.1.42:8000/play       ║
║  (Share the player URL with teams)                 ║
╚════════════════════════════════════════════════════╝
```

Open `http://localhost:8000/host` in your browser, select a quiz (or open `http://localhost:8000/editor` to create one), and click **Start Session**.

---

## Network Setup & Offline Play

Quiz-Meister does **not** need internet access to function. Communication happens directly between player phones and your host machine over local Wi-Fi.

### Option 1: Use an Old / Discarded Wi-Fi Router / Wifi Extender (Recommended for Offline Events)

An old broadband router tucked away in a drawer is ideal for running quiz nights anywhere (e.g. community halls, pubs, campsites, or basements).

1. **No internet connection is needed.** Plug the old router or range extender into power. You do **not** need to plug in any DSL, fibre, or WAN broadband cable. A plug-in range extender can work, although you may be limited in the number of connections.
2. If you are using a wifi extender to host the network, ensure 'DHCP Server' is enabled.
2. Connect your host laptop to this router's Wi-Fi network.
3. Connect players' phones to the same Wi-Fi network.
4. Launch Quiz-Meister (`uv run python start.py`). The router assigns local IP addresses (e.g. `192.168.1.x`), and Quiz-Meister will display the correct Player URL.

> [!IMPORTANT]
> **CRITICAL: Turn OFF Mobile Data on Player Phones!**
>
> Modern smartphones (iOS and Android) automatically detect when a connected Wi-Fi network does not have an active internet connection. To "help" the user, phones will silently bypass the Wi-Fi and route web requests over mobile/cellular data (4G/5G).
>
> Because Quiz-Meister is running strictly on the offline local Wi-Fi, the phone's browser will fail to connect or time out if mobile data remains enabled.
>
> **Always instruct players to:**
> 1. Turn **OFF** Mobile / Cellular Data in their phone settings or control center.
> 2. Connect to the quiz Wi-Fi.
> 3. If prompted with *"This network has no internet access. Stay connected?"*, select **Yes / Keep Connected**.
> 4. Scan the QR code or navigate to the Player URL.

---

### Option 2: Existing Home or Venue Wi-Fi

If you are hosting at home or at a venue with existing Wi-Fi:

1. Connect your host laptop to the Wi-Fi.
2. Connect players' phones to the same Wi-Fi network.
3. If the venue Wi-Fi blocks client-to-client communication (common on public "guest" Wi-Fi networks with client isolation enabled), use an old router (Option 1) or a laptop hotspot (Option 3).
4. If the venue Wi-Fi has no internet access, ensure players switch off mobile data as described above.

---

### Option 3: Laptop Wi-Fi Hotspot (No Router Needed)

Your host laptop can create its own Wi-Fi hotspot for players to connect to:

#### Windows: Mobile Hotspot (untested)
1. Open **Settings** → **Network & Internet** → **Mobile hotspot**.
2. Turn on Mobile Hotspot.
3. Note the Network Name (SSID) and Password.
4. Have players connect their phones to this hotspot.
5. Run `uv run python start.py`.

#### macOS: Internet Sharing
1. Open **System Settings** → **General** → **Sharing**.
2. Enable **Internet Sharing** to Wi-Fi.
3. Configure Wi-Fi Options (network name and password).
4. Have players connect to your Mac's network.
5. Run `uv run python start.py`.
Note: You might need to enable a dummy network connection before sharing becomes visible. For example by enabling 'Thunderbolt bridge' in Network settings (IP address 192.168.1.88, Subnet mask 255.255.255.0), then sharing it over WiFi from 'System Settings > General > Sharing > Internet Sharing'. I've not fully tested either method.

#### Linux: Wi-Fi Hotspot (untested)
- **GNOME:** System menu → Wi-Fi Settings → **Turn On Wi-Fi Hotspot...**
- **Terminal (NetworkManager):**
  ```bash
  nmcli device wifi hotspot ifname wlan0 ssid "QuizMeister" password "quizmaster123"
  ```

---

## Running a Quiz Night

### 1. Setup Your Screens
- **Host Panel (`/host`)**: The quizmaster's cockpit on your laptop. Select a quiz file, advance questions, trigger reveals, review incoming team answers, and manually adjust scores.
- **Big Screen (`/display`)**: Project this on a TV, projector, or second monitor for the room. Shows the lobby, current question, timer, and animated leaderboards.
- **Visual Editor (`/editor`)**: Create or customize quizzes via a visual web interface and save directly to your `quizzes/` folder.

### 2. Player Joining
- **QR Code**: Displayed automatically on both the host panel and the big screen. Players scan with their phone camera to join directly.
- **Direct URL**: Players can also type the Player URL (e.g., `http://192.168.1.42:8000/play`) into any browser on their phone.
- Players pick a team name and join the lobby.

### 3. During the Game
- **Lobby**: Monitor connected teams as they join. Click **Start Round** when ready.
- **Question**: Displayed on big screen and player handsets with an active countdown timer.
- **Answer Reveal**: View all submitted answers in real time. The quizmaster can override or adjust points if needed (e.g. accepting minor spelling variations).
- **Leaderboard**: Displays rankings after each round with smooth animations. Teams with equal scores place equally.
- **Finale**: Final podium rankings complete with celebratory fireworks!

---

## Question Types & YAML Format

Quizzes can be created visually in the **Quiz Editor** (`/editor`) or authored directly as `.yaml` files in the `quizzes/` directory.

### Supported Question Types

| Type | Description | Key Fields |
|------|-------------|------------|
| `multiple_choice` | Single correct answer from choices | `options`, `correct` (zero-based index) |
| `select_many` | Multiple correct answers (exact match required) | `options`, `correct` (array of zero-based indices) |
| `order` | Drag-and-drop items into the correct sequence | `items` (ordered correctly in YAML) |
| `numeric` | Number guess | `answer`, `tolerance` (optional) |
| `picture` | Question based on an image | `options`, `correct`, `image` (path or URL) |
| `first_letter` | Players tap the starting letter on an on-screen keyboard | `answer` (correct text or letter) |

### Optional Question Fields

- `time`: Seconds for question timer (default: `30`)
- `points`: Points awarded for a correct answer (default: `5`)
- `tiebreaker`: Set to `true` to flag as a tiebreaker question (default: `false`, typically worth `0` regular points)
- `image`: Relative path (e.g., `/quiz-images/photo.jpg`) or external URL
- `note`: Quizmaster hint or trivia note displayed on the host panel

### Example Quiz YAML (`quizzes/my-quiz.yaml`)

```yaml
title: "My Quiz"

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
        text: "Which of the following are primary colors of light?"
        options:
          - Red
          - Yellow
          - Green
          - Blue
        correct: [0, 2, 3]
        time: 30
        points: 2

      - type: order
        text: "Put these historical events in chronological order:"
        items:
          - Moon Landing
          - Fall of the Berlin Wall
          - Launch of Wikipedia
        time: 45
        points: 2

      - type: numeric
        text: "How many days in a leap year"
        answer: 366
        tolerance: 0
        time: 30
        points: 1

      - type: first_letter
        text: "What is the name of the ship that brought the Pilgrims to America in 1620?"
        answer: M
        answer_info: "Woody"
        time: 20
        points: 1

      - type: numeric
        text: "Tiebreaker: In what year was the first telegraph message sent?"
        answer: 1844
        time: 30
        points: 0
        tiebreaker: true
```

### Picture Questions & Local Media

You can add pictures to any question type:

1. Place image files in `quizzes/images/` (e.g. `quizzes/images/landmark.jpg`).
2. In your YAML, reference them as: `image: "/quiz-images/landmark.jpg"`.
3. You can also upload images directly from the visual Quiz Editor (`/editor`).

---

## State & Persistence

- **Live Game Sessions:** Stored in-memory for instant, zero-latency WebSocket updates. Sessions survive player phone disconnections and browser refreshes during an event, but reset if the server process is stopped.
- **Quizzes & Media:** Persisted permanently on disk in the `quizzes/` folder and `quizzes/images/` folder.

---

## Troubleshooting

### Players cannot connect to the Player URL
1. **Turn OFF Mobile / Cellular Data:** On player phones, turn off mobile data so the operating system doesn't bypass the local Wi-Fi network.
2. **Check Wi-Fi Network:** Confirm the host laptop and all player phones are connected to the exact same Wi-Fi SSID.
3. **Guest Wi-Fi Isolation:** If using public/venue Wi-Fi, the router may have "AP / Client Isolation" enabled. Use a standalone router or laptop hotspot instead.
4. **Firewall:** Ensure your host computer's firewall permits incoming connections on port 8000.
5. **Use HTTP:** Ensure players open `http://...` and not `https://...`.

### "Address already in use" (Port 8000)
Another process is using port 8000. Specify a different port using the `PORT` environment variable:
- **macOS / Linux:**
  ```bash
  PORT=8080 uv run python start.py
  ```
- **Windows (PowerShell):**
  ```powershell
  $env:PORT="8080"; uv run python start.py
  ```

---

## Tech Stack

- **Backend:** Python 3.13+, [FastAPI](https://fastapi.tiangolo.com/), WebSockets, [uvicorn](https://www.uvicorn.org/)
- **Toolchain & Package Management:** [uv](https://docs.astral.sh/uv/)
- **Storage:** High-speed in-memory session store, local YAML and media files
- **Frontend:** Plain HTML5, CSS3, vanilla JavaScript (no build step, no npm runtime dependencies)

---

## License

This project is licensed under the terms of the **GNU General Public License v3.0** (GPL-3.0). See the [LICENSE](LICENSE) file for details.
