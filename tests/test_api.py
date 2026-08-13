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
