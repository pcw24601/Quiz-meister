"""
Supabase database client and helper functions.
Uses the REST API directly via httpx (no Python Supabase SDK required).
"""

import os
import json
import httpx
from typing import Any


SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "")

_headers = {
    "apikey": SUPABASE_ANON_KEY,
    "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}


def _url(table: str) -> str:
    return f"{SUPABASE_URL}/rest/v1/{table}"


def _get(table: str, params: dict = None) -> list[dict]:
    r = httpx.get(_url(table), headers=_headers, params=params)
    r.raise_for_status()
    return r.json()


def _post(table: str, data: dict) -> dict:
    r = httpx.post(_url(table), headers=_headers, json=data)
    r.raise_for_status()
    result = r.json()
    return result[0] if isinstance(result, list) else result


def _patch(table: str, filters: dict, data: dict) -> list[dict]:
    params = {k: f"eq.{v}" for k, v in filters.items()}
    r = httpx.patch(_url(table), headers=_headers, params=params, json=data)
    r.raise_for_status()
    return r.json()


# ── Sessions ──────────────────────────────────────────────────────────────────

def create_session(quiz_file: str, quiz_data: dict, host_secret: str) -> dict:
    return _post("sessions", {
        "quiz_file": quiz_file,
        "quiz_data": quiz_data,
        "state": "lobby",
        "current_round_index": 0,
        "current_question_index": 0,
        "host_secret": host_secret,
    })


def get_session(session_id: str) -> dict | None:
    rows = _get("sessions", {"id": f"eq.{session_id}", "select": "*"})
    return rows[0] if rows else None


def update_session(session_id: str, data: dict) -> dict:
    rows = _patch("sessions", {"id": session_id}, data)
    return rows[0] if rows else {}


# ── Teams ─────────────────────────────────────────────────────────────────────

def register_team(session_id: str, name: str, browser_id: str) -> dict:
    # Upsert by browser_id
    existing = _get("teams", {
        "session_id": f"eq.{session_id}",
        "browser_id": f"eq.{browser_id}",
        "select": "*",
    })
    if existing:
        return existing[0]
    return _post("teams", {
        "session_id": session_id,
        "name": name,
        "browser_id": browser_id,
    })


def get_teams(session_id: str) -> list[dict]:
    return _get("teams", {"session_id": f"eq.{session_id}", "select": "*"})


def update_team(team_id: str, data: dict) -> dict:
    rows = _patch("teams", {"id": team_id}, data)
    return rows[0] if rows else {}


# ── Answers ───────────────────────────────────────────────────────────────────

def submit_answer(session_id: str, team_id: str, round_index: int,
                  question_index: int, answer_data: list, score: int) -> dict:
    # Check if answer already exists (prevent double-submit)
    existing = _get("answers", {
        "session_id": f"eq.{session_id}",
        "team_id": f"eq.{team_id}",
        "round_index": f"eq.{round_index}",
        "question_index": f"eq.{question_index}",
        "select": "id",
    })
    if existing:
        return existing[0]
    return _post("answers", {
        "session_id": session_id,
        "team_id": team_id,
        "round_index": round_index,
        "question_index": question_index,
        "answer_data": answer_data,
        "score": score,
    })


def get_answers(session_id: str, round_index: int = None,
                question_index: int = None) -> list[dict]:
    params = {"session_id": f"eq.{session_id}", "select": "*"}
    if round_index is not None:
        params["round_index"] = f"eq.{round_index}"
    if question_index is not None:
        params["question_index"] = f"eq.{question_index}"
    return _get("answers", params)


def override_score(answer_id: str, score: int) -> dict:
    rows = _patch("answers", {"id": answer_id}, {
        "score": score,
        "score_overridden": True,
    })
    return rows[0] if rows else {}


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
