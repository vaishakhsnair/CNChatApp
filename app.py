from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict
import json
import uvicorn

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)


class Message:
    def __init__(self, from_username: str, message: str, to_username: str,message_type = "message"):
        self.username = from_username
        self.message = message
        self.to_username = to_username
        self.message_type = message_type

    def jsonify(self):
        return json.dumps({
            "type": self.message_type,
            "from": self.username,
            "message": self.message,
            "to": self.to_username,
        })

class ConnectionManager:
    def __init__(self):
        # Map of usernames to their WebSocket connections
        self.connections: Dict[str, WebSocket] = {}

    async def connect(self, username: str, websocket: WebSocket):
        await websocket.accept()
        self.connections[username] = websocket

    def disconnect(self, username: str):
        if username in self.connections:
            del self.connections[username]

    async def send_message(self, from_username: str, to_username: str, message: str):
        if to_username in self.connections:
            to_connection = self.connections[to_username]
            from_connection = self.connections[from_username]

            await from_connection.send_text(
                Message(from_username, message, to_username).jsonify()
            )
            await to_connection.send_text(
                Message(from_username, message, to_username).jsonify()
            )
        else:
            if from_username in self.connections:
                from_connection = self.connections[from_username]
                await from_connection.send_text(
                    Message(from_username, "User is not available", to_username, "error").jsonify()
                )

manager = ConnectionManager()

@app.websocket("/api/chat/{from_username}/{to_username}")
async def chat_endpoint(websocket: WebSocket, from_username: str, to_username: str):
    await manager.connect(from_username, websocket)
    try:
        while True:
            data = await websocket.receive_text()
            await manager.send_message(from_username, to_username, data)
    except WebSocketDisconnect:
        manager.disconnect(from_username)
        # Notify the recipient if needed
        if to_username in manager.connections:
            recipient_connection = manager.connections[to_username]
            await recipient_connection.send_text(
                Message(from_username, "User has left the chat", to_username, "error").jsonify()
            )

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
