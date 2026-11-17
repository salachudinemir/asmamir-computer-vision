"""Serve the local web overlay on http://127.0.0.1:8765 (no HTTPS)."""

import mimetypes
import threading
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

ROOT = Path(__file__).resolve().parent
HOST = "127.0.0.1"
PORT = 8765
URL = f"http://{HOST}:{PORT}/deagle/"
OVERLAY_URL = f"http://{HOST}:{PORT}/deagle/overlay.html"
AIRBUS_URL = f"http://{HOST}:{PORT}/airbus/"

# Windows mimetypes often has no .glb/.gltf entry; Three.js / browsers need these.
mimetypes.add_type("model/gltf-binary", ".glb")
mimetypes.add_type("model/gltf+json", ".gltf")
mimetypes.add_type("application/octet-stream", ".bin")
mimetypes.add_type("text/javascript", ".js")
mimetypes.add_type("text/javascript", ".mjs")
mimetypes.add_type("application/wasm", ".wasm")

EXTRA_MIME = {
    ".glb": "model/gltf-binary",
    ".gltf": "model/gltf+json",
    ".bin": "application/octet-stream",
    ".js": "text/javascript",
    ".mjs": "text/javascript",
    ".css": "text/css",
    ".wasm": "application/wasm",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".html": "text/html",
}


class Handler(SimpleHTTPRequestHandler):
    extensions_map = {
        **getattr(SimpleHTTPRequestHandler, "extensions_map", {}),
        **EXTRA_MIME,
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def guess_type(self, path):
        ext = Path(path).suffix.lower()
        if ext in EXTRA_MIME:
            return EXTRA_MIME[ext]
        return super().guess_type(path)

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def log_message(self, format, *args):
        print(f"[{self.log_date_time_string()}] {fmt % args}")


def make_server():
    return ThreadingHTTPServer((HOST, PORT), Handler)


def serve_in_background():
    """Daemon thread; same files as `python web/serve.py`. Returns the server."""
    httpd = make_server()
    thread = threading.Thread(target=httpd.serve_forever, daemon=True, name="deagle-overlay")
    thread.start()
    return httpd


if __name__ == "__main__":
    httpd = make_server()
    print(f"Deagle GPU glTF: {URL}")
    print(f"Deagle camera overlay: {OVERLAY_URL}")
    print(f"Airbus viewer: {AIRBUS_URL}")
    print("Stop with Ctrl+C.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
