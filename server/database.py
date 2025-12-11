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
                execution_id TEXT,
                executed_at INTEGER NOT NULL,
                expired_at INTEGER,
                status TEXT,
                execution_time_ms INTEGER,
                error TEXT,
                FOREIGN KEY (task_id) REFERENCES tasks(id)
            )
        """)
        
        # Execution results table (for storing agent execution results)
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS execution_results (
                execution_id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                result_data TEXT,
                result_status TEXT NOT NULL,
                stored_at INTEGER NOT NULL,
                expires_at INTEGER,
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
        await self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_results_task_id ON execution_results(task_id)
        """)
        await self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_results_stored_at ON execution_results(stored_at)
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

    async def claim_task(self, task_id: str, worker_id: str, lease_timeout: int = 300) -> Optional[str]:
        """
        Atomically claim a task for execution
        
        Args:
            task_id: Task ID
            worker_id: ID of worker claiming the task
            lease_timeout: How long the claim is valid for (seconds)
            
        Returns:
            execution_id if claimed successfully, None otherwise
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
        
        # Generate execution_id for this claim
        import uuid
        execution_id = str(uuid.uuid4())
        
        # Case 1: Active task - allow parallel execution
        if current_status == "active":
            metadata["locked_by"] = worker_id
            metadata["locked_at"] = now
            metadata["current_execution_id"] = execution_id
            success = await self.update_task(
                task_id,
                updates={
                    "status": "processing",
                    "metadata": metadata
                },
                condition={"status": "active"}
            )
            return execution_id if success else None
            
        # Case 2: Allow parallel execution - always allow claiming even if processing
        # This enables multiple instances to run in parallel
        elif current_status == "processing":
            # Always allow new claim for parallel execution
            # Store execution_id in a list to track multiple concurrent executions
            execution_ids = metadata.get("execution_ids", [])
            execution_ids.append(execution_id)
            metadata["execution_ids"] = execution_ids
            metadata["current_execution_id"] = execution_id
            metadata["locked_by"] = worker_id  # Update to latest worker
            metadata["locked_at"] = now
            success = await self.update_task(
                task_id,
                updates={
                    "metadata": metadata
                }
            )
            return execution_id if success else None
        
        return None
    
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
        
        # For agent execution tasks, include them even if is_webhook is set
        # (they may have callbacks but still need to be executed)
        # The is_webhook filter only applies to exclude regular webhook tasks, not agent executions
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

    async def get_due_webhook_tasks(self, current_time: int, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get due webhook tasks (status=active, is_webhook=true, next_execution <= current_time)
        Excludes agent execution tasks (run_agent, execute_agent) and HTTP request tasks (http_request) - 
        those are handled by AgentExecutorWorker and HTTPExecutorWorker respectively
        """
        async with self.conn.execute("""
            SELECT *
            FROM tasks
            WHERE status = 'active'
              AND next_execution IS NOT NULL
              AND next_execution <= ?
              AND COALESCE(json_extract(metadata, '$.is_webhook'), 0) = 1
              AND schedule_type NOT IN ('run_agent', 'execute_agent', 'http_request')
            ORDER BY next_execution ASC
            LIMIT ?
        """, (current_time, limit)) as cursor:
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
    
    async def record_execution(self, task_id: str, execution_id: Optional[str], executed_at: int, 
                              status: str, execution_time_ms: Optional[int] = None,
                              error: Optional[str] = None, expired_at: Optional[int] = None):
        """Record task execution in history"""
        await self.conn.execute("""
            INSERT INTO execution_history (task_id, execution_id, executed_at, expired_at, status, execution_time_ms, error)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (task_id, execution_id, executed_at, expired_at, status, execution_time_ms, error))
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
                # sqlite3.Row supports dict-style access but not .get()
                "execution_id": row["execution_id"],
                "executed_at": row["executed_at"],
                "executed_at_iso": datetime.utcfromtimestamp(row["executed_at"]).isoformat() + "Z",
                "expired_at": row["expired_at"],
                "expired_at_iso": datetime.utcfromtimestamp(row["expired_at"]).isoformat() + "Z" if row["expired_at"] else None,
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
    
    async def get_expired_tasks(self, current_time: int, max_age_seconds: int = 60) -> List[Dict[str, Any]]:
        """
        Get tasks that should be expired (not claimed within max_age_seconds)
        
        Args:
            current_time: Current Unix timestamp
            max_age_seconds: Maximum age in seconds before expiration (default: 60)
            
        Returns:
            List of tasks that should be expired
        """
        expired_threshold = current_time - max_age_seconds
        async with self.conn.execute("""
            SELECT * FROM tasks
            WHERE status = 'active'
            AND next_execution IS NOT NULL
            AND next_execution <= ?
        """, (expired_threshold,)) as cursor:
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
    
    async def update_execution_status(self, execution_id: str, new_status: str) -> bool:
        """
        Update execution status by execution_id (for late acknowledgments)
        
        Args:
            execution_id: Execution ID to update
            new_status: New status (e.g., "success", "failed")
            
        Returns:
            True if updated successfully
        """
        async with self.conn.execute("""
            UPDATE execution_history
            SET status = ?
            WHERE execution_id = ?
        """, (new_status, execution_id)) as cursor:
            await self.conn.commit()
            return cursor.rowcount > 0
    
    async def get_execution_by_id(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """Get execution record by execution_id"""
        async with self.conn.execute("""
            SELECT * FROM execution_history
            WHERE execution_id = ?
        """, (execution_id,)) as cursor:
            row = await cursor.fetchone()
        
        if not row:
            return None
        
        return {
            "id": row["id"],
            "task_id": row["task_id"],
            "execution_id": row.get("execution_id"),
            "executed_at": row["executed_at"],
            "expired_at": row.get("expired_at"),
            "status": row["status"],
            "execution_time_ms": row["execution_time_ms"],
            "error": row["error"]
        }
    
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
    
    async def store_execution_result(
        self,
        execution_id: str,
        task_id: str,
        result: Any,
        status: str,
        expires_at: Optional[int] = None,
    ):
        """
        Store execution result
        
        Args:
            execution_id: Unique execution ID
            task_id: Task ID
            result: Result data (will be JSON serialized)
            status: Result status (e.g., "success", "failed")
            expires_at: Optional expiration timestamp
        """
        stored_at = int(time.time())
        result_data_json = json.dumps(result) if result is not None else None
        
        await self.conn.execute("""
            INSERT OR REPLACE INTO execution_results 
            (execution_id, task_id, result_data, result_status, stored_at, expires_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (execution_id, task_id, result_data_json, status, stored_at, expires_at))
        await self.conn.commit()
    
    async def get_execution_result(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the most recent execution result for a task
        
        Args:
            task_id: Task ID
            
        Returns:
            Result dict or None if not found
        """
        async with self.conn.execute("""
            SELECT * FROM execution_results
            WHERE task_id = ?
            ORDER BY stored_at DESC
            LIMIT 1
        """, (task_id,)) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None
            
            return {
                "execution_id": row["execution_id"],
                "task_id": row["task_id"],
                "result": json.loads(row["result_data"]) if row["result_data"] else None,
                "status": row["result_status"],
                "stored_at": row["stored_at"],
                "expires_at": row.get("expires_at"),
            }
    
    async def get_execution_result_by_execution_id(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """
        Get execution result by execution ID
        
        Args:
            execution_id: Execution ID
            
        Returns:
            Result dict or None if not found
        """
        async with self.conn.execute("""
            SELECT * FROM execution_results
            WHERE execution_id = ?
        """, (execution_id,)) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None
            
            return {
                "execution_id": row["execution_id"],
                "task_id": row["task_id"],
                "result": json.loads(row["result_data"]) if row["result_data"] else None,
                "status": row["result_status"],
                "stored_at": row["stored_at"],
                "expires_at": row.get("expires_at"),
            }
    
    async def close(self):
        """Close database connection"""
        if self.conn:
            await self.conn.close()



