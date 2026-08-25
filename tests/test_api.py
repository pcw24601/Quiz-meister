from fastapi.testclient import TestClient
import server

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


def test_load_gpc_2026_quiz():
    import quiz_loader
    import os
    path = os.path.abspath('GCP_2026_quiz/gpc-2026.yaml')
    quiz = quiz_loader.load_quiz(path)
    assert quiz['title'] == 'GPC_2026'
    assert len(quiz['rounds']) == 8
    
    # Check answer_info on Old Testament Q1
    q1 = quiz['rounds'][0]['questions'][0]
    assert q1['type'] == 'first_letter'
    assert q1['answer'] == 'E'
    assert q1['answer_info'] == 'Ezekiel'

    # Check instructions on Say what?
    r3 = quiz['rounds'][2]
    assert '"Who wrote \'Alice in Wonderland\'?"' in r3['instructions']


def test_create_session_gpc_2026():
    import os
    path = os.path.abspath('GCP_2026_quiz/gpc-2026.yaml')
    res = client.post('/api/sessions', json={'quiz_file': path, 'bonus_points': 5})
    assert res.status_code == 200
    data = res.json()
    assert 'session_id' in data
    assert data['quiz_title'] == 'GPC_2026'


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

