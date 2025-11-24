# Swappo Notifications Service

## Overview

The Swappo Notifications Service is a RESTful microservice responsible for managing push notifications for users in the Swappo platform. This service handles the creation, storage, and retrieval of notifications related to trade offers, messages, and other app events.

## Features

### Notification Management
- Create notifications for users
- Retrieve user notifications with filtering
- Mark notifications as read (single or bulk)
- Delete notifications
- Get unread notification counts
- View notification statistics

### Notification Types
- `trade_offer_received` - New trade offer received
- `trade_offer_accepted` - Trade offer was accepted
- `trade_offer_rejected` - Trade offer was rejected
- `trade_offer_cancelled` - Trade offer was cancelled
- `trade_completed` - Trade was completed
- `new_message` - New message received
- `item_liked` - Someone liked your item
- `system` - System notifications

## Architecture

```
Swappo-Notifications/
├── main.py              # FastAPI application and endpoints
├── models.py            # Pydantic and SQLAlchemy models
├── database.py          # Database connection and session management
├── requirements.txt     # Python dependencies
├── Dockerfile          # Container configuration
├── docker-compose.yml  # Multi-container orchestration
└── README.md           # This file
```

## Data Models

### Notification

**Database Schema:**
```sql
CREATE TABLE notifications (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(100) NOT NULL,
    type VARCHAR(50) NOT NULL,
    title VARCHAR(255) NOT NULL,
    body TEXT NOT NULL,
    related_user_id VARCHAR(100),
    related_item_id INTEGER,
    related_offer_id INTEGER,
    is_read BOOLEAN DEFAULT FALSE,
    read_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

## API Endpoints

### Health Check

#### `GET /`
Basic health check returning service information.

#### `GET /health`
Detailed health check with service status.

### Notification Management

#### `POST /api/v1/notifications`
Create a new notification for a user.

**Request Body:**
```json
{
  "user_id": "user123",
  "type": "trade_offer_received",
  "title": "New Trade Offer",
  "body": "You received a new trade offer from John",
  "related_user_id": "user456",
  "related_item_id": 123,
  "related_offer_id": 789
}
```

**Response:** `201 Created`
```json
{
  "id": 1,
  "user_id": "user123",
  "type": "trade_offer_received",
  "title": "New Trade Offer",
  "body": "You received a new trade offer from John",
  "related_user_id": "user456",
  "related_item_id": 123,
  "related_offer_id": 789,
  "is_read": false,
  "read_at": null,
  "created_at": "2025-11-24T10:30:00Z"
}
```

---

#### `GET /api/v1/notifications/{user_id}`
Get all notifications for a specific user.

**Query Parameters:**
- `unread_only` (optional, default: false): Filter to show only unread notifications
- `limit` (optional, default: 50): Number of notifications to retrieve
- `offset` (optional, default: 0): Pagination offset

**Response:** `200 OK` - Array of notifications

---

#### `GET /api/v1/notifications/{user_id}/unread-count`
Get the count of unread notifications for a user (lightweight endpoint for badge counters).

**Response:** `200 OK`
```json
{
  "unread_count": 5
}
```

---

#### `GET /api/v1/notifications/{user_id}/stats`
Get notification statistics for a user.

**Response:** `200 OK`
```json
{
  "total_notifications": 25,
  "unread_notifications": 5,
  "read_notifications": 20
}
```

---

#### `PATCH /api/v1/notifications/mark-read`
Mark multiple notifications as read.

**Query Parameters:**
- `user_id` (required): User ID performing the action

**Request Body:**
```json
{
  "notification_ids": [1, 2, 3]
}
```

**Response:** `200 OK`
```json
{
  "marked_count": 3,
  "notification_ids": [1, 2, 3]
}
```

---

#### `PATCH /api/v1/notifications/{notification_id}/read`
Mark a single notification as read.

**Query Parameters:**
- `user_id` (required): User ID performing the action

**Response:** `200 OK` - Updated notification

---

#### `DELETE /api/v1/notifications/{notification_id}`
Delete a specific notification.

**Query Parameters:**
- `user_id` (required): User ID performing the action

**Response:** `204 No Content`

---

#### `DELETE /api/v1/notifications/user/{user_id}`
Delete all notifications for a user.

**Response:** `204 No Content`

---

## Running the Service

### Prerequisites

- Docker and Docker Compose
- Python 3.11+ (for local development)
- PostgreSQL 15+ (for local development)

### Using Docker Compose (Recommended)

1. **Start the service:**
```powershell
cd Swappo-Notifications
docker-compose up -d
```

2. **Check service health:**
```powershell
curl http://localhost:8003/health
```

3. **View logs:**
```powershell
docker-compose logs -f notifications_service
```

4. **Stop the service:**
```powershell
docker-compose down
```

### Local Development

1. **Create virtual environment:**
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

2. **Install dependencies:**
```powershell
pip install -r requirements.txt
```

3. **Set environment variables:**
```powershell
$env:DATABASE_URL = "postgresql://swappo_user:swappo_pass@localhost:5432/swappo_notifications"
```

4. **Start PostgreSQL:**
```powershell
docker run -d --name notifications-db `
  -e POSTGRES_DB=swappo_notifications `
  -e POSTGRES_USER=swappo_user `
  -e POSTGRES_PASSWORD=swappo_pass `
  -p 5435:5432 `
  postgres:15-alpine
```

