"""Start the portal:  python -m app  [--host 127.0.0.1] [--port 8765] [--demo]"""
from __future__ import annotations

import argparse
import webbrowser
import threading

import uvicorn

from .config import HOST, PORT, settings


def main() -> None:
    parser = argparse.ArgumentParser(description="RNU Thesis Copilot")
    parser.add_argument("--host", default=HOST)
    parser.add_argument("--port", type=int, default=PORT)
    parser.add_argument("--demo", action="store_true", help="use the built-in demo model (no LLM needed)")
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    if args.demo:
        settings.override({"llm_provider": "mock"})
    url = f"http://{'localhost' if args.host in ('0.0.0.0', '127.0.0.1') else args.host}:{args.port}"
    print(f"\n  RNU Thesis Copilot → {url}\n  LLM: {settings.get('llm_provider')} / {settings.get('llm_model')}\n")
    if not args.no_browser:
        threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    uvicorn.run("app.web:app", host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
