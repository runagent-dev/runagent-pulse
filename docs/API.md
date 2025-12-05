# RunAgent Pulse API Documentation

## Base URL

```
http://localhost:8000
```

## Authentication

Optional API key authentication via Bearer token:

```
Authorization: Bearer {api_key}
```

If no API key is configured, authentication is disabled.

## Endpoints

### Health Check

```http
GET /health
```

Returns server health status.

**Response:**
```json
{
  "status": "healthy",
  "uptime_seconds": 86400,
  "active_tasks": 1234
}
```

### Schedule Task

```http
POST /tasks/schedule
Content-Type: application/json
```

Schedule a new task.

**Request Body:**
```json
{
  "schedule_type": "send_mail",
  "when": {
    "type": "once",
    "time": "2024-12-05T14:30:00Z"
  },
  "payload": {
    "to": "user@example.com",
    "body": "Hello"
  },
  "repeat": null,
  "metadata": {
    "created_by": "agent_123"
  }
}
```

**When Types:**

1. **Once** - Single execution:
   ```json
   {
     "type": "once",
     "time": "2024-12-05T14:30:00Z"  // ISO 8601
   }
   ```
   ```json
   {
     "type": "once",
     "delay": "5m"  // Relative: 5m, 2h, 1d
   }
   ```
   ```json
   {
     "type": "once",
     "natural": "tomorrow at 2pm"  // Natural language
   }
   ```

2. **Recurring** - Repeated execution:
   ```json
   {
     "type": "recurring",
     "delay": "5m",
     "repeat": {
       "interval": "1h",
       "times": 5  // null for infinite
     }
   }
   ```

3. **Cron** - Cron expression:
   ```json
   {
     "type": "cron",
     "cron": "0 9 * * *"  // Daily at 9am
   }
   ```

**Response:**
```json
{
  "task_id": "uuid-here",
  "schedule_type": "send_mail",
  "next_execution": "2024-12-05T14:30:00Z",
  "status": "active"
}
```

### Poll for Due Tasks

```http
GET /tasks/poll?types=send_mail,order_food&limit=10
```

High-performance endpoint for polling due tasks.

**Query Parameters:**
- `types`: Comma-separated schedule types
- `limit`: Maximum tasks to return (1-100)

**Response:**
```json
{
  "tasks": [
    {
      "task_id": "uuid-here",
      "schedule_type": "send_mail",
      "payload": {
        "to": "user@example.com",
        "body": "Hello"
      },
      "scheduled_for": "2024-12-05T14:30:00Z"
    }
  ],
  "next_poll_at": "2024-12-05T14:30:05Z"
}
```

**Headers:**
- `ETag`: For conditional requests (304 Not Modified)
- `X-Poll-Interval`: Suggested polling interval in seconds

### Acknowledge Task

```http
POST /tasks/{task_id}/ack
Content-Type: application/json
```

Acknowledge task execution.

**Request Body:**
```json
{
  "status": "success",
  "execution_time_ms": 123,
  "error": null
}
```

**Response:**
```json
{
  "next_execution": "2024-12-06T14:30:00Z"  // null if no more executions
}
```

### Get Task

```http
GET /tasks/{task_id}
```

Get task details.

**Response:**
```json
{
  "id": "uuid-here",
  "schedule_type": "send_mail",
  "created_at": 1733409000,
  "payload": {...},
  "schedule_config": {...},
  "status": "active",
  "next_execution_iso": "2024-12-05T14:30:00Z"
}
```

### Update Task

```http
PATCH /tasks/{task_id}
Content-Type: application/json
```

Update task (pause, resume, modify).

**Request Body:**
```json
{
  "status": "paused"
}
```

### Delete Task

```http
DELETE /tasks/{task_id}
```

Cancel/delete task.

**Response:**
```json
{
  "status": "cancelled"
}
```

### List Tasks

```http
GET /tasks?status=active&schedule_type=send_mail&limit=100&offset=0
```

List tasks with filters.

**Query Parameters:**
- `status`: Filter by status (active, paused, completed, cancelled)
- `schedule_type`: Filter by schedule type
- `limit`: Maximum results (1-1000)
- `offset`: Pagination offset

**Response:**
```json
{
  "tasks": [...],
  "count": 10
}
```

### Get Task History

```http
GET /tasks/{task_id}/history?limit=100
```

Get execution history for a task.

**Response:**
```json
{
  "history": [
    {
      "executed_at": 1733409000,
      "executed_at_iso": "2024-12-05T14:30:00Z",
      "status": "success",
      "execution_time_ms": 123,
      "error": null
    }
  ]
}
```

### Metrics

```http
GET /metrics
```

Prometheus-format metrics.

**Response:**
```
# HELP pulse_tasks_active Number of active tasks
# TYPE pulse_tasks_active gauge
pulse_tasks_active 1234

# HELP pulse_tasks_executed_total Total tasks executed
# TYPE pulse_tasks_executed_total counter
pulse_tasks_executed_total 56789
```

## Error Responses

All errors return JSON:

```json
{
  "detail": "Error message"
}
```

**Status Codes:**
- `400`: Bad Request
- `401`: Unauthorized
- `404`: Not Found
- `500`: Internal Server Error


