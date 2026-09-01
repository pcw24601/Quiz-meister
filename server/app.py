"""
Quiz-Meister backend server.
FastAPI + WebSockets. Single process, in-memory broadcast hub.

Routes:
  GET  /                          → redirect to /host
  GET  /host                      → host control panel
  GET  /display                   → big screen display
  GET  /play                      → player handset
  GET  /api/quizzes               → list YAML files
  POST /api/sessions              → create a new session
  GET  /api/sessions/{id}         → get session state
  POST /api/sessions/{id}/action  → host actions (next, reveal, override, etc.)
  POST /api/sessions/{id}/join    → team registration
  POST /api/sessions/{id}/answer  → submit answer
  GET  /api/sessions/{id}/leaderboard → current scores
  WS   /ws/{session_id}           → real-time updates for all clients
"""

import asyncio
import json
import os
import secrets
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import db
import quiz_loader

BASE_DIR = Path(__file__).parent.parent
STATIC_DIR = BASE_DIR / "static"
QUIZZES_DIR = BASE_DIR / "quizzes"


# ── WebSocket connection manager ───────────────────────────────────────────────

class ConnectionManager:
    def __init__(self):
        # session_id → list of websockets
        self.connections: dict[str, list[WebSocket]] = {}

    async def connect(self, session_id: str, ws: WebSocket):
        await ws.accept()
        self.connections.setdefault(session_id, []).append(ws)

    def disconnect(self, session_id: str, ws: WebSocket):
        conns = self.connections.get(session_id, [])
        if ws in conns:
            conns.remove(ws)

    async def broadcast(self, session_id: str, message: dict):
        conns = list(self.connections.get(session_id, []))
        dead = []
        for ws in conns:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(session_id, ws)


manager = ConnectionManager()


# ── Timer tasks ────────────────────────────────────────────────────────────────

_timer_tasks: dict[str, asyncio.Task] = {}


def _score_current_question(session_id: str, session: dict):
    quiz = session["quiz_data"]
    rounds = quiz.get("rounds", [])
    ri = session["current_round_index"]
    qi = session["current_question_index"]

    current_round = rounds[ri] if ri < len(rounds) else None
    if not current_round:
        return
    qs = current_round.get("questions", [])
    if qi >= len(qs):
        return
    question = qs[qi]
    answers = db.get_answers(session_id, ri, qi)
    bonus_pts = session.get("bonus_points", 0)

    if question["type"] == "numeric":
        # Numeric: closest wins
        ta_list = [{"team_id": a["team_id"], "answer_data": a["answer_data"]} for a in answers]
        scores = quiz_loader.score_numeric_round(ta_list, question)

        # Apply bonus points to closest answers
        if bonus_pts > 0:
            try:
                correct_val = float(question["answer"])
                distances = []
                for a in answers:
                    try:
                        val = float(a["answer_data"][0]) if a["answer_data"] else None
                    except (ValueError, TypeError):
                        val = None
                    if val is not None:
                        distances.append((abs(val - correct_val), a["team_id"], a["id"]))
                distances.sort(key=lambda x: x[0])

                # Award bonus points (N, N-1, ..., 1) to closest correct
                for i, (dist, tid, aid) in enumerate(distances):
                    if i < bonus_pts and scores.get(tid, 0) > 0:
                        bonus = bonus_pts - i
                        scores[tid] = scores.get(tid, 0) + bonus
            except (ValueError, TypeError):
                pass

        for answer in answers:
            if not answer["score_overridden"]:
                new_score = scores.get(answer["team_id"], 0)
                db.override_score(answer["id"], new_score)
    else:
        # Other types: fastest correct gets bonus
        if bonus_pts > 0:
            # Sort correct answers by submission time
            correct_answers = [
                a for a in answers
                if not a["score_overridden"] and a["score"] > 0
            ]
            correct_answers.sort(key=lambda x: x.get("submitted_at", ""))

            # Award bonus to top N fastest correct answers
            for i, answer in enumerate(correct_answers):
                if i < bonus_pts:
                    bonus = bonus_pts - i
                    db.override_score(answer["id"], answer["score"] + bonus)


