from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, Query, Form
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import json

from app import models
from app.database import engine
from app.auth import get_current_user, require_role

router = APIRouter()

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}
    
    async def connect(self, username: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[username] = websocket
    
    def disconnect(self, username: str):
        if username in self.active_connections:
            del self.active_connections[username]
    
    async def send_message(self, username: str, message: dict):
        if username in self.active_connections:
            try:
                await self.active_connections[username].send_json(message)
            except:
                self.disconnect(username)
    
    async def broadcast_to_room(self, room_id: int, message: dict, exclude_username: Optional[str] = None):
        """Send message to all users in a chat room"""
        with Session(engine) as session:
            room = session.query(models.ChatRoom).filter(models.ChatRoom.id == room_id).first()
            if room:
                for username in [room.teknisi_username, room.admin_regional_username]:
                    if username != exclude_username:
                        await self.send_message(username, message)

manager = ConnectionManager()

@router.websocket("/ws/chat/{username}")
async def websocket_endpoint(websocket: WebSocket, username: str):
    """WebSocket endpoint for real-time chat"""
    await manager.connect(username, websocket)
    try:
        while True:
            data = await websocket.receive_json()
            
            # Process message
            action = data.get("action")
            
            if action == "send_message":
                with Session(engine) as session:
                    # Save message to database
                    message = models.ChatMessage(
                        room_id=data["room_id"],
                        sender_username=username,
                        sender_role=data["sender_role"],
                        message=data["message"],
                        message_type=data.get("message_type", "text"),
                        attachment_url=data.get("attachment_url")
                    )
                    session.add(message)
                    
                    # Update chat room
                    room = session.query(models.ChatRoom).filter(
                        models.ChatRoom.id == data["room_id"]
                    ).first()
                    
                    if room:
                        room.last_message = data["message"]
                        room.last_message_at = datetime.now()
                        
                        # Increment unread count
                        if data["sender_role"] == "teknisi":
                            room.unread_count_admin += 1
                        else:
                            room.unread_count_teknisi += 1
                    
                    session.commit()
                    session.refresh(message)
                    
                    # Broadcast to room
                    await manager.broadcast_to_room(
                        data["room_id"],
                        {
                            "type": "new_message",
                            "message": {
                                "id": message.id,
                                "room_id": message.room_id,
                                "sender_username": message.sender_username,
                                "sender_role": message.sender_role,
                                "message": message.message,
                                "message_type": message.message_type,
                                "attachment_url": message.attachment_url,
                                "created_at": message.created_at.strftime("%Y-%m-%d %H:%M:%S")
                            }
                        }
                    )
            
            elif action == "mark_read":
                with Session(engine) as session:
                    room = session.query(models.ChatRoom).filter(
                        models.ChatRoom.id == data["room_id"]
                    ).first()
                    
                    if room:
                        if data["role"] == "teknisi":
                            room.unread_count_teknisi = 0
                        else:
                            room.unread_count_admin = 0
                        
                        # Mark messages as read
                        session.query(models.ChatMessage).filter(
                            models.ChatMessage.room_id == data["room_id"],
                            models.ChatMessage.sender_username != username,
                            models.ChatMessage.is_read == False
                        ).update({"is_read": True})
                        
                        session.commit()
    
    except WebSocketDisconnect:
        manager.disconnect(username)
    except Exception as e:
        print(f"WebSocket error: {e}")
        manager.disconnect(username)

@router.get("/chat/rooms", tags=["Chat"], summary="Get Chat Rooms")
async def get_chat_rooms(
    current_user: models.User = Depends(get_current_user)
):
    """
    Get all chat rooms for current user
    
    **Teknisi:** Get room with their admin regional
    **Admin Regional:** Get all rooms with teknisi for which they are assigned
    """
    with Session(engine) as session:
        if current_user.role == "teknisi":
            rooms = session.query(models.ChatRoom).filter(
                models.ChatRoom.teknisi_username == current_user.username
            ).all()
        elif current_user.role == "admin_regional":
            rooms = session.query(models.ChatRoom).filter(
                models.ChatRoom.admin_regional_username == current_user.username
            ).all()
        else:  # admin
            rooms = session.query(models.ChatRoom).all()
        
        return {
            "status": "success",
            "data": [
                {
                    "id": room.id,
                    "teknisi_username": room.teknisi_username,
                    "admin_regional_username": room.admin_regional_username,
                    "region": room.region,
                    "last_message": room.last_message,
                    "last_message_at": room.last_message_at.strftime("%Y-%m-%d %H:%M:%S") if room.last_message_at else None,
                    "unread_count": room.unread_count_teknisi if current_user.role == "teknisi" else room.unread_count_admin,
                    "created_at": room.created_at.strftime("%Y-%m-%d %H:%M:%S")
                }
                for room in rooms
            ]
        }

@router.post("/chat/rooms", tags=["Chat"], summary="Create or Get Chat Room")
async def create_or_get_chat_room(
    teknisi_username: str = Form(...),
    current_user: models.User = Depends(require_role(["admin_regional", "teknisi"]))
):
    """
    Create or get existing chat room between teknisi and admin regional
    """
    with Session(engine) as session:
        # Get teknisi user
        teknisi = session.query(models.User).filter(
            models.User.username == teknisi_username,
            models.User.role == "teknisi"
        ).first()
        
        if not teknisi:
            raise HTTPException(status_code=404, detail="Teknisi tidak ditemukan")
        
        # Get admin regional for teknisi's city (area-first), fallback to region
        admin_regional = session.query(models.User).filter(
            models.User.role == "admin_regional",
            models.User.area == teknisi.area
        ).first()
        if not admin_regional:
            admin_regional = session.query(models.User).filter(
                models.User.role == "admin_regional",
                models.User.region == teknisi.region
            ).first()
        
        if not admin_regional:
            raise HTTPException(status_code=404, detail="Admin Regional tidak ditemukan untuk kota/region ini")
        
        # Check if room already exists
        room = session.query(models.ChatRoom).filter(
            models.ChatRoom.teknisi_username == teknisi.username,
            models.ChatRoom.admin_regional_username == admin_regional.username
        ).first()
        
        if not room:
            # Create new room
            room = models.ChatRoom(
                teknisi_username=teknisi.username,
                admin_regional_username=admin_regional.username,
                region=teknisi.region
            )
            session.add(room)
            session.commit()
            session.refresh(room)
        
        return {
            "status": "success",
            "data": {
                "id": room.id,
                "teknisi_username": room.teknisi_username,
                "admin_regional_username": room.admin_regional_username,
                "region": room.region
            }
        }

@router.get("/chat/rooms/{room_id}/messages", tags=["Chat"], summary="Get Chat Messages")
async def get_chat_messages(
    room_id: int,
    skip: int = Query(0),
    limit: int = Query(50),
    current_user: models.User = Depends(get_current_user)
):
    """Get all messages in a chat room"""
    with Session(engine) as session:
        # Verify user has access to this room
        room = session.query(models.ChatRoom).filter(models.ChatRoom.id == room_id).first()
        
        if not room:
            raise HTTPException(status_code=404, detail="Chat room tidak ditemukan")
        
        if current_user.role == "teknisi" and room.teknisi_username != current_user.username:
            raise HTTPException(status_code=403, detail="Akses ditolak")
        
        if current_user.role == "admin_regional" and room.admin_regional_username != current_user.username:
            raise HTTPException(status_code=403, detail="Akses ditolak")
        
        # Get messages
        messages = session.query(models.ChatMessage).filter(
            models.ChatMessage.room_id == room_id
        ).order_by(models.ChatMessage.created_at.desc()).offset(skip).limit(limit).all()
        
        messages.reverse()  # Show oldest first
        
        return {
            "status": "success",
            "data": [
                {
                    "id": msg.id,
                    "sender_username": msg.sender_username,
                    "sender_role": msg.sender_role,
                    "message": msg.message,
                    "message_type": msg.message_type,
                    "attachment_url": msg.attachment_url,
                    "is_read": msg.is_read,
                    "created_at": msg.created_at.strftime("%Y-%m-%d %H:%M:%S")
                }
                for msg in messages
            ]
        }
