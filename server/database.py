"""
Database layer for RunAgent Pulse
SQLite with WAL mode for concurrent reads
"""
import aiosqlite
import json
import os
import time
from typing import Optional, List, Dict, Any
from datetime import datetime

class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn: Optional[aiosqlite.Connection] = None
        
    async def initialize(self):
        """Initialize database connection and create tables"""
        # Ensure directory exists
        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        
        self.conn = await aiosqlite.connect(self.db_path)
        self.conn.row_factory = aiosqlite.Row
        
        # Enable WAL mode for concurrent reads
        await self.conn.execute("PRAGMA journal_mode=WAL")
        await self.conn.execute("PRAGMA synchronous=NORMAL")
        await self.conn.execute("PRAGMA foreign_keys=ON")
        
        # Create tables
        await self._create_tables()
        await self.conn.commit()
        
    async def _create_tables(self):
        """Create database schema"""
        # Tasks table
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                schedule_type TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                payload TEXT NOT NULL,
                schedule_config TEXT NOT NULL,
                status TEXT DEFAULT 'active',
                metadata TEXT,
                next_execution INTEGER
            )
        """)
        
        # Time buckets table
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS time_buckets (
                bucket_time INTEGER PRIMARY KEY,
                task_ids TEXT NOT NULL
            )
        """)
        
        # Execution history table
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS execution_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL,
                executed_at INTEGER NOT NULL,
                status TEXT,
                execution_time_ms INTEGER,
                error TEXT,
                FOREIGN KEY (task_id) REFERENCES tasks(id)
            )
        """)
        
        # Create indexes
        await self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)
        """)
        await self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_tasks_type ON tasks(schedule_type)
        """)
        await self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_tasks_next_execution ON tasks(next_execution)
        """)
        await self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_bucket_time ON time_buckets(bucket_time)
        """)
        await self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_history_task_id ON execution_history(task_id)
        """)
        await self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_history_executed_at ON execution_history(executed_at)
        """)
        
    async def create_task(self, task_id: str, schedule_type: str, created_at: int,
                         payload: dict, schedule_config: dict, metadata: Optional[dict] = None,
                         next_execution: Optional[int] = None):
        """Create a new task"""
        await self.conn.execute("""
            INSERT INTO tasks (id, schedule_type, created_at, payload, schedule_config, 
                             status, metadata, next_execution)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            task_id,
            schedule_type,
            created_at,
            json.dumps(payload),
            json.dumps(schedule_config),
            "active",
            json.dumps(metadata) if metadata else None,
            next_execution
        ))
        await self.conn.commit()
        
    async def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get task by ID"""
        async with self.conn.execute("""
            SELECT * FROM tasks WHERE id = ?
        """, (task_id,)) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None
            
            return {
                "id": row["id"],
                "schedule_type": row["schedule_type"],
                "created_at": row["created_at"],
                "payload": json.loads(row["payload"]),
                "schedule_config": json.loads(row["schedule_config"]),
                "status": row["status"],
                "metadata": json.loads(row["metadata"]) if row["metadata"] else None,
                "next_execution": row["next_execution"],
                "next_execution_iso": datetime.utcfromtimestamp(row["next_execution"]).isoformat() + "Z" if row["next_execution"] else None
            }
    
    async def update_task(self, task_id: str, updates: dict, condition: Optional[Dict[str, Any]] = None) -> bool:
        """
        Update task fields
        
        Args:
            task_id: Task ID
            updates: Fields to update
            condition: Optional condition that must be met for update to succeed (e.g. {"status": "active"})
            
        Returns:
            True if update succeeded, False otherwise
        """
        set_clauses = []
        values = []
        
        for key, value in updates.items():
            if key in ["payload", "schedule_config", "metadata"]:
                set_clauses.append(f"{key} = ?")
                values.append(json.dumps(value))
            elif key == "next_execution":
                set_clauses.append("next_execution = ?")
                values.append(value)
            else:
                set_clauses.append(f"{key} = ?")
                values.append(value)
        
        if not set_clauses:
            return True
        
        query = f"UPDATE tasks SET {', '.join(set_clauses)} WHERE id = ?"
        values.append(task_id)
        
        if condition:
            for key, value in condition.items():
                query += f" AND {key} = ?"
                values.append(value)
        
        async with self.conn.execute(query, values) as cursor:
            await self.conn.commit()
            return cursor.rowcount > 0

    async def claim_task(self, task_id: str, worker_id: str, lease_timeout: int = 300) -> bool:
        """
        Atomically claim a task for execution
        
        Args:
            task_id: Task ID
            worker_id: ID of worker claiming the task
            lease_timeout: How long the claim is valid for (seconds)
            
        Returns:
            True if claimed successfully
        """
        now = int(time.time())
        
        # We can claim if:
        # 1. Status is 'active'
        # OR
        # 2. Status is 'processing' BUT lease has expired (zombie task)
        
        # Check if task exists and get current state
        task = await self.get_task(task_id)
        if not task:
            return False
            
        current_status = task["status"]
        metadata = task.get("metadata") or {}
        
        # Case 1: Active task
        if current_status == "active":
            metadata["locked_by"] = worker_id
            metadata["locked_at"] = now
            return await self.update_task(
                task_id,
                updates={
                    "status": "processing",
                    "metadata": metadata
                },
                condition={"status": "active"}
            )
            
        # Case 2: Zombie task (processing but expired)
        elif current_status == "processing":
            locked_at = metadata.get("locked_at", 0)
            if now - locked_at > lease_timeout:
                # Lease expired, we can steal it
                metadata["locked_by"] = worker_id
                metadata["locked_at"] = now
                return await self.update_task(
                    task_id,
                    updates={
                        "status": "processing",
                        "metadata": metadata
                    },
                    condition={"status": "processing"}  # Optimistic lock on status
                )
        
        return False
    
    async def add_to_time_bucket(self, bucket_time: int, task_id: str):
        """Add task to time bucket"""
        # Get existing bucket
        async with self.conn.execute("""
            SELECT task_ids FROM time_buckets WHERE bucket_time = ?
        """, (bucket_time,)) as cursor:
            row = await cursor.fetchone()
            
            if row:
                task_ids = json.loads(row["task_ids"])
                if task_id not in task_ids:
                    task_ids.append(task_id)
                    await self.conn.execute("""
                        UPDATE time_buckets SET task_ids = ? WHERE bucket_time = ?
                    """, (json.dumps(task_ids), bucket_time))
            else:
                await self.conn.execute("""
                    INSERT INTO time_buckets (bucket_time, task_ids)
                    VALUES (?, ?)
                """, (bucket_time, json.dumps([task_id])))
        
        await self.conn.commit()
    
    async def remove_from_time_bucket(self, bucket_time: int, task_id: str):
        """Remove task from time bucket"""
        async with self.conn.execute("""
            SELECT task_ids FROM time_buckets WHERE bucket_time = ?
        """, (bucket_time,)) as cursor:
            row = await cursor.fetchone()
            if row:
                task_ids = json.loads(row["task_ids"])
                if task_id in task_ids:
                    task_ids.remove(task_id)
                    if task_ids:
                        await self.conn.execute("""
                            UPDATE time_buckets SET task_ids = ? WHERE bucket_time = ?
                        """, (json.dumps(task_ids), bucket_time))
                    else:
                        await self.conn.execute("""
                            DELETE FROM time_buckets WHERE bucket_time = ?
                        """, (bucket_time,))
                    await self.conn.commit()
    
    async def get_tasks_from_bucket(self, bucket_time: int) -> List[str]:
        """Get all task IDs from a time bucket"""
        async with self.conn.execute("""
            SELECT task_ids FROM time_buckets WHERE bucket_time = ?
        """, (bucket_time,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return json.loads(row["task_ids"])
            return []
    
    async def get_due_tasks_from_buckets(self, start_time: int, end_time: int,
                                        schedule_types: List[str]) -> List[Dict[str, Any]]:
        """Get tasks due in time range"""
        # Get all buckets in range
        async with self.conn.execute("""
            SELECT task_ids FROM time_buckets
            WHERE bucket_time >= ? AND bucket_time <= ?
        """, (start_time, end_time)) as cursor:
            rows = await cursor.fetchall()
            
        task_ids = set()
        for row in rows:
            task_ids.update(json.loads(row["task_ids"]))
        
        if not task_ids:
            return []
        
        # Get task details
        placeholders = ",".join("?" * len(task_ids))
        type_placeholders = ",".join("?" * len(schedule_types))
        
        query = f"""
            SELECT * FROM tasks
            WHERE id IN ({placeholders})
            AND schedule_type IN ({type_placeholders})
            AND status = 'active'
        """
        
        async with self.conn.execute(query, list(task_ids) + schedule_types) as cursor:
            rows = await cursor.fetchall()
            
        tasks = []
        for row in rows:
            tasks.append({
                "task_id": row["id"],
                "schedule_type": row["schedule_type"],
                "payload": json.loads(row["payload"]),
                "scheduled_for": datetime.utcfromtimestamp(row["next_execution"]).isoformat() + "Z" if row["next_execution"] else None,
                "metadata": json.loads(row["metadata"]) if row["metadata"] else None
            })
        
        return tasks
    
    async def record_execution(self, task_id: str, executed_at: int, status: str,
                              execution_time_ms: Optional[int] = None,
                              error: Optional[str] = None):
        """Record task execution in history"""
        await self.conn.execute("""
            INSERT INTO execution_history (task_id, executed_at, status, execution_time_ms, error)
            VALUES (?, ?, ?, ?, ?)
        """, (task_id, executed_at, status, execution_time_ms, error))
        await self.conn.commit()
    
    async def get_execution_history(self, task_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get execution history for a task"""
        async with self.conn.execute("""
            SELECT * FROM execution_history
            WHERE task_id = ?
            ORDER BY executed_at DESC
            LIMIT ?
        """, (task_id, limit)) as cursor:
            rows = await cursor.fetchall()
            
        history = []
        for row in rows:
            history.append({
                "executed_at": row["executed_at"],
                "executed_at_iso": datetime.utcfromtimestamp(row["executed_at"]).isoformat() + "Z",
                "status": row["status"],
                "execution_time_ms": row["execution_time_ms"],
                "error": row["error"]
            })
        
        return history
    
    async def list_tasks(self, status: Optional[str] = None,
                        schedule_type: Optional[str] = None,
                        start_time: Optional[int] = None,
                        end_time: Optional[int] = None,
                        limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """List tasks with filters"""
        conditions = []
        params = []
        
        if status:
            conditions.append("status = ?")
            params.append(status)
        if schedule_type:
            conditions.append("schedule_type = ?")
            params.append(schedule_type)
        if start_time:
            conditions.append("next_execution >= ?")
            params.append(start_time)
        if end_time:
            conditions.append("next_execution <= ?")
            params.append(end_time)
        
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        params.extend([limit, offset])
        
        query = f"""
            SELECT * FROM tasks
            WHERE {where_clause}
            ORDER BY next_execution ASC, created_at DESC
            LIMIT ? OFFSET ?
        """
        
        async with self.conn.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            
        tasks = []
        for row in rows:
            tasks.append({
                "id": row["id"],
                "schedule_type": row["schedule_type"],
                "created_at": row["created_at"],
                "payload": json.loads(row["payload"]),
                "schedule_config": json.loads(row["schedule_config"]),
                "status": row["status"],
                "metadata": json.loads(row["metadata"]) if row["metadata"] else None,
                "next_execution": row["next_execution"],
                "next_execution_iso": datetime.utcfromtimestamp(row["next_execution"]).isoformat() + "Z" if row["next_execution"] else None
            })
        
        return tasks
    
    async def get_all_active_tasks(self) -> List[Dict[str, Any]]:
        """Get all active tasks"""
        async with self.conn.execute("""
            SELECT * FROM tasks WHERE status = 'active'
        """) as cursor:
            rows = await cursor.fetchall()
            
        tasks = []
        for row in rows:
            tasks.append({
                "id": row["id"],
                "schedule_type": row["schedule_type"],
                "created_at": row["created_at"],
                "payload": json.loads(row["payload"]),
                "schedule_config": json.loads(row["schedule_config"]),
                "status": row["status"],
                "metadata": json.loads(row["metadata"]) if row["metadata"] else None,
                "next_execution": row["next_execution"]
            })
        
        return tasks
    
    async def count_active_tasks(self) -> int:
        """Count active tasks"""
        async with self.conn.execute("""
            SELECT COUNT(*) as count FROM tasks WHERE status = 'active'
        """) as cursor:
            row = await cursor.fetchone()
            return row["count"] if row else 0
    
    async def count_total_executions(self) -> int:
        """Count total executions"""
        async with self.conn.execute("""
            SELECT COUNT(*) as count FROM execution_history
        """) as cursor:
            row = await cursor.fetchone()
            return row["count"] if row else 0
    
    async def get_next_task_time(self, schedule_types: List[str], current_time: int) -> Optional[int]:
        """Get the next task execution time for given types"""
        type_placeholders = ",".join("?" * len(schedule_types))
        query = f"""
            SELECT MIN(next_execution) as next_time
            FROM tasks
            WHERE schedule_type IN ({type_placeholders})
            AND status = 'active'
            AND next_execution > ?
        """
        
        async with self.conn.execute(query, schedule_types + [current_time]) as cursor:
            row = await cursor.fetchone()
            return row["next_time"] if row and row["next_time"] else None
    
    async def close(self):
        """Close database connection"""
        if self.conn:
            await self.conn.close()