async def _run_timer(session_id: str, duration: int):
    """Auto-advance state after timer expires."""
    await asyncio.sleep(duration)
    session = db.get_session(session_id)
    if not session or session["state"] != "question":
        return
    _score_current_question(session_id, session)
    # Move to answer reveal
    db.update_session(session_id, {"state": "answer_reveal"})
    session = db.get_session(session_id)
    await _broadcast_state(session_id, session)


def start_timer(session_id: str, duration: int):
    if session_id in _timer_tasks:
        _timer_tasks[session_id].cancel()
    task = asyncio.create_task(_run_timer(session_id, duration))
    _timer_tasks[session_id] = task


def cancel_timer(session_id: str):
    if session_id in _timer_tasks:
        _timer_tasks[session_id].cancel()
        del _timer_tasks[session_id]


def _begin_question(session_id: str, ri: int, qi: int, question: dict):
    """Put the session into 'question' state for (ri, qi) with a fresh timer."""
    duration = question.get("time", 30)
    ends = datetime.now(timezone.utc) + timedelta(seconds=duration)
    db.update_session(session_id, {
        "state": "question",
        "current_round_index": ri,
        "current_question_index": qi,
        "timer_ends_at": ends.isoformat(),
    })
    start_timer(session_id, duration)


# ── State broadcast helper ────────────────────────────────────────────────────

def _resolve_session_image_url(session_id: str, img_ref: str | None) -> str | None:
    if not img_ref:
        return None
    ref = str(img_ref).strip()
    if not ref:
        return None
    if ref.startswith(("http://", "https://", "data:", "/quiz-images/", "/static/")):
        return ref
    clean_path = ref.lstrip("/")
    return f"/api/sessions/{session_id}/image?path={clean_path}"


def _compute_next_question(rounds: list, ri: int, qi: int) -> dict:
    """Peek at what comes after the current question, for the host 'coming up' preview."""
    current_round = rounds[ri] if ri < len(rounds) else None
    total_qs = len(current_round["questions"]) if current_round else 0

    if current_round and qi + 1 < total_qs:
        return {
            "next_question": dict(current_round["questions"][qi + 1]),
            "next_question_index": qi + 1,
            "next_round_index": ri,
            "next_round_name": current_round["name"],
            "next_round_instructions": current_round.get("instructions"),
            "next_is_new_round": False,
            "next_is_end": False,
        }

    next_ri = ri + 1
    if next_ri < len(rounds):
        next_round = rounds[next_ri]
        next_qs = next_round.get("questions", [])
        return {
            "next_question": dict(next_qs[0]) if next_qs else None,
            "next_question_index": 0,
            "next_round_index": next_ri,
            "next_round_name": next_round["name"],
            "next_round_instructions": next_round.get("instructions"),
            "next_is_new_round": True,
            "next_is_end": False,
        }

    return {
        "next_question": None,
        "next_question_index": None,
        "next_round_index": None,
        "next_round_name": None,
        "next_round_instructions": None,
        "next_is_new_round": False,
        "next_is_end": True,
    }


