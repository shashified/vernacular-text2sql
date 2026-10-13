"""
Start the review-panel demo.

    python scripts/demo_server.py                # http://localhost:8000
    python scripts/demo_server.py --port 8080
    python scripts/demo_server.py --env .env     # model used for Live mode (default .env)

Needs: pip install fastapi uvicorn   (and data/agri/agri_india.db, built by scripts/build_agri_db.py)
"""
from __future__ import annotations

import argparse
import os
import sys
import webbrowser

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--env", default=None, help="env file with the model for Live mode")
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args()
    if args.env:
        os.environ["DEMO_ENV"] = os.path.abspath(args.env)

    import uvicorn
    from src.benchmark.agri import DB_PATH
    if not os.path.exists(DB_PATH):
        sys.exit("Database missing. Run: python scripts/build_agri_db.py")
    url = f"http://localhost:{args.port}"
    print(f"Demo running at {url}  (Ctrl+C to stop)")
    if not args.no_browser:
        webbrowser.open(url)
    uvicorn.run("src.demo.server:app", host="127.0.0.1", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
