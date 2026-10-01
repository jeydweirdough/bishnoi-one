"""Start the Sales API for development, reloading on code changes.

    uv run main.py
    uv run main.py --port 8312

Same as: uv run uvicorn app.main:create_app --factory --reload --port 8302
"""

import argparse
import sys
from pathlib import Path

try:
    import uvicorn
except ImportError:
    sys.exit("The API's packages aren't installed in this Python. Run `uv sync`, then `uv run main.py`.")

API_DIR = Path(__file__).resolve().parent

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the Bishnoi One CRM API with auto-reload.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8302)
    args = parser.parse_args()
    uvicorn.run(
        "app.main:create_app",
        factory=True,
        host=args.host,
        port=args.port,
        reload=True,
        reload_dirs=[str(API_DIR / "app")],
    )
