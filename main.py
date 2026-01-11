import asyncio
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy import and_
from sqlalchemy.orm import Session

from database import get_db, init_db
from metrics import record_http_request
from models import (
    ErrorResponse,
    NotificationCreate,
    NotificationDB,
    NotificationMarkRead,
    NotificationResponse,
    NotificationStats,
)

# Import RabbitMQ consumer
from rabbitmq_consumer import NotificationConsumer, run_consumer_in_background

# Global consumer instance
consumer: Optional[NotificationConsumer] = None
consumer_task: Optional[asyncio.Task] = None


def handle_notification_message(notification_data: dict) -> bool:
    """
    Handler function for processing notification messages from RabbitMQ

    Args:
        notification_data: Notification payload from queue

    Returns:
        True if processed successfully, False otherwise
    """
    try:
        # Create database session
        db = next(get_db())

        # Create notification in database
        db_notification = NotificationDB(
            user_id=notification_data["user_id"],
            type=notification_data["type"],
            title=notification_data["title"],
            body=notification_data["body"],
            related_user_id=notification_data.get("related_user_id"),
            is_read=False,
            created_at=datetime.now(timezone.utc),
        )

        db.add(db_notification)
        db.commit()
        db.refresh(db_notification)

        print(f"✅ Notification saved to database: {db_notification.id}")

        db.close()
        return True

    except Exception as e:
        print(f"❌ Error handling notification message: {type(e).__name__}: {e}")
        return False


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup and shutdown events.
    """
    global consumer, consumer_task

    # Startup: Initialize database
    init_db()

    # Initialize and start RabbitMQ consumer
    consumer = NotificationConsumer(message_handler=handle_notification_message)
    consumer_task = asyncio.create_task(run_consumer_in_background(consumer))
    print("✅ RabbitMQ consumer started in background")

    yield

    # Shutdown: Cleanup
    if consumer:
        consumer.close()

    if consumer_task:
        consumer_task.cancel()
        try:
            await consumer_task
        except asyncio.CancelledError:
            print("✅ Consumer task cancelled")

    print("✅ Notifications service shutdown complete")


# Initialize FastAPI app
app = FastAPI(
    title="Swappo Notifications Service",
    description="Microservice for managing push notifications in the Swappo app",
    version="1.0.0",
    lifespan=lifespan,
)

# Prometheus instrumentation
Instrumentator().instrument(app).expose(app, endpoint="/metrics")


# Middleware to track HTTP request metrics
@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    if request.url.path == "/metrics":
        return await call_next(request)

    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time

    record_http_request(
        method=request.method,
        endpoint=request.url.path,
        status_code=response.status_code,
        duration=duration,
    )

    return response


# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", tags=["Health"])
async def root():
    """Health check endpoint"""
    return {
        "service": "Swappo Notifications Service",
        "status": "running",
        "version": "1.0.0",
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """Detailed health check endpoint"""
    return {"status": "healthy", "service": "notifications", "version": "1.0.0"}


@app.post(
    "/api/v1/notifications",
    response_model=NotificationResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Notifications"],
    responses={
        201: {"description": "Notification created successfully"},
        400: {"model": ErrorResponse, "description": "Invalid request data"},
    },
)
async def create_notification(
    notification_data: NotificationCreate, db: Session = Depends(get_db)
):
    """
    Create a new notification for a user.

    This endpoint is typically called by other microservices (e.g., matchmaking)
    to notify users about events like new trade offers, accepted trades, etc.

    Args:
        notification_data: Notification details

    Returns:
        NotificationResponse: Created notification
    """
    db_notification = NotificationDB(
        user_id=notification_data.user_id,
        type=notification_data.type.value,
        title=notification_data.title,
        body=notification_data.body,
        related_user_id=notification_data.related_user_id,
        related_item_id=notification_data.related_item_id,
        related_offer_id=notification_data.related_offer_id,
        is_read=False,
    )

    db.add(db_notification)
    db.commit()
    db.refresh(db_notification)

    return db_notification


@app.get(
    "/api/v1/notifications/{user_id}",
    response_model=List[NotificationResponse],
    tags=["Notifications"],
    responses={200: {"description": "Notifications retrieved successfully"}},
)
async def get_user_notifications(
    user_id: str,
    unread_only: bool = Query(
        False, description="Filter to show only unread notifications"
    ),
    limit: int = Query(
        50, ge=1, le=100, description="Number of notifications to retrieve"
    ),
    offset: int = Query(0, ge=0, description="Number of notifications to skip"),
    db: Session = Depends(get_db),
):
    """
    Get all notifications for a specific user.

    Args:
        user_id: User ID
        unread_only: If True, return only unread notifications
        limit: Maximum number of notifications to return
        offset: Number of notifications to skip (for pagination)

    Returns:
        List[NotificationResponse]: List of notifications
    """
    query = db.query(NotificationDB).filter(NotificationDB.user_id == user_id)

    if unread_only:
        query = query.filter(NotificationDB.is_read.is_(False))

    query = query.order_by(NotificationDB.created_at.desc()).offset(offset).limit(limit)

    return query.all()


@app.patch(
    "/api/v1/notifications/mark-read",
    response_model=dict,
    tags=["Notifications"],
    responses={
        200: {"description": "Notifications marked as read"},
        404: {"model": ErrorResponse, "description": "Notifications not found"},
    },
)
async def mark_notifications_as_read(
    mark_data: NotificationMarkRead,
    user_id: str = Query(..., description="User ID performing the action"),
    db: Session = Depends(get_db),
):
    """
    Mark one or more notifications as read.

    Args:
        mark_data: List of notification IDs to mark as read
        user_id: User ID performing the action (for authorization)

    Returns:
        dict: Summary of marked notifications
    """
    # Get notifications that belong to this user
    notifications = (
        db.query(NotificationDB)
        .filter(
            and_(
                NotificationDB.id.in_(mark_data.notification_ids),
                NotificationDB.user_id == user_id,
            )
        )
        .all()
    )

    if not notifications:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No notifications found for the given IDs",
        )

    # Mark as read
    now = datetime.now(timezone.utc)
    for notification in notifications:
        if not notification.is_read:
            notification.is_read = True
            notification.read_at = now

    db.commit()

    return {
        "marked_count": len(notifications),
        "notification_ids": [n.id for n in notifications],
    }


@app.patch(
    "/api/v1/notifications/{notification_id}/read",
    response_model=NotificationResponse,
    tags=["Notifications"],
    responses={
        200: {"description": "Notification marked as read"},
        404: {"model": ErrorResponse, "description": "Notification not found"},
        403: {"model": ErrorResponse, "description": "Not authorized"},
    },
)
async def mark_single_notification_as_read(
    notification_id: int,
    user_id: str = Query(..., description="User ID performing the action"),
    db: Session = Depends(get_db),
):
    """
    Mark a single notification as read.

    Args:
        notification_id: Notification ID
        user_id: User ID performing the action

    Returns:
        NotificationResponse: Updated notification
    """
    notification = (
        db.query(NotificationDB)
        .filter(
            and_(
                NotificationDB.id == notification_id, NotificationDB.user_id == user_id
            )
        )
        .first()
    )

    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Notification with ID {notification_id} not found",
        )

    if not notification.is_read:
        notification.is_read = True
        notification.read_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(notification)

    return notification


@app.delete(
    "/api/v1/notifications/{notification_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Notifications"],
    responses={
        204: {"description": "Notification deleted successfully"},
        403: {"model": ErrorResponse, "description": "Not authorized"},
        404: {"model": ErrorResponse, "description": "Notification not found"},
    },
)
async def delete_notification(
    notification_id: int,
    user_id: str = Query(..., description="User ID performing the action"),
    db: Session = Depends(get_db),
):
    """
    Delete a notification.

    Args:
        notification_id: Notification ID
        user_id: User ID performing the action
    """
    notification = (
        db.query(NotificationDB)
        .filter(
            and_(
                NotificationDB.id == notification_id, NotificationDB.user_id == user_id
            )
        )
        .first()
    )

    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Notification with ID {notification_id} not found",
        )

    db.delete(notification)
    db.commit()

    return None


@app.delete(
    "/api/v1/notifications/user/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Notifications"],
    responses={204: {"description": "All notifications deleted successfully"}},
)
async def delete_all_user_notifications(user_id: str, db: Session = Depends(get_db)):
    """
    Delete all notifications for a user.

    Args:
        user_id: User ID
    """
    db.query(NotificationDB).filter(NotificationDB.user_id == user_id).delete()
    db.commit()

    return None


@app.get(
    "/api/v1/notifications/{user_id}/stats",
    response_model=NotificationStats,
    tags=["Notifications"],
    responses={200: {"description": "Notification statistics retrieved successfully"}},
)
async def get_notification_stats(user_id: str, db: Session = Depends(get_db)):
    """
    Get notification statistics for a user.

    Args:
        user_id: User ID

    Returns:
        NotificationStats: Statistics about user's notifications
    """
    notifications = (
        db.query(NotificationDB).filter(NotificationDB.user_id == user_id).all()
    )

    total = len(notifications)
    unread = sum(1 for n in notifications if not n.is_read)
    read = total - unread

    return NotificationStats(
        total_notifications=total, unread_notifications=unread, read_notifications=read
    )


@app.get(
    "/api/v1/notifications/{user_id}/unread-count",
    response_model=dict,
    tags=["Notifications"],
    responses={200: {"description": "Unread count retrieved successfully"}},
)
async def get_unread_count(user_id: str, db: Session = Depends(get_db)):
    """
    Get the count of unread notifications for a user.

    This is a lightweight endpoint for badge counters.

    Args:
        user_id: User ID

    Returns:
        dict: Unread notification count
    """
    count = (
        db.query(NotificationDB)
        .filter(
            and_(NotificationDB.user_id == user_id, NotificationDB.is_read.is_(False))
        )
        .count()
    )

    return {"unread_count": count}
