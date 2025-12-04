# RunAgent Pulse - Product Requirements Document

## Executive Summary

RunAgent Pulse is a lightweight, self-hosted scheduling service designed for AI agents and developers. It provides second-level precision task scheduling with a simple API, native framework integrations, and a callback-based execution model. The system runs as a single Docker container with SQLite persistence, ensuring zero-configuration deployment and full state restoration.

---

## Core Design Principles

1. **Agent-First Design**: Natural, unambiguous scheduling interface optimized for both human developers and LLM agents
2. **Local-First**: Self-hosted, no vendor lock-in, runs anywhere Docker runs
3. **Stateless Server, Stateful Storage**: Full state recovery from SQLite after any restart
4. **Framework Native**: First-class integrations that feel native to each AI framework
5. **Callback-Based Execution**: Clients poll for due tasks and execute locally, not server-side webhooks

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│                  Docker Container                    │
│  ┌──────────────────────────────────────────────┐  │
│  │         Pulse Server (FastAPI/Go)            │  │
│  │  - Task Scheduling API                       │  │
│  │  - Efficient Polling Endpoint (cached)       │  │
│  │  - State Management                          │  │
│  └──────────────┬───────────────────────────────┘  │
│                 │                                    │
│  ┌──────────────▼───────────────────────────────┐  │
│  │           SQLite Database                    │  │
│  │  - Second-level time buckets (86400/day)    │  │
│  │  - Task definitions & metadata               │  │
│  │  - Execution history                         │  │
│  └──────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
                      ▲
                      │ HTTP/REST API
                      │
        ┌─────────────┴─────────────┐
        │                           │
┌───────▼────────┐        ┌─────────▼──────────┐
│  Python Client │        │  Framework Tools   │
│  (runagent-    │        │  - LangGraph       │
│   pulse)       │        │  - CrewAI          │
│                │        │  - LlamaIndex      │
│  - Schedule    │        │  - Autogen         │
│  - Poll        │        │                    │
│  - Callbacks   │        │                    │
└────────────────┘        └────────────────────┘
```

---

## Data Model

### Time Bucketing System

**Concept**: Each day is represented as an array of 86,400 seconds (24h × 60m × 60s).

**Storage Schema**:
```sql
-- tasks table
CREATE TABLE tasks (
    id TEXT PRIMARY KEY,
    schedule_type TEXT NOT NULL,
    created_at INTEGER NOT NULL,
    payload JSON NOT NULL,
    schedule_config JSON NOT NULL,  -- when to trigger, repeat, etc.
    status TEXT DEFAULT 'active',   -- active, paused, completed, cancelled
    metadata JSON
);

-- time_buckets table (for efficient lookups)
CREATE TABLE time_buckets (
    bucket_time INTEGER PRIMARY KEY,  -- Unix timestamp rounded to second
    task_ids TEXT NOT NULL,           -- JSON array of task IDs
    INDEX idx_bucket_time (bucket_time)
);

-- execution_history table
CREATE TABLE execution_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    executed_at INTEGER NOT NULL,
    status TEXT,  -- success, failed, skipped
    execution_time_ms INTEGER,
    FOREIGN KEY (task_id) REFERENCES tasks(id)
);
```

**Design Rationale**:
- Second-level precision enables fine-grained scheduling
- Time buckets allow O(1) lookup for "what tasks are due now"
- Separate execution history for audit trail and debugging
- JSON fields for flexibility in payload and schedule definitions

---

## API Design

### Core Endpoints

#### 1. Schedule Task
```http
POST /tasks/schedule
Content-Type: application/json
Authorization: Bearer {api_key}

{
  "schedule_type": "send_mail",
  "when": {
    "type": "once",           // once, recurring, cron
    "time": "2024-12-05T14:30:00Z",  // ISO 8601
    // OR
    "delay": "5m",            // relative: 5m, 2h, 1d
    // OR  
    "cron": "0 9 * * *"       // cron expression
  },
  "payload": {
    "to": "sawradip0@gmail.com",
    "body": "You are accepted"
  },
  "repeat": {               // optional, for recurring
    "times": 5,             // null = infinite
    "interval": "1d"
  },
  "metadata": {             // optional
    "created_by": "agent_123",
    "tags": ["email", "notification"]
  }
}

