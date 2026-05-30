#!/usr/bin/env python3
"""
Quiz-Meister launcher.
Run: python start.py
Then open http://localhost:8000 in your browser.
"""

import os
import sys
import subprocess
import socket

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return '127.0.0.1'

def load_env():
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    k, _, v = line.partition('=')
                    os.environ.setdefault(k.strip(), v.strip())

if __name__ == '__main__':
    load_env()

    # Map .env vars to what the app expects
    supabase_url = os.environ.get('VITE_SUPABASE_URL') or os.environ.get('SUPABASE_URL', '')
    supabase_key = (os.environ.get('VITE_SUPABASE_SUPABASE_ANON_KEY') or
                    os.environ.get('VITE_SUPABASE_ANON_KEY') or
                    os.environ.get('SUPABASE_ANON_KEY', ''))

    os.environ['SUPABASE_URL'] = supabase_url
    os.environ['SUPABASE_ANON_KEY'] = supabase_key

    ip = get_local_ip()
    os.environ['LOCAL_IP'] = ip
    port = int(os.environ.get('PORT', 8000))

    print(f"""
╔═══════════════════════════════════════════╗
║           Quiz-Meister Starting           ║
╠═══════════════════════════════════════════╣
║  Host panel:  http://localhost:{port}/host  ║
║  Big screen:  http://localhost:{port}/display
║  Player URL:  http://{ip}:{port}/play
║  (Share the player URL with teams)
╚═══════════════════════════════════════════╝
""")

    server_dir = os.path.join(os.path.dirname(__file__), 'server')
    os.chdir(server_dir)

    subprocess.run([
        sys.executable, '-m', 'uvicorn',
        'app:app',
        '--host', '0.0.0.0',
        '--port', str(port),
        '--reload',
    ])