5. **Run the application:**
```powershell
uvicorn main:app --reload --host 0.0.0.0 --port 8003
```

6. **Access API documentation:**
- Swagger UI: http://localhost:8003/docs
- ReDoc: http://localhost:8003/redoc

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://swappo_user:swappo_pass@localhost:5432/swappo_notifications` |
| `SQL_ECHO` | Enable SQL query logging | `false` |

## Integration with Other Services

### Matchmaking Service
The matchmaking service can call this service to create notifications when:
- A user receives a new trade offer
- A trade offer is accepted/rejected/cancelled
- A trade is completed

**Example Integration:**
```python
import requests

# When a trade offer is created
notification_data = {
    "user_id": receiver_id,
    "type": "trade_offer_received",
    "title": "New Trade Offer",
    "body": f"You received a new trade offer from {proposer_name}",
    "related_user_id": proposer_id,
    "related_offer_id": offer_id
}

response = requests.post(
    "http://notifications-service:8000/api/v1/notifications",
    json=notification_data
)
```

### Frontend Integration
The mobile app should:
1. Poll the `/unread-count` endpoint for badge updates
2. Fetch notifications when user opens notifications screen
3. Mark notifications as read when viewed
4. Display notifications with appropriate UI based on type

## Database Schema

The service automatically creates the required tables on startup using SQLAlchemy migrations. The main table is `notifications` with indexes on:
- `user_id` - For efficient user notification queries
- `type` - For filtering by notification type
- `is_read` - For filtering unread notifications

## Error Handling

The service uses standard HTTP status codes:

- `200 OK` - Successful GET/PATCH request
- `201 Created` - Successful POST request
- `204 No Content` - Successful DELETE request
- `400 Bad Request` - Invalid input
- `403 Forbidden` - Not authorized
- `404 Not Found` - Resource not found

**Error Response Format:**
```json
{
  "detail": "Error message describing what went wrong"
}
```

## Performance Considerations

- Indexed columns for fast queries
- Pagination support to limit response sizes
- Lightweight unread count endpoint
- Database connection pooling
- Automatic cleanup of old notifications (can be implemented)

## Future Enhancements

- [ ] Push notification integration (FCM, APNS)
- [ ] WebSocket support for real-time notifications
- [ ] Notification preferences and filtering
- [ ] Scheduled notifications
- [ ] Notification templates
- [ ] Batch notification creation
- [ ] Notification expiration/TTL
- [ ] Rich notification content (images, actions)
- [ ] Notification grouping
- [ ] Read receipts

## Troubleshooting

### Database Connection Issues
```powershell
# Check if PostgreSQL is running
docker ps | Select-String "swappo_notifications_db"

# Check database logs
docker logs swappo_notifications_db
```

### Service Not Starting
```powershell
# Check service logs
docker logs swappo_notifications_service

# Verify database URL
docker exec swappo_notifications_service env | Select-String "DATABASE_URL"
```

### Port Already in Use
If port 8003 is already in use, modify `docker-compose.yml`:
```yaml
ports:
  - "8004:8000"  # Change external port
```

## Contributing

When contributing to this service, please:
1. Follow the existing code structure and patterns
2. Add appropriate validation and error handling
3. Update this README with new features
4. Test all endpoints thoroughly
5. Maintain consistency with other Swappo services

## License

This service is part of the Swappo platform.

## Contact

For questions or issues, please refer to the main Swappo repository documentation.
