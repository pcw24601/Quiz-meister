# Project Guidelines & Rules

## Python Package and Environment Management

Always use **`uv`** as the package and environment manager for this repository:

- **Running scripts & applications:** Use `uv run` to execute Python scripts, servers, or CLI commands.
  - Example: `uv run python start.py`
  - Example: `uv run uvicorn server.app:app --reload`
- **Running tests:** Execute tests using `uv run pytest`.
- **Managing dependencies:**
  - Add dependencies with `uv add <package>` (or `uv add --dev <package>` for dev tools).
  - Remove dependencies with `uv remove <package>`.
  - Sync project dependencies with `uv sync`.
- **Avoid raw `pip` or unmanaged `python`:** Do not use `pip install` or direct unmanaged `python`/`python3` commands without `uv run`.
