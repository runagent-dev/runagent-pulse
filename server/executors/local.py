"""
Local Executor
Executes agents locally (via RunAgent local client)
"""
import asyncio
import logging
from typing import Dict, Any, Optional

from server.executors.base import BaseExecutor

logger = logging.getLogger("runagent_pulse.executor.local")


class LocalExecutor(BaseExecutor):
    """Executor for local agent execution"""
    
    def __init__(self, agent_path: Optional[str] = None):
        super().__init__("local")
        self.agent_path = agent_path
    
    def is_available(self) -> bool:
        """Check if local execution is configured"""
        return True  # Always available, but may fail if agent not found
    
    async def execute(
        self,
        agent_id: str,
        entrypoint_tag: str,
        params: Dict[str, Any],
        user_id: Optional[str] = None,
        persistent_memory: bool = False,
        **kwargs
    ) -> Any:
        """
        Execute agent via RunAgent local client (no module import needed)
        
        Args:
            agent_id: Agent ID (module name or path)
            entrypoint_tag: Entrypoint function name
            params: Parameters to pass to agent
            user_id: Optional user ID (may be used for state management)
            persistent_memory: Enable persistent memory (if supported)
            
        Returns:
            Execution result
        """
        try:
            from runagent import RunAgentClient
        except ImportError:
            raise ImportError(
                "runagent package not installed. Install with: pip install runagent"
            )
        
        self.logger.info(
            f"Executing agent via RunAgent Local client: agent_id={agent_id}, "
            f"entrypoint_tag={entrypoint_tag}"
        )

        agent_host = kwargs.get("agent_host") or kwargs.get("host")
        agent_port = kwargs.get("agent_port") or kwargs.get("port")

        if agent_host and agent_port:
            self.logger.info(f"Using explicit local agent address {agent_host}:{agent_port}")
        else:
            self.logger.info("Using agent address from local RunAgent DB")

        client = RunAgentClient(
            agent_id=agent_id,
            entrypoint_tag=entrypoint_tag,
            local=True,
            host=agent_host,
            port=agent_port,
            user_id=user_id,
            persistent_memory=persistent_memory,
        )

        def run_agent():
            return client.run(**params)

        result = await asyncio.wait_for(
            asyncio.to_thread(run_agent),
            timeout=600.0,
        )

        self.logger.info(f"Local agent execution completed: agent_id={agent_id}")
        return result

