"""Start the Inventory API for development, reloading on code changes.

    uv run main.py
    uv run main.py --port 8314

Same as: uv run uvicorn app.main:create_app --factory --reload --port 8304
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
    parser = argparse.ArgumentParser(description="Run the Bishnoi One Inventory API with auto-reload.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8304)
    args = parser.parse_args()
    uvicorn.run(
        "app.main:create_app",
        factory=True,
        host=args.host,
        port=args.port,
        reload=True,
        # A reload doesn't wait on connections the screens keep open (they never
        # close on their own, so it waited for ever and served the old code).
        timeout_graceful_shutdown=2,
        reload_dirs=[str(API_DIR / "app")],
    )