async def _broadcast_state(session_id: str, session: dict):
    """Send full game state to all connected clients."""
    if not session:
        return
    quiz = session["quiz_data"]
    rounds = quiz.get("rounds", [])
    ri = session["current_round_index"]
    qi = session["current_question_index"]

    current_round = rounds[ri] if ri < len(rounds) else None
    current_question = None
    if current_round:
        qs = current_round.get("questions", [])
        if qi < len(qs):
            current_question = dict(qs[qi])

    # Strip correct answers from question for player view (sent separately)
    player_question = _strip_answers(current_question) if current_question else None

    # Resolve relative image URLs for clients
    round_img = _resolve_session_image_url(session_id, current_round.get("image")) if current_round else None
    if current_question and current_question.get("image"):
        current_question["image"] = _resolve_session_image_url(session_id, current_question.get("image"))
    if player_question and player_question.get("image"):
        player_question["image"] = _resolve_session_image_url(session_id, player_question.get("image"))

    teams = db.get_teams(session_id)
    leaderboard = db.get_leaderboard(session_id)

    answers_for_q = []
    if current_question:
        answers_for_q = db.get_answers(session_id, ri, qi)

    answered_team_ids = {a["team_id"] for a in answers_for_q}

    next_info = _compute_next_question(rounds, ri, qi)
    if next_info["next_question"] and next_info["next_question"].get("image"):
        next_info["next_question"]["image"] = _resolve_session_image_url(
            session_id, next_info["next_question"]["image"]
        )

    payload = {
        "type": "state",
        "session_id": session_id,
        "state": session["state"],
        "quiz_title": quiz.get("title", "Quiz"),
        "round_index": ri,
        "question_index": qi,
        "round_name": current_round["name"] if current_round else "",
        "round_instructions": current_round.get("instructions") if current_round else None,
        "round_image": round_img,
        "total_rounds": len(rounds),
        "total_questions": len(current_round["questions"]) if current_round else 0,
        "question": player_question,
        "question_with_answers": current_question,  # host/display gets this
        "timer_ends_at": session.get("timer_ends_at"),
        "teams": teams,
        "leaderboard": leaderboard,
        "answered_count": len(answered_team_ids),
        "total_teams": len(teams),
        "answers": answers_for_q,
        **next_info,
    }
    await manager.broadcast(session_id, payload)


def _strip_answers(q: dict) -> dict:
    """Remove correct answer info for player-facing question."""
    if not q:
        return q
    stripped = {k: v for k, v in q.items() if k not in ("correct", "answer", "tolerance")}
    return stripped


# ── App setup ─────────────────────────────────────────────────────────────────

app = FastAPI(title="Quiz-Meister")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.mount("/quiz-images", StaticFiles(directory=str(QUIZZES_DIR / "images")), name="quiz-images")


@app.get("/")
async def root():
    return RedirectResponse("/host")


@app.get("/host")
async def host_page():
    return FileResponse(str(STATIC_DIR / "host.html"))


@app.get("/display")
async def display_page():
    return FileResponse(str(STATIC_DIR / "display.html"))


@app.get("/editor")
async def editor_page():
    return FileResponse(str(STATIC_DIR / "editor.html"))


@app.get("/play")
async def play_page():
    return FileResponse(str(STATIC_DIR / "play.html"))


# ── API ───────────────────────────────────────────────────────────────────────

@app.get("/api/quizzes")
async def list_quizzes(path: str = None):
    """List quiz files. If ?path= is provided, list that directory's files and subdirectories.

    NOTE: Allowing arbitrary paths exposes the server filesystem. This implementation
    tries to be minimally restrictive: when path is provided, it returns absolute
    paths for files and directories under that path. Callers (the host UI) should
    only use this when trusted. When no path is provided, list files under QUIZZES_DIR
    as before.
    """
    try:
        if path:
            p = Path(path)
            if not p.exists():
                return JSONResponse({"error": "Path not found"}, status_code=404)
            if not p.is_dir():
                return JSONResponse({"error": "Path is not a directory"}, status_code=400)
            files = []
            dirs = []
            for child in sorted(p.iterdir()):
                if child.is_dir():
                    dirs.append(str(child))
                elif child.is_file() and child.suffix.lower() in ('.yaml', '.yml', '.json'):
                    files.append(str(child))
            return {"cwd": str(p), "files": files, "dirs": dirs}
        else:
            files = quiz_loader.list_quiz_files(str(QUIZZES_DIR))
            return {"cwd": str(QUIZZES_DIR), "files": files}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/config")
async def get_config():
    local_ip = os.environ.get("LOCAL_IP", "localhost")
    port = os.environ.get("PORT", "8000")
    return {"player_url": f"http://{local_ip}:{port}/play"}


