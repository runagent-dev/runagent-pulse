"""
Agent Executor Worker
Background worker that executes agents using modular executors
"""
import asyncio
import logging
import time
import uuid
from typing import Optional

import httpx

from server.scheduler import Scheduler
from server.database import Database
from server.executors.factory import ExecutorFactory
from server.executors.base import BaseExecutor

logger = logging.getLogger("runagent_pulse.agent_executor_worker")


class AgentExecutorWorker:
    """Background worker that polls for and executes agent tasks"""

    def __init__(
        self,
        db: Database,
        scheduler: Scheduler,
        executor_factory: ExecutorFactory,
        interval_seconds: int = 10,
    ):
        self.db = db
        self.scheduler = scheduler
        self.executor_factory = executor_factory
        self.interval_seconds = interval_seconds
        self._task: Optional[asyncio.Task] = None
        self.worker_id = f"agent-executor-{uuid.uuid4().hex[:8]}"

    async def start(self):
        """Start the worker"""
        if self._task:
            return
        self._task = asyncio.create_task(self._run())
        logger.info(f"AgentExecutorWorker started (worker_id={self.worker_id})")

    async def stop(self):
        """Stop the worker"""
        if not self._task:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None
        logger.info("AgentExecutorWorker stopped")

    async def _run(self):
        """Main worker loop"""
        while True:
            try:
                current_time = int(time.time())
                # Poll for tasks with schedule_type="run_agent" or "execute_agent"
                tasks = await self.db.get_due_tasks_from_buckets(
                    start_time=current_time - 60,  # Look back 60 seconds for missed tasks
                    end_time=current_time + 60,  # Look ahead 60 seconds
                    schedule_types=["run_agent", "execute_agent"],
                )

                for task in tasks:
                    task_id = task["task_id"]
                    payload = task.get("payload", {})
                    metadata = task.get("metadata") or {}

                    # Try to claim the task
                    execution_id = await self.scheduler.claim_task(task_id, self.worker_id)
                    if not execution_id:
                        continue  # Task already claimed or not available

                    # Execute the task
                    await self._execute_task(task_id, execution_id, payload, metadata)

            except Exception as exc:
                logger.error(f"Error in agent executor worker: {exc}", exc_info=True)

            await asyncio.sleep(self.interval_seconds)

    async def _execute_task(
        self,
        task_id: str,
        execution_id: str,
        payload: dict,
        metadata: dict,
    ):
        """Execute a single task using the appropriate executor"""
        start_time = time.time()
        result_status = "success"
        error_message = None
        result_data = None

        try:
            # Extract agent execution parameters
            agent_id = payload.get("agent_id")
            entrypoint_tag = payload.get("entrypoint_tag")
            params = payload.get("params", {})
            user_id = payload.get("user_id")
            persistent_memory = payload.get("persistent_memory", False)
            executor_type = payload.get("executor_type") or metadata.get("executor_type")
            # Get local parameter from payload or metadata (defaults to None)
            local = payload.get("local")
            if local is None:
                local = metadata.get("local")

            agent_host = payload.get("agent_host") or metadata.get("agent_host")
            agent_port = payload.get("agent_port") or metadata.get("agent_port")

            if not agent_id or not entrypoint_tag:
                raise ValueError("agent_id and entrypoint_tag are required")

            # Get executor
            try:
                executor = self.executor_factory.get_executor(executor_type)
            except ValueError as e:
                raise ValueError(f"Failed to get executor: {e}")

            logger.info(
                f"Executing agent: agent_id={agent_id}, entrypoint_tag={entrypoint_tag}, "
                f"executor={executor.name}, local={local}, execution_id={execution_id}"
            )

            # Execute agent
            result_data = await executor.execute(
                agent_id=agent_id,
                entrypoint_tag=entrypoint_tag,
                params=params,
                user_id=user_id,
                persistent_memory=persistent_memory,
                local=local,
                agent_host=agent_host,
                agent_port=agent_port,
            )

            logger.info(f"Agent execution completed: execution_id={execution_id}")

        except asyncio.TimeoutError:
            result_status = "failed"
            error_message = "Execution timeout (exceeded 10 minutes)"
            logger.error(f"Task {task_id} timed out: {error_message}")
        except Exception as exc:
            result_status = "failed"
            error_message = str(exc)
            logger.error(f"Task {task_id} failed: {error_message}", exc_info=True)

        # Calculate execution time
        execution_time_ms = int((time.time() - start_time) * 1000)

        # Store result in database
        await self.db.store_execution_result(
            execution_id=execution_id,
            task_id=task_id,
            result=result_data,
            status=result_status,
        )

        # POST to callback URL if provided
        callback_url = metadata.get("webhook_url") or metadata.get("callback_url")
        if callback_url:
            await self._post_result_to_callback(
                callback_url=callback_url,
                task_id=task_id,
                execution_id=execution_id,
                result=result_data,
                status=result_status,
                error=error_message,
                execution_time_ms=execution_time_ms,
            )

        # Acknowledge task completion
        await self.scheduler.acknowledge_task(
            task_id=task_id,
            status=result_status,
            execution_time_ms=execution_time_ms,
            error=error_message,
            worker_id=self.worker_id,
            execution_id=execution_id,
        )

    async def _post_result_to_callback(
        self,
        callback_url: str,
        task_id: str,
        execution_id: str,
        result: any,
        status: str,
        error: Optional[str],
        execution_time_ms: int,
    ):
        """POST execution result to callback URL"""
        try:
            payload = {
                "task_id": task_id,
                "execution_id": execution_id,
                "status": status,
                "result": result,
                "execution_time_ms": execution_time_ms,
                "timestamp": int(time.time()),
            }
            if error:
                payload["error"] = error

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(callback_url, json=payload)
                response.raise_for_status()
                logger.info(f"Posted result to callback: {callback_url} (status={response.status_code})")

        except Exception as exc:
            logger.error(f"Failed to POST result to callback {callback_url}: {exc}", exc_info=True)
            # Don't fail the task if callback fails - result is already stored

