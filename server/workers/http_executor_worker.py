"""
HTTP Executor Worker
Background worker that executes HTTP requests to user-provided endpoints
"""
import asyncio
import logging
import time
import uuid
from typing import Optional

import httpx

from server.scheduler import Scheduler
from server.database import Database

logger = logging.getLogger("runagent_pulse.http_executor_worker")


class HTTPExecutorWorker:
    """Background worker that polls for and executes HTTP request tasks"""

    def __init__(
        self,
        db: Database,
        scheduler: Scheduler,
        interval_seconds: int = 10,
    ):
        self.db = db
        self.scheduler = scheduler
        self.interval_seconds = interval_seconds
        self._task: Optional[asyncio.Task] = None
        self.worker_id = f"http-executor-{uuid.uuid4().hex[:8]}"

    async def start(self):
        """Start the worker"""
        if self._task:
            return
        self._task = asyncio.create_task(self._run())
        logger.info(f"HTTPExecutorWorker started (worker_id={self.worker_id})")

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
        logger.info("HTTPExecutorWorker stopped")

    async def _run(self):
        """Main worker loop"""
        while True:
            try:
                current_time = int(time.time())
                # Poll for tasks with schedule_type="http_request"
                tasks = await self.db.get_due_tasks_from_buckets(
                    start_time=current_time - 60,  # Look back 60 seconds for missed tasks
                    end_time=current_time + 60,  # Look ahead 60 seconds
                    schedule_types=["http_request"],
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
                logger.error(f"Error in HTTP executor worker: {exc}", exc_info=True)

            await asyncio.sleep(self.interval_seconds)

    async def _execute_task(
        self,
        task_id: str,
        execution_id: str,
        payload: dict,
        metadata: dict,
    ):
        """Execute a single HTTP request task"""
        start_time = time.time()
        result_status = "success"
        error_message = None
        result_data = None

        try:
            # Extract HTTP request parameters
            url = payload.get("url")
            method = payload.get("method", "POST").upper()
            body = payload.get("body")
            headers = payload.get("headers", {})
            timeout = payload.get("timeout", 30)

            if not url:
                raise ValueError("url is required in payload")

            logger.info(
                f"Executing HTTP request: method={method}, url={url}, "
                f"execution_id={execution_id}"
            )

            # Make HTTP request
            async with httpx.AsyncClient(timeout=timeout) as client:
                # Prepare request kwargs
                request_kwargs = {
                    "headers": headers,
                }
                
                # Add body for methods that support it
                if method in ("POST", "PUT", "PATCH", "DELETE"):
                    if body is not None:
                        request_kwargs["json"] = body
                elif method == "GET" and body:
                    # For GET requests, body is used as query params
                    request_kwargs["params"] = body

                # Make the request
                response = await client.request(method, url, **request_kwargs)

                # Prepare result data
                result_data = {
                    "status_code": response.status_code,
                    "headers": dict(response.headers),
                    "body": response.text,
                }

                # Try to parse JSON response
                try:
                    result_data["json"] = response.json()
                except:
                    pass  # Not JSON, that's fine

                # Consider 2xx and 3xx as success
                if 200 <= response.status_code < 400:
                    result_status = "success"
                else:
                    result_status = "failed"
                    error_message = f"HTTP {response.status_code}: {response.text[:500]}"

                logger.info(
                    f"HTTP request completed: execution_id={execution_id}, "
                    f"status_code={response.status_code}"
                )

        except httpx.TimeoutException:
            result_status = "failed"
            error_message = f"Request timeout (exceeded {timeout}s)"
            logger.error(f"Task {task_id} timed out: {error_message}")
        except httpx.RequestError as e:
            result_status = "failed"
            error_message = f"Request error: {str(e)}"
            logger.error(f"Task {task_id} request error: {error_message}")
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