Response 200:
{
  "task_id": "snfkjsdhfisdjfhdsj",
  "schedule_type": "send_mail",
  "next_execution": "2024-12-05T14:30:00Z",
  "status": "active"
}
```

#### 2. Poll for Due Tasks (High-Performance Endpoint)
```http
GET /tasks/poll?types=send_mail,order_food&limit=10
Authorization: Bearer {api_key}

Response 200:
{
  "tasks": [
    {
      "task_id": "snfkjsdhfisdjfhdsj",
      "schedule_type": "send_mail",
      "payload": {
        "to": "sawradip0@gmail.com",
        "body": "You are accepted"
      },
      "scheduled_for": "2024-12-05T14:30:00Z"
    }
  ],
  "next_poll_at": "2024-12-05T14:30:05Z"  // hint for efficient polling
}
```

**Caching Strategy**:
- Cache key: `poll:{types}:{current_minute}`
- Cache TTL: Until next minute boundary
- Cache invalidation: On new task creation in current/next minute
- ETag support for 304 Not Modified responses
- Server sends `X-Poll-Interval` header suggesting optimal poll frequency

#### 3. Acknowledge Task Execution
```http
POST /tasks/{task_id}/ack
Content-Type: application/json
Authorization: Bearer {api_key}

{
  "status": "success",      // success, failed
  "execution_time_ms": 123,
  "error": null             // optional error message
}

Response 200:
{
  "next_execution": "2024-12-06T14:30:00Z"  // if recurring, null otherwise
}
```

#### 4. Task Management
```http
GET    /tasks/{task_id}              # Get task details
PATCH  /tasks/{task_id}              # Update (pause, resume, modify)
DELETE /tasks/{task_id}              # Cancel task
GET    /tasks?status=active&type=    # List tasks with filters
GET    /tasks/{task_id}/history      # Execution history
```

---

## Python SDK Design

### Basic Usage

```python
from runagent_pulse import PulseClient, PulseTask

# Initialize client
pc = PulseClient(
    server_url="http://localhost:8000",
    api_key="aldfnskdjfnds"  # Optional
)

# Schedule a task - flexible time formats
pulse_task = pc.schedule(
    schedule_type="send_mail",
    when="2024-12-05T14:30:00Z",  # ISO 8601
    # OR when="in 5 minutes"       # Natural language
    # OR when="tomorrow at 2pm"    
    # OR when="*/5 * * * *"        # Cron
    payload={
        "to": "sawradip0@gmail.com",
        "body": "You are accepted"
    },
    repeat=None  # or {"times": 5, "interval": "1d"}
)

# Access task ID
print(pulse_task.id)  # "snfkjsdhfisdjfhdsj"

# Reconnect to existing task
pulse_task = PulseTask("snfkjsdhfisdjfhdsj", client=pc)
```

### Callback-Based Execution

```python
from runagent_pulse import PulseClient

pc = PulseClient(server_url="http://localhost:8000")

# Register callback for schedule type
@pc.on_trigger("send_mail")
def handle_send_mail(to: str, body: str, task_id: str, scheduled_for: str):
    """
    Automatically called when task is due.
    Parameters are extracted from payload + metadata.
    """
    print(f"Sending email to {to}: {body}")
    # Send email logic here
    return {"status": "sent"}  # Return value logged

@pc.on_trigger("order_food")
def handle_order_food(name: str, count: int, task_id: str):
    print(f"Ordering {count}x {name}")
    return {"status": "ordered"}

# Start polling (blocking)
pc.start_polling(
    poll_interval=5,  # seconds
    schedule_types=["send_mail", "order_food"]
)

# Or run in background
pc.start_polling_async()
```

### Advanced SDK Features

```python
# Type-safe task definition
from runagent_pulse import TaskBuilder

