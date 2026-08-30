import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
SERVER_DIR = REPO_ROOT / "server"
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(SERVER_DIR))
