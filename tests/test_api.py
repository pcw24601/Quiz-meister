from pathlib import Path

from fastapi.testclient import TestClient
import server

REPO_ROOT = Path(__file__).resolve().parent.parent

client = TestClient(server.app)


def test_list_quizzes_default():
    res = client.get('/api/quizzes')
    assert res.status_code == 200
    data = res.json()
    assert 'files' in data
    # example.yaml is included in the repo's quizzes/ folder
    assert any('example.yaml' in f or f == 'example.yaml' for f in data['files'])


def test_list_quizzes_with_path():
    # Use the QUIZZES_DIR path from server
    quizzes_dir = str(server.QUIZZES_DIR)
    res = client.get('/api/quizzes', params={'path': quizzes_dir})
    assert res.status_code == 200
    data = res.json()
    assert 'cwd' in data and data['cwd'] == quizzes_dir
    assert 'files' in data
    assert any('example.yaml' in f or f.endswith('/example.yaml') or f.endswith('\\example.yaml') for f in data['files'])


def test_load_example_quiz():
    import quiz_loader
    path = str(REPO_ROOT / 'quizzes' / 'example.yaml')
    quiz = quiz_loader.load_quiz(path)
    assert quiz['title'] == 'General Knowledge Quiz Night'
    assert len(quiz['rounds']) == 4

    # Check first_letter question in Quickfire round
    quickfire = [r for r in quiz['rounds'] if r['name'] == 'Quickfire'][0]
    q1 = quickfire['questions'][0]
    assert q1['type'] == 'first_letter'
    assert q1['answer'] == 'H'
    assert q1['note'] == 'Water = H2O'

    # Check instructions on Geography round
    geography = [r for r in quiz['rounds'] if r['name'] == 'Geography'][0]
    assert 'Test your knowledge of countries' in geography['instructions']


def test_create_session_example_quiz():
    path = str(REPO_ROOT / 'quizzes' / 'example.yaml')
    res = client.post('/api/sessions', json={'quiz_file': path, 'bonus_points': 5})
    assert res.status_code == 200
    data = res.json()
    assert 'session_id' in data
    assert data['quiz_title'] == 'General Knowledge Quiz Night'


def test_quiz_loader_fallback_over_escaped_quotes(tmp_path):
    import quiz_loader
    content = '''
title: "Test Over-Escaped"
rounds:
  - name: "Round 1"
    instructions: "E.g. \\\\"Quote\\\\" -> \\\\"[Answer]\\\\""
    questions:
      - type: first_letter
        text: "Sample question?"
        answer: A
        answer_info: "Alpha"
'''
    f = tmp_path / "broken.yaml"
    f.write_text(content, encoding="utf-8")
    quiz = quiz_loader.load_quiz(str(f))
    assert quiz['title'] == "Test Over-Escaped"
    assert "Quote" in quiz['rounds'][0]['instructions']
    assert quiz['rounds'][0]['questions'][0]['answer_info'] == "Alpha"


def test_save_quiz_with_custom_path_and_default(tmp_path):
    custom_file = tmp_path / "subfolder" / "my_custom_quiz.yaml"
    content = 'title: "Custom Quiz"\nrounds: []\n'
    res = client.post('/api/quizzes/save', json={'path': str(custom_file), 'content': content})
    assert res.status_code == 200
    data = res.json()
    assert data['ok'] is True
    assert data['filename'] == "my_custom_quiz.yaml"
    assert custom_file.exists()
    assert custom_file.read_text(encoding="utf-8") == content


def test_upload_image_requires_quiz_file():
    # Attempt upload without quiz_file
    files = {'file': ('test.jpg', b'dummy content', 'image/jpeg')}
    res = client.post('/api/quizzes/upload-image', files=files, data={'quiz_file': ''})
    assert res.status_code == 400
    assert 'quiz_file is required' in res.json()['detail']


def test_upload_and_get_quiz_image(tmp_path):
    quiz_file = tmp_path / "sample_quiz.yaml"
    quiz_file.write_text('title: "Sample"\nrounds: []\n', encoding="utf-8")

    files = {'file': ('pic.jpg', b'fake-image-bytes', 'image/jpeg')}
    res = client.post('/api/quizzes/upload-image', files=files, data={'quiz_file': str(quiz_file)})
    assert res.status_code == 200
    data = res.json()
    assert data['ok'] is True
    assert data['path'].startswith('images/')
    
    # Check that image was written in tmp_path/images/
    saved_img = tmp_path / data['path']
    assert saved_img.exists()
    assert saved_img.read_bytes() == b'fake-image-bytes'

    # Check reading image via GET /api/quizzes/image
    img_res = client.get('/api/quizzes/image', params={'quiz_file': str(quiz_file), 'path': data['path']})
    assert img_res.status_code == 200
    assert img_res.content == b'fake-image-bytes'