@app.get("/api/quizzes/load")
async def load_quiz_content(file: str):
    provided = file or ""
    if os.path.isabs(provided):
        path = Path(provided)
    else:
        path = QUIZZES_DIR / provided
        if not path.exists():
            alt_path = BASE_DIR / provided
            if alt_path.exists():
                path = alt_path

    if not path.exists() or not path.is_file():
        raise HTTPException(404, f"Quiz file not found: {file}")
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        return {"filename": path.name, "path": str(path), "content": content}
    except Exception as e:
        raise HTTPException(500, f"Failed to read file: {e}")


class SaveQuizRequest(BaseModel):
    filename: str | None = None
    path: str | None = None
    content: str


@app.post("/api/quizzes/save")
async def save_quiz(req: SaveQuizRequest):
    if req.path:
        provided = req.path.strip()
        if os.path.isabs(provided):
            dest_path = Path(provided)
        else:
            dest_path = (QUIZZES_DIR / provided).resolve()
    elif req.filename:
        filename = req.filename.replace("..", "").replace("/", "").replace("\\", "").strip()
        if not filename.endswith((".yaml", ".yml")):
            filename += ".yaml"
        dest_path = (QUIZZES_DIR / filename).resolve()
    else:
        dest_path = (QUIZZES_DIR / "quiz.yaml").resolve()

    if not dest_path.name.endswith((".yaml", ".yml")):
        dest_path = dest_path.with_suffix(".yaml")

    try:
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        with open(dest_path, "w", encoding="utf-8") as f:
            f.write(req.content)
        return {"ok": True, "filename": dest_path.name, "path": str(dest_path)}
    except Exception as e:
        raise HTTPException(500, f"Failed to save: {e}")


def _unique_image_name(images_dir: Path, stem: str, suffix: str) -> str:
    """Return a non-colliding filename inside *images_dir*.

    Tries ``<stem><suffix>`` first, then ``<stem>_1<suffix>``,
    ``<stem>_2<suffix>``, … until a free slot is found.
    """
    candidate = f"{stem}{suffix}"
    if not (images_dir / candidate).exists():
        return candidate
    n = 1
    while (images_dir / f"{stem}_{n}{suffix}").exists():
        n += 1
    return f"{stem}_{n}{suffix}"


@app.post("/api/quizzes/upload-image")
async def upload_image(
    file: UploadFile = File(...),
    quiz_file: str | None = Form(None),
    original_filename: str | None = Form(None),
):
    """Accept an image upload and save it to an images/ folder relative to the quiz YAML file.
    Returns the relative path for use in quiz YAML files.

    *original_filename* – the browser's original filename before any re-encoding
    (e.g. ``photo.png``).  When omitted the uploaded file's own name is used.
    A ``_resized`` marker is appended to the stem when the browser converted the
    image from a non-JPEG source format to JPEG.  If a file with the chosen name
    already exists, a numeric suffix (``_1``, ``_2``, …) is appended instead of
    overwriting.
    """
    if not quiz_file or not quiz_file.strip():
        raise HTTPException(400, "quiz_file is required. Please save the quiz before uploading images.")

    provided = quiz_file.strip()
    if os.path.isabs(provided):
        quiz_path = Path(provided).resolve()
    else:
        quiz_path = (QUIZZES_DIR / provided).resolve()

    # Determine the effective suffix from the uploaded file (always .jpg after
    # browser compression, but validated against the allow-list regardless).
    upload_name = (file.filename or "image").replace("..", "").replace("/", "").replace("\\", "")
    upload_suffix = Path(upload_name).suffix.lower() or ".jpg"
    if upload_suffix not in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg"):
        raise HTTPException(400, "Unsupported image type. Use jpg, png, gif, webp, or svg.")

    # Build the destination stem from the original filename when supplied.
    raw_orig = (original_filename or upload_name).replace("..", "").replace("/", "").replace("\\", "")
    orig_suffix = Path(raw_orig).suffix.lower() or upload_suffix
    orig_stem = Path(raw_orig).stem[:60].strip("._- ") or "image"

    # If the browser converted the format (e.g. PNG → JPG), add '_resized'.
    was_converted = orig_suffix not in (".jpg", ".jpeg") and upload_suffix in (".jpg", ".jpeg")
    dest_stem = f"{orig_stem}_resized" if was_converted else orig_stem

    images_dir = quiz_path.parent / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    unique_name = _unique_image_name(images_dir, dest_stem, upload_suffix)
    dest = images_dir / unique_name
    try:
        content = await file.read()
        with open(dest, "wb") as f:
            f.write(content)
        return {
            "ok": True,
            "path": f"images/{unique_name}",
            "filename": unique_name,
        }
    except Exception as e:
        raise HTTPException(500, f"Failed to save image: {e}")


