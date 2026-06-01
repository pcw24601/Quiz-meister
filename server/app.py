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
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
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


async def _run_timer(session_id: str, duration: int):
    """Auto-advance state after timer expires."""
    await asyncio.sleep(duration)
    session = db.get_session(session_id)
    if not session or session["state"] != "question":
        return
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


# ── State broadcast helper ────────────────────────────────────────────────────

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
            current_question = qs[qi]

    # Strip correct answers from question for player view (sent separately)
    player_question = _strip_answers(current_question) if current_question else None

    teams = db.get_teams(session_id)
    leaderboard = db.get_leaderboard(session_id)

    answers_for_q = []
    if current_question:
        answers_for_q = db.get_answers(session_id, ri, qi)

    answered_team_ids = {a["team_id"] for a in answers_for_q}

    payload = {
        "type": "state",
        "session_id": session_id,
        "state": session["state"],
        "quiz_title": quiz.get("title", "Quiz"),
        "round_index": ri,
        "question_index": qi,
        "round_name": current_round["name"] if current_round else "",
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
async def list_quizzes():
    files = quiz_loader.list_quiz_files(str(QUIZZES_DIR))
    return {"quizzes": files}


@app.get("/api/config")
async def get_config():
    local_ip = os.environ.get("LOCAL_IP", "localhost")
    port = os.environ.get("PORT", "8000")
    return {"player_url": f"http://{local_ip}:{port}/play"}


class SaveQuizRequest(BaseModel):
    filename: str
    content: str


@app.post("/api/quizzes/save")
async def save_quiz(req: SaveQuizRequest):
    # Sanitize filename
    filename = req.filename.replace("..", "").replace("/", "").replace("\\", "")
    if not filename.endswith((".yaml", ".yml")):
        filename += ".yaml"
    path = QUIZZES_DIR / filename
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(req.content)
        return {"ok": True, "filename": filename}
    except Exception as e:
        raise HTTPException(500, f"Failed to save: {e}")


class CreateSessionRequest(BaseModel):
    quiz_file: str
    bonus_points: int = 0


@app.post("/api/sessions")
async def create_session(req: CreateSessionRequest):
    path = QUIZZES_DIR / req.quiz_file
    if not path.exists():
        raise HTTPException(400, f"Quiz file not found: {req.quiz_file}")
    try:
        quiz_data = quiz_loader.load_quiz(str(path))
    except Exception as e:
        raise HTTPException(400, f"Invalid quiz file: {e}")

    host_secret = secrets.token_urlsafe(16)
    session = db.create_session(req.quiz_file, quiz_data, host_secret, req.bonus_points)
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
    return session


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
        if session["state"] not in ("lobby", "answer_reveal", "leaderboard"):
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
        duration = question.get("time", 30)

        timer_ends_at = datetime.now(timezone.utc)
        # We'll store ISO string
        from datetime import timedelta
        ends = datetime.now(timezone.utc) + timedelta(seconds=duration)
        ends_str = ends.isoformat()

        db.update_session(session_id, {
            "state": "question",
            "current_round_index": ri,
            "current_question_index": qi,
            "timer_ends_at": ends_str,
        })
        session = db.get_session(session_id)
        start_timer(session_id, duration)
        await _broadcast_state(session_id, session)
        return {"state": "question"}

    elif action == "reveal_answer":
        if session["state"] != "question":
            raise HTTPException(400, "Not in question state")

        cancel_timer(session_id)

        # Score the question
        current_round = rounds[ri] if ri < len(rounds) else None
        if current_round:
            question = current_round["questions"][qi]
            answers = db.get_answers(session_id, ri, qi)
            bonus_pts = session.get("bonus_points", 0)

            if question["type"] == "numeric":
                # Numeric: closest wins
                ta_list = [{"team_id": a["team_id"], "answer_data": a["answer_data"]} for a in answers]
                scores = quiz_loader.score_numeric_round(ta_list, question)

                # Apply bonus points to closest answers
                if bonus_pts > 0:
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
        # Clear all answers for current question and go back to lobby
        db.clear_answers(session_id, ri, qi)
        db.update_session(session_id, {"state": "lobby"})
        session = db.get_session(session_id)
        await _broadcast_state(session_id, session)
        return {"state": "lobby"}

    elif action == "next_round":
        if ri + 1 >= len(rounds):
            db.update_session(session_id, {"state": "ended"})
            session = db.get_session(session_id)
            await _broadcast_state(session_id, session)
            return {"state": "ended"}
        db.update_session(session_id, {
            "state": "lobby",
            "current_round_index": ri + 1,
            "current_question_index": 0,
        })
        session = db.get_session(session_id)
        await _broadcast_state(session_id, session)
        return {"state": "lobby", "round_index": ri + 1}

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
