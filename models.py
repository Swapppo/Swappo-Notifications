from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict
from enum import Enum

Base = declarative_base()


class NotificationType(str, Enum):
    """Notification type enum"""
    trade_offer_received = "trade_offer_received"
    trade_offer_accepted = "trade_offer_accepted"
    trade_offer_rejected = "trade_offer_rejected"
    trade_offer_cancelled = "trade_offer_cancelled"
    trade_completed = "trade_completed"
    new_message = "new_message"
    item_liked = "item_liked"
    system = "system"


# SQLAlchemy Models (Database)
class NotificationDB(Base):
    """SQLAlchemy model for notifications table"""
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    
    # User who receives the notification
    user_id = Column(String(100), nullable=False, index=True)
    
    # Notification type
    type = Column(String(50), nullable=False, index=True)
    
    # Title and body
    title = Column(String(255), nullable=False)
    body = Column(Text, nullable=False)
    
    # Related entity IDs (optional)
    related_user_id = Column(String(100), nullable=True)  # User who triggered the notification
    related_item_id = Column(Integer, nullable=True)
    related_offer_id = Column(Integer, nullable=True)
    
    # Read status
    is_read = Column(Boolean, nullable=False, default=False, index=True)
    read_at = Column(DateTime(timezone=True), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


# Pydantic Models (Request/Response)
class NotificationCreate(BaseModel):
    """Schema for creating a notification"""
    user_id: str = Field(..., min_length=1, max_length=100, description="User ID to receive notification")
    type: NotificationType = Field(..., description="Type of notification")
    title: str = Field(..., min_length=1, max_length=255, description="Notification title")
    body: str = Field(..., min_length=1, description="Notification body/message")
    related_user_id: Optional[str] = Field(None, max_length=100, description="ID of user who triggered notification")
    related_item_id: Optional[int] = Field(None, description="Related item ID")
    related_offer_id: Optional[int] = Field(None, description="Related trade offer ID")


class NotificationResponse(BaseModel):
    """Schema for notification response"""
    id: int
    user_id: str
    type: str
    title: str
    body: str
    related_user_id: Optional[str] = None
    related_item_id: Optional[int] = None
    related_offer_id: Optional[int] = None
    is_read: bool
    read_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class NotificationMarkRead(BaseModel):
    """Schema for marking notification as read"""
    notification_ids: list[int] = Field(..., min_items=1, description="List of notification IDs to mark as read")


class NotificationStats(BaseModel):
    """Schema for notification statistics"""
    total_notifications: int
    unread_notifications: int
    read_notifications: int


class ErrorResponse(BaseModel):
    """Standard error response"""
    detail: str