@app.get("/api/quizzes/image")
async def get_quiz_image(quiz_file: str, path: str):
    """Serve an image relative to a quiz YAML file (e.g. for editor previews)."""
    if not quiz_file:
        raise HTTPException(400, "quiz_file is required")
    provided = quiz_file.strip()
    if os.path.isabs(provided):
        quiz_path = Path(provided).resolve()
    else:
        quiz_path = (QUIZZES_DIR / provided).resolve()

    quiz_dir = quiz_path.parent
    clean_path = path.lstrip("/")

    img_path = (quiz_dir / clean_path).resolve()
    if not img_path.exists() or not img_path.is_file():
        alt_path = (quiz_dir / "images" / clean_path).resolve()
        if alt_path.exists() and alt_path.is_file():
            img_path = alt_path
        else:
            fallback = (QUIZZES_DIR / "images" / clean_path).resolve()
            if fallback.exists() and fallback.is_file():
                img_path = fallback
            else:
                raise HTTPException(404, f"Image not found: {path}")

    if img_path.suffix.lower() not in ('.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg'):
        raise HTTPException(400, "Invalid image format")

    return FileResponse(str(img_path))


@app.get("/api/sessions/{session_id}/image")
async def get_session_image(session_id: str, path: str):
    """Serve an image relative to the session's active quiz YAML file."""
    session = db.get_session(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    quiz_file = session.get("quiz_file")
    if not quiz_file:
        raise HTTPException(404, "Quiz file not found in session")

    provided = str(quiz_file).strip()
    if os.path.isabs(provided):
        quiz_path = Path(provided).resolve()
    else:
        quiz_path = (QUIZZES_DIR / provided).resolve()

    quiz_dir = quiz_path.parent
    clean_path = path.lstrip("/")

    img_path = (quiz_dir / clean_path).resolve()
    if not img_path.exists() or not img_path.is_file():
        alt_path = (quiz_dir / "images" / clean_path).resolve()
        if alt_path.exists() and alt_path.is_file():
            img_path = alt_path
        else:
            fallback = (QUIZZES_DIR / "images" / clean_path).resolve()
            if fallback.exists() and fallback.is_file():
                img_path = fallback
            else:
                raise HTTPException(404, f"Image not found: {path}")

    if img_path.suffix.lower() not in ('.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg'):
        raise HTTPException(400, "Invalid image format")

    return FileResponse(str(img_path))


class CreateSessionRequest(BaseModel):
    quiz_file: str
    bonus_points: int = 0


@app.post("/api/sessions")
async def create_session(req: CreateSessionRequest):
    # Allow either a path relative to QUIZZES_DIR or an absolute path when provided.
    # If an absolute path is given, use it directly; otherwise resolve under QUIZZES_DIR.
    provided = req.quiz_file or ""
    if os.path.isabs(provided):
        path = Path(provided)
    else:
        path = QUIZZES_DIR / provided

    if not path.exists():
        raise HTTPException(400, f"Quiz file not found: {req.quiz_file}")
    try:
        quiz_data = quiz_loader.load_quiz(str(path))
    except Exception as e:
        raise HTTPException(400, f"Invalid quiz file: {e}")

    host_secret = secrets.token_urlsafe(16)
    # Store the original provided string so sessions created from absolute paths
    # remember the actual path used.
    session = db.create_session(str(path), quiz_data, host_secret, req.bonus_points)
    return {
        "session_id": session["id"],
        "host_secret": host_secret,
        "quiz_title": quiz_data["title"],
        "bonus_points": req.bonus_points,
    }


@app.get("/api/sessions/{session_id}")
async def get_session(session_id: str):
    session = db.get_session(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    # Unauthenticated endpoint — don't leak the host secret or the full quiz
    # (with answers) to anyone who can guess/enumerate a session ID.
    return {k: v for k, v in session.items() if k not in ("host_secret", "quiz_data")}


class JoinRequest(BaseModel):
    team_name: str
    browser_id: str


@app.post("/api/sessions/{session_id}/join")
async def join_session(session_id: str, req: JoinRequest):
    session = db.get_session(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    if session["state"] not in ("lobby", "question"):
        raise HTTPException(400, "Session is not accepting new players")

    name = req.team_name.strip()[:30]
    if not name:
        raise HTTPException(400, "Team name required")

    # Check name uniqueness
    teams = db.get_teams(session_id)
    existing_names = {t["name"].lower() for t in teams if t["browser_id"] != req.browser_id}
    if name.lower() in existing_names:
        raise HTTPException(409, "Team name already taken")

    try:
        team = db.register_team(session_id, name, req.browser_id)
    except Exception as e:
        raise HTTPException(409, str(e))

    # Broadcast updated team list
    session = db.get_session(session_id)
    await _broadcast_state(session_id, session)

    return {"team_id": team["id"], "team_name": team["name"]}


class AnswerRequest(BaseModel):
    team_id: str
    answer_data: list


@app.post("/api/sessions/{session_id}/answer")
async def submit_answer(session_id: str, req: AnswerRequest):
    session = db.get_session(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    if session["state"] != "question":
        raise HTTPException(400, "Not currently accepting answers")

    quiz = session["quiz_data"]
    ri = session["current_round_index"]
    qi = session["current_question_index"]
    rounds = quiz.get("rounds", [])

    if ri >= len(rounds):
        raise HTTPException(400, "Invalid round")
    qs = rounds[ri].get("questions", [])
    if qi >= len(qs):
        raise HTTPException(400, "Invalid question")

    question = qs[qi]

    # Don't score numeric here — scored relatively at reveal
    score = 0
    if question["type"] != "numeric":
        score = quiz_loader.score_answer(question, req.answer_data)

    answer = db.submit_answer(session_id, req.team_id, ri, qi, req.answer_data, score)

    # Broadcast updated answered count
    session = db.get_session(session_id)
    await _broadcast_state(session_id, session)

    return {"answer_id": answer["id"], "score": score}


class ActionRequest(BaseModel):
    host_secret: str
    action: str
    payload: dict = {}


@app.post("/api/sessions/{session_id}/action")
async def session_action(session_id: str, req: ActionRequest):
    session = db.get_session(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    if session["host_secret"] != req.host_secret:
        raise HTTPException(403, "Invalid host secret")

    action = req.action
    quiz = session["quiz_data"]
    rounds = quiz.get("rounds", [])
    ri = session["current_round_index"]
    qi = session["current_question_index"]

    if action == "start_question":
        if session["state"] not in ("lobby", "round_intro", "answer_reveal", "leaderboard"):
            raise HTTPException(400, f"Cannot start question from state: {session['state']}")

        # Advance indices if coming from answer_reveal
        if session["state"] == "answer_reveal":
            current_round = rounds[ri] if ri < len(rounds) else None
            total_qs = len(current_round["questions"]) if current_round else 0
            if qi + 1 < total_qs:
                qi += 1
            else:
                # Round over — go to leaderboard first
                db.update_session(session_id, {"state": "leaderboard"})
                session = db.get_session(session_id)
                await _broadcast_state(session_id, session)
                return {"state": "leaderboard"}

        current_round = rounds[ri] if ri < len(rounds) else None
        if not current_round:
            raise HTTPException(400, "No more rounds")

        question = current_round["questions"][qi]
        _begin_question(session_id, ri, qi, question)
        session = db.get_session(session_id)
        await _broadcast_state(session_id, session)
        return {"state": "question"}

    elif action == "start_round":
        if session["state"] != "lobby":
            raise HTTPException(400, f"Cannot start round from state: {session['state']}")
        db.update_session(session_id, {
            "state": "round_intro",
            "current_round_index": 0,
            "current_question_index": 0,
        })
        session = db.get_session(session_id)
        await _broadcast_state(session_id, session)
        return {"state": "round_intro"}

    elif action == "reveal_answer":
        if session["state"] != "question":
            raise HTTPException(400, "Not in question state")

        cancel_timer(session_id)

        # Score the question
        _score_current_question(session_id, session)

        db.update_session(session_id, {"state": "answer_reveal"})
        session = db.get_session(session_id)
        await _broadcast_state(session_id, session)
        return {"state": "answer_reveal"}

    elif action == "show_leaderboard":
        db.update_session(session_id, {"state": "leaderboard"})
        session = db.get_session(session_id)
        await _broadcast_state(session_id, session)
        return {"state": "leaderboard"}

    elif action == "back_to_reveal":
        # Return to the answer reveal for the current question
        db.update_session(session_id, {"state": "answer_reveal"})
        session = db.get_session(session_id)
        await _broadcast_state(session_id, session)
        return {"state": "answer_reveal"}

    elif action == "restart_question":
        if session["state"] not in ("question", "answer_reveal"):
            raise HTTPException(400, f"Cannot restart question from state: {session['state']}")

        current_round = rounds[ri] if ri < len(rounds) else None
        if not current_round:
            raise HTTPException(400, "No more rounds")

        cancel_timer(session_id)
        db.clear_answers(session_id, ri, qi)
        question = current_round["questions"][qi]
        _begin_question(session_id, ri, qi, question)
        session = db.get_session(session_id)
        await _broadcast_state(session_id, session)
        return {"state": "question"}

    elif action == "next_round":
        if ri + 1 >= len(rounds):
            db.update_session(session_id, {"state": "ended"})
            session = db.get_session(session_id)
            await _broadcast_state(session_id, session)
            return {"state": "ended"}
        db.update_session(session_id, {
            "state": "round_intro",
            "current_round_index": ri + 1,
            "current_question_index": 0,
        })
        session = db.get_session(session_id)
        await _broadcast_state(session_id, session)
        return {"state": "round_intro", "round_index": ri + 1}

    elif action == "override_score":
        answer_id = req.payload.get("answer_id")
        score = req.payload.get("score")
        if answer_id is None or score is None:
            raise HTTPException(400, "answer_id and score required")
        db.override_score(answer_id, int(score))
        session = db.get_session(session_id)
        await _broadcast_state(session_id, session)
        return {"ok": True}

    elif action == "override_team_score":
        team_id = req.payload.get("team_id")
        adjustment = req.payload.get("adjustment", 0)
        if not team_id:
            raise HTTPException(400, "team_id required")
        # Add a synthetic answer row for the adjustment
        db.submit_answer(
            session_id, team_id, -1, -1,
            ["manual_override"],
            int(adjustment)
        )
        session = db.get_session(session_id)
        await _broadcast_state(session_id, session)
        return {"ok": True}

    elif action == "reset_to_lobby":
        db.update_session(session_id, {
            "state": "lobby",
            "current_round_index": ri,
            "current_question_index": qi,
        })
        session = db.get_session(session_id)
        await _broadcast_state(session_id, session)
        return {"state": "lobby"}

    else:
        raise HTTPException(400, f"Unknown action: {action}")


@app.get("/api/sessions/{session_id}/leaderboard")
async def get_leaderboard(session_id: str):
    session = db.get_session(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    return {"leaderboard": db.get_leaderboard(session_id)}


# ── WebSocket ─────────────────────────────────────────────────────────────────

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(ws: WebSocket, session_id: str):
    await manager.connect(session_id, ws)
    # Send current state on connect
    session = db.get_session(session_id)
    if session:
        await _broadcast_state(session_id, session)
    try:
        while True:
            # Keep connection alive; clients send pings
            data = await ws.receive_text()
            if data == "ping":
                await ws.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(session_id, ws)
