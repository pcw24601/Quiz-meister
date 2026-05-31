"""
In-memory database store for Quiz-Meister.
All data is lost on server restart. No external dependencies required.
"""

import uuid
from typing import Any


# ── In-memory stores ──────────────────────────────────────────────────────────

_sessions: dict[str, dict] = {}
_teams: dict[str, dict] = {}      # team_id → team
_answers: dict[str, dict] = {}    # answer_id → answer


# ── Sessions ──────────────────────────────────────────────────────────────────

def create_session(quiz_file: str, quiz_data: dict, host_secret: str,
                   bonus_points: int = 0) -> dict:
    session_id = str(uuid.uuid4())
    session = {
        "id": session_id,
        "quiz_file": quiz_file,
        "quiz_data": quiz_data,
        "state": "lobby",
        "current_round_index": 0,
        "current_question_index": 0,
        "host_secret": host_secret,
        "timer_ends_at": None,
        "bonus_points": bonus_points,
    }
    _sessions[session_id] = session
    return session


def get_session(session_id: str) -> dict | None:
    return _sessions.get(session_id)


def update_session(session_id: str, data: dict) -> dict:
    session = _sessions.get(session_id)
    if session:
        session.update(data)
    return session or {}


# ── Teams ─────────────────────────────────────────────────────────────────────

def register_team(session_id: str, name: str, browser_id: str) -> dict:
    # Return existing team for this browser_id if already registered
    for team in _teams.values():
        if team["session_id"] == session_id and team["browser_id"] == browser_id:
            return team
    team_id = str(uuid.uuid4())
    team = {
        "id": team_id,
        "session_id": session_id,
        "name": name,
        "browser_id": browser_id,
    }
    _teams[team_id] = team
    return team


def get_teams(session_id: str) -> list[dict]:
    return [t for t in _teams.values() if t["session_id"] == session_id]


def update_team(team_id: str, data: dict) -> dict:
    team = _teams.get(team_id)
    if team:
        team.update(data)
    return team or {}


# ── Answers ───────────────────────────────────────────────────────────────────

def submit_answer(session_id: str, team_id: str, round_index: int,
                  question_index: int, answer_data: list, score: int,
                  submitted_at: str = None) -> dict:
    # Prevent double-submit
    for answer in _answers.values():
        if (answer["session_id"] == session_id and
                answer["team_id"] == team_id and
                answer["round_index"] == round_index and
                answer["question_index"] == question_index):
            return answer
    answer_id = str(uuid.uuid4())
    if submitted_at is None:
        from datetime import datetime, timezone
        submitted_at = datetime.now(timezone.utc).isoformat()
    answer = {
        "id": answer_id,
        "session_id": session_id,
        "team_id": team_id,
        "round_index": round_index,
        "question_index": question_index,
        "answer_data": answer_data,
        "score": score,
        "score_overridden": False,
        "submitted_at": submitted_at,
    }
    _answers[answer_id] = answer
    return answer


def get_answers(session_id: str, round_index: int = None,
                question_index: int = None) -> list[dict]:
    result = [a for a in _answers.values() if a["session_id"] == session_id]
    if round_index is not None:
        result = [a for a in result if a["round_index"] == round_index]
    if question_index is not None:
        result = [a for a in result if a["question_index"] == question_index]
    return result


def override_score(answer_id: str, score: int) -> dict:
    answer = _answers.get(answer_id)
    if answer:
        answer["score"] = score
        answer["score_overridden"] = True
    return answer or {}


def clear_answers(session_id: str, round_index: int, question_index: int) -> int:
    """Delete all answers for a specific question. Returns count deleted."""
    to_delete = [
        aid for aid, a in _answers.items()
        if (a["session_id"] == session_id and
            a["round_index"] == round_index and
            a["question_index"] == question_index)
    ]
    for aid in to_delete:
        del _answers[aid]
    return len(to_delete)


def get_leaderboard(session_id: str) -> list[dict]:
    """Returns [{team_id, name, total_score}] sorted descending."""
    teams = get_teams(session_id)
    answers = get_answers(session_id)

    score_map: dict[str, int] = {}
    for a in answers:
        tid = a["team_id"]
        score_map[tid] = score_map.get(tid, 0) + a["score"]

    result = []
    for t in teams:
        result.append({
            "team_id": t["id"],
            "name": t["name"],
            "total_score": score_map.get(t["id"], 0),
        })
    result.sort(key=lambda x: x["total_score"], reverse=True)
    return result
