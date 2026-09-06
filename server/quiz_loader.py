"""
Loads and validates quiz YAML files. Returns structured quiz data.

Supported question types:
  - multiple_choice: one correct answer (options list, correct: index)
  - select_many: multiple correct answers (options list, correct: [indices])
  - order: put items in correct order (items list)
  - numeric: closest number wins (answer: number, tolerance optional)
  - picture: like multiple_choice but with an image displayed
"""

import re
import yaml
import os
from typing import Any


def load_quiz(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    try:
        raw = yaml.safe_load(content)
    except (yaml.parser.ParserError, yaml.scanner.ScannerError):
        # Fallback: clean up over-escaped backslashes before quotes
        fixed = re.sub(r'\\{2,}"', r'\"', content)
        raw = yaml.safe_load(fixed)

    if not isinstance(raw, dict):
        raw = {}

    quiz = {
        "title": str(raw.get("title", "Quiz")),
        "rounds": [],
    }

    for ri, round_raw in enumerate(raw.get("rounds", [])):
        round_obj = {
            "name": str(round_raw.get("name", f"Round {ri + 1}")),
            "instructions": round_raw.get("instructions") if round_raw.get("instructions") else None,
            "image": round_raw.get("image") if round_raw.get("image") else None,
            "questions": [],
        }
        for qi, q_raw in enumerate(round_raw.get("questions", [])):
            q = _parse_question(q_raw, ri, qi)
            round_obj["questions"].append(q)
        quiz["rounds"].append(round_obj)

    return quiz


def _parse_question(q: dict, ri: int, qi: int) -> dict:
    qtype = str(q.get("type", "multiple_choice"))
    base = {
        "type": qtype,
        "text": str(q.get("text", "")),
        "image": q.get("image"),
        "time": int(q.get("time", 30)),
        "points": int(q.get("points", 5)),
        "tiebreaker": bool(q.get("tiebreaker", False)),
        "answer_info": None,
    }
    # Backwards-compatible mapping for legacy keys that held explanations/hints
    ai = q.get("answer_info") or q.get("answerInfo") or q.get("explanation") or q.get("explain") or q.get("info")
    # Many older quizzes used `note` for an explanatory line; map it for non-first_letter types
    if ai is None and q.get("note") and qtype != "first_letter":
        ai = q.get("note")
    if ai is not None:
        base["answer_info"] = str(ai)

    if qtype in ("multiple_choice", "picture"):
        options = [str(o) for o in q.get("options", [])]
        correct = int(q.get("correct", 0))
        base["options"] = options
        base["correct"] = correct

    elif qtype == "select_many":
        options = [str(o) for o in q.get("options", [])]
        correct = [int(c) for c in q.get("correct", [])]
        base["options"] = options
        base["correct"] = correct

    elif qtype == "order":
        items = [str(i) for i in q.get("items", [])]
        base["items"] = items
        # correct order is the original order (indices 0,1,2,...)

    elif qtype == "numeric":
        base["answer"] = float(q.get("answer", 0))
        base["tolerance"] = q.get("tolerance")  # optional exact match tolerance

    elif qtype == "first_letter":
        base["answer"] = str(q.get("answer", "")).upper()
        # Optional note showing the full answer (displayed with question)
        if q.get("note"):
            base["note"] = str(q.get("note"))
        # Letters to display in the grid (optional, defaults to A-Z)
        letters = q.get("letters")
        if letters:
            base["letters"] = [str(l).upper() for l in letters]
        else:
            base["letters"] = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")

    return base


def score_answer(question: dict, answer_data: list) -> int:
    """Score a submitted answer against the correct answer. Returns points earned."""
    qtype = question["type"]
    points = question.get("points", 5)

    if qtype in ("multiple_choice", "picture"):
        if answer_data and int(answer_data[0]) == question["correct"]:
            return points
        return 0

    elif qtype == "select_many":
        correct_set = set(question["correct"])
        submitted_set = set(int(x) for x in answer_data)
        if submitted_set == correct_set:
            return points
        # partial credit: each correct selection minus each wrong selection, min 0
        correct_hits = len(submitted_set & correct_set)
        wrong_hits = len(submitted_set - correct_set)
        partial = max(0, correct_hits - wrong_hits)
        max_correct = len(correct_set)
        return round((partial / max_correct) * points) if max_correct else 0

    elif qtype == "order":
        n = len(question["items"])
        if not answer_data or len(answer_data) != n:
            return 0
        submitted = [int(x) for x in answer_data]
        correct = list(range(n))
        if submitted == correct:
            return points
        return 0

    elif qtype == "numeric":
        if not answer_data:
            return 0
        # Numeric scoring is relative — scored at reveal time vs all teams
        # Here we just return the submitted value for later comparison
        return 0

    elif qtype == "first_letter":
        if answer_data and str(answer_data[0]).upper() == question.get("answer", "").upper():
            return points
        return 0

    return 0


def score_numeric_round(teams_answers: list[dict], question: dict) -> dict[str, int]:
    """
    Given a list of {team_id, answer_data} for a numeric question,
    return {team_id: score}. Closest answer wins full points; ties share.
    """
    correct = float(question["answer"])
    points = question.get("points", 5)
    tolerance = question.get("tolerance")

    distances = []
    for ta in teams_answers:
        try:
            val = float(ta["answer_data"][0]) if ta["answer_data"] else None
        except (ValueError, TypeError):
            val = None
        if val is not None:
            distances.append((abs(val - correct), ta["team_id"]))

    if not distances:
        return {}

    distances.sort(key=lambda x: x[0])
    min_dist = distances[0][0]

    # If tolerance set, any answer within tolerance gets full points
    if tolerance is not None:
        result = {}
        for dist, tid in distances:
            result[tid] = points if dist <= float(tolerance) else 0
        return result

    # Otherwise closest wins; ties all get points
    result = {}
    for dist, tid in distances:
        result[tid] = points if dist == min_dist else 0
    return result


def list_quiz_files(quizzes_dir: str) -> list[str]:
    if not os.path.isdir(quizzes_dir):
        return []
    return sorted(
        f for f in os.listdir(quizzes_dir) if f.endswith((".yaml", ".yml"))
    )
