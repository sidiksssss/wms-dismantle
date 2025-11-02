from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text
from datetime import datetime
from app.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False, index=True)
    email = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    full_name = Column(String, nullable=True)
    role = Column(String, nullable=False)  # admin, admin_regional, teknisi
    area = Column(String, nullable=True)  # City (Simplified) untuk teknisi
    region = Column(String, nullable=True)  # WEST, CENTRAL, EAST untuk admin regional
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

class DismantleData(Base):
    __tablename__ = "dismantle_data"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(String, nullable=False)
    wo_id_xl = Column(String, nullable=False, unique=True, index=True)
    city_simplified = Column(String, nullable=False, index=True)
    product_name = Column(String, nullable=True)
    status_wo = Column(String, nullable=True, index=True)
    vendor = Column(String, nullable=True)
    region = Column(String, nullable=True)  # Tambahan untuk filter regional
    
    # Foto fields
    foto_rumah = Column(String, nullable=True)
    foto_fat = Column(String, nullable=True)
    foto_cabut_port = Column(String, nullable=True)
    foto_ont = Column(String, nullable=True)
    foto_adapter = Column(String, nullable=True)
    foto_kabel_lan = Column(String, nullable=True)
    foto_customer = Column(String, nullable=True)
    foto_sn = Column(String, nullable=True)
    sn_ocr_result = Column(String, nullable=True)  # Hasil OCR dari foto SN
    
    # Approval System (untuk Admin Regional)
    approval_status = Column(String, nullable=True)  # pending, approved, rejected
    approval_by = Column(String, nullable=True)  # Username admin regional yang approve
    approval_date = Column(DateTime, nullable=True)  # Tanggal approval
    approval_notes = Column(Text, nullable=True)  # Catatan approval/rejection
    
    # Tracking
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    updated_by = Column(String, nullable=True)  # Username teknisi yang update

class ChatRoom(Base):
    __tablename__ = "chat_rooms"
    
    id = Column(Integer, primary_key=True, index=True)
    teknisi_username = Column(String, nullable=False, index=True)
    admin_regional_username = Column(String, nullable=False, index=True)
    region = Column(String, nullable=False)  # Region untuk filter
    last_message = Column(Text, nullable=True)
    last_message_at = Column(DateTime, nullable=True)
    unread_count_teknisi = Column(Integer, default=0)  # Unread untuk teknisi
    unread_count_admin = Column(Integer, default=0)  # Unread untuk admin regional
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

class ChatMessage(Base):
    __tablename__ = "chat_messages"
    
    id = Column(Integer, primary_key=True, index=True)
    room_id = Column(Integer, nullable=False, index=True)
    sender_username = Column(String, nullable=False)
    sender_role = Column(String, nullable=False)  # teknisi or admin_regional
    message = Column(Text, nullable=False)
    message_type = Column(String, default="text")  # text, image, wo_link
    attachment_url = Column(String, nullable=True)  # URL foto jika ada
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now, nullable=False, index=True)
