import asyncio
import json
import logging
from typing import Set, Dict, Any
from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


class WebSocketManager:
    """
    Manages WebSocket connections and broadcasts real-time updates to connected clients.
    """
    
    def __init__(self):
        # Store active connections by role
        self.connections: Dict[str, Set[WebSocket]] = {
            "superadmin": set(),
            "admin": set(),
            "user": set(),
        }
        self.connection_count = 0
    
    async def connect(self, websocket: WebSocket, role: str = "admin"):
        """Accept a new WebSocket connection"""
        await websocket.accept()
        if role not in self.connections:
            role = "admin"
        self.connections[role].add(websocket)
        self.connection_count += 1
        logger.info(f"WebSocket connected: {role} (total: {self.connection_count})")
    
    def disconnect(self, websocket: WebSocket, role: str = "admin"):
        """Remove a WebSocket connection"""
        if role in self.connections:
            self.connections[role].discard(websocket)
            self.connection_count -= 1
            logger.info(f"WebSocket disconnected: {role} (total: {self.connection_count})")
    
    async def broadcast(self, message: Dict[str, Any], roles: list[str] = None):
        """
        Broadcast a message to all connected clients of specified roles.
        If roles is None, broadcast to all.
        """
        if roles is None:
            roles = list(self.connections.keys())
        
        message_json = json.dumps(message)
        dead_connections = []
        
        for role in roles:
            if role not in self.connections:
                continue
            
            for connection in self.connections[role]:
                try:
                    await connection.send_text(message_json)
                except Exception as e:
                    logger.error(f"Error sending to {role} client: {e}")
                    dead_connections.append((connection, role))
        
        # Clean up dead connections
        for conn, role in dead_connections:
            self.disconnect(conn, role)
    
    async def broadcast_event(self, event_type: str, data: Dict[str, Any], roles: list[str] = None):
        """
        Broadcast an event with type and data
        """
        message = {
            "type": event_type,
            "data": data,
            "timestamp": asyncio.get_event_loop().time()
        }
        await self.broadcast(message, roles)
    
    def get_connection_count(self) -> int:
        """Get total number of active connections"""
        return self.connection_count


# Global WebSocket manager instance
ws_manager = WebSocketManager()
