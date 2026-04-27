import asyncio
import json
import pathlib
from typing import Optional, Set

import websockets
from websockets import WebSocketServerProtocol


HOST = "0.0.0.0"
PORT = 5678
FILE_PATH = pathlib.Path("liveshare.py")


class SyncServer:
    def __init__(self, file_path: pathlib.Path) -> None:
        self.file_path = file_path
        self.clients: Set[WebSocketServerProtocol] = set()
        self.current_content = self._load_initial_content()

    def _load_initial_content(self) -> str:
        if self.file_path.exists():
            return self.file_path.read_text(encoding="utf-8")
        return ""

    async def broadcast(self, content: str, sender: Optional[WebSocketServerProtocol]) -> None:
        if not self.clients:
            return

        message = json.dumps({"type": "sync", "content": content})
        recipients = [client for client in self.clients if client != sender]

        if recipients:
            await asyncio.gather(
                *(client.send(message) for client in recipients),
                return_exceptions=True,
            )

    async def handler(self, websocket: WebSocketServerProtocol) -> None:
        self.clients.add(websocket)
        print(f"Client connected: {websocket.remote_address}")

        try:
            await websocket.send(
                json.dumps({"type": "sync", "content": self.current_content})
            )

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
                await self.broadcast(content, sender=websocket)
        finally:
            self.clients.discard(websocket)
            print(f"Client disconnected: {websocket.remote_address}")


async def main() -> None:
    server = SyncServer(FILE_PATH)
    async with websockets.serve(server.handler, HOST, PORT):
        print(f"Sync server listening on ws://{HOST}:{PORT}")
        await asyncio.Future()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nServer stopped")