task = (
    TaskBuilder(pc)
    .type("send_mail")
    .in_("5 minutes")
    .with_payload(to="user@example.com", body="Hello")
    .repeat(times=3, every="1 hour")
    .tag("urgent", "notification")
    .build()
)

# Batch scheduling
tasks = pc.schedule_batch([
    {"schedule_type": "task1", "when": "tomorrow", "payload": {...}},
    {"schedule_type": "task2", "when": "in 1 hour", "payload": {...}}
])

# Pause/resume
pulse_task.pause()
pulse_task.resume()
pulse_task.cancel()

# Query execution history
history = pulse_task.get_history(limit=10)
for execution in history:
    print(f"{execution.executed_at}: {execution.status}")
```

---

## Framework Integrations

### Installation

```bash
pip install runagent-pulse                    # Core SDK
pip install runagent-pulse[langgraph]         # + LangGraph tools
pip install runagent-pulse[crewai]            # + CrewAI tools
pip install runagent-pulse[llamaindex]        # + LlamaIndex tools
pip install runagent-pulse[all]               # All integrations
```

### LangGraph Integration

```python
from runagent_pulse.tools.langgraph import SchedulerTool

# Define schedule types with schemas
scheduler_tool = SchedulerTool(
    server_url="http://localhost:8000",
    api_key="optional_key",
    schedule_types={
        "send_mail": {
            "to": str,
            "body": str,
            "subject": str | None  # Optional field
        },
        "order_food": {
            "name": str,
            "count": int,
            "notes": str | None
        }
    }
)

# Register callbacks
@scheduler_tool.on_trigger("send_mail")
def send_mail_handler(to: str, body: str, subject: str = "No Subject"):
    # Implementation
    pass

# Use in LangGraph
from langgraph.prebuilt import create_react_agent

tools = [scheduler_tool.as_langgraph_tool()]
agent = create_react_agent(model, tools)

# Agent can now naturally schedule tasks:
# "Schedule an email to sawradip0@gmail.com tomorrow at 9am 
#  with body 'Meeting reminder'"
```

**Design Choice**: Tool generates structured output matching LangGraph's tool calling format. Automatically handles parameter validation and type conversion.

### CrewAI Integration

```python
from runagent_pulse.tools.crewai import PulseSchedulerTool
from crewai import Agent, Task, Crew

scheduler_tool = PulseSchedulerTool(
    server_url="http://localhost:8000",
    schedule_types={
        "send_mail": {"to": str, "body": str}
    }
)

@scheduler_tool.on_trigger("send_mail")
def handle_mail(to: str, body: str):
    pass

# Create agent with scheduling capability
scheduler_agent = Agent(
    role="Task Scheduler",
    goal="Schedule tasks based on user requests",
    tools=[scheduler_tool],
    verbose=True
)

crew = Crew(agents=[scheduler_agent], tasks=[...])
```

**Design Choice**: Inherits from `BaseTool`, provides natural language description optimized for CrewAI's planning approach.

### LlamaIndex Integration

```python
from runagent_pulse.tools.llamaindex import PulseSchedulerTool
from llama_index.core.agent import ReActAgent

scheduler_tool = PulseSchedulerTool(
    server_url="http://localhost:8000",
    schedule_types={"send_mail": {"to": str, "body": str}}
)

agent = ReActAgent.from_tools([scheduler_tool], llm=llm)
response = agent.chat("Schedule a reminder email for tomorrow")
```

**Design Choice**: Implements `BaseTool` interface, returns structured FunctionOutput for ReAct agent loop.

---

## Time Format Parsing

### Supported Formats

**Absolute Times**:
- ISO 8601: `2024-12-05T14:30:00Z`, `2024-12-05T14:30:00+05:30`
- Unix timestamp: `1733409000`

**Relative Times** (Natural Language):
- `in 5 minutes`, `in 2 hours`, `in 3 days`
- `tomorrow at 2pm`, `next Monday at 9am`
- `in 30 seconds`, `after 1 week`

**Cron Expressions**:
- Standard 5-field: `0 9 * * *` (daily at 9am)
- Standard 6-field: `0 0 9 * * *` (with seconds)

**Recurring Patterns**:
- `every 5 minutes`, `every hour`, `every day at 9am`
- `every weekday at 2pm`, `every Monday at 10am`

### Parser Implementation

```python
from runagent_pulse.parser import TimeParser

