import asyncio
import json
from typing import Any, Dict, Optional, Set

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

from chat_logic import handle_human_message, init_chat_logic, register_system_message
from llm_service import LLMService


app = FastAPI(title="Geveze / Lafbaz.AI - Kaotik Çoklu Ajan Sohbeti")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

templates = Jinja2Templates(directory="templates")


class ConnectionManager:
    def __init__(self) -> None:
        self.active_connections: Set[WebSocket] = set()
        self.usernames: Dict[WebSocket, str] = {}
        self.user_types: Dict[WebSocket, str] = {}
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, username: str, user_type: str) -> None:
        async with self._lock:
            self.active_connections.add(websocket)
            self.usernames[websocket] = username
            self.user_types[websocket] = user_type

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self.active_connections.discard(websocket)
            self.usernames.pop(websocket, None)
            self.user_types.pop(websocket, None)

    async def broadcast(self, message: Dict[str, Any]) -> None:
        data = json.dumps(message, ensure_ascii=False)
        async with self._lock:
            if not self.active_connections:
                return
            to_remove: List[WebSocket] = []
            for connection in self.active_connections:
                try:
                    await connection.send_text(data)
                except WebSocketDisconnect:
                    to_remove.append(connection)
            for conn in to_remove:
                self.active_connections.discard(conn)
                self.usernames.pop(conn, None)
                self.user_types.pop(conn, None)


manager = ConnectionManager()
llm_service = LLMService()


@app.on_event("startup")
async def on_startup() -> None:
    async def broadcast_chat(sender: str, sender_type: str, content: str) -> None:
        await manager.broadcast(
            {
                "type": "chat",
                "sender": sender,
                "sender_type": sender_type,
                "content": content,
            }
        )

    async def broadcast_system(content: str) -> None:
        await manager.broadcast({"type": "system", "content": content})

    def has_audience() -> bool:
        return bool(manager.active_connections)

    await llm_service.start()
    await init_chat_logic(llm_service, broadcast_chat, broadcast_system, has_audience)


@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("index.html", {"request": request})


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    username: Optional[str] = None
    user_type = "human"
    try:
        # WebSocket bağlantısını hemen kabul et, ardından ilk mesajı bekle
        await websocket.accept()

        data_text = await websocket.receive_text()
        init_data = json.loads(data_text)
        if not isinstance(init_data, dict) or init_data.get("type") != "join":
            await websocket.close(code=1008)
            return
        username = str(init_data.get("username") or "Misafir")
        username = username.strip() or "Misafir"

        await manager.connect(websocket, username, user_type)

        await register_system_message(f"{username} sohbete katıldı.")

        while True:
            message_text = await websocket.receive_text()
            try:
                payload = json.loads(message_text)
            except json.JSONDecodeError:
                continue

            if not isinstance(payload, dict):
                continue

            if payload.get("type") != "chat":
                continue

            content = str(payload.get("content") or "").strip()
            if not content:
                continue

            await manager.broadcast(
                {
                    "type": "chat",
                    "sender": username,
                    "sender_type": "human",
                    "content": content,
                }
            )

            await handle_human_message(username, content)

    except WebSocketDisconnect:
        if username:
            await register_system_message(f"{username} sohbetten ayrıldı.")
    finally:
        await manager.disconnect(websocket)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=7800, reload=True)

