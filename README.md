# Swappo-Notifications

Notification microservice for the Swappo platform managing push notifications with RabbitMQ integration.

## Features

- **Notification Management**: Create, read, delete notifications
- **RabbitMQ Consumer**: Background processing of async notifications
- **Mark as Read**: Single or bulk read status updates
- **Unread Counts**: Efficient badge counter endpoint
- **Statistics**: User notification analytics
- **Prometheus Metrics**: Built-in monitoring

## Notification Types

- `trade_offer_received`, `trade_offer_accepted`, `trade_offer_rejected`
- `trade_offer_cancelled`, `trade_completed`
- `new_message`, `item_liked`, `system`

## Quick Start

### Docker (Recommended)

```bash
docker-compose up -d
```

### Local Development

```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Service info |
| GET | `/health` | Health check |
| POST | `/api/v1/notifications` | Create notification |
| GET | `/api/v1/notifications/{user_id}` | Get user notifications |
| GET | `/api/v1/notifications/{user_id}/unread-count` | Get unread count |
| GET | `/api/v1/notifications/{user_id}/stats` | Get statistics |
| PATCH | `/api/v1/notifications/mark-read` | Mark multiple as read |
| PATCH | `/api/v1/notifications/{id}/read` | Mark single as read |
| DELETE | `/api/v1/notifications/{id}` | Delete notification |
| DELETE | `/api/v1/notifications/user/{user_id}` | Delete all user notifications |
| GET | `/metrics` | Prometheus metrics |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | - | PostgreSQL connection string |
| `SQL_ECHO` | false | Enable SQL query logging |
| `RABBITMQ_HOST` | rabbitmq | RabbitMQ host |
| `RABBITMQ_PORT` | 5672 | RabbitMQ port |
| `RABBITMQ_QUEUE` | notifications | Queue name |

## Service Integration

- **RabbitMQ Consumer**: Background worker processes async notification messages from queue
- **Matchmaking Service**: Publishes trade offer notifications
- **Chat Service**: Publishes new message notifications

## Documentation

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
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
