"""The API as one ready-made app, for hosts that import it instead of running
main.py (Vercel: pyproject.toml's [tool.vercel] entrypoint). Its settings come
from the host's environment variables, as they would from backend/.env.
"""

from app.main import create_app

app = create_app()
