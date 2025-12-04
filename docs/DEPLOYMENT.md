# RunAgent Pulse Deployment Guide

## Docker Deployment

### Quick Start

```bash
# Start server
docker-compose up -d

# Check logs
docker-compose logs -f

# Stop server
docker-compose down
```

### Docker Compose Configuration

Edit `docker-compose.yml`:

```yaml
version: '3.8'

services:
  pulse:
    build: .
    container_name: runagent-pulse
    ports:
      - "8000:8000"
    volumes:
      - ./pulse-data:/app/data
    environment:
      - PULSE_API_KEY=your_secret_key_here
      - PULSE_TIMEZONE=UTC
      - PULSE_LOG_LEVEL=INFO
    restart: unless-stopped
```

### Environment Variables

- `PULSE_HOST`: Server host (default: `0.0.0.0`)
- `PULSE_PORT`: Server port (default: `8000`)
- `PULSE_API_KEY`: Optional API key for authentication
- `PULSE_TIMEZONE`: Default timezone (default: `UTC`)
- `PULSE_DB_PATH`: Database path (default: `/app/data/pulse.db`)
- `PULSE_LOG_LEVEL`: Logging level (default: `INFO`)

### Manual Docker Run

```bash
# Development (no API key)
docker run -p 8000:8000 \
  -v $(pwd)/pulse-data:/app/data \
  runagent/pulse:latest

# Production (with API key)
docker run -p 8000:8000 \
  -e PULSE_API_KEY=your_secret_key \
  -v /var/pulse/data:/app/data \
  runagent/pulse:latest
```

## Local Development

### Prerequisites

- Python 3.8+
- pip

### Setup

```bash
# Install dependencies
cd server
pip install -r requirements.txt

# Run server
python -m uvicorn server.main:app --host 0.0.0.0 --port 8000
```

### Database Location

By default, SQLite database is created at:
- Docker: `/app/data/pulse.db`
- Local: `./pulse-data/pulse.db` (create directory first)

## Production Considerations

### Security

1. **API Key**: Always set `PULSE_API_KEY` in production
2. **Network**: Use reverse proxy (nginx) with TLS
3. **Firewall**: Restrict access to API port
4. **Database**: Backup SQLite database regularly

### Performance

1. **Caching**: Enable Redis cache for high-traffic deployments
2. **Connection Pooling**: Tune database connection pool size
3. **Monitoring**: Set up Prometheus metrics collection
4. **Logging**: Configure structured logging

### Backup

```bash
# Backup database
cp /app/data/pulse.db /backup/pulse-$(date +%Y%m%d).db

# Restore database
cp /backup/pulse-20241205.db /app/data/pulse.db
```

### Health Checks

```bash
# Check health
curl http://localhost:8000/health

# Check metrics
curl http://localhost:8000/metrics
```

## Scaling

### Single Instance

Default deployment is single-instance. Suitable for:
- Up to 10,000 active tasks
- Up to 100 concurrent polling clients
- Low to medium traffic

### Multi-Instance (Future)

For horizontal scaling:
1. Use Redis for shared cache
2. Implement distributed locking
3. Use external database (PostgreSQL) instead of SQLite

## Troubleshooting

### Database Locked

If you see "database is locked" errors:
- Ensure only one instance is running
- Check for long-running queries
- Increase SQLite timeout

### Tasks Not Executing

1. Check task status: `GET /tasks/{task_id}`
2. Verify time bucket: Check database `time_buckets` table
3. Check server logs for errors
4. Verify client is polling correctly

### High Memory Usage

1. Reduce task retention period
2. Archive old execution history
3. Optimize payload sizes
4. Increase polling interval

## Monitoring

### Metrics Endpoint

```bash
curl http://localhost:8000/metrics
```

### Key Metrics

- `pulse_tasks_active`: Number of active tasks
- `pulse_tasks_executed_total`: Total executions
- `pulse_poll_requests_total`: Poll request count
- `pulse_poll_latency_seconds`: Poll endpoint latency

### Logging

Structured JSON logs include:
- Task creation/execution events
- Error details
- Performance metrics

## Maintenance

### Database Cleanup

```sql
-- Remove old execution history (older than 90 days)
DELETE FROM execution_history 
WHERE executed_at < unixepoch('now', '-90 days');

-- Remove completed tasks
DELETE FROM tasks 
WHERE status = 'completed' 
AND created_at < unixepoch('now', '-30 days');
```

### Performance Tuning

1. **Index Optimization**: Ensure indexes exist on frequently queried columns
2. **Vacuum Database**: Run `VACUUM` periodically
3. **Analyze Tables**: Run `ANALYZE` for query optimization