def test_session_image_serving(tmp_path):
    import os
    quiz_yaml = """title: "Session Test"
rounds:
  - name: "Round 1"
    image: "images/round1.png"
    questions:
      - type: picture
        text: "What is this?"
        image: "images/q1.png"
        options: ["A", "B"]
        correct: 0
"""
    q_file = tmp_path / "test_quiz.yaml"
    q_file.write_text(quiz_yaml, encoding="utf-8")
    img_dir = tmp_path / "images"
    img_dir.mkdir()
    (img_dir / "round1.png").write_bytes(b'round-img-bytes')
    (img_dir / "q1.png").write_bytes(b'question-img-bytes')

    # Create session
    res = client.post('/api/sessions', json={'quiz_file': str(q_file)})
    assert res.status_code == 200
    session_id = res.json()['session_id']

    # Retrieve round image via session endpoint
    r_img_res = client.get(f'/api/sessions/{session_id}/image', params={'path': 'images/round1.png'})
    assert r_img_res.status_code == 200
    assert r_img_res.content == b'round-img-bytes'

    # Retrieve question image via session endpoint
    q_img_res = client.get(f'/api/sessions/{session_id}/image', params={'path': 'images/q1.png'})
    assert q_img_res.status_code == 200
    assert q_img_res.content == b'question-img-bytes'

    # Non-existent image returns 404
    missing_res = client.get(f'/api/sessions/{session_id}/image', params={'path': 'images/does_not_exist.png'})
    assert missing_res.status_code == 404


def test_upload_image_invalid_extension(tmp_path):
    quiz_file = tmp_path / "sample.yaml"
    quiz_file.write_text('title: "Sample"\nrounds: []\n', encoding="utf-8")
    files = {'file': ('bad.exe', b'bad-content', 'application/x-msdownload')}
    res = client.post('/api/quizzes/upload-image', files=files, data={'quiz_file': str(quiz_file)})
    assert res.status_code == 400
    assert 'Unsupported image type' in res.json()['detail']


def test_upload_image_preserves_original_filename(tmp_path):
    quiz_file = tmp_path / "sample.yaml"
    quiz_file.write_text('title: "Sample"\nrounds: []\n', encoding="utf-8")
    files = {'file': ('my_photo.jpg', b'img-bytes', 'image/jpeg')}
    data = {'quiz_file': str(quiz_file), 'original_filename': 'my_photo.jpg'}
    res = client.post('/api/quizzes/upload-image', files=files, data=data)
    assert res.status_code == 200
    assert res.json()['path'] == 'images/my_photo.jpg'


def test_upload_image_disambiguation(tmp_path):
    quiz_file = tmp_path / "sample.yaml"
    quiz_file.write_text('title: "Sample"\nrounds: []\n', encoding="utf-8")
    # First upload
    f1 = {'file': ('photo.jpg', b'v1', 'image/jpeg')}
    d1 = {'quiz_file': str(quiz_file), 'original_filename': 'photo.jpg'}
    r1 = client.post('/api/quizzes/upload-image', files=f1, data=d1)
    assert r1.json()['path'] == 'images/photo.jpg'
    # Duplicate upload
    f2 = {'file': ('photo.jpg', b'v2', 'image/jpeg')}
    d2 = {'quiz_file': str(quiz_file), 'original_filename': 'photo.jpg'}
    r2 = client.post('/api/quizzes/upload-image', files=f2, data=d2)
    assert r2.json()['path'] == 'images/photo_1.jpg'
    # Third upload
    f3 = {'file': ('photo.jpg', b'v3', 'image/jpeg')}
    d3 = {'quiz_file': str(quiz_file), 'original_filename': 'photo.jpg'}
    r3 = client.post('/api/quizzes/upload-image', files=f3, data=d3)
    assert r3.json()['path'] == 'images/photo_2.jpg'


def test_upload_image_resized_suffix(tmp_path):
    """PNG converted to JPEG by the browser should get a _resized suffix."""
    quiz_file = tmp_path / "sample.yaml"
    quiz_file.write_text('title: "Sample"\nrounds: []\n', encoding="utf-8")
    files = {'file': ('logo.jpg', b'img-bytes', 'image/jpeg')}
    data = {'quiz_file': str(quiz_file), 'original_filename': 'logo.png'}
    res = client.post('/api/quizzes/upload-image', files=files, data=data)
    assert res.status_code == 200
    assert res.json()['path'] == 'images/logo_resized.jpg'


