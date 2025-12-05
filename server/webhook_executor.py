"""
Webhook executor for RunAgent Pulse
Sends task payloads to user-provided webhook URLs
"""
import logging
from typing import Optional, Dict, Any, Tuple

import httpx


class WebhookExecutor:
    def __init__(self, default_timeout: int = 30, default_retries: int = 3):
        self.default_timeout = default_timeout
        self.default_retries = default_retries
        self.logger = logging.getLogger("runagent_pulse.webhook")

    async def execute_webhook(self, task: Dict[str, Any], execution_id: str) -> Tuple[bool, Optional[str]]:
        """
        Execute a single webhook attempt.

        Returns:
            (success, error_message)
        """
        metadata = task.get("metadata") or {}
        webhook_url = metadata.get("webhook_url")
        timeout = metadata.get("webhook_timeout", self.default_timeout)

        if not webhook_url:
            return False, "missing webhook_url"

        # Basic URL validation
        if not (webhook_url.startswith("http://") or webhook_url.startswith("https://")):
            return False, f"invalid webhook_url scheme: {webhook_url}"

        payload = {
            "task_id": task.get("task_id"),
            "schedule_type": task.get("schedule_type"),
            "scheduled_for": task.get("scheduled_for"),
            "execution_id": execution_id,
            "payload": task.get("payload", {}),
            "metadata": metadata,
        }

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(webhook_url, json=payload)

            if 200 <= response.status_code < 300:
                return True, None

            error_msg = f"status {response.status_code}, body={response.text[:500]}"
            self.logger.error(f"Webhook failed for task {task.get('task_id')}: {error_msg}")
            return False, error_msg

        except httpx.RequestError as e:
            error_msg = f"request error: {str(e)}"
            self.logger.error(f"Webhook request error for task {task.get('task_id')}: {error_msg}")
            return False, error_msg
        except Exception as e:
            error_msg = f"unexpected error: {str(e)}"
            self.logger.error(f"Webhook unexpected error for task {task.get('task_id')}: {error_msg}", exc_info=True)
            return False, error_msg

