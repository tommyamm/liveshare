import asyncio
import json
import pathlib
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from typing import Optional, Set

from websockets.asyncio.server import ServerConnection, serve


HOST = "0.0.0.0"
HTTP_PORT = 8000
WS_PORT = 5678
FILE_PATH = pathlib.Path("liveshare.py")
WEB_DIR = pathlib.Path(__file__).with_name("web")


class SyncServer:
    def __init__(self, file_path: pathlib.Path) -> None:
        self.file_path = file_path
        self.clients: Set[ServerConnection] = set()
        self.current_content = self._load_initial_content()

    def _load_initial_content(self) -> str:
        if self.file_path.exists():
            return self.file_path.read_text(encoding="utf-8")
        return ""

    def _write_file(self, content: str) -> None:
        self.file_path.write_text(content, encoding="utf-8")

    async def send_state(self, websocket: ServerConnection) -> None:
        await websocket.send(
            json.dumps(
                {
                    "type": "sync",
                    "content": self.current_content,
                    "participants": len(self.clients),
                }
            )
        )

    async def broadcast_presence(self) -> None:
        if not self.clients:
            return

        message = json.dumps(
            {"type": "presence", "participants": len(self.clients)}
        )
        await asyncio.gather(
            *(client.send(message) for client in self.clients),
            return_exceptions=True,
        )

    async def broadcast_content(
        self, content: str, sender: Optional[ServerConnection]
    ) -> None:
        recipients = [client for client in self.clients if client != sender]
        if not recipients:
            return

        message = json.dumps(
            {
                "type": "sync",
                "content": content,
                "participants": len(self.clients),
            }
        )
        await asyncio.gather(
            *(client.send(message) for client in recipients),
            return_exceptions=True,
        )

    async def handler(self, websocket: ServerConnection) -> None:
        self.clients.add(websocket)
        print(f"Browser connected: {websocket.remote_address}")
        await self.send_state(websocket)
        await self.broadcast_presence()

        try:
            async for raw_message in websocket:
                try:
                    payload = json.loads(raw_message)
                except json.JSONDecodeError:
                    print("Ignored invalid JSON message")
                    continue

                if payload.get("type") != "sync":
                    print(f"Ignored unknown message type: {payload.get('type')}")
                    continue

                content = payload.get("content")
                if not isinstance(content, str):
                    print("Ignored sync message without text content")
                    continue

                if content == self.current_content:
                    continue

                self.current_content = content
                self._write_file(content)
                await self.broadcast_content(content, sender=websocket)
        finally:
            self.clients.discard(websocket)
            print(f"Browser disconnected: {websocket.remote_address}")
            await self.broadcast_presence()


def run_http_server() -> None:
    handler = partial(SimpleHTTPRequestHandler, directory=str(WEB_DIR))
    httpd = ThreadingHTTPServer((HOST, HTTP_PORT), handler)
    print(f"Editor UI listening on http://127.0.0.1:{HTTP_PORT}")
    httpd.serve_forever()


async def main() -> None:
    http_thread = threading.Thread(target=run_http_server, daemon=True)
    http_thread.start()

    server = SyncServer(FILE_PATH)
    async with serve(server.handler, HOST, WS_PORT):
        print(f"WebSocket sync listening on ws://0.0.0.0:{WS_PORT}")
        await asyncio.Future()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nServer stopped")
