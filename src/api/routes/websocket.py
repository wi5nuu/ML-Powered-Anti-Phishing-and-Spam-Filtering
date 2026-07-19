from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from sqlalchemy.orm import Session
from src.infrastructure.database.session import get_db
from src.infrastructure.websocket.manager import ws_manager
from src.infrastructure.auth.jwt import decode_token
import logging

router = APIRouter(prefix="/ws", tags=["websocket"])
logger = logging.getLogger(__name__)


@router.websocket("/admin")
async def websocket_admin_endpoint(
    websocket: WebSocket,
    token: str = Query(...),
    db: Session = Depends(get_db)
):
    """
    WebSocket endpoint for admin/superadmin real-time updates.
    
    Usage: ws://localhost:8000/ws/admin?token=<jwt_token>
    
    Events broadcasted:
    - user_created, user_updated, user_deleted
    - mailbox_created, mailbox_updated, mailbox_deleted
    - email_quarantined, email_released, email_status_changed
    - report_created, report_updated
    - company_created, company_updated, company_deleted
    - system_health_update
    """
    
    # Authenticate user via JWT token
    try:
        payload = decode_token(token)
        username = payload.get("sub")
        role = payload.get("role")
        
        if role not in ["admin", "superadmin"]:
            await websocket.close(code=1008, reason="Unauthorized: admin or superadmin role required")
            return
        
        # Connect websocket
        await ws_manager.connect(websocket, role)
        
        # Send welcome message
        await websocket.send_json({
            "type": "connected",
            "data": {
                "message": "WebSocket connected",
                "user": username,
                "role": role
            }
        })
        
        # Keep connection alive and handle incoming messages (ping/pong)
        try:
            while True:
                data = await websocket.receive_text()
                # Echo ping/pong for keep-alive
                if data == "ping":
                    await websocket.send_text("pong")
        
        except WebSocketDisconnect:
            ws_manager.disconnect(websocket, role)
            logger.info(f"WebSocket disconnected: {username} ({role})")
    
    except Exception as e:
        logger.error(f"WebSocket auth error: {e}")
        await websocket.close(code=1008, reason="Authentication failed")
