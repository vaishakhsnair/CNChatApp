from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
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
    def __init__(self, from_username: str, message: str, to_username: str, message_type="message"):
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

    def is_recipient_available(self, to_username: str):
        return to_username in self.connections

    async def connect(self,websocket: WebSocket, username: str):

        await websocket.accept()        
        self.connections[username] = websocket


    def disconnect(self, username: str):
        if username in self.connections:
            del self.connections[username]

    async def send_message(self, from_username: str, to_username: str, message: str):
        print(self.connections)
        if to_username in self.connections:
            to_connection = self.connections[to_username]
            from_connection = self.connections[from_username]   
            try:
                await from_connection.send_text(
                    Message(from_username, message, to_username).jsonify()
                )
                await to_connection.send_text(
                    Message(from_username, message, to_username).jsonify()
                )
            except RuntimeError:
                pass  # Handle any unexpected disconnects during send

    async def broadcast_status(self, username: str, status_message: str):
        # Broadcast user's status to all users except themselves
        for user, connection in self.connections.items():
            if user != username:
                try:
                    await connection.send_text(
                        Message(username, status_message, user, "status").jsonify()
                    )
                except RuntimeError:
                    pass  # Ignore if user disconnected unexpectedly


manager = ConnectionManager()


@app.websocket("/api/chat")
async def chat_endpoint(websocket: WebSocket, from_username: str, to_username: str):
    print(from_username, to_username)
    print(websocket)
    await manager.connect(websocket, from_username)
    try:
        while True:
            data = await websocket.receive_text()
            data = json.loads(data)
            await manager.send_message(data["from"], data["to"], data["message"])
    except WebSocketDisconnect:
        manager.disconnect(websocket)   
    


@app.websocket("/api/connect/{from_username}")
async def connect_endpoint(websocket: WebSocket, from_username: str):
    await manager.connect(websocket,from_username)
    try:
        # Broadcast that the user is online to all other users
        await manager.broadcast_status(from_username, "User is online")
        while True:
            # Keep the connection open
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(from_username)
        # Broadcast that the user is offline to all other users
        await manager.broadcast_status(from_username, "User is offline")


@app.get("/api/userlist")
async def get_user_list():
    return {
        "users": list(manager.connections.keys())
    }


@app.get("/api/useronline/{username}")
async def is_user_online(username: str):
    return {
        "username": username,
        "online": manager.is_recipient_available(username)
    }


app.mount("/static", StaticFiles(directory="static", html=True), name="static")


@app.get("/")
async def read_index():
    return FileResponse('static/index.html')


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
