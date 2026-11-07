#!/usr/bin/env python3
"""Serve the WeekendWise HTML mockup with clean page paths.

Plain `python3 -m http.server` returns 404 for /itinerary or /architecture, because
no such files exist. This server answers any single-segment path without a file
extension (e.g. /plan, /itinerary, /sources, /architecture) with index.html, and the
page's script picks the screen from the path. Real files (CSS, JS, SVG) are served as-is.

Local use only: binds to 127.0.0.1 and disables caching so edits show on refresh.

Usage: python3 scripts/serve_mockups.py [PORT]   (default 8000)
"""
from __future__ import annotations

import functools
import re
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent / "artifacts" / "google-cloud-ai-copilot" / "weekendwise-mockups"
PAGE_PATH = re.compile(r"^/[A-Za-z0-9_-]*/?$")


class MockupHandler(SimpleHTTPRequestHandler):
    def do_GET(self) -> None:
        if self._redirect_trailing_slash():
            return
        self._route_pages()
        super().do_GET()

    def _redirect_trailing_slash(self) -> bool:
        # /architecture/ -> /architecture, so relative CSS/JS links keep resolving to the root.
        parts = urlsplit(self.path)
        if parts.path != "/" and parts.path.endswith("/") and PAGE_PATH.match(parts.path):
            self.send_response(301)
            self.send_header("Location", parts.path.rstrip("/") + (f"?{parts.query}" if parts.query else ""))
            self.end_headers()
            return True
        return False

    def do_HEAD(self) -> None:
        self._route_pages()
        super().do_HEAD()

    def _route_pages(self) -> None:
        path = urlsplit(self.path).path
        if PAGE_PATH.match(path) and not (ROOT / path.strip("/")).is_file():
            self.path = "/index.html"

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    handler = functools.partial(MockupHandler, directory=str(ROOT))
    with ThreadingHTTPServer(("127.0.0.1", port), handler) as server:
        print(f"WeekendWise mockup: http://localhost:{port}/plan  (Ctrl+C to stop)")
        print(f"  Pages: /plan  /itinerary  /sources  /architecture")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nStopped.")


if __name__ == "__main__":
    main()