parser = TimeParser(timezone="UTC")  # or "America/New_York"

# Returns: (next_execution_timestamp, recurrence_rule or None)
timestamp, recurrence = parser.parse("tomorrow at 2pm")
timestamp, recurrence = parser.parse("every 5 minutes")
timestamp, recurrence = parser.parse("2024-12-05T14:30:00Z")
```

**Design Rationale**:
- Unambiguous: Each format has clear semantics
- AI-Friendly: Natural language that LLMs naturally generate
- Human-Friendly: Intuitive for developers
- Parseable: Deterministic parsing, no guessing

---

## State Restoration on Restart

### Requirements
1. **Full State Recovery**: All scheduled tasks restored from SQLite
2. **No Time Confusion**: Handle system clock changes, DST, timezone shifts
3. **Missed Task Handling**: Execute or skip tasks that were due during downtime

### Implementation Strategy

```python
# On server startup
def restore_state():
    current_time = int(time.time())
    
    # 1. Load all active tasks
    active_tasks = db.query("SELECT * FROM tasks WHERE status='active'")
    
    # 2. Rebuild time buckets for future tasks
    for task in active_tasks:
        next_exec = calculate_next_execution(task, current_time)
        if next_exec:
            add_to_bucket(next_exec, task.id)
    
    # 3. Handle missed tasks
    missed_tasks = db.query("""
        SELECT t.* FROM tasks t
        JOIN time_buckets tb ON tb.task_ids LIKE '%' || t.id || '%'
        WHERE tb.bucket_time < ? AND t.status='active'
    """, (current_time,))
    
    for task in missed_tasks:
        if task.config.catch_up:
            # Execute immediately
            add_to_bucket(current_time, task.id)
        else:
            # Skip to next occurrence
            next_exec = calculate_next_execution(task, current_time)
            if next_exec:
                add_to_bucket(next_exec, task.id)
            log_skipped_execution(task.id, "server_downtime")
```

**Design Choices**:
1. Store all timestamps as Unix seconds (UTC) - immune to timezone issues
2. Clients specify timezone in schedule request, server converts immediately
3. Each task has `catch_up` flag (default: false) - whether to run missed executions
4. Execution history records skipped tasks for audit trail

**Edge Cases Handled**:
- System clock moved backward: Detect via last_shutdown_time, reschedule affected tasks
- DST transitions: Store UTC, convert to local on display only
- Leap seconds: Use TAI-based time library for sub-second precision if needed
- Docker container restart: Identical to normal startup, fully recovered

---

## Efficient Polling Endpoint

### Performance Requirements
- Handle 1000+ requests/minute from multiple clients
- Sub-10ms response time for cache hits
- Minimize database queries
- Graceful degradation under load

### Caching Architecture

```python
# Cache structure (Redis or in-memory)
cache_key = f"poll:{types_hash}:{current_minute}"
cache_value = {
    "tasks": [...],
    "next_poll_minute": next_minute_with_tasks,
    "etag": hash(tasks)
}

# Cache invalidation triggers
1. New task scheduled in current/next minute
2. Task cancelled/paused in current/next minute  
3. Minute boundary crossed (automatic expiry)

# Request handling
@app.get("/tasks/poll")
async def poll_tasks(types: str, etag: str = None):
    cache_key = f"poll:{hash(types)}:{current_minute()}"
    
    # Check ETag first (cheapest)
    if etag and cache.get_etag(cache_key) == etag:
        return Response(status_code=304)  # Not Modified
    
    # Check cache
    cached = cache.get(cache_key)
    if cached:
        return JSONResponse(
            content=cached["tasks"],
            headers={
                "ETag": cached["etag"],
                "X-Poll-Interval": calculate_optimal_interval(),
                "Cache-Control": f"max-age={seconds_until_next_minute}"
            }
        )
    
    # Cache miss - query database
    tasks = db.get_tasks_for_minute(current_minute(), types)
    etag = hash(tasks)
    
    # Cache for remainder of minute
    cache.set(cache_key, {
        "tasks": tasks,
        "etag": etag
    }, ttl=seconds_until_next_minute)
    
    return JSONResponse(content=tasks, headers={"ETag": etag})
