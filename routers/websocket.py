import json
import time
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import DefaultDict
from collections import defaultdict

router = APIRouter()

# quiz_id -> list of connected WebSockets
connections: DefaultDict[str, list[WebSocket]] = defaultdict(list)
# quiz_id -> teacher WebSocket (only one)
teacher_sockets: dict[str, WebSocket] = {}
# quiz_id -> unix timestamp (ms) when teacher started the quiz
started_quizzes: dict[str, int] = {}


async def broadcast(quiz_id: str, data: dict, exclude: WebSocket | None = None):
    dead = []
    for ws in connections[quiz_id]:
        if ws is exclude:
            continue
        try:
            await ws.send_text(json.dumps(data))
        except Exception:
            dead.append(ws)
    for ws in dead:
        connections[quiz_id].discard(ws) if hasattr(connections[quiz_id], 'discard') else None
        try:
            connections[quiz_id].remove(ws)
        except ValueError:
            pass


@router.websocket("/ws/quiz/{quiz_id}")
async def quiz_ws(websocket: WebSocket, quiz_id: str):
    await websocket.accept()
    connections[quiz_id].append(websocket)
    role = None  # will be set by first message

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except Exception:
                continue

            msg_type = msg.get("type")

            if msg_type == "teacher_join":
                role = "teacher"
                teacher_sockets[quiz_id] = websocket

            elif msg_type == "student_join":
                role = "student"
                # If quiz already started, reject late joiners
                if quiz_id in started_quizzes:
                    await websocket.send_text(json.dumps({"type": "quiz_already_started"}))
                else:
                    # broadcast to teacher (and all monitor watchers)
                    await broadcast(quiz_id, {
                        "type": "student_join",
                        "student_id": msg.get("student_id"),
                        "name": msg.get("name"),
                    }, exclude=websocket)

            elif msg_type == "student_submit":
                await broadcast(quiz_id, {
                    "type": "student_submit",
                    "student_id": msg.get("student_id"),
                }, exclude=websocket)

            elif msg_type == "cheat_flag":
                await broadcast(quiz_id, {
                    "type": "cheat_flag",
                    "student_id": msg.get("student_id"),
                    "timestamp": msg.get("timestamp"),
                }, exclude=websocket)

            elif msg_type == "quiz_start":
                # teacher starts the quiz — all students begin simultaneously
                started_quizzes[quiz_id] = int(time.time() * 1000)
                await broadcast(quiz_id, {
                    "type": "quiz_start",
                    "quiz_id": quiz_id,
                    "server_time": started_quizzes[quiz_id],
                })

            elif msg_type == "quiz_close":
                # teacher closing — broadcast to all students
                await broadcast(quiz_id, {
                    "type": "quiz_close",
                    "quiz_id": quiz_id,
                })

            elif msg_type == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))

    except WebSocketDisconnect:
        connections[quiz_id].remove(websocket) if websocket in connections[quiz_id] else None
        if teacher_sockets.get(quiz_id) is websocket:
            del teacher_sockets[quiz_id]
    except Exception:
        try:
            connections[quiz_id].remove(websocket)
        except ValueError:
            pass