def test_resolve_session_image_url():
    from app import _resolve_session_image_url
    # None and empty
    assert _resolve_session_image_url("s1", None) is None
    assert _resolve_session_image_url("s1", "") is None
    
    # External URLs
    assert _resolve_session_image_url("s1", "https://example.com/pic.jpg") == "https://example.com/pic.jpg"
    assert _resolve_session_image_url("s1", "http://example.com/pic.jpg") == "http://example.com/pic.jpg"
    assert _resolve_session_image_url("s1", "data:image/png;base64,...") == "data:image/png;base64,..."
    
    # Legacy /quiz-images/ mount
    assert _resolve_session_image_url("s1", "/quiz-images/round1.jpg") == "/quiz-images/round1.jpg"

    # Relative paths
    assert _resolve_session_image_url("s1", "images/round1.jpg") == "/api/sessions/s1/image?path=images/round1.jpg"
    assert _resolve_session_image_url("s1", "/images/round1.jpg") == "/api/sessions/s1/image?path=images/round1.jpg"
    assert _resolve_session_image_url("s1", "round1.jpg") == "/api/sessions/s1/image?path=round1.jpg"


def test_question_reveal_scoring_and_answers(tmp_path):
    quiz_yaml = """title: "Score Test"
rounds:
  - name: "Round 1"
    questions:
      - type: multiple_choice
        text: "What is 2+2?"
        options: ["3", "4", "5"]
        correct: 1
        points: 10
"""
    q_file = tmp_path / "score_test.yaml"
    q_file.write_text(quiz_yaml, encoding="utf-8")

    # Create session with 2 bonus points
    res = client.post('/api/sessions', json={'quiz_file': str(q_file), 'bonus_points': 2})
    assert res.status_code == 200
    session_id = res.json()['session_id']
    host_secret = res.json()['host_secret']

    # Register 3 teams
    t1_res = client.post(f'/api/sessions/{session_id}/join', json={'team_name': 'Team Alpha', 'browser_id': 'b1'})
    t1_id = t1_res.json()['team_id']

    t2_res = client.post(f'/api/sessions/{session_id}/join', json={'team_name': 'Team Beta', 'browser_id': 'b2'})
    t2_id = t2_res.json()['team_id']

    t3_res = client.post(f'/api/sessions/{session_id}/join', json={'team_name': 'Team Gamma', 'browser_id': 'b3'})
    t3_id = t3_res.json()['team_id']

    # Host starts question
    action_res = client.post(f'/api/sessions/{session_id}/action', json={
        'host_secret': host_secret,
        'action': 'start_question'
    })
    assert action_res.status_code == 200
    assert action_res.json()['state'] == 'question'

    # Team Alpha submits correct answer (index 1) first
    a1_res = client.post(f'/api/sessions/{session_id}/answer', json={
        'team_id': t1_id,
        'answer_data': [1]
    })
    assert a1_res.status_code == 200
    assert a1_res.json()['score'] == 10

    # Team Beta submits correct answer (index 1) second
    a2_res = client.post(f'/api/sessions/{session_id}/answer', json={
        'team_id': t2_id,
        'answer_data': [1]
    })
    assert a2_res.status_code == 200
    assert a2_res.json()['score'] == 10

    # Team Gamma submits incorrect answer (index 0)
    a3_res = client.post(f'/api/sessions/{session_id}/answer', json={
        'team_id': t3_id,
        'answer_data': [0]
    })
    assert a3_res.status_code == 200
    assert a3_res.json()['score'] == 0

    # Host reveals answer
    reveal_res = client.post(f'/api/sessions/{session_id}/action', json={
        'host_secret': host_secret,
        'action': 'reveal_answer'
    })
    assert reveal_res.status_code == 200
    assert reveal_res.json()['state'] == 'answer_reveal'

    # Verify answers stored in db
    import db
    answers = db.get_answers(session_id, 0, 0)
    ans_by_team = {a['team_id']: a['score'] for a in answers}
    
    # Team Alpha got 10 + 2 bonus = 12
    assert ans_by_team[t1_id] == 12
    # Team Beta got 10 + 1 bonus = 11
    assert ans_by_team[t2_id] == 11
    # Team Gamma got 0
    assert ans_by_team[t3_id] == 0