```

### Optimization Techniques

1. **Minute-Level Bucketing**: 
   - Pre-aggregate tasks by minute instead of second
   - Reduces index size 60x
   - Still allows second-precision via client-side filtering

2. **Bloom Filters**:
   - Quick negative lookups: "No tasks of type X in next hour"
   - Avoids database queries for empty results

3. **Adaptive Poll Intervals**:
   ```python
   if no_tasks_in_next_5_minutes:
       suggest_interval = 60  # Poll every minute
   elif tasks_in_next_minute:
       suggest_interval = 5   # Poll every 5 seconds
   else:
       suggest_interval = 30  # Poll every 30 seconds
   ```

4. **Connection Pooling**:
   - SQLite with WAL mode for concurrent reads
   - Connection pool sized for expected client count

5. **Response Compression**:
   - Gzip compression for payload (80%+ reduction for JSON)

---

## Docker Deployment

### Dockerfile

```dockerfile
FROM python:3.11-slim
# OR golang:1.21-alpine for Go implementation

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create volume mount point for SQLite
VOLUME /app/data

# Expose API port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s \
    CMD curl -f http://localhost:8000/health || exit 1

# Run server
CMD ["python", "server.py"]
```

### Docker Compose

```yaml
version: '3.8'

services:
  pulse:
    image: runagent/pulse:latest
    container_name: runagent-pulse
    ports:
      - "8000:8000"
    volumes:
      - ./pulse-data:/app/data
    environment:
      - PULSE_API_KEY=${PULSE_API_KEY:-}
      - PULSE_TIMEZONE=UTC
      - PULSE_LOG_LEVEL=INFO
    restart: unless-stopped
```

### Deployment Modes

**Development Mode** (no API key):
```bash
docker run -p 8000:8000 -v $(pwd)/data:/app/data runagent/pulse:latest
```

**Production Mode** (with API key):
```bash
docker run -p 8000:8000 \
  -e PULSE_API_KEY=your_secret_key \
  -v /var/pulse/data:/app/data \
  runagent/pulse:latest
```

---

## Configuration

### Environment Variables

```bash
# Server Configuration
PULSE_HOST=0.0.0.0
PULSE_PORT=8000
PULSE_API_KEY=                  # Optional, enables authentication
PULSE_TIMEZONE=UTC              # Default timezone for relative times

# Database Configuration  
PULSE_DB_PATH=/app/data/pulse.db
PULSE_DB_POOL_SIZE=10

# Caching Configuration
PULSE_CACHE_TYPE=memory         # memory, redis
PULSE_REDIS_URL=redis://localhost:6379  # if cache_type=redis

# Performance Tuning
PULSE_MAX_POLL_CLIENTS=1000
PULSE_POLL_CACHE_TTL=60         # seconds
PULSE_WORKER_THREADS=4

# Logging
PULSE_LOG_LEVEL=INFO            # DEBUG, INFO, WARNING, ERROR
PULSE_LOG_FILE=/app/logs/pulse.log
```

### Runtime Configuration API

```http
GET  /config                    # Get current config
POST /config                    # Update config (requires admin key)
```

---

## Security Considerations

### API Key Authentication

```python
# Optional but recommended for production
Authorization: Bearer {api_key}

# Key scopes (future enhancement)
- read: List and poll tasks
- write: Create, update, delete tasks  
- admin: Config changes, user management
```

### Data Isolation

- Each API key has isolated namespace
- Tasks are only visible/accessible within same namespace
- Multi-tenancy support via key prefixing

### Rate Limiting

```python
# Per API key rate limits
- Schedule: 100 tasks/minute
- Poll: 1000 requests/minute
- Other: 500 requests/minute
```

---

## Monitoring & Observability

### Health Endpoint

```http
GET /health

