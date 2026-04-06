from __future__ import annotations

import argparse
import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from agent_runtime.config import REPO_ROOT
from creator_runtime.chat import ConversationState, reply
from creator_runtime.persona import ensure_default_persona, load_persona


STATIC_DIR = REPO_ROOT / "creator_ui"
STATE: dict[str, ConversationState] = {}


class CreatorHandler(BaseHTTPRequestHandler):
    def _send_json(self, payload: dict, status: int = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path: Path, content_type: str) -> None:
        body = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path in ("/", "/index.html"):
            return self._send_file(STATIC_DIR / "index.html", "text/html; charset=utf-8")
        if self.path == "/app.js":
            return self._send_file(STATIC_DIR / "app.js", "application/javascript; charset=utf-8")
        if self.path == "/style.css":
            return self._send_file(STATIC_DIR / "style.css", "text/css; charset=utf-8")
        if self.path == "/api/persona":
            state = next(iter(STATE.values()))
            persona = state.persona
            return self._send_json(
                {
                    "name": persona.name,
                    "tagline": persona.tagline,
                    "style": persona.style,
                    "audience": persona.audience,
                    "topics": persona.topics,
                    "first_message": persona.first_message,
                }
            )
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        if self.path != "/api/chat":
            self.send_error(HTTPStatus.NOT_FOUND)
            return

        content_length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(content_length)
        data = json.loads(raw.decode("utf-8"))
        message = (data.get("message") or "").strip()
        model = data.get("model") or "fast"
        if not message:
            self._send_json({"error": "message is required"}, status=HTTPStatus.BAD_REQUEST)
            return

        state = next(iter(STATE.values()))
        output = reply(state, message, model=model)
        self._send_json({"reply": output})


def run_server(host: str = "127.0.0.1", port: int = 8767, persona_name: str = "lab_vtuber") -> None:
    ensure_default_persona()
    STATE["default"] = ConversationState(persona=load_persona(persona_name))
    server = ThreadingHTTPServer((host, port), CreatorHandler)
    print(f"Local AI creator chat running at http://{host}:{port}")
    server.serve_forever()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8767)
    parser.add_argument("--persona", default="lab_vtuber")
    args = parser.parse_args()
    run_server(host=args.host, port=args.port, persona_name=args.persona)


if __name__ == "__main__":
    main()