def test_restart_question_reruns_in_place_for_later_round(tmp_path):
    quiz_yaml = """title: "Restart Test"
rounds:
  - name: "Round 1"
    questions:
      - type: multiple_choice
        text: "Round 1 Q1"
        options: ["A", "B"]
        correct: 0
  - name: "Round 2"
    questions:
      - type: multiple_choice
        text: "Round 2 Q1"
        options: ["A", "B"]
        correct: 0
      - type: multiple_choice
        text: "Round 2 Q2"
        options: ["A", "B"]
        correct: 0
"""
    q_file = tmp_path / "restart_test.yaml"
    q_file.write_text(quiz_yaml, encoding="utf-8")

    res = client.post('/api/sessions', json={'quiz_file': str(q_file)})
    assert res.status_code == 200
    session_id = res.json()['session_id']
    host_secret = res.json()['host_secret']

    team_res = client.post(f'/api/sessions/{session_id}/join', json={'team_name': 'Team Alpha', 'browser_id': 'b1'})
    team_id = team_res.json()['team_id']

    def do_action(action):
        r = client.post(f'/api/sessions/{session_id}/action', json={'host_secret': host_secret, 'action': action})
        assert r.status_code == 200
        return r.json()

    # Walk through round 1 into round 2, question 1 (index 0)
    do_action('start_round')
    do_action('start_question')
    do_action('reveal_answer')
    do_action('next_round')
    started = do_action('start_question')
    assert started['state'] == 'question'

    # Team answers Round 2 Q1
    ans_res = client.post(f'/api/sessions/{session_id}/answer', json={'team_id': team_id, 'answer_data': [0]})
    assert ans_res.status_code == 200

    reveal = do_action('reveal_answer')
    assert reveal['state'] == 'answer_reveal'

    session_before = client.get(f'/api/sessions/{session_id}').json()
    timer_before = session_before['timer_ends_at']

    restarted = do_action('restart_question')
    assert restarted['state'] == 'question'

    session_after = client.get(f'/api/sessions/{session_id}').json()
    assert session_after['current_round_index'] == 1
    assert session_after['current_question_index'] == 0
    assert session_after['timer_ends_at'] != timer_before

    import db
    answers = db.get_answers(session_id, 1, 0)
    assert answers == []


def test_next_question_preview_across_round_boundary(tmp_path):
    quiz_yaml = """title: "Next Preview Test"
rounds:
  - name: "Round 1"
    questions:
      - type: multiple_choice
        text: "Round 1 Q1"
        options: ["A", "B"]
        correct: 0
  - name: "Round 2"
    instructions: "Round 2 instructions"
    questions:
      - type: multiple_choice
        text: "Round 2 Q1"
        options: ["A", "B"]
        correct: 0
"""
    q_file = tmp_path / "next_preview_test.yaml"
    q_file.write_text(quiz_yaml, encoding="utf-8")

    res = client.post('/api/sessions', json={'quiz_file': str(q_file)})
    session_id = res.json()['session_id']
    host_secret = res.json()['host_secret']

    def do_action(action):
        r = client.post(f'/api/sessions/{session_id}/action', json={'host_secret': host_secret, 'action': action})
        assert r.status_code == 200

    with client.websocket_connect(f'/ws/{session_id}') as ws:
        ws.receive_json()  # initial lobby state

        do_action('start_round')
        ws.receive_json()  # round_intro

        do_action('start_question')
        state = ws.receive_json()

        assert state['state'] == 'question'
        assert state['round_index'] == 0
        assert state['question_index'] == 0
        assert state['next_is_new_round'] is True
        assert state['next_is_end'] is False
        assert state['next_round_index'] == 1
        assert state['next_round_name'] == 'Round 2'
        assert state['next_round_instructions'] == 'Round 2 instructions'
        assert state['next_question_index'] == 0
        assert state['next_question']['text'] == 'Round 2 Q1'

        do_action('reveal_answer')
        ws.receive_json()

        do_action('start_question')  # round over -> leaderboard
        ws.receive_json()

        do_action('next_round')
        ws.receive_json()  # round_intro for Round 2

        do_action('start_question')  # Round 2 Q1
        state = ws.receive_json()

        assert state['round_index'] == 1
        assert state['question_index'] == 0
        assert state['next_is_end'] is True
        assert state['next_question'] is None


def test_session_id_is_five_digit_number(tmp_path):
    quiz_yaml = 'title: "Session ID Test"\nrounds: []\n'
    q_file = tmp_path / "sid_test.yaml"
    q_file.write_text(quiz_yaml, encoding="utf-8")

    res1 = client.post('/api/sessions', json={'quiz_file': str(q_file)})
    res2 = client.post('/api/sessions', json={'quiz_file': str(q_file)})
    assert res1.status_code == 200 and res2.status_code == 200

    sid1 = res1.json()['session_id']
    sid2 = res2.json()['session_id']

    assert sid1 != sid2
    for sid in (sid1, sid2):
        assert sid.isdigit()
        assert len(sid) == 5
        assert 10000 <= int(sid) <= 99999


def test_get_session_does_not_leak_host_secret_or_quiz_data(tmp_path):
    quiz_yaml = 'title: "Leak Test"\nrounds: []\n'
    q_file = tmp_path / "leak_test.yaml"
    q_file.write_text(quiz_yaml, encoding="utf-8")

    res = client.post('/api/sessions', json={'quiz_file': str(q_file)})
    session_id = res.json()['session_id']

    get_res = client.get(f'/api/sessions/{session_id}')
    assert get_res.status_code == 200
    data = get_res.json()
    assert 'host_secret' not in data
    assert 'quiz_data' not in data
    assert data['id'] == session_id