Response 200:
{
  "status": "healthy",
  "uptime_seconds": 86400,
  "active_tasks": 1234,
  "tasks_executed_today": 5678,
  "database_size_mb": 45,
  "cache_hit_rate": 0.95
}
```

### Metrics Endpoint (Prometheus format)

```http
GET /metrics

# HELP pulse_tasks_active Number of active tasks
# TYPE pulse_tasks_active gauge
pulse_tasks_active 1234

# HELP pulse_tasks_executed_total Total tasks executed
# TYPE pulse_tasks_executed_total counter
pulse_tasks_executed_total 56789

# HELP pulse_poll_requests_total Total poll requests
# TYPE pulse_poll_requests_total counter
pulse_poll_requests_total{status="200"} 100000
pulse_poll_requests_total{status="304"} 50000

# HELP pulse_poll_latency_seconds Poll endpoint latency
# TYPE pulse_poll_latency_seconds histogram
pulse_poll_latency_seconds_bucket{le="0.005"} 98000
pulse_poll_latency_seconds_bucket{le="0.01"} 99500
```

### Logging

```json
{
  "timestamp": "2024-12-05T14:30:00Z",
  "level": "INFO",
  "event": "task_scheduled",
  "task_id": "abc123",
  "schedule_type": "send_mail",
  "scheduled_for": "2024-12-05T15:00:00Z"
}
```

---

## Testing Strategy

### Unit Tests
- Time parser (all formats)
- Schedule calculation (including edge cases)
- Cache invalidation logic
- State restoration logic

### Integration Tests
- Full schedule → poll → execute → ack flow
- Docker container restart and recovery
- Multiple concurrent clients
- Cache coherence under load

### Performance Tests
- 10,000 active tasks
- 100 concurrent polling clients
- Schedule creation throughput
- Database performance under load

### Chaos Tests
- Server crash mid-execution
- Clock skew simulation
- Database corruption recovery
- Network partition handling

---

## Open Questions for Review

1. **Server Implementation Language**:
   - Python (FastAPI): Easier integration with ecosystem, slightly slower
   - Go: Better performance, smaller binary, harder to extend
   - **Recommendation**: Python for v1 (faster iteration), Go for v2 if performance critical

2. **Cache Backend**:
   - In-memory: Simple, no dependencies, limited scalability
   - Redis: Better for multi-instance deployment, adds complexity
   - **Recommendation**: In-memory default, Redis optional for scale

3. **Task Execution Model**:
   - Current: Client polls and executes
   - Alternative: Server executes via webhooks
   - **Trade-off**: Polling gives client control but requires active polling
   - **Recommendation**: Start with polling, add webhook support later

4. **Natural Language Parsing**:
   - Library-based (dateparser, parsedatetime): Fast, limited coverage
   - LLM-based: Better coverage, adds latency/cost
   - **Recommendation**: Library for common cases, fallback to LLM for edge cases

5. **Missed Task Behavior**:
   - Current: `catch_up` flag decides skip vs execute
   - Alternative: Always execute, or always skip, or configurable per task
   - **Recommendation**: Keep flexible flag, document clearly

6. **Maximum Schedule Horizon**:
   - How far in future can tasks be scheduled? 1 year? 10 years? Unlimited?
   - **Impact**: Database size, index performance
   - **Recommendation**: 1 year default, configurable, warn if exceeded

7. **Multi-Instance Support**:
   - Single instance sufficient for v1?
   - If multi-instance: Leader election? Task claiming? Distributed locking?
   - **Recommendation**: Single instance for v1, design DB schema for future horizontal scaling

8. **Payload Size Limits**:
   - Reasonable limit for task payload? 1KB? 10KB? 1MB?
   - **Impact**: Database size, network transfer
   - **Recommendation**: 10KB default, configurable, document clearly

9. **Historical Data Retention**:
   - Keep execution history forever? Auto-archive? Configurable retention?
   - **Recommendation**: 90 days default, configurable, provide archive endpoint

10. **Framework Priority**:
    - Which framework integrations for v1? LangGraph + CrewAI sufficient?
    - Add Autogen, Semantic Kernel, Haystack later?
    - **Recommendation**: LangGraph + CrewAI for v1, community can contribute others

---

## Success Metrics

**Technical Metrics**:
- Poll endpoint p95 latency < 50ms
- Schedule creation < 100ms
- Cache hit rate > 90%
- State restoration < 5 seconds for 10K tasks
- Database size < 100MB for 100K tasks

**Adoption Metrics**:
- GitHub stars (target: 1000 in 6 months)
- PyPI downloads (target: 10K/month)
- Framework integration PRs from community
- Docker Hub pulls

**Quality Metrics**:
- Test coverage > 85%
- Zero critical bugs in production
- Documentation completeness (all APIs documented)
- Community responsiveness (issues addressed within 48h)

---

## Development Roadmap

### Phase 1: MVP (2-3 weeks)
- [x] Core server with SQLite
- [x] Schedule/poll/ack endpoints
- [x] Basic time parsing
- [x] Python SDK with callbacks
- [x] Docker deployment
- [x] LangGraph integration
- [ ] Documentation
- [ ] Unit tests

### Phase 2: Polish (1-2 weeks)
- [ ] Advanced time parsing (natural language)
- [ ] CrewAI integration
- [ ] Caching layer
- [ ] Performance optimization
- [ ] Integration tests
- [ ] Example projects

### Phase 3: Scale (2-3 weeks)
- [ ] Redis cache support
- [ ] Horizontal scaling design
- [ ] Prometheus metrics
- [ ] Admin dashboard (optional)
- [ ] Load testing
- [ ] Production deployment guide

### Phase 4: Community (Ongoing)
- [ ] LlamaIndex integration
- [ ] Autogen integration
- [ ] JavaScript/TypeScript SDK
- [ ] Go SDK
- [ ] Webhook execution mode
- [ ] Cloud-hosted option

---

## Did I Miss Anything?

**Critical Items to Confirm**:

1. ✅ **Time Zones**: Confirmed - store UTC, convert on display
2. ✅ **Recurring Tasks**: Handled via repeat config
3. ✅ **Error Handling**: Covered via ack endpoint + status tracking
4. ✅ **Authentication**: Optional API key system
5. ✅ **State Recovery**: Full restoration from SQLite

**Potential Gaps**:

1. **Task Dependencies**: Not addressed - is this needed? (e.g., "run task B after task A completes")
2. **Task Priority**: Not addressed - should high-priority tasks execute first?
3. **Concurrent Execution Limits**: Not addressed - max N tasks of same type running simultaneously?
4. **Dead Letter Queue**: What happens to tasks that consistently fail? Manual review queue?
5. **Task Cancellation During Execution**: If client is executing a task and it gets cancelled, how to notify?
6. **Bulk Operations**: Schedule 1000 tasks at once - single API call or batch endpoint?
7. **Task Search/Filtering**: Complex queries like "all send_mail tasks scheduled for next week"?
8. **Audit Logging**: Who created/modified/deleted which tasks? Security compliance?
9. **Backup/Restore**: SQLite backup strategy? Point-in-time recovery?
10. **Migration Path**: How to upgrade server without losing scheduled tasks?

**Questions for You**:

1. Do you want webhook execution mode in v1, or polling-only?
2. Should we support task dependencies (DAG-like workflows)?
3. Is horizontal scaling a v1 requirement or can it wait?
4. Do you want a web UI for task management, or API-only?
5. Should framework integrations auto-start polling, or require explicit `start_polling()`?
6. Max payload size - 10KB reasonable, or need larger?
7. Authentication: API key sufficient, or need OAuth/JWT?
8. LLM-based time parsing: worth the added dependency?
9. Execution timeout: should tasks have max execution time before marked as failed?
10. Notification channels: email/Slack/Discord in v1, or just webhooks/callbacks?

---

**Ready to start implementation? Which component should we build first - server, SDK, or framework integration?**
